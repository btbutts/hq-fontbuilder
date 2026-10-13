"""Where the console listens: addresses for a host name and the choice of a free port.

``localhost`` means both loopback addresses, ``127.0.0.1`` and ``::1``; any other host
name or address is resolved as it is. The port is chosen in this order:

1. the port given with ``--port`` (an error when it is in use: the user asked for it);
2. the port saved in the configuration by an earlier run (a new one is chosen, with a
   notice, when it is in use);
3. the first free port of ``8700-9000`` and then of ``18700-19000``, in steps of five
   (so the last digit is 0 or 5).

"In use" is judged by connecting to the address, not by binding to it. On macOS a
socket bound to one address can share a port with a listener on the wildcard address
when ``SO_REUSEADDR`` is set, and the console sets it so that a restart does not have
to wait for ``TIME_WAIT``; a connection attempt finds such a listener, a bind does not.
"""

from __future__ import annotations

import errno
import socket
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

LOCALHOST = "localhost"
LOOPBACK_ADDRESSES = ("127.0.0.1", "::1")

PORT_RANGES = ((8700, 9000), (18700, 19000))
PORT_STEP = 5

_PROBE_TIMEOUT = 0.25


class PortUnavailableError(Exception):
    """Raised when the requested port, or every automatic candidate, is in use."""


def candidate_ports() -> Iterator[int]:
    """Yield the automatic candidates: 8700, 8705, ... 9000, then 18700 ... 19000."""
    for low, high in PORT_RANGES:
        yield from range(low, high + 1, PORT_STEP)


def local_addresses(host: str) -> list[str]:
    """Return the IP addresses to listen on for a host name or address.

    ``localhost`` is both loopback addresses whatever the resolver says; anything
    else is resolved with the system resolver (a name may give several addresses).
    """
    if host.lower() == LOCALHOST:
        return list(LOOPBACK_ADDRESSES)
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM,
                                   flags=socket.AI_PASSIVE)
    except socket.gaierror as exc:
        message = f"cannot resolve host {host!r}: {exc}"
        raise PortUnavailableError(message) from exc
    addresses: list[str] = []
    for info in infos:
        address = str(info[4][0])
        if address not in addresses:
            addresses.append(address)
    return addresses


def _family(address: str) -> int:
    """Return the socket family of an IP address literal."""
    return socket.AF_INET6 if ":" in address else socket.AF_INET


def port_in_use(addresses: list[str], port: int) -> bool:
    """Return True when something already accepts connections on the port.

    An address this machine cannot use at all (no IPv6, say) counts as free: nothing
    can be listening there.
    """
    for address in addresses:
        try:
            with socket.socket(_family(address), socket.SOCK_STREAM) as probe:
                probe.settimeout(_PROBE_TIMEOUT)
                probe.connect((address, port))
        except ConnectionRefusedError:
            continue
        except TimeoutError:
            return True  # something is there but not answering: not ours to take
        except OSError as exc:
            if exc.errno in {errno.EADDRNOTAVAIL, errno.EAFNOSUPPORT, errno.ENETUNREACH,
                             errno.EHOSTUNREACH, errno.EPROTONOSUPPORT}:
                continue
            raise
        return True
    return False


def pick_port(
    addresses: list[str],
    host_label: str,
    requested: int | None,
    saved: int | None,
) -> tuple[int, str | None]:
    """Choose the port to listen on; return ``(port, notice or None)``.

    Raises :class:`PortUnavailableError`, with a message fit to show the user, when the
    requested port is in use or no candidate is free.
    """
    if requested is not None:
        if port_in_use(addresses, requested):
            message = (
                f"port {requested} is already in use on {host_label}. Choose another with "
                "--port, or drop --port to have a free port chosen automatically."
            )
            raise PortUnavailableError(message)
        return requested, None
    notice = None
    if saved is not None:
        if not port_in_use(addresses, saved):
            return saved, None
        notice = f"the port used last time ({saved}) is in use; chose another"
    for port in candidate_ports():
        if not port_in_use(addresses, port):
            return port, notice
    ranges = " and ".join(f"{low}-{high}" for low, high in PORT_RANGES)
    message = (
        f"no free port in {ranges} on {host_label}. Choose one with --port."
    )
    raise PortUnavailableError(message)
