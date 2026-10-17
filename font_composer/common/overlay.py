"""The category overlay: three display categories that divide a block.

The overlay is a way to look at and edit glyph choices in the console; the configuration
file and the build only know the official blocks. These are the only categories kept by
hand.
"""

from __future__ import annotations

from dataclasses import dataclass

OVERLAY_PREFIX = "overlay:"


@dataclass(frozen=True)
class OverlayCategory:
    """A named subset of one block's code points."""

    id: str
    label: str
    #: the id (official name) of the block it divides
    block: str
    ranges: tuple[tuple[int, int], ...]
    #: named rows of the group page, as (label, low, high); empty for rows of 16
    rows: tuple[tuple[str, int, int], ...] = ()


OVERLAY_CATEGORIES: tuple[OverlayCategory, ...] = (
    OverlayCategory(
        "overlay:ascii-alnum", "ASCII Letters and Digits", "Basic Latin",
        ((0x30, 0x39), (0x41, 0x5A), (0x61, 0x7A)),
        rows=(("0-9", 0x30, 0x39), ("A-Z", 0x41, 0x5A), ("a-z", 0x61, 0x7A))),
    OverlayCategory(
        "overlay:ascii-symbols", "Other Printable ASCII", "Basic Latin",
        ((0x20, 0x2F), (0x3A, 0x40), (0x5B, 0x60), (0x7B, 0x7E))),
    OverlayCategory("overlay:powerline", "Powerline", "Private Use Area", ((0xE0A0, 0xE0D4),)),
)


def is_overlay_id(group_id: str) -> bool:
    """Tell whether a category id names an overlay category (a block is named by its name)."""
    return group_id.startswith(OVERLAY_PREFIX)
