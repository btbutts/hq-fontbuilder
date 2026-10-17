"""Tests for font_composer.composer.web.server: routing, content types, static fallback."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.client import HTTPConnection
from typing import TYPE_CHECKING, Any

import pytest
from support import FontSpec, NameSpec, build_font, sample_catalog

from font_composer.common.config import Config
from font_composer.composer.state import ConsoleState
from font_composer.composer.web import ports
from font_composer.composer.web import server as web_server

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class _Client:
    """A minimal HTTP client bound to the test server's port."""

    def __init__(self, port: int) -> None:
        """Remember the port of the running test server."""
        self.port = port

    def request(self, method: str, path: str, body: bytes | None = None,
                content_type: str | None = None) -> tuple[int, dict[str, str], bytes]:
        """Send one request; return status, lower-cased headers and body."""
        connection = HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            headers = {"Content-Type": content_type} if content_type else {}
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            data = response.read()
            return response.status, {k.lower(): v for k, v in response.getheaders()}, data
        finally:
            connection.close()

    def json(self, method: str, path: str, payload: Any = None,
             content_type: str | None = "application/json") -> tuple[int, Any]:
        """Send a JSON request and decode the JSON answer."""
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        status, _headers, data = self.request(method, path, body, content_type)
        return status, json.loads(data)


@pytest.fixture(name="client")
def client_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[_Client]:
    """Run the console server on a free loopback port over two tiny families."""
    fonts = tmp_path / "fonts"
    for label in ("Alpha", "Beta"):
        (fonts / label).mkdir(parents=True)
        build_font(fonts / label / f"{label}-Regular.ttf", codepoints=[ord("M"), 0x2190])
    build_font(fonts / "Alpha" / "Alpha-Bold.ttf", codepoints=[ord("M")],
               spec=FontSpec(names=NameSpec(style="Bold", weight=700)))
    static = tmp_path / "static"
    static.mkdir()
    (static / "200.html").write_text("<p>shell</p>", encoding="utf-8")
    (static / "index.html").write_text("<p>index</p>", encoding="utf-8")
    monkeypatch.setattr(web_server, "STATIC_DIR", static)
    config = Config.load(tmp_path / "font_composer.toml", default_base="Alpha")
    state = ConsoleState(fonts, config, catalog=sample_catalog())
    httpd = web_server.ConsoleHTTPServer("127.0.0.1", 0, state)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield _Client(httpd.server_address[1])
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def test_listens_on_localhost_by_default() -> None:
    """Never expose the unauthenticated console on every interface unless asked."""
    assert web_server.DEFAULT_HOST == "localhost"
    assert ports.local_addresses(web_server.DEFAULT_HOST) == ["127.0.0.1", "::1"]


def test_state_and_version(client: _Client) -> None:
    """Serve the snapshot and the version counter."""
    status, state = client.json("GET", "/api/state")
    assert status == HTTPStatus.OK
    assert [family["label"] for family in state["families"]] == ["Alpha", "Beta"]
    status, version = client.json("GET", "/api/version")
    assert status == HTTPStatus.OK
    assert version == {"version": state["version"]}


def test_choose_requires_a_json_content_type(client: _Client) -> None:
    """Refuse the body a cross-site form post could send without a preflight."""
    body = {"group": "Arrows", "family": "Alpha", "action": "add"}
    status, payload = client.json("POST", "/api/choose", body, content_type="text/plain")
    assert status == HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    assert "error" in payload
    status, payload = client.json("POST", "/api/choose", body)
    assert status == HTTPStatus.OK
    assert payload["choices"] == {"Arrows": ["Alpha"]}


def test_choose_rejects_a_malformed_body(client: _Client) -> None:
    """Answer 400 for JSON that is not {group, family}."""
    for body in ({"family": "Alpha"}, {"group": "Arrows", "action": "add", "family": 3}):
        assert client.json("POST", "/api/choose", body)[0] == HTTPStatus.BAD_REQUEST


def test_glyphs_endpoint(client: _Client) -> None:
    """Serve the present code points of a group for each style of a family."""
    status, payload = client.json("GET", "/api/glyphs?family=Alpha&group=Arrows")
    assert status == HTTPStatus.OK
    assert payload["styles"] == {"Alpha-Regular.ttf": [0x2190], "Alpha-Bold.ttf": []}
    assert client.json("GET", "/api/glyphs?family=Nowhere&group=Arrows")[0] == HTTPStatus.NOT_FOUND


def test_font_bytes_are_served_from_family_folders_only(client: _Client) -> None:
    """Serve a font file, and nothing outside a family folder."""
    status, headers, data = client.request("GET", "/fonts/Alpha/Alpha-Regular.ttf")
    assert status == HTTPStatus.OK
    assert headers["content-type"] == "font/ttf"
    assert data[:4] == b"\x00\x01\x00\x00"
    escape = client.request("GET", "/fonts/Alpha/..%2F..%2Ffont_composer.toml")
    assert escape[0] == HTTPStatus.BAD_REQUEST
    assert client.request("GET", "/fonts/Alpha/missing.ttf")[0] == HTTPStatus.NOT_FOUND


def test_static_fallback_is_for_routes_not_for_missing_assets(client: _Client) -> None:
    """Give client-side routes the app shell, but 404 a missing script."""
    status, _headers, data = client.request("GET", "/group")
    assert (status, data) == (HTTPStatus.OK, b"<p>shell</p>")
    status, _headers, data = client.request("GET", "/")
    assert (status, data) == (HTTPStatus.OK, b"<p>index</p>")
    assert client.request("GET", "/_app/immutable/missing.js")[0] == HTTPStatus.NOT_FOUND
    assert client.request("GET", "/%2e%2e/%2e%2e/etc/passwd")[0] == HTTPStatus.BAD_REQUEST


def test_composition_glyph_and_style_routes(client: _Client) -> None:
    """Resolve a group, pin a glyph, map a style: the three inheritance routes."""
    for label in ("Alpha", "Beta"):
        body = {"group": "Arrows", "family": label, "action": "add"}
        assert client.json("POST", "/api/choose", body)[0] == HTTPStatus.OK
    status, composition = client.json("GET", "/api/composition?group=Arrows")
    assert status == HTTPStatus.OK
    assert composition["order"] == ["Alpha", "Beta"]
    glyph = composition["glyphs"][0]
    assert (glyph["source"], glyph["candidates"]) == ("Alpha", ["Alpha", "Beta"])
    status, pinned = client.json("POST", "/api/glyph", {"codepoint": 0x2190, "family": "Beta"})
    assert status == HTTPStatus.OK
    assert pinned["glyphs"][0]["source"] == "Beta"
    assert pinned["glyphs"][0]["overridden"]
    bad = client.json("POST", "/api/glyph", {"codepoint": "x", "family": None})
    assert bad[0] == HTTPStatus.BAD_REQUEST
    style = {"style": "Bold", "family": "Alpha", "file": "Alpha-Regular.ttf"}
    status, state = client.json("POST", "/api/style", style)
    assert status == HTTPStatus.OK
    assert state["styleMap"]["entries"]["Bold"]["Alpha"]["overridden"]
    assert client.json("GET", "/api/composition?group=nonsense")[0] == HTTPStatus.BAD_REQUEST


def test_state_takes_the_overlay_flag(client: _Client) -> None:
    """List the blocks by default and the overlay categories when asked."""
    _status, plain = client.json("GET", "/api/state?overlay=0")
    _status, overlaid = client.json("GET", "/api/state?overlay=1")
    _status, default = client.json("GET", "/api/state")
    assert [group["id"] for group in plain["groups"]] == ["Basic Latin", "Arrows"]
    assert [group["id"] for group in overlaid["groups"]] == ["overlay:ascii-alnum", "Arrows"]
    assert default["groups"] == plain["groups"]


def test_choosing_in_an_overlay_category_answers_with_the_new_order(client: _Client) -> None:
    """Take the browser's order in the body and give the new one back."""
    body = {"group": "overlay:ascii-alnum", "action": "add", "family": "Alpha", "order": []}
    status, payload = client.json("POST", "/api/choose", body)
    assert status == HTTPStatus.OK
    assert payload["order"] == ["Alpha"]
    status, composition = client.json(
        "GET", "/api/composition?group=overlay:ascii-alnum&overlay=1&order=Alpha&order=Beta")
    assert status == HTTPStatus.OK
    assert composition["order"] == ["Alpha", "Beta"]
    assert client.json("POST", "/api/choose", {**body, "order": "Alpha"})[0] == (
        HTTPStatus.BAD_REQUEST)


def test_the_overlay_store_route_checks_its_body(client: _Client) -> None:
    """Answer 400 to a body of the wrong shape and 200 to a right one."""
    store = "/api/overlay-store"
    assert client.json("POST", store, {"enabled": "yes", "orders": {}})[0] == (
        HTTPStatus.BAD_REQUEST)
    assert client.json("POST", store, {"enabled": True, "orders": {"Arrows": ["Alpha"]}})[0] == (
        HTTPStatus.BAD_REQUEST)
    assert client.json("POST", store, {"enabled": True,
                                       "orders": {"overlay:powerline": ["Alpha"]}})[0] == (
        HTTPStatus.OK)
    assert client.json("POST", store, {"enabled": False, "orders": {}})[0] == HTTPStatus.OK


def test_the_read_routes_follow_the_view(client: _Client) -> None:
    """Serve a category only in the view it belongs to."""
    assert client.json("GET", "/api/glyphs?family=Alpha&group=Basic%20Latin&overlay=1")[0] == (
        HTTPStatus.BAD_REQUEST)
    assert client.json("GET", "/api/glyphs?family=Alpha&group=Basic%20Latin")[0] == HTTPStatus.OK
    assert client.json("GET", "/api/names?group=overlay:ascii-alnum")[0] == HTTPStatus.BAD_REQUEST
    assert client.json("GET", "/api/names?group=overlay:ascii-alnum&overlay=1")[0] == HTTPStatus.OK
