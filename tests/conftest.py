"""Test-suite wide settings."""

from __future__ import annotations

import os

from font_composer.common.unicode.ucd import NO_DOWNLOAD_ENV

# The suite must never reach for the network (the console downloads the Unicode names list
# when it starts, and the pseudo-terminal test starts the console in a child process).
os.environ[NO_DOWNLOAD_ENV] = "1"
