"""Stdlib HTTP server exposing the font-composer web console.

Routes:

* ``GET /`` and ``GET /static/*`` — the two pages, their scripts and the stylesheet.
* ``GET /api/state`` — the full snapshot: families, groups, coverage, choices,
  summary, problem fonts and the version counter.
* ``GET /api/version`` — just the version counter; pages poll it and refetch the
  state when it changed (the directory watcher bumps it).
* ``POST /api/choose`` ``{group, family|null}`` — record a choice, save the
  configuration and bump the version.
* ``GET /fonts/<family>/<filename>`` — raw font bytes for ``@font-face``, guarded
  against path traversal: only files directly inside a family folder of the scanned
  fonts directory are served.

The state the routes serialize lives in :mod:`font_composer.composer.state`.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse

from font_composer.common.config import Config
from font_composer.common.inspect import looks_like_font
from font_composer.composer.state import ConsoleState
from font_composer.composer.watcher import DirectoryWatcher

STATIC_DIR = Path(__file__).parent / "static"

_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}

_FONT_TYPES = {".ttf": "font/ttf", ".otf": "font/otf"}

_FONT_URL_PARTS = 2  # /fonts/<family>/<filename>


class _ConsoleHTTPServer(ThreadingHTTPServer):
    """Threading server carrying the shared :class:`ConsoleState`."""

    daemon_threads = True

    def __init__(self, port: int, state: ConsoleState) -> None:
        """Bind on all interfaces; the console is meant for localhost use."""
        super().__init__(("", port), _Handler)
        self.state = state


class _Handler(BaseHTTPRequestHandler):
    """Route requests to the static files, the JSON API or the font bytes."""

    # -- helpers ---------------------------------------------------------

    @property
    def _state(self) -> ConsoleState:
        """The shared console state attached to the server instance."""
        return cast("_ConsoleHTTPServer", self.server).state

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

    # -- routing ---------------------------------------------------------

    def _route_get(self) -> None:
        """Dispatch GET requests."""
        path = urlparse(self.path).path
        if path == "/":
            self._send_file(STATIC_DIR / "index.html", _STATIC_TYPES[".html"])
        elif path == "/group.html":
            self._send_file(STATIC_DIR / "group.html", _STATIC_TYPES[".html"])
        elif path.startswith("/static/"):
            self._get_static(path.removeprefix("/static/"))
        elif path == "/api/state":
            self._send_json(self._state.snapshot())
        elif path == "/api/version":
            self._send_json({"version": self._state.version})
        elif path.startswith("/fonts/"):
            self._get_font(path.removeprefix("/fonts/"))
        else:
            self._send_json({"error": f"not found: {path}"}, status=404)

    def _route_post(self) -> None:
        """Dispatch POST requests (only ``/api/choose`` exists)."""
        path = urlparse(self.path).path
        if path != "/api/choose":
            self._send_json({"error": f"not found: {path}"}, status=404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self._send_json({"error": "invalid JSON body"}, status=400)
            return
        if not isinstance(body, dict) or not isinstance(body.get("group"), str):
            self._send_json({"error": "body must be {group: str, family: str|null}"},
                            status=400)
            return
        family = body.get("family")
        if family is not None and not isinstance(family, str):
            self._send_json({"error": "family must be a string or null"}, status=400)
            return
        status, payload = self._state.choose(body["group"], family)
        self._send_json(payload, status=status)

    def _get_static(self, name: str) -> None:
        """Serve one file from the package's static directory."""
        target = (STATIC_DIR / unquote(name)).resolve()
        if not target.is_file() or not target.is_relative_to(STATIC_DIR.resolve()):
            self._send_json({"error": f"not found: /static/{name}"}, status=404)
            return
        self._send_file(target, _STATIC_TYPES.get(target.suffix, "application/octet-stream"))

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


def serve(fonts_dir: Path, config: Config, port: int) -> None:
    """Run the console (watcher plus HTTP server) until Ctrl-C."""
    state = ConsoleState(fonts_dir, config)
    watcher = DirectoryWatcher(fonts_dir, state.refresh)
    watcher.start()
    server = _ConsoleHTTPServer(port, state)
    print(f"font_composer console: http://localhost:{port}/")
    print(f"  fonts: {fonts_dir}   config: {config.path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping.")
    finally:
        server.server_close()
        watcher.stop()
