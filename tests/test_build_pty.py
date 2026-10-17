"""End to end: ``python -m font_composer build --show-proof`` in a pseudo-terminal.

The proof is presented like the console is: a few header lines that stay on screen, a request
window of 60% of the terminal height that scrolls like ``tail -f``, and the prompt on the
last line; ``R`` starts the command over (it builds again) and ``Q`` quits with status 0.
POSIX only.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from pty_support import LOG_LINES, Session, screen_of
from support import build_font

PROMPT = "Press 'Q' to quit or 'R' to Reload"
ADDRESS = re.compile(r"The proof of the fonts is at: http://127\.0\.0\.1:(\d+)/buildProof")
REQUESTS = 30
HEADER_LINES = 4


def _start(tmp_path: Path) -> Session:
    fonts = tmp_path / "fonts"
    (fonts / "Alpha").mkdir(parents=True)
    build_font(fonts / "Alpha" / "Alpha-Regular.ttf", codepoints=[ord("M"), 0x2190])
    config = tmp_path / "font_composer.toml"
    config.write_text('[cell]\nbase = "Alpha"\n[output]\nfamily = "Test"\n', encoding="utf-8")
    return Session(["build", "--fonts-dir", str(fonts), "--config", str(config),
                    "--output-dir", str(tmp_path / "out"), "--show-proof"])


def _port(session: Session, since: int = 0) -> int:
    session.read_until("proof of the fonts is at", since)
    match = ADDRESS.search(session.output, since)
    assert match, session.output[-400:]
    return int(match.group(1))


def test_the_proof_has_a_header_a_tail_window_reload_and_quit(tmp_path: Path) -> None:
    """Drive the real command through a terminal."""
    with _start(tmp_path) as session:
        session.port = _port(session)
        session.read_until(PROMPT)
        for index in range(REQUESTS):
            session.get(f"/api/proof?n={index}")
        session.read_until(f"n={REQUESTS - 1} HTTP")
        time.sleep(0.4)  # let the last redraw land
        screen = screen_of(session.output)
        screen = screen[next(i for i, line in enumerate(screen)
                             if line.startswith("The proof of the fonts is at")):]
        url = f"http://127.0.0.1:{session.port}/buildProof"
        assert screen[0] == f"The proof of the fonts is at: {url}"
        assert screen[1].lstrip() == "listening on IP Addresses: 127.0.0.1"
        assert screen[2].lstrip().startswith("fonts written to: ")
        assert screen[3].lstrip() == "styles: Regular (1 of 1 written)"
        log = screen[HEADER_LINES:-1]
        assert len(log) == LOG_LINES
        assert f"n={REQUESTS - 1} HTTP" in log[-1]
        assert f"n={REQUESTS - LOG_LINES} HTTP" in log[0]
        assert screen[-1] == PROMPT
        assert len(screen) == HEADER_LINES + LOG_LINES + 1

        mark = len(session.output)
        session.press("r")
        session.read_until("reloading...", since=mark)
        session.port = _port(session, mark)  # built again, and served again
        session.read_until(PROMPT, since=mark + 1)
        session.get("/api/proof")
        session.press("Q")
        assert session.wait_exit() == 0
