"""Tests for font_composer.composer.web.ports: candidates, in-use detection, choice."""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING

import pytest

from font_composer.composer.web import ports

if TYPE_CHECKING:
    from collections.abc import Iterator

WILDCARD = "0.0.0.0"
FIRST = 8700
SECOND = 8705
THIRD = 8710
RANGE_END = 9000
FALLBACK_START = 18700
FALLBACK_END = 19000
SAVED = 8765
REQUESTED = 8800


@pytest.fixture(name="busy_ports")
def busy_ports_fixture(monkeypatch: pytest.MonkeyPatch) -> set[int]:
    """Replace the in-use probe with a set of ports the test declares busy."""
    busy: set[int] = set()
    monkeypatch.setattr(ports, "port_in_use", lambda _addresses, port: port in busy)
    return busy


@pytest.fixture(name="listener")
def listener_fixture() -> Iterator[socket.socket]:
    """Listen on the IPv4 wildcard address, as another dev server would."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((WILDCARD, 0))
    sock.listen()
    try:
        yield sock
    finally:
        sock.close()


def test_candidates_are_multiples_of_five_in_the_two_ranges() -> None:
    """Try 8700-9000 first, then 18700-19000, always ending in 0 or 5."""
    candidates = list(ports.candidate_ports())
    assert candidates[0] == FIRST
    assert RANGE_END in candidates
    assert candidates.index(RANGE_END) + 1 == candidates.index(FALLBACK_START)
    assert candidates[-1] == FALLBACK_END
    assert all(port % 5 == 0 for port in candidates)
    assert candidates == sorted(candidates)


def test_localhost_is_both_loopback_addresses() -> None:
    """Listen on IPv4 and IPv6 loopback for the default host."""
    assert ports.local_addresses("localhost") == ["127.0.0.1", "::1"]
    assert ports.local_addresses("LocalHost") == ["127.0.0.1", "::1"]
    assert ports.local_addresses("127.0.0.1") == ["127.0.0.1"]


def test_a_wildcard_listener_makes_the_port_busy_on_loopback(listener: socket.socket) -> None:
    """Find a listener bound to the wildcard address, which a bind test would miss."""
    port = listener.getsockname()[1]
    assert ports.port_in_use(["127.0.0.1"], port)
    listener.close()
    assert not ports.port_in_use(["127.0.0.1"], port)


def test_requested_port_in_use_is_an_error(busy_ports: set[int]) -> None:
    """Tell the user to pick another port or drop --port; never pick one for them."""
    busy_ports.add(REQUESTED)
    with pytest.raises(ports.PortUnavailableError, match=r"--port"):
        ports.pick_port(["127.0.0.1"], "localhost", REQUESTED, None)
    free = REQUESTED + 1
    assert ports.pick_port(["127.0.0.1"], "localhost", free, None) == (free, None)


def test_saved_port_is_reused_when_free(busy_ports: set[int]) -> None:
    """Prefer the port of the last run over a fresh search."""
    assert busy_ports == set()
    assert ports.pick_port(["127.0.0.1"], "localhost", None, SAVED) == (SAVED, None)


def test_saved_port_in_use_falls_back_to_a_search_with_a_notice(busy_ports: set[int]) -> None:
    """Choose a new port, and say so, when the saved one is taken."""
    busy_ports.update({SAVED, FIRST})
    port, notice = ports.pick_port(["127.0.0.1"], "localhost", None, SAVED)
    assert port == SECOND
    assert notice is not None
    assert str(SAVED) in notice


def test_search_skips_busy_ports_and_falls_back_to_the_second_range(
    busy_ports: set[int],
) -> None:
    """Take the first free candidate; the 18700 range only when 8700-9000 is full."""
    busy_ports.update({FIRST, SECOND})
    assert ports.pick_port(["127.0.0.1"], "localhost", None, None) == (THIRD, None)
    busy_ports.update(range(FIRST, RANGE_END + 1))
    assert ports.pick_port(["127.0.0.1"], "localhost", None, None) == (FALLBACK_START, None)
    busy_ports.update(range(FALLBACK_START, FALLBACK_END + 1))
    with pytest.raises(ports.PortUnavailableError, match=r"18700-19000"):
        ports.pick_port(["127.0.0.1"], "localhost", None, None)
