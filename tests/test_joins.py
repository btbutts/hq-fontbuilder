"""Tests for font_composer.builder.joins: do the box glyphs of a written font meet each other."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fontTools.ttLib import TTFont
from support import build_font

from font_composer.builder.assemble import Layout
from font_composer.builder.joins import JOIN_WARNING, find_seams
from font_composer.builder.verify import verify_font
from font_composer.common.fitting.fit import Box

if TYPE_CHECKING:
    from pathlib import Path

CELL = Box(0.0, -0.2, 0.6, 0.8)  # a 600 x 1000 cell at 1000 units per em
LIGHT, LEFT_ARM, RIGHT_ARM, UP_ARM, VERTICAL = 0x2500, 0x2574, 0x2576, 0x2575, 0x2502
UPPER, LOWER = 0x2580, 0x2584


def _seams(tmp_path: Path, ink: dict[int, tuple[int, int, int, int]]) -> list:
    path = build_font(tmp_path / "Box.ttf", codepoints=list(ink), ink=ink)
    font = TTFont(path)
    try:
        return find_seams(font, CELL, 1000.0)
    finally:
        font.close()


def test_lines_that_meet_exactly_are_not_reported(tmp_path: Path) -> None:
    """Accept a rule and the arms that continue it, drawn at the same height."""
    seams = _seams(tmp_path, {LIGHT: (0, 300, 600, 340), LEFT_ARM: (0, 300, 300, 340),
                              RIGHT_ARM: (300, 300, 600, 340)})
    assert not seams


def test_an_arm_that_sits_a_little_too_high_is_a_seam_with_its_size(tmp_path: Path) -> None:
    """Report the glyphs and how far their lines miss each other, in em."""
    seams = _seams(tmp_path, {LIGHT: (0, 300, 600, 340), RIGHT_ARM: (300, 306, 600, 346)})
    assert len(seams) == 1
    assert {member.codepoint for member in seams[0].members} == {LIGHT, RIGHT_ARM}
    assert seams[0].spread == pytest.approx(0.006, abs=0.0005)
    assert seams[0].spread > JOIN_WARNING


def test_a_miss_of_a_unit_or_two_is_within_tolerance(tmp_path: Path) -> None:
    """Ignore what no screen can show."""
    assert not _seams(tmp_path, {LIGHT: (0, 300, 600, 340), RIGHT_ARM: (300, 301, 600, 341)})


def test_light_and_heavy_lines_are_different_lines_not_a_miss(tmp_path: Path) -> None:
    """Never compare a heavy rule with a light one."""
    heavy = 0x2501
    assert not _seams(tmp_path, {LIGHT: (0, 300, 600, 340), heavy: (0, 270, 600, 370)})


def test_vertical_arms_are_compared_through_the_top_and_bottom_edges(tmp_path: Path) -> None:
    """Find an arm that is a little left of the rule it continues."""
    seams = _seams(tmp_path, {VERTICAL: (280, -200, 320, 800), UP_ARM: (270, 300, 310, 800)})
    assert len(seams) == 1
    assert seams[0].spread == pytest.approx(0.01, abs=0.0005)
    assert {member.codepoint for member in seams[0].members} == {VERTICAL, UP_ARM}


def test_a_glyph_that_stops_short_of_the_edge_has_nothing_to_join(tmp_path: Path) -> None:
    """Take no port from an arm that ends inside the cell."""
    seams = _seams(tmp_path, {LIGHT: (0, 300, 600, 340), LEFT_ARM: (0, 330, 300, 370)})
    assert not seams  # LEFT_ARM's right end is at x=300, not at the cell edge


def test_the_halves_of_a_block_split_the_cell_at_the_same_line(tmp_path: Path) -> None:
    """Report an upper half and a lower half that leave a gap or overlap in the middle."""
    assert not _seams(tmp_path, {UPPER: (0, 300, 600, 800), LOWER: (0, -200, 600, 300)})
    seams = _seams(tmp_path, {UPPER: (0, 300, 600, 800), LOWER: (0, -200, 600, 310)})
    assert len(seams) == 1
    assert {member.codepoint for member in seams[0].members} == {UPPER, LOWER}
    assert seams[0].spread == pytest.approx(0.01, abs=0.0005)


def _verified(tmp_path: Path, ink: dict[int, tuple[int, int, int, int]], donor: str | None):
    """Verify a tiny font whose box glyphs have this ink; ``donor`` drew them (None: the base)."""
    path = build_font(tmp_path / "Out.ttf", codepoints=list(ink), ink=ink)
    layout = Layout(cmap={cp: f"uni{cp:04X}" for cp in ink},
                    drawn_from=dict.fromkeys(ink, donor) if donor else {})
    return verify_font(path, layout, 600)


def _join_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if "join" in line]


def test_a_visible_gap_in_a_donors_box_glyphs_is_an_error_that_names_the_donor(
    tmp_path: Path,
) -> None:
    """Fail the style, and say which family to look at and by how much its lines miss."""
    found = _verified(tmp_path, {LIGHT: (0, 300, 600, 340), RIGHT_ARM: (300, 315, 600, 355)},
                      "Donor")
    errors = _join_lines(found.errors)
    assert len(errors) == 1
    assert "Donor" in errors[0]
    assert "0.015 em" in errors[0]
    assert "U+2500" in errors[0]
    assert "U+2576" in errors[0]


def test_a_barely_visible_miss_is_only_a_warning(tmp_path: Path) -> None:
    """Warn about a step of a few units, and keep the font."""
    found = _verified(tmp_path, {LIGHT: (0, 300, 600, 340), RIGHT_ARM: (300, 306, 600, 346)},
                      "Donor")
    assert not _join_lines(found.errors)
    assert len(_join_lines(found.warnings)) == 1


def test_a_miss_in_the_base_fonts_own_glyphs_is_only_a_warning(tmp_path: Path) -> None:
    """Do not fail a build for glyphs that were copied as they are."""
    found = _verified(tmp_path, {LIGHT: (0, 300, 600, 340), RIGHT_ARM: (300, 315, 600, 355)}, None)
    assert not _join_lines(found.errors)
    assert len(_join_lines(found.warnings)) == 1


def test_box_glyphs_that_meet_produce_no_join_finding(tmp_path: Path) -> None:
    """Say nothing when everything lines up."""
    found = _verified(tmp_path, {LIGHT: (0, 300, 600, 340), RIGHT_ARM: (300, 300, 600, 340)},
                      "Donor")
    assert not _join_lines([*found.errors, *found.warnings])
