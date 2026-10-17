"""Glyph categories: the Unicode blocks, the optional overlay, and the coverage maths.

A *block* is an entry of ``Blocks.txt``; its id is its official name, and it is what the
configuration and the build use. An *overlay category* (``common/overlay.py``) is a named
part of a block, shown instead of that block when the overlay is on. A block counts the
code points ``NamesList.txt`` names as characters (its ``<control>``, ``<reserved>`` and
``<not a character>`` placeholders are not); a block with none (Private Use Area, the CJK
blocks, the supplementary private use areas) counts its whole range. ``box drawing`` and ``block
elements`` are *atomic*: the build takes all of them from one family or none at all.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING

from font_composer.common.blocks import UNICODE_CHAR_RANGES_PATH, load_blocks
from font_composer.common.names import UnicodeNames
from font_composer.common.overlay import OVERLAY_CATEGORIES

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence
    from pathlib import Path

    from font_composer.common.blocks import Block

#: blocks whose glyphs must all come from one family
ATOMIC_BLOCKS = ("Box Drawing", "Block Elements")

Ranges = tuple[tuple[int, int], ...]
NamedRows = tuple[tuple[str, int, int], ...]


@dataclass(frozen=True)
class GlyphGroup:
    """One row of the coverage table: a block, an overlay category, or a block's rest."""

    id: str
    label: str
    ranges: Ranges
    atomic: bool = False
    #: the id of the block this category lies in (its own id for a block)
    block: str = ""
    #: the code points it counts, or None for every code point of its ranges
    members: frozenset[int] | None = field(default=None, compare=False, repr=False)
    rows: NamedRows = ()

    def __post_init__(self) -> None:
        """Make a block its own block."""
        if not self.block:
            object.__setattr__(self, "block", self.id)

    @property
    def overlay(self) -> bool:
        """Tell whether this is an overlay category: it lies in a block of another name."""
        return self.id != self.block

    @property
    def total(self) -> int:
        """The number of code points the group counts."""
        if self.members is not None:
            return len(self.members)
        return sum(high - low + 1 for low, high in self.ranges)

    @cached_property
    def codepoints(self) -> tuple[int, ...]:
        """Every code point of the group, in order."""
        if self.members is not None:
            return tuple(sorted(self.members))
        return tuple(cp for low, high in self.ranges for cp in range(low, high + 1))

    @cached_property
    def codepoint_set(self) -> frozenset[int]:
        """Every code point of the group, for membership tests and intersections."""
        return self.members if self.members is not None else frozenset(self.codepoints)

    @cached_property
    def runs(self) -> Ranges:
        """The group as stretches of consecutive code points."""
        if self.members is None:
            return self.ranges
        runs: list[tuple[int, int]] = []
        for codepoint in self.codepoints:
            if runs and runs[-1][1] == codepoint - 1:
                runs[-1] = (runs[-1][0], codepoint)
            else:
                runs.append((codepoint, codepoint))
        return tuple(runs)

    def contains(self, codepoint: int) -> bool:
        """Tell whether the group counts a code point (no set is built for a plain range)."""
        if self.members is not None:
            return codepoint in self.members
        return any(low <= codepoint <= high for low, high in self.ranges)

    def count_in(self, points: frozenset[int], ordered: Sequence[int]) -> int:
        """Count the group's code points that a font holds.

        ``points`` is the font's code point set and ``ordered`` the same, sorted, so that a
        group that is a plain range (private use) is counted without building its set.
        """
        if self.members is not None:
            return len(self.members & points)
        return sum(bisect_right(ordered, high) - bisect_left(ordered, low)
                   for low, high in self.ranges)


def _is_character(name: str) -> bool:
    """Tell whether a NamesList name is a character's: ``<control>`` and the like are not."""
    return not name.startswith("<")


def coverage(codepoints: Iterable[int], group: GlyphGroup) -> tuple[int, int]:
    """Return ``(present, total)`` of the group's code points found in ``codepoints``."""
    have = codepoints if isinstance(codepoints, (set, frozenset)) else frozenset(codepoints)
    return len(group.codepoint_set & have), group.total


def _subtract(ranges: Ranges, removed: Ranges) -> Ranges:
    """Return ``ranges`` without the code points of ``removed``."""
    left = list(ranges)
    for low_cut, high_cut in removed:
        kept: list[tuple[int, int]] = []
        for low, high in left:
            if high_cut < low or low_cut > high:
                kept.append((low, high))
                continue
            if low < low_cut:
                kept.append((low, low_cut - 1))
            if high_cut < high:
                kept.append((high_cut + 1, high))
        left = kept
    return tuple(left)


def _rest_of(block: GlyphGroup, parts: Sequence[GlyphGroup]) -> GlyphGroup:
    """Return what a block keeps once its overlay categories are taken out."""
    ranges = _subtract(block.ranges, tuple(r for part in parts for r in part.ranges))
    members = None
    if block.members is not None:
        members = block.members - frozenset().union(*(part.codepoint_set for part in parts))
    return GlyphGroup(block.id, block.label, ranges, atomic=block.atomic, members=members)


def _overlay_rows(
    blocks: Sequence[GlyphGroup], overlay: Sequence[GlyphGroup],
) -> tuple[GlyphGroup, ...]:
    """Return the table rows with the overlay on: divided blocks give way to their parts."""
    parts_of: dict[str, list[GlyphGroup]] = {}
    for category in overlay:
        parts_of.setdefault(category.block, []).append(category)
    rows: list[GlyphGroup] = []
    for block in blocks:
        parts = parts_of.get(block.id)
        if not parts:
            rows.append(block)
            continue
        rows.extend(parts)
        rest = _rest_of(block, parts)
        if rest.total > 0:
            rows.append(rest)
    return tuple(sorted(rows, key=lambda group: group.ranges[0][0]))


class Catalog:
    """The glyph categories: the blocks, the overlay categories and the two table views."""

    def __init__(self, blocks: Sequence[GlyphGroup], overlay: Sequence[GlyphGroup]) -> None:
        """Index the blocks (ordered by their first code point) and the overlay categories."""
        self.blocks = tuple(blocks)
        self.overlay = tuple(overlay)
        self._by_id = {group.id: group for group in (*self.blocks, *self.overlay)}
        self._lows = [group.ranges[0][0] for group in self.blocks]
        self._views = {False: self.blocks, True: _overlay_rows(self.blocks, self.overlay)}
        self._rows_by_id = {flag: {row.id: row for row in rows}
                            for flag, rows in self._views.items()}

    @classmethod
    def load(
        cls, blocks_path: Path = UNICODE_CHAR_RANGES_PATH, names: UnicodeNames | None = None,
    ) -> Catalog:
        """Read the blocks and names from ``src/char-sets`` (an empty catalog without them)."""
        known = names if names is not None else UnicodeNames()
        return build_catalog(load_blocks(blocks_path), known.names)

    def by_id(self, group_id: str) -> GlyphGroup | None:
        """Return the block or overlay category with this id, or None."""
        return self._by_id.get(group_id)

    def rows(self, *, overlay: bool) -> tuple[GlyphGroup, ...]:
        """Return the rows of the table: the blocks, or with the overlay on its categories."""
        return self._views[overlay]

    def row(self, group_id: str, *, overlay: bool) -> GlyphGroup | None:
        """Return the row of a view with this id, or None.

        With the overlay on, a block the overlay divides is not a row (it is the part the
        overlay leaves, or nothing), and with it off the overlay categories are not rows.
        """
        return self._rows_by_id[overlay].get(group_id)

    def row_of(self, codepoint: int, *, overlay: bool) -> GlyphGroup | None:
        """Return the row of a view that counts this code point: one row, never two."""
        block = self.group_of(codepoint)
        if block is None or not overlay:
            return block
        for category in self.overlay:
            if category.block == block.id and category.contains(codepoint):
                return category
        rest = self._rows_by_id[True].get(block.id)
        return rest if rest is not None and rest.contains(codepoint) else None

    def group_of(self, codepoint: int) -> GlyphGroup | None:
        """Return the block that counts this code point, or None."""
        index = bisect_right(self._lows, codepoint) - 1
        if index < 0:
            return None
        block = self.blocks[index]
        return block if block.contains(codepoint) else None


def build_catalog(blocks: Iterable[Block], names: Mapping[int, str]) -> Catalog:
    """Make the catalog of blocks (counted by the names) and of the overlay categories."""
    named = sorted(cp for cp, name in names.items() if _is_character(name))
    groups: list[GlyphGroup] = []
    for block in blocks:
        inside = named[bisect_left(named, block.low):bisect_right(named, block.high)]
        groups.append(GlyphGroup(
            block.name, block.name, ((block.low, block.high),),
            atomic=block.name in ATOMIC_BLOCKS,
            members=frozenset(inside) if inside else None))
    by_name = {group.id: group for group in groups}
    overlay: list[GlyphGroup] = []
    for category in OVERLAY_CATEGORIES:
        owner = by_name.get(category.block)
        if owner is None:
            continue
        members = None
        if owner.members is not None:
            members = frozenset(cp for low, high in category.ranges
                                for cp in range(low, high + 1) if cp in owner.members)
        overlay.append(GlyphGroup(category.id, category.label, category.ranges, block=owner.id,
                                  members=members, rows=category.rows))
    return Catalog(groups, overlay)
