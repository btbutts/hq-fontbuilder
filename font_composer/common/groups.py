"""Glyph group definitions (the unit of choice) and coverage maths.

A group is a named set of Unicode code point ranges. A composed font takes a whole group
from one donor family because mixed sets do not line up; ``box-drawing`` and
``block-elements`` are *atomic*, meaning the build must take all of them from one family
or none at all. Ranges are defined so that no two groups overlap, which keeps the
coverage matrix unambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class GlyphGroup:
    """One row of the coverage table: a named set of code point ranges."""

    id: str
    label: str
    ranges: tuple[tuple[int, int], ...]
    atomic: bool = False

    @property
    def total(self) -> int:
        """The number of code points assigned to this group."""
        return sum(high - low + 1 for low, high in self.ranges)

    @property
    def codepoints(self) -> tuple[int, ...]:
        """Every code point of the group, in order."""
        return tuple(cp for low, high in self.ranges for cp in range(low, high + 1))


# Group table, in display order. Two deliberate deviations from the Unicode block
# boundaries so that no groups overlap:
# * ``punctuation`` ends at U+209F; U+20A0-20CF is owned by ``currency``.
# * ``nerd-icons`` excludes U+E0A0-E0D4, which is owned by ``powerline``.
GROUPS: tuple[GlyphGroup, ...] = (
    GlyphGroup("alnum", "ASCII letters and digits",
               ((0x30, 0x39), (0x41, 0x5A), (0x61, 0x7A))),
    GlyphGroup("ascii-symbols", "Other printable ASCII",
               ((0x20, 0x2F), (0x3A, 0x40), (0x5B, 0x60), (0x7B, 0x7E))),
    GlyphGroup("latin-1", "Latin-1 Supplement", ((0xA0, 0xFF),)),
    GlyphGroup("latin-ext", "Latin Extended-A", ((0x100, 0x17F),)),
    GlyphGroup("greek", "Greek", ((0x370, 0x3FF),)),
    GlyphGroup("cyrillic", "Cyrillic", ((0x400, 0x4FF),)),
    GlyphGroup("punctuation", "General Punctuation", ((0x2000, 0x209F),)),
    GlyphGroup("currency", "Currency Symbols", ((0x20A0, 0x20CF),)),
    GlyphGroup("arrows", "Arrows", ((0x2190, 0x21FF),)),
    GlyphGroup("math", "Mathematical Operators", ((0x2200, 0x22FF),)),
    GlyphGroup("technical", "Miscellaneous Technical", ((0x2300, 0x23FF),)),
    GlyphGroup("box-drawing", "Box Drawing", ((0x2500, 0x257F),), atomic=True),
    GlyphGroup("block-elements", "Block Elements", ((0x2580, 0x259F),), atomic=True),
    GlyphGroup("geometric", "Geometric Shapes", ((0x25A0, 0x25FF),)),
    GlyphGroup("misc-symbols", "Miscellaneous Symbols", ((0x2600, 0x26FF),)),
    GlyphGroup("dingbats", "Dingbats", ((0x2700, 0x27BF),)),
    GlyphGroup("braille", "Braille Patterns", ((0x2800, 0x28FF),)),
    GlyphGroup("powerline", "Powerline", ((0xE0A0, 0xE0D4),)),
    GlyphGroup("nerd-icons", "Nerd Font private use",
               ((0xE000, 0xE09F), (0xE0D5, 0xF8FF), (0xF0000, 0xFFFFD))),
)

GROUPS_BY_ID: dict[str, GlyphGroup] = {group.id: group for group in GROUPS}


def coverage(codepoints: Iterable[int], group: GlyphGroup) -> tuple[int, int]:
    """Return ``(present, total)`` of the group's code points found in ``codepoints``."""
    have = set(codepoints)
    present = sum(1 for cp in group.codepoints if cp in have)
    return present, group.total
