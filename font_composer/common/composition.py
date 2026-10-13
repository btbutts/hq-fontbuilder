"""The inheritance order of a glyph group, resolved glyph by glyph.

A group has an ordered list of families. A code point is taken from the first family in
that order that has a glyph for it, unless the configuration names another of the
families that have it (``[glyphs]``). "Has a glyph" is judged on each family's reference
style, like the coverage table; the build re-resolves per output style.

Pure functions over the scanned library, so the console and the builder share them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from font_composer.common.groups import GlyphGroup
    from font_composer.common.library import FontLibrary


@dataclass(frozen=True)
class ResolvedGlyph:
    """One code point of a group: where it comes from and what else could serve it."""

    codepoint: int
    source: str
    candidates: tuple[str, ...]
    overridden: bool


@dataclass(frozen=True)
class InvalidOverride:
    """A ``[glyphs]`` entry that cannot be honoured, with the reason."""

    codepoint: int
    family: str
    reason: str


@dataclass(frozen=True)
class GroupComposition:
    """The resolution of a whole group."""

    glyphs: tuple[ResolvedGlyph, ...]
    missing: int
    invalid_overrides: tuple[InvalidOverride, ...]

    def contributions(self, order: Sequence[str]) -> dict[str, int]:
        """Count, per family of ``order``, the glyphs that are taken from it."""
        counts = dict.fromkeys(order, 0)
        for glyph in self.glyphs:
            counts[glyph.source] = counts.get(glyph.source, 0) + 1
        return counts


def _reference_codepoints(order: Sequence[str], library: FontLibrary) -> dict[str, frozenset[int]]:
    """Return, per family of the order, the code points of its reference style."""
    have: dict[str, frozenset[int]] = {}
    for label in order:
        family = library.family(label)
        reference = family.regular_style() if family is not None else None
        have[label] = reference.info.codepoints if reference is not None else frozenset()
    return have


def resolve_group(
    group: GlyphGroup,
    order: Sequence[str],
    library: FontLibrary,
    overrides: Mapping[int, str],
) -> GroupComposition:
    """Resolve every code point of ``group`` that at least one family of ``order`` has."""
    have = _reference_codepoints(order, library)
    available: set[int] = set()
    for codepoints in have.values():
        available |= group.codepoint_set & codepoints
    glyphs: list[ResolvedGlyph] = []
    invalid: list[InvalidOverride] = []
    for codepoint in sorted(available):
        candidates = tuple(label for label in order if codepoint in have[label])
        wanted = overrides.get(codepoint)
        if wanted is not None and wanted in candidates:
            glyphs.append(ResolvedGlyph(codepoint, wanted, candidates, overridden=True))
            continue
        if wanted is not None:
            reason = (f"{wanted} is not among the families that have this glyph "
                      f"({', '.join(candidates)})")
            invalid.append(InvalidOverride(codepoint, wanted, reason))
        glyphs.append(ResolvedGlyph(codepoint, candidates[0], candidates, overridden=False))
    invalid.extend(
        InvalidOverride(codepoint, wanted, "no family of the group has it")
        for codepoint, wanted in overrides.items()
        if codepoint in group.codepoint_set and codepoint not in available
    )
    return GroupComposition(tuple(glyphs), group.total - len(glyphs), tuple(invalid))
