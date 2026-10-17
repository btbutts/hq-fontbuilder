"""The proof of a build: what ``build --show-proof`` serves.

The proof is a hidden page of the console's SPA (``/buildProof``) that draws tables with
the fonts the build wrote, so that the box glyphs can be seen to join. Only what that page
needs is answered: ``GET /api/proof`` (the fonts, their cells and the join findings of
:mod:`font_composer.builder.joins`) and ``GET /proof-fonts/<file>`` (the written fonts
themselves, and no other file). Nothing else is: the console's API is not here, and no
request changes anything.
"""

from __future__ import annotations

import errno
import socket
import threading
from dataclasses import dataclass
from http.server import ThreadingHTTPServer
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import unquote, urlparse

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

from font_composer.builder.joins import find_seams
from font_composer.common.cli.console_ui import Action
from font_composer.common.cli.ports import PortUnavailableError, pick_port
from font_composer.common.cli.session import present, reload_process
from font_composer.common.fitting.fit import Box
from font_composer.composer.web.server import StaticHandler

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

PROOF_PAGE = "/buildProof"
_LOCALHOST = "127.0.0.1"
_FONT_PREFIX = "/proof-fonts/"
_FONT_TYPES = {".ttf": "font/ttf", ".otf": "font/otf"}
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
            "url": f"{_FONT_PREFIX}{font.path.name}",
            "cell": {"width": cell.x1, "ascent": cell.y1, "descent": cell.y0},
            "units": units, "outlines": outlines, "seams": seams}


def proof_payload(fonts: Sequence[ProofFont]) -> dict[str, Any]:
    """Return what ``GET /api/proof`` answers for the fonts that were written."""
    return {"fonts": [_entry(font) for font in fonts]}


class ProofHTTPServer(ThreadingHTTPServer):
    """Threading server on one address, carrying the written fonts."""

    daemon_threads = True

    def __init__(self, address: str, port: int, fonts: Sequence[ProofFont]) -> None:
        """Bind on one address; the fonts are measured once, here."""
        self.address_family = socket.AF_INET6 if ":" in address else socket.AF_INET
        super().__init__((address, port), _ProofHandler)
        self.files = {font.path.name: font.path for font in fonts}
        self.payload = proof_payload(fonts)


class _ProofHandler(StaticHandler):
    """Answer the proof's two routes, and the SPA for everything else."""

    @property
    def _proof(self) -> ProofHTTPServer:
        return cast("ProofHTTPServer", self.server)

    def _route_get(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/proof":
            self._send_json(self._proof.payload)
        elif path.startswith(_FONT_PREFIX):
            self._get_font(unquote(path.removeprefix(_FONT_PREFIX)))
        elif path.startswith("/api/"):
            self._send_json({"error": f"not found: {path}"}, status=404)
        else:
            self._get_static(path)

    def _get_font(self, name: str) -> None:
        """Serve a font the build wrote, by its file name; nothing else."""
        target = self._proof.files.get(name)
        if target is None:
            self._send_json({"error": f"not found: {name}"}, status=404)
            return
        self._send_file(target, _FONT_TYPES.get(target.suffix.lower(), "application/octet-stream"))


def serve_proof(
    fonts: Sequence[ProofFont], say: Callable[[str], None] = print, *,
    details: Sequence[str] = (),
) -> None:
    """Serve the proof of the fonts on a free local port until the user quits.

    It is presented like the console is: the address and ``details`` stay on screen above a
    window of the requests, with ``Press 'Q' to quit or 'R' to Reload`` under it. ``R`` starts
    the command over, so the fonts are built again. Nothing is opened for the user.
    """
    try:
        port, _notice = pick_port([_LOCALHOST], _LOCALHOST, None, None)
        httpd = ProofHTTPServer(_LOCALHOST, port, fonts)
    except (PortUnavailableError, OSError) as exc:
        reason = "no free port" if getattr(exc, "errno", None) != errno.EADDRINUSE else "port taken"
        say(f"font_composer: cannot show the proof ({reason}): {exc}")
        return
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    header = [f"The proof of the fonts is at: http://{_LOCALHOST}:{port}{PROOF_PAGE}",
              f"\tlistening on IP Addresses: {_LOCALHOST}",
              f"\tfonts written to: {fonts[0].path.parent}",
              *(f"\t{line}" for line in details)]
    try:
        action = present(header, [])
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
    if action is Action.RELOAD:
        reload_process()
