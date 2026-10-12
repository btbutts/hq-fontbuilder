"""Tests for font_composer.common.groups: ranges, totals, atomic flags, coverage."""

from __future__ import annotations

from font_composer.common.groups import GROUPS, GROUPS_BY_ID, GlyphGroup, coverage

EXPECTED_TOTALS = {
    "alnum": 62,
    "ascii-symbols": 33,
    "latin-1": 96,
    "latin-ext": 128,
    "greek": 144,
    "cyrillic": 256,
    "punctuation": 160,
    "currency": 48,
    "arrows": 112,
    "math": 256,
    "technical": 256,
    "box-drawing": 128,
    "block-elements": 32,
    "geometric": 96,
    "misc-symbols": 256,
    "dingbats": 192,
    "braille": 256,
    "powerline": 53,
    "nerd-icons": 6400 - 53 + 65534,
}


def test_expected_totals() -> None:
    """Match the block sizes the design doc measured against."""
    assert set(GROUPS_BY_ID) == set(EXPECTED_TOTALS)
    for group in GROUPS:
        assert group.total == EXPECTED_TOTALS[group.id], group.id


def test_groups_do_not_overlap() -> None:
    """Keep the coverage matrix unambiguous: no code point in two groups."""
    seen: set[int] = set()
    for group in GROUPS:
        points = set(group.codepoints)
        assert len(points) == group.total, group.id
        overlap = seen & points
        assert not overlap, f"{group.id} overlaps another group"
        seen |= points


def test_atomic_groups() -> None:
    """Only box-drawing and block-elements are atomic."""
    atomic = {group.id for group in GROUPS if group.atomic}
    assert atomic == {"box-drawing", "block-elements"}


def test_coverage_math() -> None:
    """Count only the group's own code points as present."""
    group = GROUPS_BY_ID["box-drawing"]
    assert coverage(set(), group) == (0, 128)
    assert coverage({0x2500, 0x2501}, group) == (2, 128)
    assert coverage(set(group.codepoints), group) == (128, 128)
    # Code points outside the group never count.
    assert coverage({0x2500, 0x41}, group) == (1, 128)


def test_custom_group_ranges() -> None:
    """Build a group from several ranges and count its code points."""
    group = GlyphGroup("toy", "Toy", ((0x41, 0x43), (0x61, 0x61)))
    assert group.codepoints == (0x41, 0x42, 0x43, 0x61)
    assert group.total == len(group.codepoints)
    assert coverage({0x42, 0x61}, group) == (2, group.total)
