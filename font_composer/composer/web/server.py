"""Stdlib HTTP server exposing the font-composer web console.

Routes:

* ``GET /api/state`` — the full snapshot: families, groups, coverage, choices,
  summary, problem fonts and the version counter.
* ``GET /api/version`` — just the version counter; the SPA polls it and refetches
  the state when it changed (the directory watcher bumps it).
* ``POST /api/choose`` ``{group, family|null}`` — record a choice, save the
  configuration and bump the version.
* ``GET /fonts/<family>/<filename>`` — raw font bytes for ``@font-face``, guarded
  against path traversal: only files directly inside a family folder of the scanned
  fonts directory are served.
* any other ``GET`` — the compiled SvelteKit SPA from the static directory: files
  are served by URL path, and any path that does not map to an existing file gets
  the SPA fallback ``200.html`` so client-side routes (e.g.
  ``/group?family=…&group=…``) load the app shell. Paths that escape the static
  directory are rejected with a 400. The compiled SPA is a build artifact and not
  committed; when it is absent, page requests get a 503 explaining how to compile
  it.

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
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
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
        """Dispatch GET requests."""
        path = urlparse(self.path).path
        if path == "/api/state":
            self._send_json(self._state.snapshot())
        elif path == "/api/version":
            self._send_json({"version": self._state.version})
        elif path.startswith("/fonts/"):
            self._get_font(path.removeprefix("/fonts/"))
        else:
            self._get_static(path)

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

    def _get_static(self, path: str) -> None:
        """Serve a static file by URL path, falling back to ``index.html``.

        The SPA is compiled into the static directory, so most paths map to a real
        file; directories get their ``index.html`` and client-side routes such as
        ``/group`` get the SPA fallback page ``200.html``. Paths that resolve
        outside the static directory are a traversal attempt. When no compiled
        page exists at all, the SPA was never built on this checkout.
        """
        static_root = STATIC_DIR.resolve()
        target = (static_root / unquote(path).lstrip("/")).resolve()
        if not target.is_relative_to(static_root):
            self._send_json({"error": f"invalid path: {path}"}, status=400)
            return
        if target.is_dir():
            target /= "index.html"
        if not target.is_file():
            target = static_root / "200.html"
        if not target.is_file():
            self._send_not_built()
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
