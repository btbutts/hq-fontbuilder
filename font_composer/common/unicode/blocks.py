"""Official Unicode blocks, from ``Blocks.txt`` of the Unicode Character Database.

A block is a named range of code points (``0000..007F; Basic Latin``). The blocks are the
glyph categories of the console and of the build. The file is not part of the repository:
the console and the build fetch it to ``src/char-sets/Blocks.txt`` when it is missing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from font_composer.common.paths import PROJECT_ROOT
from font_composer.common.unicode.ucd import UCD_PREFIXES, download, ensure_file

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

UNICODE_CHAR_RANGES_URLS = tuple(f"{prefix}/Blocks.txt" for prefix in UCD_PREFIXES)
UNICODE_CHAR_RANGES_PATH = PROJECT_ROOT / "src" / "char-sets" / "Blocks.txt"

_BLOCK_LINE = re.compile(r"^([0-9A-Fa-f]{4,6})\.\.([0-9A-Fa-f]{4,6});\s*(\S.*?)\s*$")


@dataclass(frozen=True)
class Block:
    """One entry of ``Blocks.txt``: an inclusive range of code points and its official name."""

    low: int
    high: int
    name: str


def parse_blocks(text: str) -> tuple[Block, ...]:
    """Read the ``low..high; Name`` lines of a Blocks.txt, ordered by their first code point."""
    blocks: list[Block] = []
    for line in text.splitlines():
        match = _BLOCK_LINE.match(line)
        if match:
            blocks.append(Block(int(match.group(1), 16), int(match.group(2), 16), match.group(3)))
    return tuple(sorted(blocks, key=lambda block: block.low))


def ensure_blocks_list(
    path: Path = UNICODE_CHAR_RANGES_PATH,
    urls: Sequence[str] = UNICODE_CHAR_RANGES_URLS,
    *,
    fetch: Callable[[str], bytes] = download,
    say: Callable[[str], None] = print,
) -> bool:
    """Make sure the blocks list is at ``path``, downloading it when missing."""
    return ensure_file(path, urls, "block categories", fetch=fetch, say=say)


def load_blocks(path: Path = UNICODE_CHAR_RANGES_PATH) -> tuple[Block, ...]:
    """Read the blocks list at ``path`` (empty when there is no readable list)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()
    return parse_blocks(text)
