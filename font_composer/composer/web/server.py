"""Stdlib HTTP server exposing the font-composer web console.

Routes:

* ``GET /api/state`` — the full snapshot: families, groups, coverage, choices,
  summary, problem fonts and the version counter.
* ``GET /api/version`` — just the version counter; the SPA polls it and refetches
  the state when it changed (the directory watcher bumps it, and so does a hand edit
  of the configuration file).
* ``GET /api/glyphs?family=F&group=G`` — for each style file of a family, the code
  points of the group it holds (the group page draws only those).
* ``GET /api/fit?family=F&group=G&file=S&codepoints=1,2,3`` — the fit of those code
  points of one style file, for a group too large to fit whole (``/api/glyphs`` leaves
  its ``fit`` empty): the page asks for the glyphs it draws, a page at a time.
* ``GET /api/names?group=G`` — the official Unicode names of the group's code points
  (from ``NamesList.txt``; empty when the list is not available).
* ``GET /api/composition?group=G`` — the group resolved through its inheritance
  order and the glyph overrides: for every code point some family has, its source and
  the other families that could serve it.
* ``POST /api/choose`` ``{group, action, family}`` — add a family to the end of the
  group's inheritance order, remove it, move it up or down, or clear the group
  (``action``: add, remove, up, down, clear).
* ``POST /api/glyph`` ``{codepoint, family|null}`` — serve one code point from one of
  the group's families, or (null) go back to the inheritance order.
* ``POST /api/style`` ``{style, family, file|null}`` — map an output style of a family
  to one of its style files, or (null) back to the default rules.
* ``POST /api/style-type`` ``{style, included}`` — consider a style (``Bold``, ``Light
  Italic`` ...) in the build and the style mapping, or leave it out (``[output] styles``).
* ``POST /api/style-consolidate`` ``{enabled}`` — list similar styles as one entry.
* ``POST /api/style-name`` ``{style, name|null}`` — build an output style under another
  name (``[output] style-names``; it must be unique), or (null) under its own again.

  Every POST saves the configuration and bumps the version, and its body must be sent
  as ``application/json``: a cross-site page cannot do that without a CORS preflight,
  which is refused.
* ``GET /fonts/<family>/<filename>`` — raw font bytes for ``@font-face``, guarded
  against path traversal: only files directly inside a family folder of the scanned
  fonts directory are served.
* any other ``GET`` — the compiled SvelteKit SPA from the static directory: files
  are served by URL path, and any path that does not map to an existing file gets
  the SPA fallback ``200.html`` so client-side routes (e.g.
  ``/group?family=…&group=…``) load the app shell; a path with a file extension that
  matches no file is a 404 (a missing script must not come back as an HTML page).
  Paths that escape the static directory are rejected with a 400. The compiled SPA is
  a build artifact and not committed; when it is absent, page requests get a 503
  explaining how to compile it.

The server listens on ``localhost`` (both ``127.0.0.1`` and ``::1``) unless told
otherwise: the console writes a file on this machine and has no authentication. The
port is chosen by :mod:`font_composer.common.cli.ports`.

The state the routes serialize lives in :mod:`font_composer.composer.state`.
"""

from __future__ import annotations

import errno
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, TypeGuard, cast
from urllib.parse import parse_qs, unquote, urlparse

from font_composer.common.cli.console_ui import Action
from font_composer.common.cli.ports import (
    LOCALHOST,
    PortUnavailableError,
    local_addresses,
    pick_port,
)
from font_composer.common.cli.session import present
from font_composer.common.config import Config, ConfigError
from font_composer.common.fonts.inspect import looks_like_font
from font_composer.composer.state import ConsoleState
from font_composer.composer.watcher import DirectoryWatcher

STATIC_DIR = Path(__file__).parent / "static"

DEFAULT_HOST = LOCALHOST

_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}

_FONT_TYPES = {".ttf": "font/ttf", ".otf": "font/otf"}

_FONT_URL_PARTS = 2  # /fonts/<family>/<filename>

_TRUE_FLAGS = ("1", "true")


class ConsoleHTTPServer(ThreadingHTTPServer):
    """Threading server on one IP address, carrying the shared :class:`ConsoleState`."""

    daemon_threads = True

    def __init__(self, address: str, port: int, state: ConsoleState) -> None:
        """Bind on one IPv4 or IPv6 address; the console is meant for localhost use."""
        self.address_family = socket.AF_INET6 if ":" in address else socket.AF_INET
        super().__init__((address, port), _Handler)
        self.state = state


def _flag(query: dict[str, list[str]]) -> bool:
    """Read the ``overlay`` query parameter: the view the request is about."""
    return query.get("overlay", ["0"])[0] in _TRUE_FLAGS


def _is_string_list(value: Any) -> TypeGuard[list[str]]:
    """Tell whether a JSON value is a list of strings."""
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_orders(value: Any) -> TypeGuard[dict[str, list[str]]]:
    """Tell whether a JSON value maps names to lists of strings."""
    return isinstance(value, dict) and all(
        isinstance(key, str) and _is_string_list(item) for key, item in value.items())


class StaticHandler(BaseHTTPRequestHandler):
    """Answer GET requests with the compiled SPA; subclasses add their own routes.

    It is also the base of the page a build proof is shown on (see
    :mod:`font_composer.composer.web.proof`).
    """

    # -- helpers ---------------------------------------------------------

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        try:
            body = path.read_bytes()
        except OSError:
            self._send_json({"error": f"cannot read {path.name}"}, status=404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_not_built(self) -> None:
        """Explain that the SPA has not been compiled yet (fresh clone)."""
        body = (
            b"<!doctype html><meta charset='utf-8'><title>font-composer</title>"
            b"<h1>Web console not compiled</h1>"
            b"<p>The console's static files are build artifacts and are not in the "
            b"repository. Compile them once, then reload:</p>"
            b"<pre>./compile-spa.sh</pre>"
        )
        self.send_response(503)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # -- routing ---------------------------------------------------------

    def _route_get(self) -> None:
        """Dispatch GET requests: the SPA only."""
        self._get_static(urlparse(self.path).path)

    def _route_post(self) -> None:
        """Refuse POST requests: there is nothing to change."""
        self._send_json({"error": "not found"}, status=404)

    def _get_static(self, path: str) -> None:
        """Serve a static file by URL path, falling back to ``index.html``.

        The SPA is compiled into the static directory, so most paths map to a real
        file; directories get their ``index.html`` and client-side routes such as
        ``/group`` get the SPA fallback page ``200.html``; a missing file with an
        extension is a 404. Paths that resolve outside the static directory are a
        traversal attempt. When no compiled page exists at all, the SPA was never
        built on this checkout.
        """
        static_root = STATIC_DIR.resolve()
        target = (static_root / unquote(path).lstrip("/")).resolve()
        if not target.is_relative_to(static_root):
            self._send_json({"error": f"invalid path: {path}"}, status=400)
            return
        if target.is_dir():
            target /= "index.html"
        if not target.is_file():
            if target.suffix:
                self._send_json({"error": f"not found: {path}"}, status=404)
                return
            target = static_root / "200.html"
        if not target.is_file():
            self._send_not_built()
            return
        self._send_file(target, _STATIC_TYPES.get(target.suffix, "application/octet-stream"))

    def __getattr__(self, name: str) -> Any:
        """Map the stdlib's ``do_<METHOD>`` lookup onto the routing methods.

        ``BaseHTTPRequestHandler`` calls ``getattr(self, "do_GET")`` etc.; answering
        through ``__getattr__`` keeps those HTTP-style names out of the class body.
        """
        if name == "do_GET":
            return self._route_get
        if name == "do_POST":
            return self._route_post
        raise AttributeError(name)


class _Handler(StaticHandler):
    """Route requests to the static files, the JSON API or the font bytes."""

    # -- helpers ---------------------------------------------------------

    @property
    def _state(self) -> ConsoleState:
        """The shared console state attached to the server instance."""
        return cast("ConsoleHTTPServer", self.server).state

    # -- routing ---------------------------------------------------------

    def _route_get(self) -> None:
        """Dispatch GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/state":
            self._send_json(self._state.snapshot(overlay=_flag(parse_qs(parsed.query))))
        elif path == "/api/version":
            self._send_json({"version": self._state.current_version()})
        elif path == "/api/glyphs":
            query = parse_qs(parsed.query)
            status, payload = self._state.glyphs(
                query.get("family", [""])[0], query.get("group", [""])[0],
                overlay=_flag(query))
            self._send_json(payload, status=status)
        elif path == "/api/fit":
            query = parse_qs(parsed.query)
            try:
                points = [int(item) for item in query.get("codepoints", [""])[0].split(",") if item]
            except ValueError:
                self._send_json({"error": "codepoints must be integers"}, status=400)
                return
            status, payload = self._state.fit(
                query.get("family", [""])[0], query.get("group", [""])[0],
                query.get("file", [""])[0], points)
            self._send_json(payload, status=status)
        elif path == "/api/names":
            query = parse_qs(parsed.query)
            status, payload = self._state.glyph_names(
                query.get("group", [""])[0], overlay=_flag(query))
            self._send_json(payload, status=status)
        elif path == "/api/composition":
            query = parse_qs(parsed.query)
            status, payload = self._state.composition(
                query.get("group", [""])[0], query.get("order"), overlay=_flag(query))
            self._send_json(payload, status=status)
        elif path.startswith("/fonts/"):
            self._get_font(path.removeprefix("/fonts/"))
        else:
            self._get_static(path)

    def _read_json_body(self) -> dict[str, Any] | None:
        """Read the request body as a JSON object; answer the error and return None if not."""
        content_type = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if content_type != "application/json":
            self._send_json({"error": "Content-Type must be application/json"}, status=415)
            return None
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._send_json({"error": "invalid JSON body"}, status=400)
            return None
        if not isinstance(body, dict):
            self._send_json({"error": "body must be a JSON object"}, status=400)
            return None
        return body

    def _route_post(self) -> None:
        """Dispatch POST requests: choose, glyph and style (all JSON, all state changes)."""
        path = urlparse(self.path).path
        handlers = {"/api/choose": self._post_choose, "/api/glyph": self._post_glyph,
                    "/api/style": self._post_style,
                    "/api/style-type": self._post_style_type,
                    "/api/style-consolidate": self._post_style_consolidate,
                    "/api/style-name": self._post_style_name,
                    "/api/overlay-store": self._post_overlay_store}
        handler = handlers.get(path)
        if handler is None:
            self._send_json({"error": f"not found: {path}"}, status=404)
            return
        body = self._read_json_body()
        if body is None:
            return
        status, payload = handler(body)
        self._send_json(payload, status=status)

    def _post_choose(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """``{group, action, family, order?}``: add, remove, move or clear a family of a group."""
        group, action, family = body.get("group"), body.get("action"), body.get("family")
        order = body.get("order")
        if not isinstance(group, str) or not isinstance(action, str):
            return 400, {"error": "body must be {group: str, action: str, family: str}"}
        if family is not None and not isinstance(family, str):
            return 400, {"error": "family must be a string"}
        if order is not None and not _is_string_list(order):
            return 400, {"error": "order must be a list of strings"}
        return self._state.choose(group, family, action, order)

    def _post_glyph(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """``{codepoint, family|null, group?, order?}``: pin a code point or release it."""
        codepoint, family = body.get("codepoint"), body.get("family")
        group, order = body.get("group"), body.get("order")
        if not isinstance(codepoint, int) or isinstance(codepoint, bool):
            return 400, {"error": "codepoint must be an integer"}
        if family is not None and not isinstance(family, str):
            return 400, {"error": "family must be a string or null"}
        if group is not None and not isinstance(group, str):
            return 400, {"error": "group must be a string"}
        if order is not None and not _is_string_list(order):
            return 400, {"error": "order must be a list of strings"}
        return self._state.set_glyph(codepoint, family, group, order)

    def _post_overlay_store(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """Handle ``{enabled, orders}``: keep the overlay orders in the toml, or remove them."""
        enabled, orders = body.get("enabled"), body.get("orders")
        if not isinstance(enabled, bool) or not _is_orders(orders):
            return 400, {"error": "enabled must be a boolean and orders a map of id to families"}
        return self._state.set_overlay_store(enabled=enabled, orders=orders)

    def _post_style(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """``{style, family, file|null}``: map an output style of a family to a file."""
        style, family, file_name = body.get("style"), body.get("family"), body.get("file")
        if not isinstance(style, str) or not isinstance(family, str):
            return 400, {"error": "body must be {style: str, family: str, file: str|null}"}
        if file_name is not None and not isinstance(file_name, str):
            return 400, {"error": "file must be a string or null"}
        return self._state.set_style(style, family, file_name)

    def _post_style_type(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """``{style, included}``: consider a style type or leave it out."""
        style, included = body.get("style"), body.get("included")
        if not isinstance(style, str) or not isinstance(included, bool):
            return 400, {"error": "body must be {style: str, included: bool}"}
        return self._state.set_style_included(style, included=included)

    def _post_style_consolidate(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """Handle ``{enabled}``: list similar styles as one entry, or as the fonts spell them."""
        enabled = body.get("enabled")
        if not isinstance(enabled, bool):
            return 400, {"error": "body must be {enabled: bool}"}
        return self._state.set_consolidate(enabled=enabled)

    def _post_style_name(self, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        """``{style, name|null}``: give an output style a custom name, or take it away."""
        style, name = body.get("style"), body.get("name")
        if not isinstance(style, str) or not (name is None or isinstance(name, str)):
            return 400, {"error": "body must be {style: str, name: str|null}"}
        return self._state.set_style_name(style, name)

    def _get_font(self, relative: str) -> None:
        """Serve raw font bytes, only from inside a scanned family folder."""
        parts = Path(unquote(relative)).parts
        if len(parts) != _FONT_URL_PARTS or ".." in parts:
            self._send_json({"error": "expected /fonts/<family>/<filename>"}, status=400)
            return
        fonts_dir = self._state.fonts_dir.resolve()
        target = (fonts_dir / parts[0] / parts[1]).resolve()
        family_dir = (fonts_dir / parts[0]).resolve()
        inside = target.parent == family_dir and family_dir.parent == fonts_dir
        if not inside or not target.is_file() or not looks_like_font(target):
            self._send_json({"error": f"not found: /fonts/{relative}"}, status=404)
            return
        self._send_file(target, _FONT_TYPES.get(target.suffix.lower(),
                                                "application/octet-stream"))


def _url_host(host: str) -> str:
    """Return the host as it is written in a URL (IPv6 literals in brackets)."""
    return f"[{host}]" if ":" in host else host


def _bind(address: str, port: int, state: ConsoleState) -> ConsoleHTTPServer | None:
    """Bind one server, or return None for an IPv6 address this machine cannot use."""
    try:
        return ConsoleHTTPServer(address, port, state)
    except OSError as exc:
        unusable = {errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT, errno.EPROTONOSUPPORT}
        if ":" in address and exc.errno in unusable:
            return None
        raise


def _open_servers(addresses: list[str], port: int, state: ConsoleState) -> list[ConsoleHTTPServer]:
    """Bind one server per address; all of them or, on failure, none.

    An IPv6 address this machine cannot bind (IPv6 switched off) is skipped as long as
    another address could be bound.
    """
    servers: list[ConsoleHTTPServer] = []
    try:
        for address in addresses:
            server = _bind(address, port, state)
            if server is not None:
                servers.append(server)
    except OSError as exc:
        for server in servers:
            server.server_close()
        if exc.errno == errno.EADDRINUSE:
            message = f"port {port} was taken just now; run the command again"
            raise PortUnavailableError(message) from exc
        raise
    if not servers:
        message = f"cannot listen on {', '.join(addresses)}: no usable address"
        raise PortUnavailableError(message)
    return servers


def _header(host: str, port: int, bound: list[str], fonts_dir: Path, config: Config) -> list[str]:
    """Return the four lines that stay on screen while the console runs."""
    return [
        f"The font_composer console is reachable at: http://{_url_host(host)}:{port}/",
        f"\tlistening on IP Addresses: {', '.join(bound)}",
        f"\tfonts: {fonts_dir}",
        f"\tconfig: {config.path}",
    ]


def _startup_notes(
    config: Config, chosen: int, notice: str | None, addresses: list[str], bound: list[str],
) -> list[str]:
    """Save the port and collect what is worth telling the user besides the header."""
    notes: list[str] = []
    try:
        config.set_port(chosen)
    except ConfigError as exc:
        notes.append(f"warning: the port was not saved: {exc}")
    if notice:
        notes.append(notice)
    notes.extend(f"not available on this machine: {address}"
                 for address in addresses if address not in bound)
    return notes


def serve(
    fonts_dir: Path,
    config: Config,
    host: str = DEFAULT_HOST,
    port: int | None = None,
    monitor: bool = False,
) -> bool:
    """Run the console (watcher plus HTTP servers) until it is told to stop.

    ``port`` is the one the user asked for, or None to reuse the port saved in the
    configuration or pick a free one. On a terminal the output is the in-place block of
    :mod:`font_composer.common.cli.console_ui`; ``monitor`` (or no terminal) streams
    every request line instead. Returns True when the user asked for a reload.

    Raises :class:`PortUnavailableError` (with a message for the user) when the port
    cannot be had, and :class:`OSError` for other failures to listen.
    """
    addresses = local_addresses(host)
    chosen, notice = pick_port(addresses, host, port, config.saved_port)
    state = ConsoleState(fonts_dir, config)
    servers = _open_servers(addresses, chosen, state)
    bound = [str(server.server_address[0]) for server in servers]
    notes = _startup_notes(config, chosen, notice, addresses, bound)
    watcher = DirectoryWatcher(fonts_dir, state.refresh)
    watcher.start()
    for server in servers:
        threading.Thread(target=server.serve_forever, name=f"console-{server.server_address[0]}",
                         daemon=True).start()
    try:
        action = present(_header(host, chosen, bound, fonts_dir, config), notes, monitor=monitor)
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        watcher.stop()
    return action is Action.RELOAD
