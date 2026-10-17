"""Tests for common.unicode.ucd: downloading the Unicode files from more than one place."""

from __future__ import annotations

from typing import TYPE_CHECKING

from font_composer.common.unicode.blocks import UNICODE_CHAR_RANGES_URLS
from font_composer.common.unicode.names import UNICODE_CHAR_NAMES_URLS
from font_composer.common.unicode.ucd import UCD_PREFIXES, ensure_file

if TYPE_CHECKING:
    from pathlib import Path

FIRST, SECOND = "https://one.invalid/File.txt", "https://two.invalid/File.txt"
BODY = b"0000..007F; Basic Latin\n"


def test_both_unicode_locations_serve_each_file_in_a_fixed_order() -> None:
    """Try the "latest" location first, then UNIDATA, for the names and the blocks alike."""
    assert UCD_PREFIXES == ("https://www.unicode.org/Public/UCD/latest/ucd",
                            "https://www.unicode.org/Public/UNIDATA")
    names = tuple(f"{prefix}/NamesList.txt" for prefix in UCD_PREFIXES)
    blocks = tuple(f"{prefix}/Blocks.txt" for prefix in UCD_PREFIXES)
    assert names == UNICODE_CHAR_NAMES_URLS
    assert blocks == UNICODE_CHAR_RANGES_URLS


def test_the_next_location_is_tried_when_one_fails(tmp_path: Path) -> None:
    """Fall back to the second URL, say so, and still store the file."""
    calls: list[str] = []
    messages: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        if url == FIRST:
            message = "404"
            raise OSError(message)
        return BODY

    target = tmp_path / "File.txt"
    assert ensure_file(target, (FIRST, SECOND), "things", fetch=fetch, say=messages.append)
    assert calls == [FIRST, SECOND]
    assert target.read_bytes() == BODY
    assert any(FIRST in message and "trying" in message for message in messages)
    assert not any("unavailable" in message for message in messages)


def test_the_second_location_is_left_alone_when_the_first_works(tmp_path: Path) -> None:
    """Download once, from the first URL only."""
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return BODY

    assert ensure_file(tmp_path / "File.txt", (FIRST, SECOND), "things", fetch=fetch,
                       say=lambda _message: None)
    assert calls == [FIRST]


def test_an_empty_answer_counts_as_a_failure(tmp_path: Path) -> None:
    """Do not keep an empty file as if it were the list; try the next location."""
    answers = {FIRST: b"", SECOND: BODY}
    target = tmp_path / "File.txt"
    assert ensure_file(target, (FIRST, SECOND), "things", fetch=answers.__getitem__,
                       say=lambda _message: None)
    assert target.read_bytes() == BODY


def test_when_every_location_fails_the_file_is_unavailable_not_an_error(tmp_path: Path) -> None:
    """Report each failure and that the things are unavailable; store nothing."""
    messages: list[str] = []

    def broken(_url: str) -> bytes:
        message = "offline"
        raise OSError(message)

    target = tmp_path / "File.txt"
    assert not ensure_file(target, (FIRST, SECOND), "things", fetch=broken, say=messages.append)
    assert not target.exists()
    assert not list(tmp_path.glob("*.part"))
    assert FIRST in " ".join(messages)
    assert SECOND in " ".join(messages)
    assert "things are unavailable" in messages[-1]
