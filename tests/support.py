"""Helpers shared by the test modules: tiny deterministic fonts, no network."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen


@dataclass(frozen=True)
class NameSpec:
    """The name and style parameters of a tiny test font."""

    family: str = "Test Family"
    style: str = "Regular"
    weight: int = 400
    italic: bool = False
    #: an oblique that only sets post.italicAngle, not the italic selection bit
    angle_only: bool = False


@dataclass(frozen=True)
class MetricSpec:
    """The metric parameters of a tiny test font."""

    upm: int = 1000
    ascent: int = 800
    descent: int = -200
    advance: int = 600
    fixed: bool = True


@dataclass(frozen=True)
class FontSpec:
    """The variable parameters of a tiny test font; defaults make a plain Regular."""

    names: NameSpec = NameSpec()
    metrics: MetricSpec = MetricSpec()


def _rectangle(box: tuple[int, int, int, int]) -> Any:
    """Return a glyph that is the filled rectangle ``(x0, y0, x1, y1)``."""
    x0, y0, x1, y1 = box
    pen = TTGlyphPen(None)
    pen.moveTo((x0, y0))
    pen.lineTo((x0, y1))
    pen.lineTo((x1, y1))
    pen.lineTo((x1, y0))
    pen.closePath()
    return pen.glyph()


def build_font(
    path: Path, *, codepoints: list[int], spec: FontSpec | None = None,
    ink: dict[int, tuple[int, int, int, int]] | None = None,
) -> Path:
    """Build a tiny valid TTF with one glyph per code point and save it.

    Glyphs are empty unless ``ink`` gives a rectangle ``(x0, y0, x1, y1)`` in font units.
    """
    spec = spec or FontSpec()
    names_spec, metrics = spec.names, spec.metrics
    builder = FontBuilder(metrics.upm, isTTF=True)
    cmap_names = {cp: f"uni{cp:04X}" for cp in sorted(codepoints)}
    glyph_order = [".notdef", *cmap_names.values()]
    builder.setupGlyphOrder(glyph_order)
    builder.setupCharacterMap(cmap_names)
    named_ink = {cmap_names[cp]: box for cp, box in (ink or {}).items()}
    empty = TTGlyphPen(None).glyph()
    builder.setupGlyf({name: _rectangle(named_ink[name]) if name in named_ink else empty
                       for name in glyph_order})
    builder.setupHorizontalMetrics(
        {name: (metrics.advance, named_ink[name][0] if name in named_ink else 0)
         for name in glyph_order})
    builder.setupHorizontalHeader(ascent=metrics.ascent, descent=metrics.descent)
    builder.setupNameTable({"familyName": names_spec.family, "styleName": names_spec.style})
    builder.setupOS2(usWeightClass=names_spec.weight, usWidthClass=5)
    builder.setupPost(isFixedPitch=1 if metrics.fixed else 0,
                      italicAngle=-12.0 if names_spec.angle_only else 0.0)
    builder.setupMaxp()
    if names_spec.italic:
        # fontTools fills table attributes at decompile time; the stubs lack them.
        os2: Any = builder.font["OS/2"]
        head: Any = builder.font["head"]
        os2.fsSelection |= 0x01
        head.macStyle |= 0x02
    builder.save(path)
    return path
