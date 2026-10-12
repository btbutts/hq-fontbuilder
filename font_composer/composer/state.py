"""The console's shared state: library scan, choices, summary and version counter.

The coverage matrix and the full-coverage candidate lists exist to feed the console,
so they live here rather than in :mod:`font_composer.common.library` (which only
knows how to scan the fonts directory). :class:`ConsoleState` is what the watcher
refreshes and what the HTTP server serializes; every successful choice saves the
configuration and bumps the version counter the pages poll.
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
        self._lock = threading.Lock()

    def refresh(self) -> None:
        """Rescan the fonts directory and bump the version (the watcher callback).

        Must not raise: it runs on the watcher thread. The scan is total by design
        (unreadable fonts become problem entries, not exceptions).
        """
        library = FontLibrary.scan(self.fonts_dir)
        with self._lock:
            self.library = library
            self.version += 1

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
            library = self.library
            choices = self.config.choices
            version = self.version
            base = self._base_metrics()
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
            "choices": choices,
            "base": base,
            "summary": summary,
            "problems": [{"path": str(error.path), "reason": error.reason}
                         for error in library.problems],
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
                self.config.choose(group_id, family_label)
                self.config.save()
            except ConfigError as exc:
                return 500, {"error": str(exc)}
            self.version += 1
        return 200, self.snapshot()
