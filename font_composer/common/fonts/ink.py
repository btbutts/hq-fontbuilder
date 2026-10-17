"""Read the ink bounds of glyphs: where a glyph's outline really is, in em.

The advance width says where the next character starts; the *ink* says what is drawn,
and the two differ (a wide arrow, an accent above the line). Bounds come from the
outlines with fontTools' ``BoundsPen``, so composites and CFF are handled alike; the
result is a :class:`font_composer.common.fitting.fit.Box` in em, which :mod:`fit` judges.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont

from font_composer.common.fitting.fit import Box

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

FULL_BLOCK = 0x2588


def glyph_box(glyph_set: Any, name: str, upm: float) -> Box | None:
    """Return the ink of one glyph of a glyph set in em (None when it has no outline)."""
    if name not in glyph_set:
        return None
    pen = BoundsPen(glyph_set)
    glyph_set[name].draw(pen)
    if pen.bounds is None:
        return None
    x0, y0, x1, y1 = pen.bounds
    return Box(x0 / upm, y0 / upm, x1 / upm, y1 / upm)


def read_ink(path: Path, codepoints: Iterable[int]) -> tuple[dict[int, Box], Box | None]:
    """Return ``({code point: ink box}, frame)`` for the code points the font has.

    Blank glyphs are left out. ``frame`` is the ink of the full block U+2588, the
    extent the font gives glyphs that are meant to join their neighbours.
    """
    font = TTFont(path, fontNumber=0)
    try:
        head: Any = font["head"]  # fontTools fills table attributes at decompile time
        upm = float(head.unitsPerEm)
        glyph_set = font.getGlyphSet()
        cmap = font.getBestCmap() or {}

        def bounds(codepoint: int) -> Box | None:
            name = cmap.get(codepoint)
            return glyph_box(glyph_set, name, upm) if name is not None else None

        result = {}
        for codepoint in codepoints:
            box = bounds(codepoint)
            if box is not None:
                result[codepoint] = box
        return result, bounds(FULL_BLOCK)
    finally:
        font.close()
