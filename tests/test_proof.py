"""Tests for the build proof: what ``build --show-proof`` serves and when it starts."""

from __future__ import annotations

import json
import socket
import threading
from http import HTTPStatus
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest
from support import build_font, sample_catalog

from font_composer.__main__ import parse_args
from font_composer.builder.build import BuildOptions, run_build
from font_composer.builder.proof import ProofFont, ProofSet, proof_payload
from font_composer.common.config import Config
from font_composer.composer.state import ConsoleState
from font_composer.composer.web import proof
from font_composer.composer.web import server as web_server
from font_composer.composer.web.proof import ProofHTTPServer, reuse_console

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
    httpd = ProofHTTPServer("127.0.0.1", 0, ProofSet([ProofFont("Regular", font)]))
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


def _build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, show_proof: bool,
    saved_port: int | None = None, port: int | None = None,
) -> tuple[list, list[str]]:
    """Build with a recording ``serve_proof``; return what it was asked to serve, and the report."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    shown: list = []
    monkeypatch.setattr(
        proof, "serve_proof",
        lambda fonts, _say, details, port, saved_port: shown.append(
            (list(fonts), details, port, saved_port)))
    config = tmp_path / "font_composer.toml"
    server = f"[server]\nport = {saved_port}\n" if saved_port else ""
    config.write_text(f'[cell]\nbase = "Base"\n[output]\nfamily = "Test"\n{server}',
                      encoding="utf-8")
    lines: list[str] = []
    status = run_build(BuildOptions(config, _families(tmp_path), tmp_path / "out", "fail",
                                    show_proof=show_proof, port=port),
                       say=lines.append, ask=lambda _prompt: "", interactive=False,
                       catalog=sample_catalog())
    assert status == 0
    return shown, lines


PINNED_PORT = 8731


def test_the_proof_is_shown_after_the_build_only_when_asked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Start the proof server with the fonts that were written, and never unasked."""
    unasked, _ = _build(tmp_path / "a", monkeypatch, show_proof=False)
    asked, _ = _build(tmp_path / "b", monkeypatch, show_proof=True, saved_port=8745,
                      port=PINNED_PORT)
    assert not unasked
    assert len(asked) == 1
    fonts, details, port, saved_port = asked[0]
    assert [font.path.name for font in fonts] == ["Test-Regular.ttf"]
    assert fonts[0].style == "Regular"
    assert details == ["styles: Regular (1 of 1 written)"]
    assert (port, saved_port) == (PINNED_PORT, 8745)  # --port, and the console's saved port


def test_show_proof_takes_a_port_like_the_console() -> None:
    """Accept --port on build, as compose does."""
    requested = 8800
    assert parse_args(["build", "--show-proof", "--port", str(requested)]).port == requested
    assert parse_args(["build"]).port is None


def test_the_proof_set_starts_empty_and_is_replaced_whole(tmp_path: Path) -> None:
    """Keep nothing of an earlier proof once a new one is set."""
    ink = {LIGHT: (0, 300, 600, 340)}
    first = build_font(tmp_path / "A-Regular.ttf", codepoints=[LIGHT], ink=ink)
    second = build_font(tmp_path / "B-Bold.ttf", codepoints=[LIGHT], ink=ink)
    proofs = ProofSet()
    before = proofs.payload
    assert before is None
    assert proofs.file("A-Regular.ttf") is None
    proofs.replace([ProofFont("Regular", first)])
    assert proofs.file("A-Regular.ttf") == first
    proofs.replace([ProofFont("Bold", second)])
    assert proofs.file("A-Regular.ttf") is None
    payload = proofs.payload
    assert payload is not None
    assert [entry["file"] for entry in payload["fonts"]] == ["B-Bold.ttf"]


@pytest.fixture(name="console")
def console_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    """Run the console's server on a free loopback port; yield the port."""
    fonts = tmp_path / "console-fonts" / "Alpha"
    fonts.mkdir(parents=True)
    build_font(fonts / "Alpha-Regular.ttf", codepoints=[ord("M")])
    static = tmp_path / "static"
    static.mkdir()
    (static / "200.html").write_text("<p>shell</p>", encoding="utf-8")
    monkeypatch.setattr(web_server, "STATIC_DIR", static)
    config = Config.load(tmp_path / "console.toml", default_base="Alpha")
    state = ConsoleState(tmp_path / "console-fonts", config, catalog=sample_catalog())
    httpd = web_server.ConsoleHTTPServer("127.0.0.1", 0, state)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _post(port: int, body: object) -> int:
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("POST", "/api/proof", body=json.dumps(body).encode(),
                           headers={"Content-Type": "application/json"})
        return connection.getresponse().status
    finally:
        connection.close()


def test_a_console_has_no_proof_until_one_is_registered(console: int) -> None:
    """Answer 'not found', so that the page can say how to get a proof."""
    assert _get(console, "/api/proof")[0] == HTTPStatus.NOT_FOUND
    assert _get(console, "/proof-fonts/Out-Regular.ttf")[0] == HTTPStatus.NOT_FOUND


def test_a_running_console_takes_over_the_proof(console: int, tmp_path: Path) -> None:
    """Register the written fonts with it; it then serves the data and the font bytes."""
    font = build_font(tmp_path / "Out-Regular.ttf", codepoints=[LIGHT],
                      ink={LIGHT: (0, 300, 600, 340)})
    assert reuse_console([ProofFont("Regular", font)], console) == (
        f"http://localhost:{console}{proof.PROOF_PAGE}")
    status, _headers, body = _get(console, "/api/proof")
    assert status == HTTPStatus.OK
    assert json.loads(body)["fonts"][0]["file"] == "Out-Regular.ttf"
    status, headers, body = _get(console, "/proof-fonts/Out-Regular.ttf")
    assert (status, headers["content-type"], body) == (
        HTTPStatus.OK, "font/ttf", font.read_bytes())
    assert _get(console, "/proof-fonts/Other.ttf")[0] == HTTPStatus.NOT_FOUND


def test_the_console_refuses_a_proof_that_is_not_fonts_it_can_find(
    console: int, tmp_path: Path,
) -> None:
    """Take only absolute paths of existing font files, and change nothing otherwise."""
    text = tmp_path / "notes.ttf"
    text.write_text("not a font", encoding="utf-8")
    font = build_font(tmp_path / "Ok-Regular.ttf", codepoints=[LIGHT])
    bad = [{"fonts": []}, {"fonts": "x"}, {"fonts": [{"style": "Regular", "path": "Ok.ttf"}]},
           {"fonts": [{"style": "Regular", "path": str(tmp_path / "missing.ttf")}]},
           {"fonts": [{"style": "Regular", "path": str(text)}]},
           {"fonts": [{"style": 3, "path": str(font)}]}, ["nope"]]
    for body in bad:
        assert _post(console, body) == HTTPStatus.BAD_REQUEST, body
    assert _get(console, "/api/proof")[0] == HTTPStatus.NOT_FOUND


def test_nothing_is_taken_over_when_no_console_answers(tmp_path: Path) -> None:
    """Report no console for a closed port, and for a server that is not the console."""
    font = build_font(tmp_path / "Out-Regular.ttf", codepoints=[LIGHT])
    fonts = [ProofFont("Regular", font)]
    with socket.socket() as closed:
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
    assert reuse_console(fonts, port) is None  # nothing listens there now

    # a server that answers nothing the console would: every method is "not implemented"
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        assert reuse_console(fonts, httpd.server_address[1]) is None
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_a_build_hands_its_proof_to_the_running_console_and_starts_no_server(
    console: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the port the console saved; print the same address; start nothing of its own."""
    shown, lines = _build(tmp_path, monkeypatch, show_proof=True, saved_port=console)
    assert not shown  # serve_proof was never needed
    assert any(f"http://localhost:{console}{proof.PROOF_PAGE}" in line for line in lines)
    assert any("already running" in line for line in lines)
    status, _headers, body = _get(console, "/api/proof")
    assert status == HTTPStatus.OK
    assert [entry["file"] for entry in json.loads(body)["fonts"]] == ["Test-Regular.ttf"]
