"""Default locations, relative to the project root rather than the working directory.

The project root is the directory that holds the ``font_composer`` package. In a release
tarball it also holds an (empty) ``fonts/`` directory for the user's fonts, and it is
where the console keeps ``composer.toml``; both are untracked user data.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_FONTS_DIR = PROJECT_ROOT / "fonts"
DEFAULT_CONFIG = PROJECT_ROOT / "composer.toml"
