"""Check a written font against what the configuration asked for.

Everything here reopens the saved file, so it tests what a renderer will read. A failure
is an error, never a warning, except where the cause is the base font itself (its own
glyphs and metrics are copied as they are).
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fontTools.ttLib import TTFont

from font_composer.common.fit import EPS, Box, overflow_of
from font_composer.common.ink import glyph_box

if TYPE_CHECKING:
    from pathlib import Path

    from font_composer.builder.assemble import Layout

PANOSE_MONOSPACED = 9


@dataclass
class Findings:
    """What verification found for one font."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _ink(font: TTFont, name: str, upm: float) -> Box | None:
    return glyph_box(font.getGlyphSet(), name, upm)


def verify_font(path: Path, layout: Layout, advance: int) -> Findings:
    """Verify one written font against the layout that was meant to be written.

    ``advance`` is the cell width in font units.
    """
    found = Findings()
    font = TTFont(path)
    try:
        _check_tables(font, layout, advance, found)
        _check_glyphs(font, layout, advance, found)
    finally:
        font.close()
    return found


def _check_tables(font: TTFont, layout: Layout, advance: int, found: Findings) -> None:
    cmap = font.getBestCmap() or {}
    if set(cmap) != set(layout.cmap):
        missing = sorted(set(layout.cmap) - set(cmap))[:5]
        extra = sorted(set(cmap) - set(layout.cmap))[:5]
        found.errors.append(f"cmap differs from the plan (missing {missing}, extra {extra})")
    post: Any = font["post"]
    if post.isFixedPitch != 1:
        found.errors.append("post.isFixedPitch is not set")
    os2: Any = font["OS/2"]
    if os2.panose.bProportion != PANOSE_MONOSPACED:
        found.errors.append("OS/2 panose proportion is not 'monospaced'")
    if os2.xAvgCharWidth != advance:
        found.errors.append("OS/2 xAvgCharWidth is not the cell advance")
    hhea: Any = font["hhea"]
    if (hhea.ascent, hhea.descent) != (os2.usWinAscent, -os2.usWinDescent):
        found.warnings.append(
            "hhea and OS/2 win metrics differ (copied from the base font); renderers "
            "that read different tables will place lines differently")


def _cell_of(font: TTFont, advance: int) -> tuple[Box, float]:
    """Return the cell of the written font in em, and its units per em."""
    head: Any = font["head"]
    hhea: Any = font["hhea"]
    upm = float(head.unitsPerEm)
    return Box(0.0, hhea.descent / upm, advance / upm, hhea.ascent / upm), upm


def _check_glyphs(font: TTFont, layout: Layout, advance: int, found: Findings) -> None:
    cell, upm = _cell_of(font, advance)
    hmtx: Any = font["hmtx"]
    wrong = [name for name, (width, _lsb) in hmtx.metrics.items() if width != advance]
    if wrong:
        found.errors.append(f"{len(wrong)} glyphs do not have the cell advance, e.g. {wrong[:3]}")
    base_letters = 0
    for codepoint, name in (font.getBestCmap() or {}).items():
        ink = _ink(font, name, upm)
        if ink is None:
            continue
        problem = _glyph_problem(codepoint, ink, cell, layout)
        donor = layout.drawn_from.get(codepoint)
        if problem is None:
            continue
        if donor is None:
            base_letters += _is_letter(codepoint)
        else:
            found.errors.append(f"U+{codepoint:04X} ({donor}) {problem}")
    if base_letters:
        found.warnings.append(
            f"{base_letters} letters of the base font itself leave its cell (not changed)")


def _is_letter(codepoint: int) -> bool:
    return unicodedata.category(chr(codepoint))[0] in "LM"


def _glyph_problem(codepoint: int, ink: Box, cell: Box, layout: Layout) -> str | None:
    """Return what is wrong with one glyph, or None."""
    over = overflow_of(ink, cell)
    if _is_letter(codepoint) and over > EPS:
        return f"is cut off by the cell: {over:.3f} em outside"
    if not _joins(ink, cell, layout.joins.get(codepoint)):
        return "no longer reaches the cell edge it was drawn to, so it will not join its neighbour"
    return None


def _joins(ink: Box, cell: Box, reach: tuple[bool, bool, bool, bool] | None) -> bool:
    """Tell whether a connector still reaches the cell edges its donor drawing reached."""
    if reach is None:
        return True
    gaps = (ink.x0 - cell.x0, cell.x1 - ink.x1, ink.y0 - cell.y0, cell.y1 - ink.y1)
    return all(gap <= EPS for gap, needed in zip(gaps, reach, strict=True) if needed)
