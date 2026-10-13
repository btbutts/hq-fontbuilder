"""Read a font file and extract the metadata the console needs.

Everything comes from fontTools, so TTF and OTF (CFF outlines) are both supported. A
file that cannot be read produces a :class:`FontError` carrying the reason; callers
must surface it, never silently skip the file.
"""

from __future__ import annotations

import struct
from collections import Counter
from dataclasses import dataclass, field
from operator import itemgetter
from pathlib import Path
from typing import Any

from fontTools.ttLib import TTFont, TTLibError

_FONT_EXTENSIONS = {".ttf", ".otf", ".ttc", ".otc"}

_ITALIC_SELECTION_BIT = 0x01
_ITALIC_MAC_STYLE_BIT = 0x02
_ITALIC_ANGLE_EPSILON = 0.01  # degrees


@dataclass(frozen=True)
class FontNames:
    """Family and style identity, from the ``name`` and ``OS/2`` tables."""

    family: str
    style: str
    weight: int
    width: int
    italic: bool


@dataclass(frozen=True)
class FontMetrics:
    """Vertical metrics, the fixed-pitch flag and the cell advance of the font."""

    units_per_em: int
    ascent: int
    descent: int
    is_fixed_pitch: bool
    cell_advance: int


@dataclass(frozen=True)
class FontInfo:
    """Metadata and code point inventory of one readable font file."""

    path: Path
    names: FontNames
    metrics: FontMetrics
    is_variable: bool
    named_instances: tuple[str, ...]
    codepoints: frozenset[int]
    advance_histogram: dict[int, int] = field(compare=False)

    @property
    def modal_advance(self) -> int:
        """The most common glyph advance, or 0 for an empty font."""
        if not self.advance_histogram:
            return 0
        return max(self.advance_histogram.items(), key=itemgetter(1))[0]


@dataclass(frozen=True)
class FontError:
    """A font file that could not be read, with the reason why."""

    path: Path
    reason: str


def looks_like_font(path: Path) -> bool:
    """Return True for file names with a font extension we attempt to read."""
    return path.suffix.lower() in _FONT_EXTENSIONS


def _name(font: TTFont, name_id: int, fallback_id: int) -> str:
    """Read a name table entry, falling back to a legacy name ID."""
    name_table = font["name"]
    return name_table.getDebugName(name_id) or name_table.getDebugName(fallback_id) or "?"


def _named_instances(font: TTFont) -> tuple[str, ...]:
    """List the named instances of a variable font (empty for static fonts)."""
    if "fvar" not in font:
        return ()
    name_table = font["name"]
    return tuple(
        name_table.getDebugName(instance.subfamilyNameID) or "?"
        for instance in font["fvar"].instances
    )


def _advance_histogram(font: TTFont, cmap: dict[int, str]) -> dict[int, int]:
    """Count advance widths over the glyphs reachable from the cmap.

    Fixed-width is judged by the glyphs themselves, not only the ``post`` flag: Nerd
    Font's plain builds are flagged monospace yet most of their icons are wider than
    one cell.
    """
    metrics = font["hmtx"].metrics
    counter: Counter[int] = Counter()
    for glyph_name in set(cmap.values()):
        if glyph_name in metrics:
            counter[metrics[glyph_name][0]] += 1
    return dict(sorted(counter.items()))


def _pick_cell_advance(
    cmap: dict[int, str],
    metrics: dict[str, tuple[int, int]],
    histogram: dict[int, int],
) -> int:
    """Return the advance of the ``M`` glyph, falling back to the modal advance."""
    m_name = cmap.get(ord("M"))
    if m_name is not None and m_name in metrics:
        return int(metrics[m_name][0])
    if histogram:
        return max(histogram.items(), key=itemgetter(1))[0]
    return 0


def _is_italic(os2: Any, head: Any, post: Any) -> bool:
    """Judge slant from every place a font may record it.

    Obliques often set only ``post.italicAngle`` or the ``head`` mac style bit, not the
    ``OS/2`` selection bit, so any of the three counts.
    """
    return (
        bool(int(os2.fsSelection) & _ITALIC_SELECTION_BIT)
        or bool(int(head.macStyle) & _ITALIC_MAC_STYLE_BIT)
        or abs(float(post.italicAngle)) > _ITALIC_ANGLE_EPSILON
    )


def _parse_font(path: Path) -> FontInfo:
    """Read the font tables and build the :class:`FontInfo`; may raise."""
    font = TTFont(path, fontNumber=0)
    try:
        cmap = font.getBestCmap() or {}
        # fontTools fills table attributes at decompile time; the stubs lack them.
        os2: Any = font["OS/2"]
        head: Any = font["head"]
        hhea: Any = font["hhea"]
        post: Any = font["post"]
        histogram = _advance_histogram(font, cmap)
        return FontInfo(
            path=path,
            names=FontNames(
                family=_name(font, 16, 1),
                style=_name(font, 17, 2),
                weight=int(os2.usWeightClass),
                width=int(os2.usWidthClass),
                italic=_is_italic(os2, head, post),
            ),
            metrics=FontMetrics(
                units_per_em=int(head.unitsPerEm),
                ascent=int(hhea.ascent),
                descent=int(hhea.descent),
                is_fixed_pitch=bool(post.isFixedPitch),
                cell_advance=_pick_cell_advance(cmap, font["hmtx"].metrics, histogram),
            ),
            is_variable="fvar" in font,
            named_instances=_named_instances(font),
            codepoints=frozenset(cmap),
            advance_histogram=histogram,
        )
    finally:
        font.close()


def read_font(path: Path) -> FontInfo | FontError:
    """Read one font file and return its :class:`FontInfo`, or a :class:`FontError`."""
    try:
        return _parse_font(path)
    except (TTLibError, OSError, ValueError, struct.error, KeyError, AttributeError) as exc:
        return FontError(path=path, reason=f"{type(exc).__name__}: {exc}")
