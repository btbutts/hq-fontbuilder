"""Shared plumbing for the Unicode Character Database files the tool downloads.

``NamesList.txt`` and ``Blocks.txt`` are fetched to ``src/char-sets/`` when missing (the
files are not part of the repository). Unicode serves each file from two locations, so a
download that fails is tried again from the other one. Having none of them is never an
error.
"""

from __future__ import annotations

import os
import tempfile
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

#: where unicode.org serves its data files from, in the order they are tried
UCD_PREFIXES = (
    "https://www.unicode.org/Public/UCD/latest/ucd",
    "https://www.unicode.org/Public/UNIDATA",
)
#: set (to anything) to forbid the download, e.g. in the test suite
NO_DOWNLOAD_ENV = "FONT_COMPOSER_NO_DOWNLOAD"
_TIMEOUT_SECONDS = 60


def download(url: str) -> bytes:
    """Fetch a URL (certificates are verified; nothing is bypassed)."""
    if os.environ.get(NO_DOWNLOAD_ENV):
        message = f"downloads are disabled ({NO_DOWNLOAD_ENV} is set)"
        raise OSError(message)
    with urllib.request.urlopen(url, timeout=_TIMEOUT_SECONDS) as response:
        return bytes(response.read())


def store(path: Path, data: bytes) -> None:
    """Write the file atomically: a partial download never looks like a finished one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, suffix=".part") as handle:
        handle.write(data)
    temporary = Path(handle.name)
    temporary.chmod(0o644)  # NamedTemporaryFile makes it private (0600)
    temporary.replace(path)


def _fetch_first(
    urls: Sequence[str], fetch: Callable[[str], bytes], say: Callable[[str], None],
) -> bytes | None:
    """Return the first non-empty answer to one of the URLs, or None when all of them fail."""
    for index, url in enumerate(urls):
        try:
            data = fetch(url)
            problem = "" if data else "empty answer"
        except OSError as exc:
            data, problem = b"", str(exc)
        if not problem:
            return data
        following = f"; trying {urls[index + 1]}" if index + 1 < len(urls) else ""
        say(f"font_composer: could not get {url}: {problem}{following}")
    return None


def ensure_file(
    path: Path, urls: Sequence[str], what: str, *,
    fetch: Callable[[str], bytes] = download, say: Callable[[str], None] = print,
) -> bool:
    """Make sure a file is at ``path``, downloading it when missing.

    The URLs are alternatives for the same file, tried in order until one answers.
    Return True when the file is there afterwards. A failed download is reported through
    ``say`` (``what`` names what is then unavailable) and is not an error.
    """
    if path.is_file():
        return True
    say(f"font_composer: downloading the Unicode {what} to {path} ...")
    data = _fetch_first(urls, fetch, say)
    if data is None:
        say(f"font_composer: warning: the Unicode {what} are unavailable")
        return False
    store(path, data)
    return True
