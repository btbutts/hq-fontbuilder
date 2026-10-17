"""A real command on a pseudo-terminal of fixed size, for the tests of what a user sees."""

from __future__ import annotations

import contextlib
import os
import re
import select
import signal
import socket
import sys
import time
from pathlib import Path

import pytest

pty = pytest.importorskip("pty")
fcntl = pytest.importorskip("fcntl")
termios = pytest.importorskip("termios")

ROWS = 20
COLUMNS = 110
LOG_LINES = 12  # round(0.6 * 20)
PROJECT = Path(__file__).resolve().parent.parent
TIMEOUT = 20.0

_ESCAPE = re.compile(r"\x1b\[(\d*)([A-Za-z])")


def screen_of(output: str) -> list[str]:
    """Replay the escape sequences the console uses and return the final screen lines."""
    lines = [""]
    row = 0
    index = 0
    while index < len(output):
        char = output[index]
        match = _ESCAPE.match(output, index) if char == "\x1b" else None
        if match:
            count = int(match.group(1) or 1)
            if match.group(2) == "A":
                row = max(0, row - count)
            elif match.group(2) == "K":
                lines[row] = ""
            elif match.group(2) == "J":
                del lines[row + 1:]
            index = match.end()
            continue
        if char == "\n":
            row += 1
            while len(lines) <= row:
                lines.append("")
        elif char != "\r":
            lines[row] += char
        index += 1
    return lines


class Session:
    """A ``font_composer`` child process, started with ``args``, on a pseudo-terminal."""

    def __init__(self, args: list[str], port: int = 0) -> None:
        """Start ``python -m font_composer`` with the arguments and keep the master side."""
        self.port = port
        self.output = ""
        size = bytes(bytearray(
            ROWS.to_bytes(2, sys.byteorder) + COLUMNS.to_bytes(2, sys.byteorder) + bytes(4)))
        pid, fd = pty.fork()
        if pid == 0:
            # Set the size from the child's side, before it starts: set from the parent
            # it can arrive after the console has already asked for it.
            fcntl.ioctl(0, termios.TIOCSWINSZ, size)
            os.chdir(PROJECT)
            os.execv(sys.executable, [sys.executable, "-m", "font_composer", *args])
        self.pid, self.fd = pid, fd

    def __enter__(self) -> Session:
        """Use the session in a ``with`` block: the child never outlives it."""
        return self

    def __exit__(self, *_exc: object) -> None:
        """Kill the child if it is still there."""
        with contextlib.suppress(OSError):
            os.kill(self.pid, signal.SIGKILL)
            os.waitpid(self.pid, 0)

    def _pump(self) -> None:
        """Move whatever the console has written into :attr:`output`."""
        ready, _w, _x = select.select([self.fd], [], [], 0.05)
        if ready:
            try:
                self.output += os.read(self.fd, 65536).decode("utf-8", errors="replace")
            except OSError:
                time.sleep(0.05)

    def read_until(self, text: str, since: int = 0) -> None:
        """Read terminal output until ``text`` appears after offset ``since``."""
        deadline = time.monotonic() + TIMEOUT
        while text not in self.output[since:]:
            if time.monotonic() > deadline:
                message = f"timed out waiting for {text!r}; got {self.output[-600:]!r}"
                raise AssertionError(message)
            self._pump()

    def get(self, path: str) -> None:
        """Send one HTTP request to the console and read the whole answer."""
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as sock:
            sock.sendall(f"GET {path} HTTP/1.0\r\nHost: test\r\n\r\n".encode())
            while sock.recv(65536):
                pass

    def press(self, key: str) -> None:
        """Type one key."""
        os.write(self.fd, key.encode())

    def wait_exit(self) -> int:
        """Wait for the child to end and return its exit status."""
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            done, status = os.waitpid(self.pid, os.WNOHANG)
            if done:
                return os.waitstatus_to_exitcode(status)
            self._pump()  # a console with unread output may not be able to finish
        os.kill(self.pid, signal.SIGKILL)
        message = "the console did not exit"
        raise AssertionError(message)


def free_port() -> int:
    """Return a port that is free right now."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
