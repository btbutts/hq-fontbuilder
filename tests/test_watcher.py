"""Tests for font_composer.composer.watcher: snapshots and the debounced callback."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from font_composer.composer.watcher import DirectoryWatcher


def test_poll_once_detects_add_modify_remove(tmp_path: Path) -> None:
    """Report exactly one change per snapshot difference."""
    target = tmp_path / "fonts"
    target.mkdir()
    watcher = DirectoryWatcher(target, lambda: None)
    assert not watcher.poll_once()

    added = target / "New.ttf"
    added.write_bytes(b"one")
    assert watcher.poll_once()
    assert not watcher.poll_once()

    added.write_bytes(b"one two")
    assert watcher.poll_once()

    added.unlink()
    assert watcher.poll_once()
    assert not watcher.poll_once()


def test_poll_once_detects_nested_files(tmp_path: Path) -> None:
    """Watch family sub-folders, not only the top level."""
    family = tmp_path / "fonts" / "Alpha"
    family.mkdir(parents=True)
    watcher = DirectoryWatcher(tmp_path / "fonts", lambda: None)
    (family / "Alpha-Regular.ttf").write_bytes(b"x")
    assert watcher.poll_once()


def test_debounced_callback_fires_once(tmp_path: Path) -> None:
    """Collapse a burst of writes into a single callback."""
    fired = threading.Event()
    calls: list[int] = []

    def on_change() -> None:
        calls.append(1)
        fired.set()

    target = tmp_path / "fonts"
    target.mkdir()
    watcher = DirectoryWatcher(target, on_change, interval=0.05, debounce=0.1)
    watcher.start()
    try:
        for index in range(3):
            (target / f"file{index}.ttf").write_bytes(b"x")
            time.sleep(0.05)
        assert fired.wait(timeout=5)
        time.sleep(0.4)  # no further changes: no further callbacks
        assert len(calls) == 1
    finally:
        watcher.stop()
