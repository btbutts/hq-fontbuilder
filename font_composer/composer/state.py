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

from font_composer.common.config import Config, ConfigError
from font_composer.common.groups import GROUPS, GROUPS_BY_ID, GlyphGroup
from font_composer.common.library import Family, FontLibrary


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
        "styles": [_style_payload(family, index) for index in range(len(family.styles))],
        "errors": [{"file": error.path.name, "reason": error.reason}
                   for error in family.errors],
    }


class ConsoleState:
    """Lock-guarded shared state: the library scan, the config, the version counter."""

    def __init__(self, fonts_dir: Path, config: Config) -> None:
        """Scan the fonts directory once; :meth:`refresh` rescans on changes."""
        self.fonts_dir = fonts_dir
        self.config = config
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
        summary = [
            {
                "group": group.id,
                "chosen": choices.get(group.id),
                "candidates": full_coverage_families(library, group),
            }
            for group in GROUPS
        ]
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
        return 200, {
            "family": family.label,
            "group": group.id,
            "styles": {
                style.file_name: [cp for cp in points if cp in style.info.codepoints]
                for style in family.styles
            },
        }

    def choose(self, group_id: str, family_label: str | None) -> tuple[int, dict[str, Any]]:
        """Record a choice; return ``(http_status, payload)`` for the response."""
        group = GROUPS_BY_ID.get(group_id)
        if group is None:
            return 400, {"error": f"unknown group: {group_id!r}"}
        with self._lock:
            library = self.library
            if family_label is not None:
                family = library.family(family_label)
                if family is None:
                    return 400, {"error": f"unknown family: {family_label!r}"}
                present, total = family.coverage(group)
                if group.atomic and present < total:
                    return 409, {
                        "error": f"{group.id} is atomic and {family_label} covers only "
                                 f"{present}/{total}; refusing the choice",
                    }
            try:
                self.config.update_choice(group_id, family_label)
            except ConfigError as exc:
                return 500, {"error": str(exc)}
            self.config_error = None
            self.version += 1
        return 200, self.snapshot()
