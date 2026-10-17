"""Tests for the console state over the catalog: populated rows, overlay edits, pins."""

from __future__ import annotations

import tomllib
from http import HTTPStatus
from typing import TYPE_CHECKING

from support import build_font, sample_catalog

from font_composer.common.config import Config
from font_composer.common.unicode.groups import build_catalog
from font_composer.composer.state import ConsoleState

if TYPE_CHECKING:
    from pathlib import Path

M, N, LEFT, UP = 0x4D, 0x4E, 0x2190, 0x2191
FONTS, ALNUM_GLYPHS = 2, 2
ALNUM = "overlay:ascii-alnum"
BASE_CONFIG = '[cell]\nbase = "Alpha"\n\n[groups]\n'


def _state(tmp_path: Path, config_text: str = BASE_CONFIG) -> ConsoleState:
    """Alpha has M, N and the left arrow; Beta has M, the left arrow and the up arrow."""
    fonts = tmp_path / "fonts"
    for label, points in {"Alpha": [M, N, LEFT], "Beta": [M, LEFT, UP]}.items():
        (fonts / label).mkdir(parents=True)
        build_font(fonts / label / f"{label}-Regular.ttf", codepoints=points)
    path = tmp_path / "font_composer.toml"
    path.write_text(config_text, encoding="utf-8")
    return ConsoleState(fonts, Config.load(path), catalog=sample_catalog())


def _data(state: ConsoleState) -> dict:
    return tomllib.loads(state.config.path.read_text(encoding="utf-8"))


def test_the_table_lists_only_categories_some_font_has_glyphs_for(tmp_path: Path) -> None:
    """Leave out the blocks nobody has a glyph in, in either view."""
    state = _state(tmp_path)
    assert [group["id"] for group in state.snapshot(overlay=False)["groups"]] == [
        "Basic Latin", "Arrows"]
    assert [group["id"] for group in state.snapshot(overlay=True)["groups"]] == [
        ALNUM, "Arrows"]  # no ASCII symbol in either font: that category is left out too


def test_each_category_lists_its_fonts_with_their_glyph_counts(tmp_path: Path) -> None:
    """Count per family on the reference style; say how many fonts are monitored."""
    snapshot = _state(tmp_path).snapshot(overlay=False)
    arrows = next(group for group in snapshot["groups"] if group["id"] == "Arrows")
    assert [(font["family"], font["count"]) for font in arrows["fonts"]] == [
        ("Alpha", 1), ("Beta", 2)]
    assert snapshot["fontCount"] == FONTS
    assert snapshot["catalogReady"]
    assert arrows["ranges"] == [[0x2190, 0x21FF]]
    assert snapshot["coverage"]["Beta"]["Arrows"] == [2, 112]
    assert "coverage" not in snapshot["families"][0]["styles"][0]


def test_without_a_catalog_there_is_nothing_to_list(tmp_path: Path) -> None:
    """Start anyway and say the block list is missing."""
    state = _state(tmp_path)
    empty = ConsoleState(state.library.fonts_dir, state.config, catalog=build_catalog([], {}))
    snapshot = empty.snapshot(overlay=True)
    assert snapshot["groups"] == []
    assert not snapshot["catalogReady"]


def test_old_group_ids_in_the_file_are_ignored(tmp_path: Path) -> None:
    """Leave a configuration with the old ids alone: nothing is renamed, nothing fails."""
    state = _state(tmp_path, BASE_CONFIG + 'arrows = ["Beta"]\nalnum = ["Alpha"]\n')
    assert state.config.overlay.pins == {}
    assert state.snapshot(overlay=True)["summary"][0]["covered"] == 0


def test_choosing_in_an_overlay_category_writes_generated_pins(tmp_path: Path) -> None:
    """Resolve the order into pins; the next family fills in for a removed one."""
    state = _state(tmp_path)
    status, payload = state.choose(ALNUM, "Alpha", "add", [])
    assert status == HTTPStatus.OK
    assert payload["order"] == ["Alpha"]
    assert state.config.overlay.pins == {M: ["Alpha"], N: ["Alpha"]}
    status, payload = state.choose(ALNUM, "Beta", "add", ["Alpha"])
    assert payload["order"] == ["Alpha", "Beta"]
    assert state.config.overlay.pins == {M: ["Alpha", "Beta"], N: ["Alpha"]}
    status, payload = state.choose(ALNUM, "Alpha", "remove", ["Alpha", "Beta"])
    assert payload["order"] == ["Beta"]
    assert state.config.overlay.pins == {M: ["Beta"]}  # N has no other family: pin gone
    data = _data(state)
    assert data["groups"] == {}  # the overlay never reaches [groups]
    assert "overlay_orders" not in data  # and its orders are not stored unless asked


def test_a_manual_pin_survives_the_regeneration_of_its_category(tmp_path: Path) -> None:
    """Keep [glyphs] apart from [generated_glyphs]; drop a pin only when its family leaves."""
    state = _state(tmp_path)
    state.choose(ALNUM, "Alpha", "add", [])
    state.choose(ALNUM, "Beta", "add", ["Alpha"])
    assert state.set_glyph(M, "Beta", ALNUM, ["Alpha", "Beta"])[0] == HTTPStatus.OK
    assert state.config.glyph_overrides == {M: "Beta"}
    state.choose(ALNUM, "Alpha", "remove", ["Alpha", "Beta"])
    assert state.config.glyph_overrides == {M: "Beta"}  # Beta is still in the order
    state.choose(ALNUM, "Beta", "remove", ["Beta"])
    assert state.config.glyph_overrides == {}  # its family left the category
    assert state.config.overlay.pins == {}


def test_a_pin_needs_a_family_of_the_order_that_has_the_glyph(tmp_path: Path) -> None:
    """Refuse the same pins the blocks refuse."""
    state = _state(tmp_path)
    assert state.set_glyph(M, "Beta", ALNUM, ["Alpha"])[0] == HTTPStatus.CONFLICT
    assert state.set_glyph(N, "Beta", ALNUM, ["Beta"])[0] == HTTPStatus.CONFLICT  # no glyph
    assert state.set_glyph(LEFT, "Alpha", ALNUM, ["Alpha"])[0] == HTTPStatus.BAD_REQUEST


def test_the_table_tallies_what_the_pins_serve_in_either_view(tmp_path: Path) -> None:
    """Show what will be built: pins count even where the block has no order."""
    state = _state(tmp_path)
    state.choose(ALNUM, "Alpha", "add", [])
    for overlay, row in ((True, ALNUM), (False, "Basic Latin")):
        summary = {entry["group"]: entry for entry in state.snapshot(overlay=overlay)["summary"]}
        assert summary[row]["covered"] == ALNUM_GLYPHS
        assert summary[row]["sources"] == {"Alpha": 2}
    assert state.snapshot(overlay=False)["choices"] == {}  # the order itself is not stored
    assert state.snapshot(overlay=True)["styleMap"]["families"].keys() == {"Alpha"}


def test_the_composition_of_an_overlay_category_uses_the_order_it_is_given(
    tmp_path: Path,
) -> None:
    """Resolve with the browser's order; families outside a block's order are listed apart."""
    state = _state(tmp_path)
    status, payload = state.composition(ALNUM, ["Beta", "Alpha"], overlay=True)
    assert status == HTTPStatus.OK
    assert {item["codepoint"]: item["source"] for item in payload["glyphs"]} == {
        M: "Beta", N: "Alpha"}
    assert payload["order"] == ["Beta", "Alpha"]
    assert payload["extra"] == []
    state.choose(ALNUM, "Alpha", "add", [])
    status, payload = state.composition("Basic Latin")
    assert (payload["order"], payload["extra"]) == ([], ["Alpha"])
    assert {item["source"] for item in payload["glyphs"]} == {"Alpha"}


def test_overlay_orders_are_stored_only_when_asked_and_follow_later_edits(
    tmp_path: Path,
) -> None:
    """Create [overlay_orders] on request, keep it current, and remove it on request."""
    state = _state(tmp_path)
    assert state.set_overlay_store(enabled=True, orders={"Arrows": ["Alpha"]})[0] == (
        HTTPStatus.BAD_REQUEST)  # a block is not an overlay category
    assert state.set_overlay_store(enabled=True, orders={ALNUM: ["Alpha"]})[0] == HTTPStatus.OK
    assert state.snapshot()["overlay"] == {
        "stored": True, "orders": {ALNUM: ["Alpha"]}}
    state.choose(ALNUM, "Beta", "add", ["Alpha"])
    assert _data(state)["overlay_orders"] == {ALNUM: ["Alpha", "Beta"]}
    assert state.snapshot()["choices"][ALNUM] == ["Alpha", "Beta"]
    assert state.set_overlay_store(enabled=False, orders={})[0] == HTTPStatus.OK
    assert "overlay_orders" not in _data(state)


def test_a_view_does_not_serve_the_categories_of_the_other(tmp_path: Path) -> None:
    """Refuse a block the overlay divided, and an overlay category while the overlay is off."""
    state = _state(tmp_path)
    assert state.glyphs("Alpha", "Basic Latin", overlay=True)[0] == HTTPStatus.BAD_REQUEST
    assert state.glyph_names("Basic Latin", overlay=True)[0] == HTTPStatus.BAD_REQUEST
    assert state.composition("Basic Latin", overlay=True)[0] == HTTPStatus.BAD_REQUEST
    assert state.glyphs("Alpha", ALNUM)[0] == HTTPStatus.BAD_REQUEST
    status, payload = state.glyphs("Alpha", ALNUM, overlay=True)
    assert status == HTTPStatus.OK
    assert M in payload["styles"]["Alpha-Regular.ttf"]
    status, payload = state.glyphs("Alpha", "Basic Latin")
    assert status == HTTPStatus.OK
    assert M in payload["styles"]["Alpha-Regular.ttf"]
