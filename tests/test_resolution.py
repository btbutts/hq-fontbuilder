"""Tests for font_composer.common.composition: manual pin, generated pin, block order."""

from __future__ import annotations

from typing import TYPE_CHECKING

from support import build_font, sample_catalog

from font_composer.common.composition import GroupComposition, generate_pins, resolve_group
from font_composer.common.fonts.library import FontLibrary

if TYPE_CHECKING:
    from pathlib import Path

M, N, LEFT, UP = 0x4D, 0x4E, 0x2190, 0x2191


def _library(tmp_path: Path) -> FontLibrary:
    """Alpha has M, N and the left arrow; Beta has M, the left arrow and the up arrow."""
    fonts = tmp_path / "fonts"
    for label, points in {"Alpha": [M, N, LEFT], "Beta": [M, LEFT, UP]}.items():
        (fonts / label).mkdir(parents=True)
        build_font(fonts / label / f"{label}-Regular.ttf", codepoints=points)
    return FontLibrary.scan(fonts)


def _sources(composition: GroupComposition) -> dict[int, str]:
    return {glyph.codepoint: glyph.source for glyph in composition.glyphs}


def test_the_first_family_of_the_order_serves_a_code_point(tmp_path: Path) -> None:
    """Fall through the order to the first family that has the glyph."""
    arrows = sample_catalog().by_id("Arrows")
    assert arrows is not None
    composition = resolve_group(arrows, ["Beta", "Alpha"], _library(tmp_path), {})
    assert _sources(composition) == {LEFT: "Beta", UP: "Beta"}
    assert composition.missing == arrows.total - 2


def test_a_generated_pin_outranks_the_order_and_keeps_its_fallbacks(tmp_path: Path) -> None:
    """Serve from the pin's first family; the others stay candidates for a missing style."""
    arrows = sample_catalog().by_id("Arrows")
    assert arrows is not None
    composition = resolve_group(arrows, ["Beta", "Alpha"], _library(tmp_path), {},
                                {LEFT: ("Alpha", "Beta")})
    glyph = next(item for item in composition.glyphs if item.codepoint == LEFT)
    assert (glyph.source, glyph.candidates, glyph.overridden) == (
        "Alpha", ("Alpha", "Beta"), False)
    assert _sources(composition)[UP] == "Beta"


def test_a_manual_pin_outranks_a_generated_pin(tmp_path: Path) -> None:
    """Let the user's own override win over what the overlay generated."""
    arrows = sample_catalog().by_id("Arrows")
    assert arrows is not None
    composition = resolve_group(arrows, ["Beta", "Alpha"], _library(tmp_path), {LEFT: "Beta"},
                                {LEFT: ("Alpha", "Beta")})
    glyph = next(item for item in composition.glyphs if item.codepoint == LEFT)
    assert (glyph.source, glyph.overridden) == ("Beta", True)


def test_generated_pins_serve_a_block_that_has_no_order(tmp_path: Path) -> None:
    """Basic Latin has no order while the overlay is in use; only pinned code points count."""
    basic = sample_catalog().by_id("Basic Latin")
    assert basic is not None
    composition = resolve_group(basic, [], _library(tmp_path), {}, {M: ("Alpha", "Beta")})
    assert _sources(composition) == {M: "Alpha"}  # N has no pin and the block has no order


def test_a_pin_of_a_family_that_is_gone_is_reported_and_skipped(tmp_path: Path) -> None:
    """Fall back to the order and say that the pin could not be honoured."""
    basic = sample_catalog().by_id("Basic Latin")
    assert basic is not None
    composition = resolve_group(basic, ["Beta"], _library(tmp_path), {}, {M: ("Gone",)})
    assert _sources(composition) == {M: "Beta"}
    [problem] = composition.invalid_overrides
    assert (problem.codepoint, problem.family) == (M, "Gone")
    assert problem.reason.startswith("generated pin")


def test_generate_pins_lists_every_family_of_the_order_that_has_the_glyph(
    tmp_path: Path,
) -> None:
    """Record the order as a list per code point: first serves, the rest are fallbacks."""
    alnum = sample_catalog().by_id("overlay:ascii-alnum")
    assert alnum is not None
    library = _library(tmp_path)
    assert generate_pins(alnum, ["Alpha", "Beta"], library) == {
        M: ("Alpha", "Beta"), N: ("Alpha",)}
    assert not generate_pins(alnum, [], library)
