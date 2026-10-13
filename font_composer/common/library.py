"""Scan the fonts directory into families of style files.

The fonts directory holds one sub-folder per family; the folder name is the family
label shown in the console. Every font file inside is read with
:func:`font_composer.common.inspect.read_font`. Files that fail to read are collected
as problem entries with their reason, never silently skipped.

The coverage cell of a family is the coverage of its *reference style*, the upright
cut nearest to Regular: that is what the plan measured, and a composed font takes its
glyphs from one style file per output style, so a union over styles would claim glyphs
that no single file holds (an atomic group could look complete when no file has it
all). The per-style detail is kept for the group page, and :meth:`Family.uneven_groups`
names the groups on which the styles of a family disagree. The console's coverage-matrix
and summary assembly lives in :mod:`font_composer.composer.state`; the builder resolves
family labels to style files with the classes here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from font_composer.common.groups import GROUPS, GlyphGroup, coverage
from font_composer.common.inspect import FontError, FontInfo, looks_like_font, read_font

REGULAR_WEIGHT = 400


@dataclass(frozen=True)
class StyleEntry:
    """One readable style file of a family, with its per-group coverage."""

    info: FontInfo
    group_coverage: dict[str, tuple[int, int]]

    @property
    def file_name(self) -> str:
        """The file name relative to its family folder."""
        return self.info.path.name


@dataclass(frozen=True)
class Family:
    """One family folder: its readable styles and its unreadable files."""

    label: str
    styles: tuple[StyleEntry, ...]
    errors: tuple[FontError, ...]

    def regular_style(self) -> StyleEntry | None:
        """Return the reference style: the upright cut with the weight nearest Regular.

        A family with only italic cuts falls back to the nearest weight among those.
        """
        upright = [style for style in self.styles if not style.info.names.italic]
        candidates = upright or list(self.styles)
        if not candidates:
            return None
        return min(candidates, key=lambda style: abs(style.info.names.weight - REGULAR_WEIGHT))

    def coverage(self, group: GlyphGroup) -> tuple[int, int]:
        """Return the reference style's coverage of one group as ``(present, total)``."""
        reference = self.regular_style()
        if reference is None:
            return 0, group.total
        return reference.group_coverage[group.id]

    def uneven_groups(self) -> frozenset[str]:
        """Return the ids of the groups on which the styles of this family disagree.

        Styles disagree when they hold different sets of the group's code points, not
        only different numbers of them.
        """
        return frozenset(
            group.id
            for group in GROUPS
            if len({group.codepoint_set & style.info.codepoints for style in self.styles}) > 1
        )


@dataclass(frozen=True)
class FontLibrary:
    """The result of scanning the fonts directory."""

    fonts_dir: Path
    families: tuple[Family, ...]
    problems: tuple[FontError, ...]

    @classmethod
    def scan(cls, fonts_dir: Path) -> FontLibrary:
        """Read every family folder under ``fonts_dir``."""
        families: list[Family] = []
        problems: list[FontError] = []
        if fonts_dir.is_dir():
            for entry in sorted(fonts_dir.iterdir(), key=lambda path: path.name):
                if entry.is_dir():
                    family = _scan_family(entry)
                    families.append(family)
                    problems.extend(family.errors)
        return cls(fonts_dir=fonts_dir, families=tuple(families), problems=tuple(problems))

    def family(self, label: str) -> Family | None:
        """Return the family with this label, or None."""
        for family in self.families:
            if family.label == label:
                return family
        return None


def _scan_family(folder: Path) -> Family:
    """Read every font file in one family folder."""
    styles: list[StyleEntry] = []
    errors: list[FontError] = []
    for path in sorted(folder.iterdir(), key=lambda item: item.name):
        if not path.is_file() or not looks_like_font(path):
            continue
        result = read_font(path)
        if isinstance(result, FontError):
            errors.append(result)
        else:
            group_coverage = {group.id: coverage(result.codepoints, group) for group in GROUPS}
            styles.append(StyleEntry(info=result, group_coverage=group_coverage))
    return Family(label=folder.name, styles=tuple(styles), errors=tuple(errors))
