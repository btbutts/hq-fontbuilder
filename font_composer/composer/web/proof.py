"""The proof of a build: what ``build --show-proof`` serves, and how it reaches a browser.

The proof is a hidden page of the console's SPA (``/buildProof``) that draws tables with the
fonts the build wrote (the data is :mod:`font_composer.builder.proof`). Whoever serves it
answers only what that page needs: ``GET /api/proof`` and ``GET /proof-fonts/<file>``.

A console that is already running serves the page itself, so a build first offers it the fonts
(:func:`reuse_console`) and starts a server of its own (:func:`serve_proof`) only when none
takes them.
"""

from __future__ import annotations

import json
import threading
import urllib.request
from http import HTTPStatus
from typing import TYPE_CHECKING

from font_composer.builder.proof import FONT_PREFIX, ProofFont, ProofSet
from font_composer.common.cli.console_ui import Action
from font_composer.common.cli.ports import (
    LOCALHOST,
    PortUnavailableError,
    local_addresses,
    open_servers,
    pick_port,
)
from font_composer.common.cli.session import present, reload_process
from font_composer.composer.web.server import SpaServer, StaticHandler

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

PROOF_PAGE = "/buildProof"
_TIMEOUT_SECONDS = 5


class ProofHTTPServer(SpaServer):
    """The server a build starts for its own proof, on one address."""

    def __init__(self, address: str, port: int, proof: ProofSet) -> None:
        """Bind on one address; ``proof`` is what the page shows."""
        super().__init__(address, port, _ProofHandler, proof)


class _ProofHandler(StaticHandler):
    """Answer the proof's two routes, and the SPA for everything else."""

    def _route_get(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/proof" or path.startswith(FONT_PREFIX):
            self._get_proof(path)
        elif path.startswith("/api/"):
            self._send_json({"error": f"not found: {path}"}, status=404)
        else:
            self._get_static(path)


def _url_host(address: str) -> str:
    """Return an IP address as it is written in a URL (IPv6 literals in brackets)."""
    return f"[{address}]" if ":" in address else address


def reuse_console(fonts: Sequence[ProofFont], port: int | None) -> str | None:
    """Hand the fonts to a console that is already listening on ``port``.

    Return the address of the proof page there, or None when nothing on that port took them
    (no listener, another program, or a console that refused the fonts). The console keeps
    them until it is stopped, so the caller has nothing to serve. Proxies are not used: the
    console is on this machine.
    """
    if port is None:
        return None
    body = json.dumps({"fonts": [{"style": font.style, "path": str(font.path)}
                                 for font in fonts]}).encode("utf-8")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for address in local_addresses(LOCALHOST):
        request = urllib.request.Request(
            f"http://{_url_host(address)}:{port}/api/proof", data=body, method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with opener.open(request, timeout=_TIMEOUT_SECONDS) as answer:
                if answer.status == HTTPStatus.OK:
                    return f"http://{LOCALHOST}:{port}{PROOF_PAGE}"
        except OSError:
            continue
    return None


def serve_proof(
    fonts: Sequence[ProofFont], say: Callable[[str], None] = print, *,
    details: Sequence[str] = (), port: int | None = None, saved_port: int | None = None,
) -> None:
    """Serve the proof of the fonts until the user quits.

    The port is chosen as the console chooses its own: ``port`` if given (an error if it is in
    use), else the console's ``saved_port`` if it is free, else a free one; every local address
    is listened on. It is presented like the console: the address and ``details`` stay on
    screen above a window of the requests, with ``Press 'Q' to quit or 'R' to Reload`` under it.
    ``R`` starts the command over, so the fonts are built again.
    """
    addresses = local_addresses(LOCALHOST)
    proof = ProofSet(fonts)
    try:
        chosen, notice = pick_port(addresses, LOCALHOST, port, saved_port)
        servers = open_servers(addresses, chosen,
                               lambda address, number: ProofHTTPServer(address, number, proof))
    except (PortUnavailableError, OSError) as exc:
        say(f"font_composer: cannot show the proof: {exc}")
        return
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    bound = ", ".join(str(server.server_address[0]) for server in servers)
    header = [f"The proof of the fonts is at: http://{LOCALHOST}:{chosen}{PROOF_PAGE}",
              f"\tlistening on IP Addresses: {bound}",
              f"\tfonts written to: {fonts[0].path.parent}",
              *(f"\t{line}" for line in details)]
    try:
        action = present(header, [notice] if notice else [])
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
    if action is Action.RELOAD:
        reload_process()
