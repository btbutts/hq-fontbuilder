"""Tests for font_composer.common.unicode.groups: blocks, totals, the overlay rows, coverage."""

from __future__ import annotations

from support import sample_catalog

from font_composer.common.unicode.blocks import parse_blocks
from font_composer.common.unicode.groups import ATOMIC_BLOCKS, GlyphGroup, build_catalog, coverage

POWERLINE_TOTAL = 53
EXPECTED_TOTALS = {
    "Basic Latin": 95,  # the controls are not counted
    "Latin-1 Supplement": 96,
    "Arrows": 112,
    "Box Drawing": 128,
    "Block Elements": 32,
    "Private Use Area": 6400,  # no names there: the whole range counts
}


def test_block_totals_count_the_assigned_code_points() -> None:
    """Count what the names list names; a block it does not enumerate counts its range."""
    totals = {group.id: group.total for group in sample_catalog().blocks}
    assert totals == EXPECTED_TOTALS


def test_blocks_do_not_overlap() -> None:
    """Keep the coverage matrix unambiguous: no code point in two blocks."""
    seen: set[int] = set()
    for group in sample_catalog().blocks:
        points = set(group.codepoints)
        assert len(points) == group.total, group.id
        assert not seen & points, f"{group.id} overlaps another block"
        seen |= points


def test_only_box_drawing_and_block_elements_are_atomic() -> None:
    """Atomic is a property of the official block, whatever the view."""
    catalog = sample_catalog()
    assert {group.id for group in catalog.blocks if group.atomic} == set(ATOMIC_BLOCKS)
    assert all(not group.atomic for group in catalog.overlay)


def test_the_overlay_divides_basic_latin_and_the_private_use_area() -> None:
    """Replace the divided blocks by their categories, in code point order."""
    catalog = sample_catalog()
    rows = catalog.rows(overlay=True)
    assert [group.id for group in rows] == [
        "overlay:ascii-symbols", "overlay:ascii-alnum", "Latin-1 Supplement", "Arrows",
        "Box Drawing", "Block Elements", "Private Use Area", "overlay:powerline",
    ]
    assert {group.id: group.total for group in rows if group.overlay} == {
        "overlay:ascii-alnum": 62, "overlay:ascii-symbols": 33, "overlay:powerline": 53}
    private = next(group for group in rows if group.id == "Private Use Area")
    assert private.total == EXPECTED_TOTALS["Private Use Area"] - POWERLINE_TOTAL
    assert [group.id for group in catalog.rows(overlay=False)] == [
        group.id for group in catalog.blocks]


def test_an_overlay_category_knows_its_block_and_by_id_finds_both_kinds() -> None:
    """Resolve block names and overlay ids; the id of a block is its name."""
    catalog = sample_catalog()
    alnum = catalog.by_id("overlay:ascii-alnum")
    assert alnum is not None
    assert alnum.block == "Basic Latin"
    assert alnum.overlay
    assert [label for label, _low, _high in alnum.rows] == ["0-9", "A-Z", "a-z"]
    block = catalog.by_id("Arrows")
    assert block is not None
    assert block.block == "Arrows"
    assert not block.overlay
    assert catalog.by_id("nonsense") is None


def test_group_of_finds_the_block_of_an_assigned_code_point() -> None:
    """Answer None for a control, an unassigned code point and a code point in no block."""
    catalog = sample_catalog()
    assert catalog.group_of(0x41) is catalog.by_id("Basic Latin")
    assert catalog.group_of(0x2190) is catalog.by_id("Arrows")
    assert catalog.group_of(0xE0A0) is catalog.by_id("Private Use Area")
    assert catalog.group_of(0x10) is None  # a control: in the range, not assigned
    assert catalog.group_of(0x3000) is None


def test_runs_are_the_stretches_of_assigned_code_points() -> None:
    """Send the group page the code points that exist, not the holes of a block."""
    group = sample_catalog().by_id("Latin-1 Supplement")
    assert group is not None
    assert group.runs == ((0xA0, 0xFF),)
    toy = GlyphGroup("toy", "Toy", ((0x41, 0x4A),), members=frozenset({0x41, 0x42, 0x45}))
    assert toy.runs == ((0x41, 0x42), (0x45, 0x45))


def test_count_in_never_exceeds_the_total() -> None:
    """A font with a glyph for an unassigned code point does not make a block more than full."""
    catalog = sample_catalog()
    basic = catalog.by_id("Basic Latin")
    private = catalog.by_id("Private Use Area")
    assert basic is not None
    assert private is not None
    points = frozenset({0x41, 0x42, 0x05, 0xE0A5, 0xE0A6})  # 0x05 is a control
    ordered = tuple(sorted(points))
    assert (basic.count_in(points, ordered), private.count_in(points, ordered)) == (2, 2)


def test_placeholder_names_do_not_make_a_character() -> None:
    """NamesList names controls, reserved code points and non-characters with <...>."""
    names = {0x41: "LATIN CAPITAL LETTER A", 0x0: "<control>",
             0xFFFFE: "<not a character>", 0xFFFFF: "<not a character>"}
    catalog = build_catalog(parse_blocks(
        "0000..007F; Basic Latin\nF0000..FFFFF; Supplementary Private Use Area-A\n"), names)
    basic = catalog.by_id("Basic Latin")
    private = catalog.by_id("Supplementary Private Use Area-A")
    assert basic is not None
    assert private is not None
    assert (basic.total, private.total) == (1, 65536)
    assert catalog.group_of(0xF0001) is private


def test_without_names_every_block_counts_its_whole_range() -> None:
    """Degrade to the ranges when the names list is not there."""
    catalog = build_catalog(parse_blocks("0000..007F; Basic Latin\n"), {})
    group = catalog.by_id("Basic Latin")
    assert group is not None
    assert (group.total, len(group.codepoints)) == (128, 128)


def test_coverage_math() -> None:
    """Count only the group's own code points as present."""
    group = sample_catalog().by_id("Box Drawing")
    assert group is not None
    assert coverage(set(), group) == (0, 128)
    assert coverage({0x2500, 0x2501}, group) == (2, 128)
    assert coverage(set(group.codepoints), group) == (128, 128)
    assert coverage({0x2500, 0x41}, group) == (1, 128)  # code points outside never count


def test_in_the_overlay_view_a_code_point_is_in_one_row_only() -> None:
    """Show a glyph under its overlay category or its block, never under both."""
    catalog = sample_catalog()
    for overlay in (False, True):
        seen: set[int] = set()
        for row in catalog.rows(overlay=overlay):
            assert not seen & row.codepoint_set, row.id
            seen |= row.codepoint_set
    dollar = 0x24
    assert catalog.row_of(dollar, overlay=True) is catalog.by_id("overlay:ascii-symbols")
    assert catalog.row_of(dollar, overlay=False) is catalog.by_id("Basic Latin")
    assert catalog.row_of(0x2190, overlay=True) is catalog.by_id("Arrows")
    assert catalog.row_of(0x3000, overlay=True) is None


def test_the_overlay_view_addresses_rows_not_whole_blocks() -> None:
    """A divided block is not a row of the overlay view; what it leaves is, without the parts."""
    catalog = sample_catalog()
    assert catalog.row("Basic Latin", overlay=True) is None  # nothing is left of it
    assert catalog.row("Basic Latin", overlay=False) is catalog.by_id("Basic Latin")
    assert catalog.row("overlay:powerline", overlay=False) is None
    private = catalog.row("Private Use Area", overlay=True)
    powerline = catalog.row("overlay:powerline", overlay=True)
    assert private is not None
    assert powerline is not None
    assert not private.codepoint_set & powerline.codepoint_set
    assert powerline.codepoint_set <= set(range(0xE000, 0xF900))
