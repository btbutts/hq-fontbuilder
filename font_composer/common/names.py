"""Official Unicode character names, from the Unicode Character Database.

The names come from ``NamesList.txt`` of the latest UCD release. The file is not part of
the repository: the console and the build fetch it to ``src/char-sets/NamesList.txt``
when it is missing, and read it into a dictionary (about 2 MB of text) the first time a
name is asked for. Having no names is never an error: a glyph is then shown without one.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from font_composer.common.paths import PROJECT_ROOT
from font_composer.common.ucd import UCD_URL, download, ensure_file

if TYPE_CHECKING:
    from collections.abc import Callable

UNICODE_CHAR_NAMES_URL = f"{UCD_URL}/NamesList.txt"
UNICODE_CHAR_NAMES_PATH = PROJECT_ROOT / "src" / "char-sets" / "NamesList.txt"

_CHARACTER_LINE = re.compile(r"^([0-9A-F]{4,6})\t(\S.*)$")


def parse_names_list(text: str) -> dict[int, str]:
    """Read the ``code point <TAB> NAME`` lines of a NamesList.txt into a dictionary.

    Block headings (``@``), comments (``;``) and the indented alias, note and
    cross-reference lines that follow a character are skipped.
    """
    names: dict[int, str] = {}
    for line in text.splitlines():
        match = _CHARACTER_LINE.match(line)
        if match:
            names[int(match.group(1), 16)] = match.group(2).strip()
    return names


def ensure_names_list(
    path: Path = UNICODE_CHAR_NAMES_PATH,
    url: str = UNICODE_CHAR_NAMES_URL,
    *,
    fetch: Callable[[str], bytes] = download,
    say: Callable[[str], None] = print,
) -> bool:
    """Make sure the names list is at ``path``, downloading it when missing.

    Return True when the file is there afterwards. A failed download is reported through
    ``say`` and is not an error: the tool runs without names.
    """
    return ensure_file(path, url, "glyph names", fetch=fetch, say=say)


class UnicodeNames:
    """Lazily loaded code point -> official name dictionary."""

    def __init__(self, path: Path = UNICODE_CHAR_NAMES_PATH) -> None:
        """Remember where the names list is; nothing is read until a name is asked for."""
        self._path = path
        self._names: dict[int, str] | None = None

    @property
    def names(self) -> dict[int, str]:
        """The dictionary (empty when there is no readable list)."""
        if self._names is None:
            try:
                text = self._path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            self._names = parse_names_list(text)
        return self._names

    def get(self, codepoint: int) -> str | None:
        """Return the official name of a code point, or None."""
        return self.names.get(codepoint)

    def for_codepoints(self, codepoints: tuple[int, ...]) -> dict[int, str]:
        """Return the names of those code points that have one."""
        names = self.names
        return {cp: names[cp] for cp in codepoints if cp in names}
