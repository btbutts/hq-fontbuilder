"""Tests for the build proof: what ``build --show-proof`` serves and when it starts."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.client import HTTPConnection
from typing import TYPE_CHECKING

import pytest
from support import build_font, sample_catalog

from font_composer.__main__ import parse_args
from font_composer.builder.build import BuildOptions, run_build
from font_composer.composer.web import proof
from font_composer.composer.web import server as web_server
from font_composer.composer.web.proof import ProofFont, ProofHTTPServer, proof_payload

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

LIGHT, RIGHT_ARM = 0x2500, 0x2576


def _get(port: int, path: str) -> tuple[int, dict[str, str], bytes]:
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
    finally:
        connection.close()


@pytest.fixture(name="served")
def served_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[int, Path]]:
    """Serve the proof of one tiny font whose box lines miss each other."""
    font = build_font(tmp_path / "Out-Regular.ttf", codepoints=[LIGHT, RIGHT_ARM],
                      ink={LIGHT: (0, 300, 600, 340), RIGHT_ARM: (300, 315, 600, 355)})
    static = tmp_path / "static"
    static.mkdir()
    (static / "200.html").write_text("<p>shell</p>", encoding="utf-8")
    monkeypatch.setattr(web_server, "STATIC_DIR", static)
    httpd = ProofHTTPServer("127.0.0.1", 0, [ProofFont("Regular", font)])
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[1], font
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_the_payload_lists_each_font_with_its_cell_and_its_seams(tmp_path: Path) -> None:
    """Give the page what it needs: where to load the font from, its cell, what is wrong."""
    font = build_font(tmp_path / "Out-Regular.ttf", codepoints=[LIGHT, RIGHT_ARM],
                      ink={LIGHT: (0, 300, 600, 340), RIGHT_ARM: (300, 315, 600, 355)})
    payload = proof_payload([ProofFont("Regular", font)])
    (entry,) = payload["fonts"]
    assert entry["style"] == "Regular"
    assert entry["file"] == "Out-Regular.ttf"
    assert entry["url"] == "/proof-fonts/Out-Regular.ttf"
    assert entry["cell"] == pytest.approx({"width": 0.6, "ascent": 0.8, "descent": -0.2})
    (seam,) = entry["seams"]
    assert seam["spread"] == pytest.approx(0.015, abs=0.0005)
    assert {member["codepoint"] for member in seam["members"]} == {LIGHT, RIGHT_ARM}


def test_the_payload_carries_the_outlines_of_the_box_glyphs_in_font_units(tmp_path: Path) -> None:
    """Let the page draw the glyphs exactly, from the file that was written."""
    font = build_font(tmp_path / "Out-Regular.ttf", codepoints=[LIGHT, RIGHT_ARM, ord("M")],
                      ink={LIGHT: (0, 300, 600, 340), RIGHT_ARM: (300, 315, 600, 355),
                           ord("M"): (50, 0, 550, 700)})
    (entry,) = proof_payload([ProofFont("Regular", font)])["fonts"]
    assert entry["units"] == {"upm": 1000, "advance": 600, "ascent": 800, "descent": -200}
    assert set(entry["outlines"]) == {str(LIGHT), str(RIGHT_ARM)}  # box and block glyphs only
    path = entry["outlines"][str(LIGHT)]
    assert path.startswith("M")
    assert path.endswith("Z")
    assert "600" in path
    assert "340" in path


def test_the_server_answers_the_proof_and_the_font_bytes(served: tuple[int, Path]) -> None:
    """Serve /api/proof as JSON and the written font by its file name."""
    port, font = served
    status, headers, body = _get(port, "/api/proof")
    assert status == HTTPStatus.OK
    assert headers["content-type"] == "application/json"
    assert json.loads(body)["fonts"][0]["file"] == "Out-Regular.ttf"
    status, headers, body = _get(port, "/proof-fonts/Out-Regular.ttf")
    assert status == HTTPStatus.OK
    assert headers["content-type"] == "font/ttf"
    assert body == font.read_bytes()


def test_the_hidden_page_is_the_spa_shell_and_nothing_else_is_answered(
    served: tuple[int, Path],
) -> None:
    """Load the SPA for /buildProof, but answer none of the console's API."""
    port, _font = served
    status, _headers, body = _get(port, "/buildProof")
    assert status == HTTPStatus.OK
    assert body == b"<p>shell</p>"
    for path in ("/api/state", "/api/version", "/api/glyphs?family=A&group=B"):
        assert _get(port, path)[0] == HTTPStatus.NOT_FOUND


@pytest.mark.parametrize("name", ["Other.ttf", "../Out-Regular.ttf", "%2e%2e/Out-Regular.ttf",
                                  "a/Out-Regular.ttf"])
def test_only_the_written_fonts_are_served(served: tuple[int, Path], name: str) -> None:
    """Refuse any other file, and any path that is not a plain file name."""
    port, _font = served
    assert _get(port, f"/proof-fonts/{name}")[0] in {HTTPStatus.NOT_FOUND, HTTPStatus.BAD_REQUEST}


def test_post_is_refused(served: tuple[int, Path]) -> None:
    """Change nothing: the proof has no write routes."""
    port, _font = served
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("POST", "/api/choose", body=b"{}",
                           headers={"Content-Type": "application/json"})
        assert connection.getresponse().status == HTTPStatus.NOT_FOUND
    finally:
        connection.close()


def test_show_proof_is_a_build_option() -> None:
    """Accept --show-proof on build only; off by default."""
    assert not parse_args(["build"]).show_proof
    assert parse_args(["build", "--show-proof"]).show_proof


def _families(tmp_path: Path) -> Path:
    fonts = tmp_path / "fonts"
    (fonts / "Base").mkdir(parents=True)
    build_font(fonts / "Base" / "Base-Regular.ttf", codepoints=[ord("M")],
               ink={ord("M"): (50, 0, 550, 700)})
    return fonts


def _build(tmp_path: Path, *, show_proof: bool, monkeypatch: pytest.MonkeyPatch) -> list:
    tmp_path.mkdir(parents=True, exist_ok=True)
    shown: list = []
    monkeypatch.setattr(proof, "serve_proof",
                        lambda fonts, _say, details: shown.append((list(fonts), details)))
    config = tmp_path / "font_composer.toml"
    config.write_text('[cell]\nbase = "Base"\n[output]\nfamily = "Test"\n', encoding="utf-8")
    status = run_build(BuildOptions(config, _families(tmp_path), tmp_path / "out", "fail",
                                    show_proof=show_proof),
                       say=lambda _text: None, ask=lambda _prompt: "", interactive=False,
                       catalog=sample_catalog())
    assert status == 0
    return shown


def test_the_proof_is_shown_after_the_build_only_when_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Start the proof server with the fonts that were written, and never unasked."""
    unasked = _build(tmp_path / "a", show_proof=False, monkeypatch=monkeypatch)
    asked = _build(tmp_path / "b", show_proof=True, monkeypatch=monkeypatch)
    assert not unasked
    assert len(asked) == 1
    fonts, details = asked[0]
    assert [font.path.name for font in fonts] == ["Test-Regular.ttf"]
    assert fonts[0].style == "Regular"
    assert details == ["styles: Regular (1 of 1 written)"]
