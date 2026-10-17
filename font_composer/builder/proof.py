"""What a build proof shows: the written fonts, measured, and their box glyphs as outlines.

The proof page (``/buildProof`` of the console's web interface) is drawn from this data. A
:class:`ProofSet` holds it for whoever serves the page: the command that built the fonts, or a
console that was already running and was handed the fonts.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

from font_composer.builder.joins import find_seams
from font_composer.common.fitting.fit import Box
from font_composer.common.fonts.inspect import looks_like_font

if TYPE_CHECKING:
    from collections.abc import Sequence

FONT_PREFIX = "/proof-fonts/"
_BOX_GLYPHS = range(0x2500, 0x25A0)  # Box Drawing and Block Elements


@dataclass(frozen=True)
class ProofFont:
    """One font the build wrote, and the output style it is."""

    style: str
    path: Path


def _outlines(ttf: TTFont) -> dict[str, str]:
    """Return the outline of each box and block glyph the font has, as an SVG path.

    The path is in font units with y pointing up; a glyph without ink is left out.
    """
    glyph_set = ttf.getGlyphSet()
    cmap = ttf.getBestCmap() or {}
    outlines: dict[str, str] = {}
    for codepoint in _BOX_GLYPHS:
        name = cmap.get(codepoint)
        if name is None:
            continue
        recording = DecomposingRecordingPen(glyph_set)
        glyph_set[name].draw(recording)
        if not recording.value:
            continue
        pen = SVGPathPen(glyph_set)
        recording.replay(pen)
        outlines[str(codepoint)] = pen.getCommands()
    return outlines


def _entry(font: ProofFont) -> dict[str, Any]:
    """Describe one written font for the page: its file, cell, outlines and seams."""
    ttf = TTFont(font.path)
    try:
        head: Any = ttf["head"]
        hhea: Any = ttf["hhea"]
        os2: Any = ttf["OS/2"]
        upm = float(head.unitsPerEm)
        cell = Box(0.0, hhea.descent / upm, os2.xAvgCharWidth / upm, hhea.ascent / upm)
        seams = [{"spread": seam.spread, "soft": seam.soft,
                  "members": [{"codepoint": member.codepoint, "edge": member.edge,
                               "start": member.start} for member in seam.members]}
                 for seam in find_seams(ttf, cell, upm)]
        units = {"upm": int(upm), "advance": int(os2.xAvgCharWidth),
                 "ascent": int(hhea.ascent), "descent": int(hhea.descent)}
        outlines = _outlines(ttf)
    finally:
        ttf.close()
    return {"style": font.style, "file": font.path.name,
            "url": f"{FONT_PREFIX}{font.path.name}",
            "cell": {"width": cell.x1, "ascent": cell.y1, "descent": cell.y0},
            "units": units, "outlines": outlines, "seams": seams}


def proof_payload(fonts: Sequence[ProofFont]) -> dict[str, Any]:
    """Return what ``GET /api/proof`` answers for the fonts that were written."""
    return {"fonts": [_entry(font) for font in fonts]}


_MAX_FONTS = 256


def parse_proof_request(body: dict[str, Any]) -> list[ProofFont] | str:
    """Read the fonts a build hands to a console: ``{fonts: [{style, path}, ...]}``.

    Return the fonts, or a sentence saying what is wrong. Only absolute paths of font files
    that exist are taken, whatever else the request holds.
    """
    entries = body.get("fonts")
    if not isinstance(entries, list) or not 0 < len(entries) <= _MAX_FONTS:
        return f"fonts must be a list of 1 to {_MAX_FONTS} entries"
    fonts: list[ProofFont] = []
    for entry in entries:
        style = entry.get("style") if isinstance(entry, dict) else None
        raw = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(style, str) or not isinstance(raw, str):
            return "each font must be {style: str, path: str}"
        path = Path(raw)
        if not path.is_absolute() or not path.is_file() or not looks_like_font(path):
            return f"not the absolute path of a font file: {raw}"
        fonts.append(ProofFont(style, path))
    if len({font.path.name for font in fonts}) != len(fonts):
        return "the fonts must have different file names"
    return fonts


class ProofSet:
    """The fonts of one proof with their measurements; replaced whole, safe across threads."""

    def __init__(self, fonts: Sequence[ProofFont] = ()) -> None:
        """Measure the fonts (none: there is no proof yet)."""
        self._lock = threading.Lock()
        self._payload: dict[str, Any] | None = None
        self._files: dict[str, Path] = {}
        if fonts:
            self.replace(fonts)

    def replace(self, fonts: Sequence[ProofFont]) -> None:
        """Make these fonts the proof, forgetting the earlier one."""
        payload = proof_payload(fonts)
        files = {font.path.name: font.path for font in fonts}
        with self._lock:
            self._payload, self._files = payload, files

    @property
    def payload(self) -> dict[str, Any] | None:
        """What ``GET /api/proof`` answers, or None when there is no proof."""
        with self._lock:
            return self._payload

    def file(self, name: str) -> Path | None:
        """Return the written font with this file name, or None."""
        with self._lock:
            return self._files.get(name)
