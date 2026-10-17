"""Tests for font_composer.common.fitting.fit and ink: the clipping classes and their fixes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from support import FontSpec, MetricSpec, build_font

from font_composer.common.fitting.fit import (
    CLASS_FLOORS,
    Box,
    CellSpec,
    class_fit,
    fit_class,
    is_joined,
    plan_fit,
    plan_in_class,
)
from font_composer.common.fonts.ink import read_ink

if TYPE_CHECKING:
    from pathlib import Path

DEJAVU = CellSpec(width=0.602, ascent=0.928, descent=-0.236)
SOURCE_CODE = CellSpec(width=0.600, ascent=0.984, descent=-0.273)
SOURCE_CODE_FRAME = Box(0.0, -0.4, 0.6, 1.0)
INCONSOLATA = CellSpec(width=0.5, ascent=0.859, descent=-0.19)
INCONSOLATA_FRAME = Box(0.0, -0.4, 0.5, 1.0)
TOLERANCE = 0.002
BLANK, ABSENT = 0x20, 0x999


def test_a_glyph_inside_the_cell_fits() -> None:
    """Leave an ordinary letter alone."""
    plan = plan_fit(Box(0.05, 0.0, 0.55, 0.73), SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    assert plan.kind == "fits"
    assert plan.identity


def test_a_hair_past_the_cell_is_a_bleed_and_kept() -> None:
    """Keep the deliberate overlap fonts give box glyphs (DejaVu's own full block)."""
    plan = plan_fit(Box(-0.010, -0.250, 0.612, 0.938), DEJAVU, Box(-0.01, -0.25, 0.612, 0.938),
                    DEJAVU)
    assert plan.kind == "bleed"
    assert plan.identity


def test_a_tall_frame_glyph_is_fitted_exactly_to_the_cell() -> None:
    """Source Code Pro's vertical line (1.4 em on a 1.164 em cell): no overhang, no gap."""
    ink = Box(0.261, -0.4, 0.339, 1.0)
    plan = plan_fit(ink, SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    assert plan.kind == "frame"
    assert plan.sx == pytest.approx(0.602 / 0.6)
    assert plan.sy == pytest.approx(1.164 / 1.4)
    moved = plan.apply(ink)
    assert moved.y0 == pytest.approx(DEJAVU.descent)
    assert moved.y1 == pytest.approx(DEJAVU.ascent)
    assert plan.residual == pytest.approx(0.0, abs=TOLERANCE)


def test_a_short_frame_glyph_is_stretched_to_cover_the_cell() -> None:
    """Inconsolata's powerline arrow is a 0.5 x 1.05 cell on a 0.602 x 1.164 one."""
    ink = Box(0.0, -0.19, 0.5, 0.859)
    plan = plan_fit(ink, INCONSOLATA, INCONSOLATA_FRAME, DEJAVU)
    assert plan.kind == "frame"
    moved = plan.apply(ink)
    assert moved.x0 == pytest.approx(0.0, abs=TOLERANCE)
    assert moved.x1 == pytest.approx(DEJAVU.width, abs=TOLERANCE)
    assert moved.y0 <= DEJAVU.descent + TOLERANCE
    assert moved.y1 >= DEJAVU.ascent - TOLERANCE


def test_a_wide_symbol_is_scaled_to_the_cell_width() -> None:
    """JetBrains Mono's left-right arrow is 0.76 em wide in a 0.6 em cell."""
    ink = Box(-0.08, 0.05, 0.68, 0.61)
    plan = plan_fit(ink, SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    assert plan.kind == "oversize"
    assert plan.sx == plan.sy < 1.0
    moved = plan.apply(ink)
    assert moved.x0 >= -TOLERANCE
    assert moved.x1 <= DEJAVU.width + TOLERANCE
    assert (moved.y0 + moved.y1) / 2 == pytest.approx((0.05 + 0.61) / 2, abs=TOLERANCE)


def test_a_letter_with_a_tall_accent_is_scaled_about_the_baseline() -> None:
    """Keep the letter on the baseline: scale about it, never move the glyph down."""
    ink = Box(0.079, -0.012, 0.521, 0.968)
    plan = plan_fit(ink, SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU, on_baseline=True)
    assert plan.kind == "oversize"
    assert plan.dy == pytest.approx(0.0)
    assert plan.sx == plan.sy
    moved = plan.apply(ink)
    assert moved.y1 <= DEJAVU.ascent + TOLERANCE
    assert (moved.x0 + moved.x1) / 2 == pytest.approx((0.079 + 0.521) / 2)


def test_an_icon_just_below_the_descent_is_moved_up() -> None:
    """Move, do not scale, a glyph that fits in size and only sits 0.03 em too low."""
    ink = Box(0.05, -0.266, 0.55, 0.5)
    plan = plan_fit(ink, CellSpec(0.6, 0.935, -0.265), None, DEJAVU)
    assert plan.kind == "offset"
    assert (plan.sx, plan.sy, plan.dx) == (1.0, 1.0, 0.0)
    assert plan.apply(ink).y0 == pytest.approx(DEJAVU.descent)


def test_a_narrow_donors_connector_is_stretched_even_though_it_does_not_overflow() -> None:
    """A 0.5 em horizontal rule leaves a 0.1 em gap in a 0.602 em cell: widen it."""
    ink = Box(0.0, 0.26, 0.5, 0.34)
    plan = plan_fit(ink, INCONSOLATA, INCONSOLATA_FRAME, DEJAVU)
    assert plan.kind == "frame"
    assert plan.overflow == pytest.approx(0.0)
    assert plan.apply(ink).x1 == pytest.approx(DEJAVU.width)


def test_every_connector_of_a_donor_gets_the_same_vertical_map() -> None:
    """Keep box lines of one font joining each other: one transform for the family."""
    vertical = plan_fit(Box(0.261, -0.4, 0.339, 1.0), SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    horizontal = plan_fit(Box(0.0, 0.26, 0.6, 0.34), SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    half_block = plan_fit(Box(0.0, 0.3, 0.6, 1.0), SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    assert {(p.kind, p.sx, p.sy, p.dy) for p in (vertical, horizontal, half_block)} == {
        ("frame", vertical.sx, vertical.sy, vertical.dy)}


def test_a_letter_is_never_taken_for_a_connector() -> None:
    """A tall accented capital reaching the line top is scaled, not stretched."""
    ink = Box(0.0, 0.0, 0.6, 0.98)  # as wide as the cell and reaching the ascent
    plan = plan_fit(ink, SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU, on_baseline=True)
    assert plan.kind != "frame"


def test_an_icon_filling_the_cell_to_within_a_hair_is_not_touched() -> None:
    """Do not relabel (or move) a Nerd Font icon that is a connector in name only."""
    donor = CellSpec(0.6, 0.928, -0.236)  # same line box as the base, 0.002 em narrower
    ink = Box(0.0, -0.236, 0.6, 0.928)  # fills it
    plan = plan_fit(ink, donor, None, DEJAVU)
    assert plan.kind == "fits"


def test_a_blank_glyph_fits() -> None:
    """Treat a space (no ink) as fitting."""
    assert plan_fit(None, SOURCE_CODE, None, DEJAVU).kind == "fits"


def test_ink_bounds_are_read_in_em_with_the_full_block_as_frame(tmp_path: Path) -> None:
    """Read outline bounds scaled by the units per em, and U+2588 as the frame."""
    path = build_font(
        tmp_path / "f.ttf", codepoints=[0x41, 0x2588, BLANK],
        spec=FontSpec(metrics=MetricSpec(upm=1000)),
        ink={0x41: (50, 0, 550, 700), 0x2588: (0, -400, 600, 1000)})
    ink, frame = read_ink(path, [0x41, BLANK, 0x2588, ABSENT])
    assert ink[0x41] == Box(0.05, 0.0, 0.55, 0.7)
    assert BLANK not in ink  # blank
    assert ABSENT not in ink  # not in the font
    assert frame == Box(0.0, -0.4, 0.6, 1.0)


def test_a_letter_off_centre_in_its_cell_is_moved_sideways_to_fit() -> None:
    """Keep the baseline, but slide a lopsided accented letter back into the cell."""
    ink = Box(0.20, 0.0, 0.70, 0.99)  # leans to the right and is too tall
    plan = plan_fit(ink, SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU, on_baseline=True)
    moved = plan.apply(ink)
    assert plan.dy == pytest.approx(0.0)
    assert moved.x1 <= DEJAVU.width + TOLERANCE
    assert moved.y1 <= DEJAVU.ascent + TOLERANCE


def test_a_rule_that_overlaps_its_neighbours_a_little_is_still_a_connector() -> None:
    """Source Code Pro's horizontal line runs 0.039 em past the cell on both sides."""
    rule = plan_fit(Box(-0.039, 0.26, 0.639, 0.34), SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    corner = plan_fit(Box(0.261, -0.4, 0.339, 0.34), SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    assert rule.kind == corner.kind == "frame"
    assert (rule.sx, rule.sy, rule.dy) == (corner.sx, corner.sy, corner.dy)


def test_a_wide_arrow_is_not_mistaken_for_a_rule() -> None:
    """Overlap of 0.08 em on each side is a symbol that is too wide, not a join."""
    plan = plan_fit(Box(-0.08, 0.05, 0.68, 0.61), SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    assert plan.kind == "oversize"


LETTERS = [Box(0.05, 0.0, 0.55, 0.73), Box(0.06, 0.0, 0.54, 0.70), Box(0.04, 0.0, 0.56, 0.74)]


def test_categories_are_fitted_together_by_class() -> None:
    """Know which blocks share a scale and which are fitted glyph by glyph."""
    assert fit_class("Basic Latin") == fit_class("Latin Extended-A") == "text"
    assert fit_class("Greek and Coptic") == fit_class("Cyrillic") == "text"
    assert fit_class("Box Drawing") == fit_class("Block Elements") == "connectors"
    assert fit_class("General Punctuation") == fit_class("Arrows") == "symbols"
    assert fit_class("Private Use Area") == fit_class("Dingbats") == "symbols"


def test_only_the_pieces_that_join_keep_a_stretching_fit() -> None:
    """Name the glyphs that must still meet their neighbours: powerline, braces, integrals."""
    assert is_joined(0xE0B0) and is_joined(0xE0A0) and is_joined(0xE0D4)
    assert is_joined(0x239B) and is_joined(0x23B3) and is_joined(0x2320) and is_joined(0x2321)
    assert not is_joined(0x2190) and not is_joined(0xE0D5) and not is_joined(0x41)


def test_a_category_with_no_offender_is_not_shrunk() -> None:
    """Change nothing when every glyph already fits."""
    shared = class_fit("text", LETTERS, SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    assert shared.scale == pytest.approx(1.0)


def test_one_offender_shrinks_the_whole_category_by_the_same_amount() -> None:
    """Keep look-alikes alike: the accented glyph and the plain one scale together."""
    accented = Box(0.079, -0.012, 0.521, 0.962)  # 0.034 em above DejaVu's ascent
    shared = class_fit("text", [*LETTERS, accented], SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    assert shared.needed == pytest.approx(0.928 / 0.962)
    assert shared.scale == pytest.approx(0.928 / 0.962)  # no floor involved: just enough
    plans = [plan_in_class(ink, shared, DEJAVU) for ink in [*LETTERS, accented]]
    assert {(p.sx, p.sy) for p in plans} == {(shared.scale, shared.scale)}
    for ink, plan in zip([*LETTERS, accented], plans, strict=True):
        assert plan.apply(ink).y0 == pytest.approx(ink.y0 * shared.scale)  # baseline kept
        assert plan.residual == pytest.approx(0.0, abs=TOLERANCE)


def test_an_outlier_cannot_shrink_a_whole_alphabet_beyond_the_floor() -> None:
    """A Greek capital far taller than any letter is fitted alone, not the alphabet."""
    tall = Box(0.1, 0.0, 0.5, 1.30)
    shared = class_fit("text", [*LETTERS, tall], SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    assert shared.needed < CLASS_FLOORS["text"]
    assert shared.scale == CLASS_FLOORS["text"]
    letter = plan_in_class(LETTERS[0], shared, DEJAVU)
    outlier = plan_in_class(tall, shared, DEJAVU)
    assert letter.sx == shared.scale  # an ordinary letter loses only the floor
    assert outlier.sx < shared.scale  # the outlier gets the extra it needs, alone
    assert outlier.apply(tall).y1 <= DEJAVU.ascent + TOLERANCE


def test_a_lopsided_letter_is_slid_back_inside_after_the_shared_scale() -> None:
    """Keep the shared scale, and give the glyph the sideways shift it still needs."""
    lopsided = Box(0.20, 0.0, 0.62, 0.70)
    shared = class_fit("text", [lopsided], SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    plan = plan_in_class(lopsided, shared, DEJAVU)
    assert plan.sx == pytest.approx(shared.scale)
    assert plan.apply(lopsided).x1 <= DEJAVU.width + TOLERANCE
    assert plan.dy == pytest.approx(0.0)


def test_connectors_share_one_map_and_keep_their_relative_places() -> None:
    """Shrink every box glyph alike, about the cell centre, with no per-glyph shift."""
    vertical = Box(0.261, -0.4, 0.339, 1.0)
    rule = Box(-0.039, 0.26, 0.639, 0.34)
    shared = class_fit("connectors", [vertical, rule], SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    a, b = (plan_in_class(ink, shared, DEJAVU) for ink in (vertical, rule))
    assert (a.sx, a.sy, a.dx, a.dy) == (b.sx, b.sy, b.dx, b.dy)
    for ink in (vertical, rule):
        moved = a.apply(ink)
        assert moved.y0 >= DEJAVU.descent - TOLERANCE
        assert moved.y1 <= DEJAVU.ascent + TOLERANCE
        assert moved.x0 >= -TOLERANCE
        assert moved.x1 <= DEJAVU.width + TOLERANCE
    # the middle of the frame stays the middle of the cell
    assert a.apply(Box(0, 0.3, 0.1, 0.3)).y0 == pytest.approx((0.928 - 0.236) / 2)


def test_the_base_font_keeps_its_own_box_drawing() -> None:
    """Do not shrink a font's connectors to a cell that is its own cell."""
    diagonal = Box(-0.03, -0.27, 0.64, 0.96)  # DejaVu's slashes run past the cell
    shared = class_fit("connectors", [diagonal], DEJAVU, Box(-0.01, -0.25, 0.612, 0.938), DEJAVU)
    assert shared.scale == pytest.approx(1.0)
    assert plan_in_class(diagonal, shared, DEJAVU).identity


def test_a_symbol_category_is_shrunk_in_proportion_and_stays_centred_on_its_baseline() -> None:
    """Scale every glyph of an arrows-like block alike, never in one direction only."""
    wide_arrow = Box(-0.05, 0.10, 0.65, 0.50)  # 0.1 em wider than the donor's 0.6 em cell
    small = Box(0.20, 0.00, 0.40, 0.60)
    shared = class_fit("symbols", [wide_arrow, small], SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    assert shared.needed == pytest.approx(DEJAVU.width / 0.70)
    assert shared.scale == pytest.approx(CLASS_FLOORS["symbols"])
    for ink in (wide_arrow, small):
        plan = plan_in_class(ink, shared, DEJAVU)
        assert plan.sx == pytest.approx(plan.sy)  # proportional: never stretched or squished
        moved = plan.apply(ink)
        assert moved.y0 == pytest.approx(ink.y0 * plan.sy)  # still on its baseline
        assert (moved.x0 + moved.x1) / 2 == pytest.approx(DEJAVU.width / 2)  # still centred
        assert moved.x0 >= -TOLERANCE
        assert moved.x1 <= DEJAVU.width + TOLERANCE
    assert plan_in_class(small, shared, DEJAVU).sx == pytest.approx(CLASS_FLOORS["symbols"])


def test_a_symbol_category_with_no_offender_is_left_alone() -> None:
    """Change nothing in a block whose glyphs all fit."""
    shared = class_fit("symbols", [Box(0.1, 0.0, 0.5, 0.7)], SOURCE_CODE, SOURCE_CODE_FRAME, DEJAVU)
    assert shared.scale == pytest.approx(1.0)
