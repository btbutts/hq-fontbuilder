"""Tests for font_composer.common.unicode.blocks: parsing, the one-time download, lazy loading."""

from __future__ import annotations

from typing import TYPE_CHECKING

from font_composer.common.unicode.blocks import ensure_blocks_list, load_blocks, parse_blocks

if TYPE_CHECKING:
    from pathlib import Path

SAMPLE = """\
# Blocks-17.0.0.txt
# Date: 2025-08-01
#
# Format: Start Code..End Code; Block Name

E000..F8FF; Private Use Area
0000..007F; Basic Latin
0080..00FF; Latin-1 Supplement
F0000..FFFFF; Supplementary Private Use Area-A
"""


def test_the_blocks_are_read_sorted_and_the_comments_skipped() -> None:
    """Take the range and name of each entry, ordered by their first code point."""
    blocks = parse_blocks(SAMPLE)
    assert [(block.low, block.high, block.name) for block in blocks] == [
        (0x0, 0x7F, "Basic Latin"),
        (0x80, 0xFF, "Latin-1 Supplement"),
        (0xE000, 0xF8FF, "Private Use Area"),
        (0xF0000, 0xFFFFF, "Supplementary Private Use Area-A"),
    ]


def test_a_missing_list_is_downloaded_once(tmp_path: Path) -> None:
    """Fetch to src/char-sets/Blocks.txt only when it is not there."""
    target = tmp_path / "char-sets" / "Blocks.txt"
    calls: list[str] = []
    messages: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return SAMPLE.encode()

    assert ensure_blocks_list(target, ("https://example.invalid/Blocks.txt",), fetch=fetch,
                              say=messages.append)
    assert target.read_text(encoding="utf-8") == SAMPLE
    assert not list(target.parent.glob("*.part"))
    assert ensure_blocks_list(target, ("https://example.invalid/x",), fetch=fetch,
                              say=messages.append)
    assert calls == ["https://example.invalid/Blocks.txt"]
    assert len(messages) == 1


def test_a_failed_download_is_reported_and_not_fatal(tmp_path: Path) -> None:
    """Say so and carry on with no blocks."""
    messages: list[str] = []

    def broken(_url: str) -> bytes:
        message = "offline"
        raise OSError(message)

    target = tmp_path / "Blocks.txt"
    assert not ensure_blocks_list(target, ("https://example.invalid/",), fetch=broken,
                                  say=messages.append)
    assert not target.exists()
    assert "block categories are unavailable" in messages[-1]
    assert not load_blocks(target)  # no list: no blocks, no error


def test_blocks_are_loaded_from_a_file(tmp_path: Path) -> None:
    """Read the list that is there; a missing file is an empty list."""
    target = tmp_path / "Blocks.txt"
    assert not load_blocks(target)
    target.write_text(SAMPLE, encoding="utf-8")
    assert [block.name for block in load_blocks(target)][:2] == [
        "Basic Latin", "Latin-1 Supplement"]
