"""End to end: run ``python -m font_composer compose`` in a pseudo-terminal.

Checks what a user sees: the four header lines, a request window of 60% of the
terminal height that scrolls like ``tail -f``, the prompt on the last line, ``R``
(reload: the same process starts over) and ``Q`` (quit, status 0). POSIX only.
"""

from __future__ import annotations

import time
from pathlib import Path

from pty_support import LOG_LINES, Session, free_port, screen_of
from support import build_font

HEADER_LINES = 4
REQUESTS = 30


def test_header_tail_window_reload_and_quit(tmp_path: Path) -> None:
    """Drive the real command through a terminal."""
    fonts = tmp_path / "fonts"
    (fonts / "Alpha").mkdir(parents=True)
    build_font(fonts / "Alpha" / "Alpha-Regular.ttf", codepoints=[ord("M"), 0x2190])
    port = free_port()
    args = ["compose", "--fonts-dir", str(fonts),
            "--config", str(tmp_path / "font_composer.toml"), "--port", str(port)]
    with Session(args, port) as session:
        session.read_until("Press 'Q' to quit or 'R' to Reload")
        for index in range(REQUESTS):
            session.get(f"/api/state?n={index}")
            session.get("/api/version")  # the page's poll: never shown
        session.read_until(f"n={REQUESTS - 1} HTTP")
        time.sleep(0.4)  # let the last redraw land
        screen = screen_of(session.output)
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
