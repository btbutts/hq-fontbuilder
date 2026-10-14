"""Draw donor glyphs into TrueType outlines of the composed font.

A donor is opened once per output style (a variable font is instanced to the weight
wanted), and a glyph is drawn through a chain of pens: components are flattened, the fit
map is applied (donor units to the base's units, then the scale and shift of the fit
plan), cubic curves become quadratic, and the result is a TrueType glyph. A connector's
overshoot is then cut at the cell edge by moving its points into the cell, which for the
axis-aligned shapes of box drawing is the same as cutting. A synthesized bold draws the
outline again at small offsets; overlapping contours of one direction fill as one shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.filterPen import DecomposingFilterPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

from font_composer.common.fit import FitPlan

if TYPE_CHECKING:
    from pathlib import Path

#: How far a synthesized bold thickens a stem, in em (about the step from 400 to 700).
BOLD_EM = 0.03
_CU2QU_ERROR = 1.0  # font units


class DrawError(Exception):
    """A donor file could not be opened or instanced."""


@dataclass(frozen=True)
class CellBox:
    """The cell in font units: ``[0, width] x [descent, ascent]``."""

    width: int
    ascent: int
    descent: int


class Source:
    """One donor style file, opened and ready to draw from."""

    def __init__(self, path: Path, weight: int, *, variable: bool) -> None:
        """Open ``path``; a variable font is instanced at ``weight``."""
        try:
            font = TTFont(path, fontNumber=0)
            if variable and "fvar" in font:
                font = instancer.instantiateVariableFont(font, _location(font, weight))
        except Exception as exc:  # fontTools raises many kinds on a damaged font
            msg = f"cannot open {path.name}: {exc}"
            raise DrawError(msg) from exc
        head: Any = font["head"]
        self.font = font
        self.path = path
        self.upm = float(head.unitsPerEm)
        self.glyphs = font.getGlyphSet()
        self.cmap: dict[int, str] = font.getBestCmap() or {}
        self.cff = "CFF " in font or "CFF2" in font

    def has(self, codepoint: int) -> bool:
        """Tell whether the font has a glyph for the code point."""
        return self.cmap.get(codepoint) in self.glyphs

    def close(self) -> None:
        """Release the font file."""
        self.font.close()


def _location(font: TTFont, weight: int) -> dict[str, float]:
    """Return an axis location: every axis at its default, the weight at ``weight``."""
    fvar: Any = font["fvar"]
    location: dict[str, float] = {}
    for axis in fvar.axes:
        value = axis.defaultValue
        if axis.axisTag == "wght":
            value = min(max(weight, axis.minValue), axis.maxValue)
        location[axis.axisTag] = value
    return location


@dataclass(frozen=True)
class DrawSpec:
    """How one glyph is drawn: into which units, fitted how, cut and thickened or not."""

    target_upm: int
    plan: FitPlan | None
    cell: CellBox
    embolden: bool = False
    clamp: bool = False


def _clamp_into(glyph: Any, cell: CellBox) -> None:
    """Move every point of a simple glyph into the cell."""
    coordinates = getattr(glyph, "coordinates", None)
    if coordinates is None:
        return
    for index, (x, y) in enumerate(list(coordinates)):
        coordinates[index] = (min(max(x, 0), cell.width), min(max(y, cell.descent), cell.ascent))


def draw_glyph(source: Source, codepoint: int, spec: DrawSpec) -> Any:
    """Return the TrueType glyph of a donor code point, fitted by ``spec.plan``."""
    return draw_named(source, source.cmap[codepoint], spec)


def _offsets(spec: DrawSpec) -> list[tuple[float, float]]:
    """Return the shifts the outline is drawn at: one, or four for a synthesized bold."""
    if not spec.embolden:
        return [(0.0, 0.0)]
    reach_x, reach_y = BOLD_EM * spec.target_upm / 2, BOLD_EM * spec.target_upm / 3
    return [(-reach_x, -reach_y), (reach_x, -reach_y), (-reach_x, reach_y), (reach_x, reach_y)]


def draw_named(source: Source, glyph_name: str, spec: DrawSpec) -> Any:
    """Return the TrueType glyph of a donor glyph name, fitted by ``spec.plan``.

    The plan is in em, so its shifts are multiplied by the target units per em; the
    donor's own units are scaled to the target's first.
    """
    upm = spec.target_upm
    scale = upm / source.upm
    plan = spec.plan if spec.plan is not None else FitPlan("fits")
    out = TTGlyphPen(None)
    chain: Any = Cu2QuPen(out, _CU2QU_ERROR, reverse_direction=True) if source.cff else out
    donor_glyph = source.glyphs[glyph_name]
    for shift_x, shift_y in _offsets(spec):
        matrix = (scale * plan.sx, 0, 0, scale * plan.sy, plan.dx * upm + shift_x,
                  plan.dy * upm + shift_y)
        donor_glyph.draw(DecomposingFilterPen(TransformPen(chain, matrix), source.glyphs))
    glyph = out.glyph()
    if spec.clamp:
        _clamp_into(glyph, spec.cell)
    return glyph
