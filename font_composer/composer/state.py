"""The console's shared state: library scan, choices, summary and version counter.

The coverage matrix and the full-coverage candidate lists exist to feed the console,
so they live here rather than in :mod:`font_composer.common.library` (which only
knows how to scan the fonts directory). :class:`ConsoleState` is what the watcher
refreshes and what the HTTP server serializes; every successful choice saves the
configuration and bumps the version counter the pages poll. Each snapshot also picks up
hand edits of the configuration file; one that does not parse is reported in the
payload (``configError``) while the last good configuration stays in force.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from font_composer.common.composition import GroupComposition, resolve_group
from font_composer.common.config import DEFAULT_STYLES, Config, ConfigError
from font_composer.common.fit import EPS, CellSpec, FitPlan
from font_composer.common.groups import GROUPS, GROUPS_BY_ID, GlyphGroup
from font_composer.common.library import Family, FontLibrary, StyleEntry
from font_composer.common.names import UnicodeNames
from font_composer.common.planner import cell_of, plan_glyphs
from font_composer.common.styles import (
    find_style,
    is_included,
    output_styles,
    parse_style_name,
    resolve_style,
    same_style_name,
    style_name_problem,
    style_options,
)

CHOICE_ACTIONS = ("add", "remove", "up", "down", "clear")

_FIT_ALL_STYLES_MAX = 512
_FIT_REQUEST_MAX = 2048


def _fit_payload(plan: FitPlan) -> dict[str, Any]:
    """Serialize a fit plan; ``clipped`` is what the user would see cut off."""
    return {
        "kind": plan.kind,
        "sx": round(plan.sx, 5), "sy": round(plan.sy, 5),
        "dx": round(plan.dx, 5), "dy": round(plan.dy, 5),
        "overflow": round(plan.overflow, 4), "residual": round(plan.residual, 4),
        "clipped": plan.overflow > EPS and plan.kind != "bleed",
        "clip": plan.clip,
    }


def coverage_matrix(library: FontLibrary) -> dict[str, dict[str, tuple[int, int]]]:
    """Family label -> group id -> ``(present, total)``."""
    return {
        family.label: {group.id: family.coverage(group) for group in GROUPS}
        for family in library.families
    }


def full_coverage_families(library: FontLibrary, group: GlyphGroup) -> list[str]:
    """Return the labels of the families that cover the whole group."""
    return [
        family.label
        for family in library.families
        if family.coverage(group)[0] == group.total
    ]


def _style_payload(family: Family, entry_index: int) -> dict[str, Any]:
    """Serialize one style file of a family for ``/api/state``."""
    entry = family.styles[entry_index]
    names, metrics = entry.info.names, entry.info.metrics
    return {
        "file": entry.info.path.name,
        "family": names.family,
        "style": names.style,
        "weight": names.weight,
        "width": names.width,
        "italic": names.italic,
        "unitsPerEm": metrics.units_per_em,
        "ascent": metrics.ascent,
        "descent": metrics.descent,
        "fixedPitch": metrics.is_fixed_pitch,
        "variable": entry.info.is_variable,
        "instances": list(entry.info.named_instances),
        "cellAdvance": metrics.cell_advance,
        "modalAdvance": entry.info.modal_advance,
        "codepointCount": len(entry.info.codepoints),
        "coverage": entry.group_coverage,
    }


def _family_payload(family: Family) -> dict[str, Any]:
    """Serialize one family for ``/api/state``."""
    return {
        "label": family.label,
        "displayName": family.display_name,
        "styles": [_style_payload(family, index) for index in range(len(family.styles))],
        "errors": [{"file": error.path.name, "reason": error.reason}
                   for error in family.errors],
    }


class ConsoleState:
    """Lock-guarded shared state: the library scan, the config, the version counter."""

    def __init__(
        self, fonts_dir: Path, config: Config, names: UnicodeNames | None = None,
    ) -> None:
        """Scan the fonts directory once; :meth:`refresh` rescans on changes."""
        self.fonts_dir = fonts_dir
        self.config = config
        self.names = names if names is not None else UnicodeNames()
        self.version = 0
        self.library = FontLibrary.scan(fonts_dir)
        self.config_error: str | None = None
        self._lock = threading.Lock()

    def refresh(self) -> None:
        """Rescan the fonts directory and bump the version (the watcher callback).

        Must not raise: it runs on the watcher thread. Unreadable fonts become problem
        entries, and a directory that vanishes or cannot be listed in the middle of a
        scan keeps the previous library until the next change.
        """
        try:
            library = FontLibrary.scan(self.fonts_dir)
        except OSError:
            return
        with self._lock:
            self.library = library
            self.version += 1

    def _reload_config(self) -> None:
        """Pick up hand edits of the configuration file; keep the last good one on error.

        Must be called with the lock held. A change, or a new parse error, bumps the
        version so that the pages polling it refetch the state.
        """
        try:
            changed = self.config.refresh_if_changed()
            error = None
        except ConfigError as exc:
            changed, error = False, str(exc)
        if changed or error != self.config_error:
            self.version += 1
        self.config_error = error

    def current_version(self) -> int:
        """Return the version counter after checking the configuration file for edits."""
        with self._lock:
            self._reload_config()
            return self.version

    def _base_metrics(self) -> dict[str, Any] | None:
        """Return the cell metrics of the configured base family's Regular cut."""
        base_label = self.config.base_family
        family = self.library.family(base_label) if base_label else None
        if family is None:
            return None
        regular = family.regular_style()
        if regular is None:
            return None
        metrics = regular.info.metrics
        return {
            "family": base_label,
            "unitsPerEm": metrics.units_per_em,
            "ascent": metrics.ascent,
            "descent": metrics.descent,
            "cellAdvance": metrics.cell_advance,
        }

    def snapshot(self) -> dict[str, Any]:
        """Build the ``/api/state`` payload."""
        with self._lock:
            self._reload_config()
            library = self.library
            choices = self.config.choices
            version = self.version
            base = self._base_metrics()
            config_error = self.config_error
            overrides = self.config.glyph_overrides
            included = self.config.setting("output", "styles", list(DEFAULT_STYLES))
            consolidate = self.config.setting("output", "consolidate_styles", True)
            configured = (self.config.style_overrides, self.config.style_names)
        built_styles = output_styles(library, included, consolidate=consolidate)
        summary = []
        for group in GROUPS:
            order = choices.get(group.id, [])
            covered = 0
            if order:
                covered = len(resolve_group(group, order, library, overrides).glyphs)
            summary.append({
                "group": group.id,
                "order": order,
                "covered": covered,
                "total": group.total,
                "candidates": full_coverage_families(library, group),
            })
        return {
            "version": version,
            "fontsDir": str(self.fonts_dir),
            "groups": [
                {"id": group.id, "label": group.label, "total": group.total,
                 "atomic": group.atomic,
                 "ranges": [[low, high] for low, high in group.ranges]}
                for group in GROUPS
            ],
            "families": [_family_payload(family) for family in library.families],
            "coverage": {label: {group: list(cell) for group, cell in matrix.items()}
                         for label, matrix in coverage_matrix(library).items()},
            "uneven": {family.label: sorted(family.uneven_groups())
                       for family in library.families},
            "choices": choices,
            "glyphOverrides": {f"U+{cp:04X}": family for cp, family in sorted(overrides.items())},
            "styleTypes": {
                "consolidate": consolidate,
                "options": [
                    {"name": option.name, "included": is_included(option, included),
                     "similar": list(option.similar)}
                    for option in style_options(library, consolidate=consolidate)
                ],
            },
            "styleMap": _style_map(library, choices, built_styles, configured),
            "base": base,
            "summary": summary,
            "problems": [{"path": str(error.path), "reason": error.reason}
                         for error in library.problems],
            "configError": config_error,
        }

    def glyphs(self, family_label: str, group_id: str) -> tuple[int, dict[str, Any]]:
        """List, per style file of a family, the code points of a group it holds.

        The group page draws a glyph only where the font has one: a browser would
        otherwise fill a missing code point from some other font on the system.
        """
        group = GROUPS_BY_ID.get(group_id)
        if group is None:
            return 400, {"error": f"unknown group: {group_id!r}"}
        with self._lock:
            family = self.library.family(family_label)
        if family is None:
            return 404, {"error": f"unknown family: {family_label!r}"}
        points = group.codepoints
        present = {
            style.file_name: [cp for cp in points if cp in style.info.codepoints]
            for style in family.styles
        }
        fits: dict[str, dict[str, Any]] = {}
        for style in family.styles:
            # a group too large to draw whole is fitted on request, a page of glyphs at a
            # time, see fit()
            if group.total > _FIT_ALL_STYLES_MAX:
                continue
            plans = self.fit_plans(family, group, style, present[style.file_name])
            fits[style.file_name] = {str(cp): _fit_payload(plan) for cp, plan in plans.items()}
        return 200, {"family": family.label, "group": group.id, "styles": present, "fit": fits}

    def fit(
        self, family_label: str, group_id: str, file_name: str, codepoints: list[int],
    ) -> tuple[int, dict[str, Any]]:
        """Plan the fit of some glyphs of one style file (for a group too large to draw whole).

        Only the code points the style holds are planned; a glyph that simply fits has no
        entry, as in :meth:`glyphs`.
        """
        group = GROUPS_BY_ID.get(group_id)
        if group is None:
            return 400, {"error": f"unknown group: {group_id!r}"}
        if len(codepoints) > _FIT_REQUEST_MAX:
            return 400, {"error": f"at most {_FIT_REQUEST_MAX} code points at a time"}
        with self._lock:
            family = self.library.family(family_label)
        if family is None:
            return 404, {"error": f"unknown family: {family_label!r}"}
        style = next((item for item in family.styles if item.file_name == file_name), None)
        if style is None:
            return 404, {"error": f"unknown style file: {file_name!r}"}
        wanted = [
            cp for cp in codepoints
            if cp in style.info.codepoints and any(low <= cp <= high for low, high in group.ranges)
        ]
        plans = self.fit_plans(family, group, style, wanted)
        fit = {str(cp): _fit_payload(plan) for cp, plan in plans.items()}
        return 200, {"family": family.label, "group": group.id, "file": file_name, "fit": fit}

    def choose(
        self, group_id: str, family_label: str | None, action: str,
    ) -> tuple[int, dict[str, Any]]:
        """Change the inheritance order of a group; return ``(http_status, payload)``.

        ``action`` is ``add`` (append the family; it ends up last), ``remove``, ``up`` or
        ``down`` (move one place) or ``clear`` (no family). An atomic group takes one
        family, which must cover it completely.
        """
        group = GROUPS_BY_ID.get(group_id)
        if group is None:
            return 400, {"error": f"unknown group: {group_id!r}"}
        if action not in CHOICE_ACTIONS:
            return 400, {"error": f"unknown action: {action!r}"}
        with self._lock:
            self._reload_config()
            order = list(self.config.choices.get(group_id, []))
            problem = self._check_family(action, family_label)
            if problem is not None:
                return problem
            result = _new_order(group, order, family_label, action, self.library)
            if isinstance(result, tuple):
                return result
            try:
                self.config.update(lambda config: _apply_order(config, group, result))
            except ConfigError as exc:
                return 500, {"error": str(exc)}
            self.config_error = None
            self.version += 1
        return 200, self.snapshot()

    def _check_family(
        self, action: str, family_label: str | None,
    ) -> tuple[int, dict[str, Any]] | None:
        """Return an error answer when the action needs a known family and has none."""
        if action == "clear":
            return None
        if family_label is None or self.library.family(family_label) is None:
            return 400, {"error": f"unknown family: {family_label!r}"}
        return None

    def _base_cell(self) -> CellSpec | None:
        """Return the cell of the configured base family (None when there is none)."""
        family = self.library.family(self.config.base_family)
        reference = family.regular_style() if family is not None else None
        return cell_of(reference) if reference is not None else None

    def fit_plans(
        self, family: Family, group: GlyphGroup, style: StyleEntry, codepoints: list[int],
    ) -> dict[int, FitPlan]:
        """Plan the fit of some glyphs of one style file onto the base cell."""
        base = self._base_cell()
        if base is None:
            return {}
        return plan_glyphs(family, group, style, codepoints, base)

    def glyph_names(self, group_id: str) -> tuple[int, dict[str, Any]]:
        """Return the official names of the code points of a group that have one."""
        group = GROUPS_BY_ID.get(group_id)
        if group is None:
            return 400, {"error": f"unknown group: {group_id!r}"}
        names = self.names.for_codepoints(group.codepoints)
        return 200, {"group": group.id, "names": {str(cp): name for cp, name in names.items()}}

    def composition(self, group_id: str) -> tuple[int, dict[str, Any]]:
        """Resolve a group through its inheritance order and the glyph overrides."""
        group = GROUPS_BY_ID.get(group_id)
        if group is None:
            return 400, {"error": f"unknown group: {group_id!r}"}
        with self._lock:
            self._reload_config()
            library = self.library
            order = list(self.config.choices.get(group_id, []))
            overrides = self.config.glyph_overrides
            version = self.version
        composition = resolve_group(group, order, library, overrides)
        payload = _composition_payload(group, order, library, composition, version)
        self._add_fits(group, library, payload)
        return 200, payload

    def _add_fits(self, group: GlyphGroup, library: FontLibrary, payload: dict[str, Any]) -> None:
        """Attach each glyph's fit plan (when it needs one) to a composition payload."""
        by_source: dict[str, list[int]] = {}
        for glyph in payload["glyphs"]:
            by_source.setdefault(glyph["source"], []).append(glyph["codepoint"])
        plans: dict[int, FitPlan] = {}
        for label, codepoints in by_source.items():
            family = library.family(label)
            reference = family.regular_style() if family is not None else None
            if family is not None and reference is not None:
                plans.update(self.fit_plans(family, group, reference, codepoints))
        for glyph in payload["glyphs"]:
            plan = plans.get(glyph["codepoint"])
            if plan is not None:
                glyph["fit"] = _fit_payload(plan)

    def set_glyph(self, codepoint: int, family_label: str | None) -> tuple[int, dict[str, Any]]:
        """Pin one code point to one of its candidate families (None: back to the order)."""
        group = next((item for item in GROUPS if codepoint in item.codepoint_set), None)
        if group is None:
            return 400, {"error": f"U+{codepoint:04X} is not in any glyph group"}
        with self._lock:
            self._reload_config()
            order = list(self.config.choices.get(group.id, []))
            problem = _glyph_problem(group, order, codepoint, family_label, self.library)
            if problem is not None:
                return problem
            try:
                self.config.update(
                    lambda config: config.set_glyph_override(codepoint, family_label))
            except ConfigError as exc:
                return 500, {"error": str(exc)}
            self.version += 1
        return self.composition(group.id)

    def set_style_included(self, style: str, *, included: bool) -> tuple[int, dict[str, Any]]:
        """Bring a style into the considered styles (``[output] styles``), or leave it out.

        What is listed is one entry (``SemiBold``) that may stand for several spellings
        (``Medium``, ``Black``). The list in the file always names the spellings themselves,
        so including an entry includes each of them and excluding it excludes each of them:
        listing the styles unconsolidated afterwards shows them as the user left them.
        """
        with self._lock:
            self._reload_config()
            consolidate = self.config.setting("output", "consolidate_styles", True)
            option = next((item for item in style_options(self.library, consolidate=consolidate)
                           if style in item.members), None)
            if option is None:
                return 400, {"error": f"no font has a {style!r} style"}

            def mutate(config: Config) -> None:
                names = [name for name in config.setting("output", "styles", list(DEFAULT_STYLES))
                         if name not in option.members]
                config.set_setting("output", "styles",
                                   [*names, *option.members] if included else names)

            try:
                self.config.update(mutate)
            except ConfigError as exc:
                return 500, {"error": str(exc)}
            self.version += 1
        return 200, self.snapshot()

    def set_consolidate(self, *, enabled: bool) -> tuple[int, dict[str, Any]]:
        """Show similar styles as one entry (or each as the fonts spell it) in the list.

        Before the listing changes, every entry that is included is spelled out in
        ``[output] styles``, so that each style merged into it stays included on its own
        (and one that was left out stays out), whichever way the toggle goes.
        """
        with self._lock:
            self._reload_config()

            def mutate(config: Config) -> None:
                current = config.setting("output", "consolidate_styles", True)
                included = config.setting("output", "styles", list(DEFAULT_STYLES))
                spelled = list(included)
                for option in style_options(self.library, consolidate=current):
                    if is_included(option, included):
                        spelled.extend(name for name in option.members if name not in spelled)
                config.set_setting("output", "styles", spelled)
                config.set_setting("output", "consolidate_styles", enabled)

            try:
                self.config.update(mutate)
            except ConfigError as exc:
                return 500, {"error": str(exc)}
            self.version += 1
        return 200, self.snapshot()

    def set_style_name(self, style: str, name: str | None) -> tuple[int, dict[str, Any]]:
        """Build an output style under another name (None: the name the fonts give it).

        The style stays tracked by its own name; the custom name is only what the build writes
        and the console shows. It must be unique, see :func:`style_name_problem`.
        """
        with self._lock:
            self._reload_config()
            included = self.config.setting("output", "styles", list(DEFAULT_STYLES))
            consolidate = self.config.setting("output", "consolidate_styles", True)
            if style not in output_styles(self.library, included, consolidate=consolidate):
                return 400, {"error": f"{style!r} is not one of the output styles"}
            value = None
            if name is not None:
                problem = style_name_problem(self.library, style, name,
                                             self.config.style_names)
                if problem is not None:
                    return 400, {"error": problem}
                value = None if same_style_name(name, style) else " ".join(name.split())

            def mutate(config: Config) -> None:
                names = config.style_names
                if value is None:
                    names.pop(style, None)
                else:
                    names[style] = value
                config.set_setting("output", "style-names", names)

            try:
                self.config.update(mutate)
            except ConfigError as exc:
                return 500, {"error": str(exc)}
            self.version += 1
        return 200, self.snapshot()

    def set_style(
        self, style: str, family_label: str, file_name: str | None,
    ) -> tuple[int, dict[str, Any]]:
        """Map an output style of a family to one of its style files (None: the default)."""
        with self._lock:
            self._reload_config()
            library = self.library
            included = self.config.setting("output", "styles", list(DEFAULT_STYLES))
            consolidate = self.config.setting("output", "consolidate_styles", True)
            if style not in output_styles(library, included, consolidate=consolidate):
                return 400, {"error": f"{style!r} is not one of the output styles"}
            family = library.family(family_label)
            if family is None:
                return 400, {"error": f"unknown family: {family_label!r}"}
            if file_name is not None and find_style(family, file_name) is None:
                return 400, {"error": f"{family_label} has no style {file_name!r}"}
            try:
                self.config.update(
                    lambda config: config.set_style_override(style, family_label, file_name))
            except ConfigError as exc:
                return 500, {"error": str(exc)}
            self.version += 1
        return 200, self.snapshot()


def _added(
    group: GlyphGroup, order: list[str], label: str, library: FontLibrary,
) -> list[str] | tuple[int, dict[str, Any]]:
    """Return the order with ``label`` appended (a family already there stays put)."""
    if label in order:
        return order
    if group.atomic:
        return _atomic_add(group, order, label, library)
    return [*order, label]


def _new_order(
    group: GlyphGroup, order: list[str], label: str | None, action: str, library: FontLibrary,
) -> list[str] | tuple[int, dict[str, Any]]:
    """Return the new order, or an error answer when the change is not allowed."""
    result: list[str] | tuple[int, dict[str, Any]]
    if action == "clear" or label is None:
        result = []
    elif action == "add":
        result = _added(group, order, label, library)
    elif label not in order:
        result = (400, {"error": f"{label} is not chosen for {group.id}"})
    elif action == "remove":
        result = [family for family in order if family != label]
    else:
        result = _moved(order, label, -1 if action == "up" else 1)
    return result


def _moved(order: list[str], label: str, offset: int) -> list[str]:
    """Return the order with one family moved ``offset`` places (not past either end)."""
    index = order.index(label)
    target = index + offset
    moved = list(order)
    if 0 <= target < len(moved):
        moved[index], moved[target] = moved[target], moved[index]
    return moved


def _atomic_add(
    group: GlyphGroup, order: list[str], label: str, library: FontLibrary,
) -> list[str] | tuple[int, dict[str, Any]]:
    """Allow one complete family for an atomic group, nothing else."""
    if order:
        return 409, {"error": f"{group.id} is atomic: it comes from one family, and "
                              f"{order[0]} is chosen; remove it first"}
    family = library.family(label)
    present, total = family.coverage(group) if family is not None else (0, group.total)
    if present < total:
        return 409, {"error": f"{group.id} is atomic and {label} covers only "
                              f"{present}/{total}; refusing the choice"}
    return [label]


def _apply_order(config: Config, group: GlyphGroup, order: list[str]) -> None:
    """Write the order, and drop the glyph overrides of families that left the group."""
    config.set_families(group.id, order)
    for codepoint, family in config.glyph_overrides.items():
        if codepoint in group.codepoint_set and family not in order:
            config.set_glyph_override(codepoint, None)


def _glyph_problem(
    group: GlyphGroup, order: list[str], codepoint: int, label: str | None,
    library: FontLibrary,
) -> tuple[int, dict[str, Any]] | None:
    """Return an error answer when a glyph may not be pinned to this family."""
    message = None
    if label is not None:
        family = library.family(label)
        reference = family.regular_style() if family is not None else None
        if group.atomic:
            message = f"{group.id} is atomic: its glyphs cannot be mixed"
        elif label not in order:
            message = f"{label} is not in the inheritance order of {group.id}"
        elif reference is None or codepoint not in reference.info.codepoints:
            message = f"{label} has no glyph for U+{codepoint:04X}"
    return None if message is None else (409, {"error": message})


def _composition_payload(
    group: GlyphGroup, order: list[str], library: FontLibrary,
    composition: GroupComposition, version: int,
) -> dict[str, Any]:
    """Serialize a resolved group for ``/api/composition``."""
    fonts: dict[str, str] = {}
    family_names: dict[str, str] = {}
    for label in order:
        family = library.family(label)
        reference = family.regular_style() if family is not None else None
        if family is not None and reference is not None:
            fonts[label] = reference.file_name
            family_names[label] = family.display_name
    glyphs = []
    for glyph in composition.glyphs:
        entry: dict[str, Any] = {"codepoint": glyph.codepoint, "source": glyph.source}
        if len(glyph.candidates) > 1:
            entry["candidates"] = list(glyph.candidates)
        if glyph.overridden:
            entry["overridden"] = True
        glyphs.append(entry)
    return {
        "version": version,
        "group": group.id,
        "label": group.label,
        "atomic": group.atomic,
        "total": group.total,
        "order": order,
        "fonts": fonts,
        "familyNames": family_names,
        "glyphs": glyphs,
        "missing": composition.missing,
        "contributions": composition.contributions(order),
        "invalidOverrides": [
            {"codepoint": item.codepoint, "family": item.family, "reason": item.reason}
            for item in composition.invalid_overrides
        ],
    }


def _style_map(
    library: FontLibrary,
    choices: dict[str, list[str]],
    styles: list[str],
    configured: tuple[dict[str, dict[str, str]], dict[str, str]],
) -> dict[str, Any]:
    """Resolve every output style for every family that is used by some group.

    ``configured`` is the ``[styles.<Output>]`` files and the custom style names.
    """
    overrides, names = configured
    used: list[str] = []
    for order in choices.values():
        for label in order:
            if label not in used and library.family(label) is not None:
                used.append(label)
    families: dict[str, list[dict[str, Any]]] = {}
    entries: dict[str, dict[str, Any]] = {style: {} for style in styles}
    for label in used:
        family = library.family(label)
        if family is None:
            continue
        families[label] = [
            {"file": style.file_name, "family": style.info.names.family,
             "style": style.info.names.style, "weight": style.info.names.weight,
             "italic": style.info.names.italic}
            for style in family.styles
        ]
        for style_name in styles:
            choice = resolve_style(family, parse_style_name(style_name),
                                   overrides.get(style_name, {}).get(label))
            entries[style_name][label] = {
                "file": choice.entry.file_name if choice.entry is not None else None,
                "reason": choice.reason,
                "overridden": choice.overridden,
            }
    return {"outputStyles": styles, "families": families, "entries": entries,
            "names": {style: names[style] for style in styles if style in names}}
