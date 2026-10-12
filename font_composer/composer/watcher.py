"""Watch the fonts directory for changes by polling with ``os.scandir``.

No third-party dependency: a snapshot of ``(path, size, mtime_ns)`` for every file in
the tree is taken about once a second; when it differs from the previous one, a
debounce timer waits for the tree to go quiet and then fires the change callback once.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

Snapshot = dict[str, tuple[int, int]]


def take_snapshot(root: Path) -> Snapshot:
    """Return ``{path: (size, mtime_ns)}`` for every file under ``root``."""
    snapshot: Snapshot = {}
    if not root.is_dir():
        return snapshot
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            path = Path(dirpath) / name
            try:
                stat = path.stat()
            except OSError:
                continue
            snapshot[str(path)] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


class DirectoryWatcher:
    """Poll a directory tree and call back (once, debounced) when it changes.

    The callback runs on the polling thread and must not raise; an exception would
    kill the thread and end the watch. Callers should guard their own callbacks.
    """

    def __init__(
        self,
        root: Path,
        on_change: Callable[[], None],
        interval: float = 1.0,
        debounce: float = 0.5,
    ) -> None:
        """Store the watch parameters; call :meth:`start` to begin watching."""
        self.root = root
        self.on_change = on_change
        self.interval = interval
        self.debounce = debounce
        self._snapshot = take_snapshot(root)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def poll_once(self) -> bool:
        """Compare the current tree with the stored snapshot; True when it changed."""
        current = take_snapshot(self.root)
        if current == self._snapshot:
            return False
        self._snapshot = current
        return True

    def start(self) -> None:
        """Start the background polling thread (a no-op when already running)."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="fonts-dir-watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the polling thread and wait for it to finish."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval * 2 + 1)
            self._thread = None

    def _run(self) -> None:
        """Poll until stopped; debounce bursts into one callback."""
        while not self._stop.wait(self.interval):
            if not self.poll_once():
                continue
            # Something changed; wait until the tree has been quiet for `debounce`.
            while not self._stop.wait(self.debounce):
                if not self.poll_once():
                    break
            self.on_change()
