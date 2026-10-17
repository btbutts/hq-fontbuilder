"""End to end: run ``python -m font_composer compose`` in a pseudo-terminal.

Checks what a user sees: the four header lines, a request window of 60% of the
terminal height that scrolls like ``tail -f``, the prompt on the last line, ``R``
(reload: the same process starts over) and ``Q`` (quit, status 0). POSIX only.
"""

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
from support import build_font

pty = pytest.importorskip("pty")
fcntl = pytest.importorskip("fcntl")
termios = pytest.importorskip("termios")

ROWS = 20
COLUMNS = 110
LOG_LINES = 12  # round(0.6 * 20)
HEADER_LINES = 4
REQUESTS = 30
PROJECT = Path(__file__).resolve().parent.parent
TIMEOUT = 20.0

_ESCAPE = re.compile(r"\x1b\[(\d*)([A-Za-z])")


def _screen(output: str) -> list[str]:
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


class _Session:
    """The console child process on a pseudo-terminal of fixed size."""

    def __init__(self, fonts: Path, config: Path, port: int) -> None:
        """Start ``compose`` on the terminal and keep its master side."""
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
            os.execv(sys.executable, [sys.executable, "-m", "font_composer", "compose",
                                      "--fonts-dir", str(fonts), "--config", str(config),
                                      "--port", str(port)])
        self.pid, self.fd = pid, fd

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


def _free_port() -> int:
    """Return a port that is free right now."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_header_tail_window_reload_and_quit(tmp_path: Path) -> None:
    """Drive the real command through a terminal."""
    fonts = tmp_path / "fonts"
    (fonts / "Alpha").mkdir(parents=True)
    build_font(fonts / "Alpha" / "Alpha-Regular.ttf", codepoints=[ord("M"), 0x2190])
    session = _Session(fonts, tmp_path / "font_composer.toml", _free_port())
    try:
        session.read_until("Press 'Q' to quit or 'R' to Reload")
        for index in range(REQUESTS):
            session.get(f"/api/state?n={index}")
            session.get("/api/version")  # the page's poll: never shown
        session.read_until(f"n={REQUESTS - 1} HTTP")
        time.sleep(0.4)  # let the last redraw land
        screen = _screen(session.output)
        screen = screen[next(i for i, line in enumerate(screen)
                             if line.startswith("The font_composer console")):]
        url = f"http://localhost:{session.port}/"
        assert screen[0] == f"The font_composer console is reachable at: {url}"
        # a line too long for the terminal has its tab expanded (and its middle cut)
        assert screen[1].lstrip() == "listening on IP Addresses: 127.0.0.1, ::1"
        assert screen[2].lstrip().startswith("fonts: ")
        assert screen[3].lstrip().startswith("config: ")
        log = screen[HEADER_LINES:-1]
        assert len(log) == LOG_LINES
        assert f"n={REQUESTS - 1} HTTP" in log[-1]
        assert f"n={REQUESTS - LOG_LINES} HTTP" in log[0]
        assert not any("/api/version" in line for line in screen)
        assert all('" 200 -' in line for line in log)
        assert screen[-1] == "Press 'Q' to quit or 'R' to Reload"
        assert len(screen) == HEADER_LINES + LOG_LINES + 1

        mark = len(session.output)
        session.press("r")
        session.read_until("reloading...", since=mark)
        session.read_until("Press 'Q' to quit or 'R' to Reload", since=mark + 1)
        session.get("/api/state")  # the restarted console answers
        session.press("Q")
        assert session.wait_exit() == 0
    finally:
        with contextlib.suppress(OSError):
            os.kill(session.pid, signal.SIGKILL)
