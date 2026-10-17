"""Present a served command on the terminal: the live view, the keys, and starting over.

``compose`` and ``build --show-proof`` both stay on screen the same way: a few header lines
that are always visible, under them a window of 60% of the terminal's height that shows the
requests like ``tail -f``, and on the last line ``Press 'Q' to quit or 'R' to Reload``.
Without a terminal (or with ``monitor``) every request line is streamed instead.
"""

from __future__ import annotations

import contextlib
import os
import sys
import threading
from typing import TYPE_CHECKING

from font_composer.common.cli.console_ui import (
    PROMPT,
    Action,
    KeyReader,
    LiveView,
    StderrCapture,
    action_for_key,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

_KEY_POLL_SECONDS = 0.1  # also how often the view is redrawn at most


def _closing(action: Action) -> str:
    """Return the closing message for the action that ended the run."""
    return "reloading..." if action is Action.RELOAD else "stopped."


def _next_key(keys: KeyReader) -> str | None:
    """Wait one poll interval for a key (there may be no terminal to read from)."""
    if keys.available:
        return keys.read(_KEY_POLL_SECONDS)
    threading.Event().wait(_KEY_POLL_SECONDS)
    return None


def _poll_actions(keys: KeyReader, view: LiveView | None) -> Action:
    """Loop until a key asks for quit or reload; keep the view fitted to the terminal."""
    while True:
        key = _next_key(keys)
        if view is not None:
            view.tick()
        action = action_for_key(key) if key else None
        if action is not None:
            return action


def _wait_for_action(keys: KeyReader, view: LiveView | None) -> Action:
    """Block until a key asks for quit or reload, or Ctrl-C (which quits)."""
    try:
        return _poll_actions(keys, view)
    except KeyboardInterrupt:
        return Action.QUIT


def present(header: Sequence[str], notes: Sequence[str], *, monitor: bool = False) -> Action:
    """Show the console on the terminal until a key (or Ctrl-C) ends it; return the action."""
    live = sys.stdout.isatty() and not monitor
    view = LiveView(list(header), sys.stdout) if live else None
    with KeyReader() as keys:
        if view is not None:
            for note in notes:
                view.add(f"font_composer: {note}")
            view.start()
            with contextlib.redirect_stderr(StderrCapture(view.add)):
                action = _wait_for_action(keys, view)
            view.finish(f"font_composer: {_closing(action)}")
            return action
        # flush: when the output is piped (a task runner, a log file) it would not show.
        print("\n".join(header), flush=True)
        for note in notes:
            print(f"font_composer: {note}", flush=True)
        if keys.available:
            print(PROMPT, flush=True)
        action = _wait_for_action(keys, None)
        print(f"\nfont_composer: {_closing(action)}", flush=True)
        return action


def reload_process() -> None:
    """Replace this process with a new one run with the same command line."""
    os.execv(sys.executable, [sys.executable, "-m", "font_composer", *sys.argv[1:]])
