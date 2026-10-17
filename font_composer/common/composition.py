"""The inheritance order of a glyph group, resolved glyph by glyph.

A code point is served by the first rule that applies: its manual pin (``[glyphs]``), its
generated pin (``[generated_glyphs]``, written from an overlay order), then the first
family of the group's inheritance order (``[groups]``) that has a glyph for it. "Has a
glyph" is judged on each family's reference style, like the coverage table; the build
re-resolves per output style.

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
    """A pin that cannot be honoured, with the reason."""

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


def generate_pins(
    group: GlyphGroup, order: Sequence[str], library: FontLibrary,
) -> dict[int, tuple[str, ...]]:
    """List, for each code point of ``group``, the families of ``order`` that have a glyph."""
    have = _reference_codepoints(order, library)
    pins: dict[int, tuple[str, ...]] = {}
    for codepoint in group.codepoints:
        families = tuple(label for label in order if codepoint in have[label])
        if families:
            pins[codepoint] = families
    return pins


def _candidates(
    codepoint: int, order: Sequence[str], pinned: Sequence[str],
    have: Mapping[str, frozenset[int]],
) -> tuple[str, ...]:
    """Return the families that could serve a code point: its pin's first, then the order."""
    first = tuple(label for label in pinned if codepoint in have[label])
    rest = tuple(label for label in order if codepoint in have[label] and label not in first)
    return (*first, *rest)


def _stale_pins(
    group: GlyphGroup, overrides: Mapping[int, str], pins: Mapping[int, tuple[str, ...]],
    have: Mapping[str, frozenset[int]], served: set[int],
) -> list[InvalidOverride]:
    """List the manual pins nobody can serve and the generated pins whose family lacks a glyph."""
    stale = [InvalidOverride(codepoint, wanted, "no family of the group has it")
             for codepoint, wanted in overrides.items()
             if group.contains(codepoint) and codepoint not in served]
    stale.extend(
        InvalidOverride(codepoint, families[0],
                        f"generated pin: {families[0]} has no glyph for it")
        for codepoint, families in sorted(pins.items())
        if codepoint not in have[families[0]])
    return stale


def _resolve_one(
    codepoint: int, candidates: tuple[str, ...], wanted: str | None,
) -> tuple[ResolvedGlyph, InvalidOverride | None]:
    """Serve one code point: the manual pin when a candidate, else the first candidate."""
    if wanted is not None and wanted in candidates:
        return ResolvedGlyph(codepoint, wanted, candidates, overridden=True), None
    problem = None
    if wanted is not None:
        reason = (f"{wanted} is not among the families that have this glyph "
                  f"({', '.join(candidates)})")
        problem = InvalidOverride(codepoint, wanted, reason)
    return ResolvedGlyph(codepoint, candidates[0], candidates, overridden=False), problem


def resolve_group(
    group: GlyphGroup,
    order: Sequence[str],
    library: FontLibrary,
    overrides: Mapping[int, str],
    generated: Mapping[int, Sequence[str]] | None = None,
) -> GroupComposition:
    """Resolve every code point of ``group`` that some family of the order or a pin has."""
    pins = {codepoint: tuple(families) for codepoint, families in (generated or {}).items()
            if group.contains(codepoint)}
    named = [*order, *(label for families in pins.values() for label in families)]
    have = _reference_codepoints(list(dict.fromkeys(named)), library)
    available: set[int] = set().union(*(group.codepoint_set & points for points in have.values()))
    glyphs: list[ResolvedGlyph] = []
    invalid: list[InvalidOverride] = []
    for codepoint in sorted(available):
        candidates = _candidates(codepoint, order, pins.get(codepoint, ()), have)
        if not candidates:
            continue
        glyph, problem = _resolve_one(codepoint, candidates, overrides.get(codepoint))
        glyphs.append(glyph)
        if problem is not None:
            invalid.append(problem)
    invalid.extend(_stale_pins(group, overrides, pins, have, {item.codepoint for item in glyphs}))
    return GroupComposition(tuple(glyphs), group.total - len(glyphs), tuple(invalid))
