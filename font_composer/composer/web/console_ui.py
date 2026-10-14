"""The terminal side of ``compose``: a fixed header, a tail-style request log, a key prompt.

On a terminal the console draws one block in place, redrawn with relative cursor
movement (no full-screen mode, so the output stays in the scrollback afterwards)::

    The font_composer console is reachable at: http://localhost:8700/
        listening on IP Addresses: 127.0.0.1, ::1
        fonts: /path/to/fonts
        config: /path/to/font_composer.toml
    <the last request lines, at most 60% of the terminal's height, like tail -f>
    Press 'Q' to quit or 'R' to Reload

Lines the server writes to ``stderr`` (the stdlib's request log, tracebacks) are caught
by :class:`StderrCapture` and shown in the tail window instead of scrolling the header
away. The front end's version poll is left out of the window: every open page asks every
two seconds, and it would push everything else out.

Without a terminal, or with ``--monitor``, none of this is used: the lines are printed
one after the other and the log streams as it comes.
"""

from __future__ import annotations

import enum
import importlib
import io
import os
import re
import select
import shutil
import sys
import threading
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import TextIO

LOG_FRACTION = 0.6
PROMPT = "Press 'Q' to quit or 'R' to Reload"

_HISTORY = 2000
_TAB_WIDTH = 8
_ELLIPSIS = "…"
_KEEP_TAIL = 22  # enough for  HTTP/1.1" 200 -
_FILE_EXTENSION = re.compile(r"\.(?:ttf|otf|ttc|otc|toml)(?![\w])", re.IGNORECASE)
_QUIET_REQUESTS = ('"GET /api/version ',)


class Action(enum.Enum):
    """What a key press asks the console to do."""

    QUIT = "quit"
    RELOAD = "reload"


def terminal_size() -> os.terminal_size:
    """Return the size of the terminal itself.

    ``shutil.get_terminal_size`` believes the ``COLUMNS`` and ``LINES`` environment
    variables first, and some shells and task runners export stale ones (a resized window
    would then be drawn at its old size), so the terminal is asked directly and the
    environment only decides when there is no terminal to ask.
    """
    try:
        size = os.get_terminal_size(sys.__stdout__.fileno()) if sys.__stdout__ else None
    except (OSError, ValueError):
        size = None
    if size is not None and size.columns > 0 and size.lines > 0:
        return size
    return shutil.get_terminal_size()


def action_for_key(key: str) -> Action | None:
    """Map a key to an action (Q quits, R reloads, case-insensitive), else None."""
    return {"q": Action.QUIT, "r": Action.RELOAD}.get(key.lower())


def log_capacity(rows: int, fixed_lines: int) -> int:
    """Return how many log lines fit: 60% of the terminal, but never more than it has.

    ``fixed_lines`` are the header lines plus the prompt; one more line is kept free
    for the shell prompt that follows when the console exits.
    """
    wanted = round(rows * LOG_FRACTION)
    room = rows - fixed_lines - 1
    return max(1, min(wanted, room))


def _file_name_span(text: str) -> tuple[int, int] | None:
    """Return ``(start, end)`` of the last font or config file name in a line, or None.

    The span starts at the ``/`` in front of the name, so a cut never lands in the name.
    """
    ends = [match.end() for match in _FILE_EXTENSION.finditer(text)]
    if not ends:
        return None
    end = ends[-1]
    start = text.rfind("/", 0, end)
    if start == -1:
        start = text.rfind(" ", 0, end) + 1
    return start, end


def _cut_middle(text: str, limit: int) -> str:
    """Drop the middle of a line, keeping its start and the end (status code)."""
    tail = min(_KEEP_TAIL, limit // 2)
    head = max(0, limit - tail - 1)
    return text[:head] + _ELLIPSIS + text[len(text) - tail:]


def fit(line: str, columns: int) -> str:
    """Cut a line to one terminal row (a longer one would wrap and break the redraws).

    A font (or config) file name is never cut: the path in front of it gives way and the
    ellipsis goes there, so ``GET /fonts/Fira…/FiraCode-Bold.ttf HTTP/1.1" 200 -`` keeps
    its name and its status. A line with no file name loses its middle instead, which
    keeps the status code at its end. Only when the name alone is wider than the
    terminal is its beginning given up.
    """
    limit = max(1, columns - 1)
    expanded = line.expandtabs(_TAB_WIDTH)
    if len(expanded) <= limit:
        return line
    span = _file_name_span(expanded)
    if span is None:
        return _cut_middle(expanded, limit)
    start, end = span
    protected = expanded[start:]
    if len(protected) + 1 <= limit:
        return expanded[: limit - len(protected) - 1] + _ELLIPSIS + protected
    name = expanded[start:end]  # includes the leading separator
    if len(name) <= limit:
        # no room for what follows the name: keep the name whole and cut after it
        return (protected[: limit - 1] + _ELLIPSIS) if limit > len(name) else name
    return _ELLIPSIS + name[len(name) - (limit - 1):]


@dataclass
class _Painted:
    """What the last paint left on the terminal."""

    height: int = 0
    size: tuple[int, int] = (0, 0)
    dirty: bool = False


class LiveView:
    """The in-place block: header, log tail, prompt."""

    def __init__(
        self,
        header: Sequence[str],
        out: TextIO,
        size: Callable[[], os.terminal_size] = terminal_size,
    ) -> None:
        """Remember the header lines, the output stream and how to ask the size."""
        self._header = list(header)
        self._out = out
        self._size = size
        self._log: deque[str] = deque(maxlen=_HISTORY)
        self._lock = threading.RLock()
        self._painted = _Painted(size=self._terminal_size())

    def _terminal_size(self) -> tuple[int, int]:
        """Return the terminal's ``(columns, rows)``."""
        columns, rows = self._size()
        return columns, rows

    def frame(self, prompt: str = PROMPT) -> list[str]:
        """Return the lines of the block for the current terminal size."""
        columns, rows = self._size()
        capacity = log_capacity(rows, len(self._header) + 1)
        tail = list(self._log)[-capacity:]
        tail += [""] * (capacity - len(tail))
        lines = [*self._header, *tail, prompt]
        return [fit(line, columns) for line in lines]

    def start(self) -> None:
        """Draw the block for the first time, below the cursor."""
        with self._lock:
            self._paint()

    def add(self, line: str) -> None:
        """Append a log line; :meth:`tick` draws it.

        Request threads only append, so a slow terminal never holds a request up, and a
        burst of requests becomes one redraw.
        """
        with self._lock:
            self._log.append(line)
            self._painted.dirty = True

    def tick(self) -> None:
        """Redraw when there are new lines or the terminal changed size."""
        with self._lock:
            if self._painted.dirty or self._terminal_size() != self._painted.size:
                self._paint()

    def finish(self, message: str) -> None:
        """Replace the prompt with a closing message and leave the cursor below the block."""
        with self._lock:
            self._paint(message)
            self._out.write("\n")
            self._out.flush()
            self._painted.height = 0

    def _paint(self, prompt: str = PROMPT) -> None:
        """Rewrite the block over itself; the cursor rests on its last line."""
        frame = self.frame(prompt)
        previous = self._painted.height
        self._painted.size = self._terminal_size()
        self._painted.dirty = False
        parts: list[str] = []
        if previous:
            parts.append("\r")
            if previous > 1:
                parts.append(f"\x1b[{previous - 1}A")
            if len(frame) != previous:
                parts.append("\x1b[J")  # the block changed height: clear what is below
        last = len(frame) - 1
        for index, text in enumerate(frame):
            parts.append("\x1b[2K" + text)
            if index < last:
                parts.append("\n")
        self._out.write("".join(parts))
        self._out.flush()
        self._painted.height = len(frame)


class StderrCapture(io.TextIOBase):
    """A ``stderr`` stand-in that hands each completed line to a callback."""

    def __init__(self, on_line: Callable[[str], None]) -> None:
        """Hold the callback; text without a line end is kept until it arrives."""
        super().__init__()
        self._on_line = on_line
        self._pending = ""
        self._lock = threading.Lock()

    @override
    def writable(self) -> bool:
        """Say that this stream can be written to."""
        return True

    @override
    def write(self, s: str, /) -> int:
        """Split text into lines; quiet requests are dropped, the rest are passed on."""
        with self._lock:
            self._pending += s
            *complete, self._pending = self._pending.split("\n")
        for line in complete:
            text = line.rstrip()
            if text and not any(marker in text for marker in _QUIET_REQUESTS):
                self._on_line(text)
        return len(s)

    @override
    def flush(self) -> None:
        """Do nothing: lines are passed on as soon as they are complete."""


class KeyReader:
    """Reads single key presses from a terminal; a context manager that restores it.

    Uses cbreak mode, so Ctrl-C still interrupts. Where there is no terminal (or no
    ``termios``) :attr:`available` is False and :meth:`read` never returns a key.
    """

    def __init__(self, stream: Any = None) -> None:
        """Use ``stream`` (default ``sys.stdin``) when it is a terminal."""
        self._stream = stream if stream is not None else sys.stdin
        self._saved: Any = None
        self._termios: Any = None
        self.available = False

    def __enter__(self) -> KeyReader:
        """Switch the terminal to cbreak mode when there is one."""
        if not self._stream.isatty():
            return self
        try:  # POSIX only: loaded by name so that other systems merely lose the keys
            termios = importlib.import_module("termios")
            tty = importlib.import_module("tty")
        except ImportError:
            return self
        fd = self._stream.fileno()
        self._termios = termios
        self._saved = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        self.available = True
        return self

    def __exit__(self, *_exc: object) -> None:
        """Put the terminal back the way it was."""
        if self._saved is not None and self._termios is not None:
            self._termios.tcsetattr(self._stream.fileno(), self._termios.TCSADRAIN, self._saved)
            self._saved = None
            self.available = False

    def read(self, timeout: float) -> str | None:
        """Wait up to ``timeout`` seconds for a key; return it or None."""
        if not self.available:
            return None
        fd = self._stream.fileno()
        ready, _w, _x = select.select([fd], [], [], timeout)
        if not ready:
            return None
        data = os.read(fd, 16)
        return data.decode("utf-8", errors="ignore")[:1] or None
