"""Tests for font_composer.common.cli.console_ui: sizing, tail window, redraws, keys."""

from __future__ import annotations

import io
import os
import sys
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from font_composer.common.cli.console_ui import (
    PROMPT,
    Action,
    LiveView,
    StderrCapture,
    action_for_key,
    fit,
    log_capacity,
    terminal_size,
)

COLUMNS = 100
SMALL_ROWS = 10
TINY_ROWS = 3
CAPACITY_20_ROWS = 12
LONG_LIMIT = 70
NAME_FILLS_ROW = 40
NAME_TOO_WIDE = 20
HEADER = ["reachable at: http://localhost:8700/", "\tlistening: 127.0.0.1", "\tfonts: /f",
          "\tconfig: /c"]


@dataclass
class _Terminal:
    """A terminal whose size the test can change."""

    columns: int
    rows: int

    def size(self) -> os.terminal_size:
        """Return the current size, as ``shutil.get_terminal_size`` does."""
        return os.terminal_size((self.columns, self.rows))


@pytest.mark.parametrize(("rows", "expected"), [(30, 18), (50, 30), (24, 14), (20, 12)])
def test_the_log_takes_sixty_percent_of_the_terminal_height(rows: int, expected: int) -> None:
    """Show round(0.6 x rows) request lines, e.g. 18 of 30."""
    assert log_capacity(rows, len(HEADER) + 1) == expected


def test_a_small_terminal_still_fits_the_whole_block() -> None:
    """Never draw more lines than the terminal has, but keep at least one log line."""
    fixed = len(HEADER) + 1
    assert log_capacity(SMALL_ROWS, fixed) + fixed + 1 <= SMALL_ROWS
    assert log_capacity(TINY_ROWS, fixed) == 1


def test_fit_keeps_short_lines_and_cuts_the_middle_of_long_ones() -> None:
    """Keep the end of a request line, which holds the status code."""
    assert fit("short", 80) == "short"
    line = '::1 - - [12/Oct/2026 22:00:13] "GET /api/glyphs?family=' + "x" * 80 + ' HTTP/1.1" 200 -'
    cut = fit(line, LONG_LIMIT)
    assert len(cut) == LONG_LIMIT - 1
    assert cut.startswith("::1 - - [12/Oct")
    assert cut.endswith('HTTP/1.1" 200 -')
    assert "…" in cut


FONT_LINE = ('::1 - - [12/Oct/2026 22:00:13] "GET /fonts/FiraMonoNerdFontMono/'
             'FiraMonoNerdFontMono-Medium.otf HTTP/1.1" 200 -')


@pytest.mark.parametrize("columns", [120, 100, 80, 70, 60, 50])
def test_a_font_file_name_is_never_cut(columns: int) -> None:
    """Shorten the path in front of the name, never the name or the status after it."""
    cut = fit(FONT_LINE, columns)
    assert len(cut) <= columns - 1
    assert "FiraMonoNerdFontMono-Medium.otf" in cut
    assert cut.endswith('/FiraMonoNerdFontMono-Medium.otf HTTP/1.1" 200 -')
    if len(FONT_LINE) > columns - 1:
        assert "…/FiraMonoNerdFontMono-Medium.otf" in cut


def test_a_config_file_name_is_never_cut() -> None:
    """Protect font_composer.toml in the header the same way, even with spaces in the path."""
    line = "\tconfig: /Users/someone/Documents/GitHub Projects/OpenWRT/font_composer.toml"
    cut = fit(line, 60)
    assert len(cut) <= LONG_LIMIT - 1
    assert cut.endswith("/font_composer.toml")
    assert "…" in cut


def test_a_name_that_fills_the_terminal_loses_its_status_not_its_name() -> None:
    """With no room for the status code, keep the whole name rather than the code."""
    cut = fit(FONT_LINE, NAME_FILLS_ROW)
    assert len(cut) <= NAME_FILLS_ROW - 1
    assert "FiraMonoNerdFontMono-Medium.otf" in cut


def test_a_name_wider_than_the_terminal_keeps_its_end() -> None:
    """Only when the name alone cannot fit is its beginning given up (keeping .otf)."""
    cut = fit(FONT_LINE, NAME_TOO_WIDE)
    assert len(cut) <= NAME_TOO_WIDE - 1
    assert cut.startswith("…")
    assert cut.endswith("Medium.otf")


def test_frame_is_header_then_the_last_lines_then_the_prompt() -> None:
    """Tail the log: only the newest lines that fit, between header and prompt."""
    terminal = _Terminal(100, 20)
    view = LiveView(HEADER, io.StringIO(), terminal.size)
    for index in range(40):
        view.add(f"request {index}")
    frame = view.frame()
    capacity = log_capacity(20, len(HEADER) + 1)
    assert capacity == CAPACITY_20_ROWS
    assert frame[: len(HEADER)] == HEADER
    assert frame[-1] == PROMPT
    log = frame[len(HEADER):-1]
    assert log == [f"request {index}" for index in range(28, 40)]


def test_the_block_has_a_constant_height_before_the_log_fills() -> None:
    """Pad with blank lines so the block never grows (and scrolls) as lines arrive."""
    view = LiveView(HEADER, io.StringIO(), _Terminal(100, 30).size)
    empty = view.frame()
    view.add("one")
    assert len(view.frame()) == len(empty) == len(HEADER) + 18 + 1
    assert view.frame()[len(HEADER)] == "one"


def test_adding_lines_draws_nothing_until_the_next_tick() -> None:
    """Coalesce a burst of requests into one redraw, made from the main loop."""
    out = io.StringIO()
    view = LiveView(HEADER, out, _Terminal(100, 24).size)
    view.start()
    drawn = out.getvalue()
    for index in range(5):
        view.add(f"request {index}")
    assert out.getvalue() == drawn
    view.tick()
    assert out.getvalue() != drawn
    after = out.getvalue()
    view.tick()  # nothing new, same size: no output
    assert out.getvalue() == after


def test_redraw_moves_up_over_the_block_and_a_resize_clears_below() -> None:
    """Rewrite in place with a relative move; clear the rest when the height changes."""
    out = io.StringIO()
    terminal = _Terminal(100, 24)
    view = LiveView(HEADER, out, terminal.size)
    view.start()
    height = len(view.frame())
    first = out.getvalue()
    assert "\x1b[" + str(height - 1) + "A" not in first  # first draw does not move up
    view.add("x")
    view.tick()
    second = out.getvalue()[len(first):]
    assert second.startswith(f"\r\x1b[{height - 1}A")
    assert "\x1b[J" not in second
    terminal.rows = 40
    view.tick()
    third = out.getvalue()[len(first) + len(second):]
    assert third.startswith(f"\r\x1b[{height - 1}A\x1b[J")


def test_finish_replaces_the_prompt_and_ends_the_line() -> None:
    """Show a closing message where the prompt was and leave the cursor below."""
    out = io.StringIO()
    view = LiveView(HEADER, out, _Terminal(100, 24).size)
    view.start()
    view.finish("font_composer: stopped.")
    assert out.getvalue().endswith("font_composer: stopped.\n")


def test_stderr_capture_passes_whole_lines_and_drops_the_version_poll() -> None:
    """Hand over complete lines only, and leave out the SPA's poll."""
    seen: list[str] = []
    capture = StderrCapture(seen.append)
    capture.write('::1 - - [d] "GET /api/state HTTP/1.1" 200 -\n::1 - - [d] "GET /api/ver')
    assert seen == ['::1 - - [d] "GET /api/state HTTP/1.1" 200 -']
    capture.write('sion HTTP/1.1" 200 -\n')
    assert len(seen) == 1
    capture.write('::1 - - [d] "GET /api/version HTTP/1.1" 200 -\n\n')
    assert len(seen) == 1
    capture.write('::1 - - [d] "GET /api/glyphs?x=1 HTTP/1.1" 200 -\n')
    assert seen[-1].endswith('HTTP/1.1" 200 -')
    assert ["/api/state" in seen[0], "/api/glyphs?x=1" in seen[1]] == [True, True]


def test_terminal_size_ignores_stale_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ask the terminal, not COLUMNS/LINES: those may be left over from another size."""
    monkeypatch.setenv("COLUMNS", "13")
    monkeypatch.setenv("LINES", "7")
    monkeypatch.setattr(os, "get_terminal_size", lambda _fd: os.terminal_size((111, 33)))
    monkeypatch.setattr(sys, "__stdout__", SimpleNamespace(fileno=lambda: 1))
    assert terminal_size() == os.terminal_size((111, 33))


def test_terminal_size_falls_back_when_there_is_no_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the environment (then 80x24) when stdout is not a terminal."""

    def refuse(_fd: int) -> os.terminal_size:
        raise OSError

    monkeypatch.setattr(os, "get_terminal_size", refuse)
    monkeypatch.setenv("COLUMNS", "90")
    monkeypatch.setenv("LINES", "30")
    assert terminal_size() == os.terminal_size((90, 30))


def test_keys() -> None:
    """Quit on Q, reload on R, either case; ignore anything else."""
    assert action_for_key("q") is Action.QUIT
    assert action_for_key("Q") is Action.QUIT
    assert action_for_key("r") is Action.RELOAD
    assert action_for_key("R") is Action.RELOAD
    assert action_for_key("x") is None
