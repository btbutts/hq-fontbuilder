"""Build mode: assemble the composed TTFs described by composer.toml.

Not implemented yet. The font-composer (:mod:`font_composer.composer`) produces
the configuration; this module will become the pipeline that reads it, resolves each
group's family to style files with :mod:`font_composer.common.library`, fits the
donor glyphs to the cell and writes one TTF per requested style.
"""

from __future__ import annotations

import sys


def build() -> int:
    """Refuse politely: the build mode is the next implementation pass."""
    print("font_composer: 'build' is not implemented yet; this pass provides "
          "'inspect' and 'compose'. The composed-font pipeline comes next.",
          file=sys.stderr)
    return 1
