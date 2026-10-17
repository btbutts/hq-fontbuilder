"""Tests for font_composer.common.unicode.names: parsing, the one-time download, lazy loading."""

from __future__ import annotations

from pathlib import Path

from font_composer.common.unicode.names import (
    UnicodeNames,
    ensure_names_list,
    parse_names_list,
)

SAMPLE = """\
; NamesList-18.0.0.txt
@@\t0000\tC0 Controls and Basic Latin\t007F
@\t\tLatin
0020\tSPACE
\t* sometimes considered a control
0041\tLATIN CAPITAL LETTER A
\t= first letter of the Latin alphabet
\tx (greek capital letter alpha - 0391)
0000\t<control>
2713\tCHECK MARK
1F600\tGRINNING FACE
@\t\tNot a character
"""


def test_the_names_are_read_and_the_notes_are_skipped() -> None:
    """Take only the code point + name lines."""
    names = parse_names_list(SAMPLE)
    assert names == {
        0x20: "SPACE", 0x41: "LATIN CAPITAL LETTER A", 0x0: "<control>",
        0x2713: "CHECK MARK", 0x1F600: "GRINNING FACE",
    }


def test_a_missing_list_is_downloaded_once(tmp_path: Path) -> None:
    """Fetch to src/char-sets/NamesList.txt only when it is not there."""
    target = tmp_path / "char-sets" / "NamesList.txt"
    calls: list[str] = []
    messages: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return SAMPLE.encode()

    assert ensure_names_list(target, ("https://example.invalid/NamesList.txt",), fetch=fetch,
                             say=messages.append)
    assert target.read_text(encoding="utf-8") == SAMPLE
    assert calls == ["https://example.invalid/NamesList.txt"]
    assert not list(target.parent.glob("*.part"))
    assert ensure_names_list(target, ("https://example.invalid/x",), fetch=fetch,
                             say=messages.append)
    assert len(calls) == 1  # already there: no second download
    assert len(messages) == 1


def test_a_failed_download_is_reported_and_not_fatal(tmp_path: Path) -> None:
    """Say so and carry on without names."""
    messages: list[str] = []

    def broken(_url: str) -> bytes:
        message = "offline"
        raise OSError(message)

    target = tmp_path / "NamesList.txt"
    assert not ensure_names_list(target, ("https://example.invalid/",), fetch=broken,
                                 say=messages.append)
    assert not target.exists()
    assert "glyph names are unavailable" in messages[-1]
    assert UnicodeNames(target).get(0x41) is None  # no list: no names, no error


def test_names_load_lazily_and_answer_for_a_set_of_code_points(tmp_path: Path) -> None:
    """Read the file on first use; return only the code points that have a name."""
    path = tmp_path / "NamesList.txt"
    names = UnicodeNames(path)
    path.write_text(SAMPLE, encoding="utf-8")  # written after construction: still read
    assert names.get(0x2713) == "CHECK MARK"
    assert names.for_codepoints((0x41, 0x2713, 0x9999)) == {
        0x41: "LATIN CAPITAL LETTER A", 0x2713: "CHECK MARK"}
