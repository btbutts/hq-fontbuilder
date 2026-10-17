"""Tests for font_composer.composer.state: inheritance order, overrides, hand edits."""

from __future__ import annotations

import os
import tomllib
from http import HTTPStatus
from pathlib import Path

import pytest
from support import FontSpec, NameSpec, build_font, sample_catalog

from font_composer.common.config import Config
from font_composer.common.names import UnicodeNames
from font_composer.composer.state import ConsoleState

COMMENTED = """\
# my notes
[output]
family = "Console Mono"   # the name

[cell]
base = "Alpha"

[groups]
"""

ARROW_LEFT, ARROW_RIGHT, ARROW_UP = 0x2190, 0x2192, 0x2191
ARROWS_IN_FIXTURE = 3


def _make_state(tmp_path: Path, config_text: str = COMMENTED) -> ConsoleState:
    """Build a console over three tiny families and a configuration file.

    Alpha: M, the first half of box-drawing, all of block-elements, the left arrow.
    Beta: M, left arrow, up arrow (Bold also has the right arrow).
    Gamma: M, right arrow.
    """
    fonts = tmp_path / "fonts"
    for label in ("Alpha", "Beta", "Gamma"):
        (fonts / label).mkdir(parents=True)
    build_font(fonts / "Alpha" / "Alpha-Regular.ttf",
               codepoints=[ord("M"), *range(0x2500, 0x2540), *range(0x2580, 0x25A0), ARROW_LEFT])
    build_font(fonts / "Beta" / "Beta-Regular.ttf", codepoints=[ord("M"), ARROW_LEFT, ARROW_UP])
    build_font(fonts / "Beta" / "Beta-Bold.ttf",
               codepoints=[ord("M"), ARROW_LEFT, ARROW_UP, ARROW_RIGHT],
               spec=FontSpec(names=NameSpec(style="Bold", weight=700)))
    build_font(fonts / "Gamma" / "Gamma-Regular.ttf", codepoints=[ord("M"), ARROW_RIGHT])
    path = tmp_path / "font_composer.toml"
    path.write_text(config_text, encoding="utf-8")
    return ConsoleState(fonts, Config.load(path), catalog=sample_catalog())


def _order(state: ConsoleState, group: str) -> list[str]:
    return state.config.choices.get(group, [])


def test_families_are_added_in_the_order_they_are_chosen(tmp_path: Path) -> None:
    """Append each choice; save it as an ordered list; keep comments; bump the version."""
    state = _make_state(tmp_path)
    before = state.version
    assert state.choose("Arrows", "Beta", "add")[0] == HTTPStatus.OK
    status, payload = state.choose("Arrows", "Alpha", "add")
    assert status == HTTPStatus.OK
    assert payload["choices"] == {"Arrows": ["Beta", "Alpha"]}
    assert state.version == before + 2
    text = state.config.path.read_text(encoding="utf-8")
    assert "# my notes" in text
    assert "# the name" in text
    assert tomllib.loads(text)["groups"] == {"Arrows": ["Beta", "Alpha"]}


def test_adding_twice_changes_nothing_and_remove_move_clear_work(tmp_path: Path) -> None:
    """A family is listed once; it can be moved up and down, removed, or all cleared."""
    state = _make_state(tmp_path)
    for label in ("Alpha", "Beta", "Gamma", "Alpha"):
        state.choose("Arrows", label, "add")
    assert _order(state, "Arrows") == ["Alpha", "Beta", "Gamma"]
    state.choose("Arrows", "Gamma", "up")
    assert _order(state, "Arrows") == ["Alpha", "Gamma", "Beta"]
    state.choose("Arrows", "Alpha", "up")  # already first: stays
    assert _order(state, "Arrows") == ["Alpha", "Gamma", "Beta"]
    state.choose("Arrows", "Alpha", "down")
    assert _order(state, "Arrows") == ["Gamma", "Alpha", "Beta"]
    state.choose("Arrows", "Alpha", "remove")
    assert _order(state, "Arrows") == ["Gamma", "Beta"]
    assert state.choose("Arrows", "Alpha", "up")[0] == HTTPStatus.BAD_REQUEST
    state.choose("Arrows", None, "clear")
    assert "Arrows" not in state.config.choices


def test_an_atomic_group_takes_one_complete_family(tmp_path: Path) -> None:
    """Refuse half a box-drawing set, and a second family for an atomic group."""
    state = _make_state(tmp_path)
    status, payload = state.choose("Box Drawing", "Alpha", "add")
    assert status == HTTPStatus.CONFLICT
    assert "atomic" in payload["error"]
    assert state.choose("Block Elements", "Alpha", "add")[0] == HTTPStatus.OK
    status, payload = state.choose("Block Elements", "Beta", "add")
    assert status == HTTPStatus.CONFLICT
    assert "one family" in payload["error"]
    assert _order(state, "Block Elements") == ["Alpha"]


def test_unknown_ids_are_rejected(tmp_path: Path) -> None:
    """Answer 400 for ids and actions the console does not know."""
    state = _make_state(tmp_path)
    assert state.choose("nonsense", "Alpha", "add")[0] == HTTPStatus.BAD_REQUEST
    assert state.choose("Arrows", "Nowhere", "add")[0] == HTTPStatus.BAD_REQUEST
    assert state.choose("Arrows", "Alpha", "explode")[0] == HTTPStatus.BAD_REQUEST


def test_a_family_is_shown_by_the_name_its_font_carries(tmp_path: Path) -> None:
    """Serve the name table's family name as ``displayName``; the folder label stays the key."""
    state = _make_state(tmp_path)
    fonts = tmp_path / "fonts"
    (fonts / "SpacedOut").mkdir()
    build_font(fonts / "SpacedOut" / "SpacedOut-Regular.ttf", codepoints=[ord("M")],
               spec=FontSpec(names=NameSpec(family="Spaced Out Mono")))
    state.refresh()
    families = {item["label"]: item["displayName"] for item in state.snapshot()["families"]}
    assert families["SpacedOut"] == "Spaced Out Mono"
    assert families["Alpha"] == "Test Family"  # a fixture font that names itself nothing special


def test_fit_is_planned_for_the_requested_glyphs_of_one_style_file(tmp_path: Path) -> None:
    """Answer ``fit`` for the code points asked for, in any style file; refuse bad requests."""
    state = _make_state(tmp_path)
    status, payload = state.fit("Beta", "Arrows", "Beta-Bold.ttf", [ARROW_LEFT, ARROW_UP, 0x41])
    assert status == HTTPStatus.OK
    assert payload["file"] == "Beta-Bold.ttf"
    assert set(payload["fit"]) <= {str(ARROW_LEFT), str(ARROW_UP)}  # 0x41 is not an arrow
    assert state.fit("Beta", "Arrows", "Nope.ttf", [ARROW_LEFT])[0] == HTTPStatus.NOT_FOUND
    assert state.fit("Nobody", "Arrows", "Beta-Bold.ttf", [])[0] == HTTPStatus.NOT_FOUND
    assert state.fit("Beta", "nonsense", "Beta-Bold.ttf", [])[0] == HTTPStatus.BAD_REQUEST
    too_many = list(range(3000))
    assert state.fit("Beta", "Arrows", "Beta-Bold.ttf", too_many)[0] == HTTPStatus.BAD_REQUEST


def test_the_composition_fills_gaps_in_order_and_counts_sources(tmp_path: Path) -> None:
    """Take each glyph from the first family that has it; the rest fill in."""
    state = _make_state(tmp_path)
    for label in ("Alpha", "Beta", "Gamma"):
        state.choose("Arrows", label, "add")
    status, payload = state.composition("Arrows")
    assert status == HTTPStatus.OK
    by_cp = {glyph["codepoint"]: glyph for glyph in payload["glyphs"]}
    assert by_cp[ARROW_LEFT]["source"] == "Alpha"
    assert by_cp[ARROW_LEFT]["candidates"] == ["Alpha", "Beta"]
    assert by_cp[ARROW_UP]["source"] == "Beta"
    assert "candidates" not in by_cp[ARROW_UP]
    assert by_cp[ARROW_RIGHT]["source"] == "Gamma"  # Beta's Regular lacks it, Bold has it
    assert payload["contributions"] == {"Alpha": 1, "Beta": 1, "Gamma": 1}
    assert payload["missing"] == payload["total"] - ARROWS_IN_FIXTURE
    assert payload["fonts"] == {"Alpha": "Alpha-Regular.ttf", "Beta": "Beta-Regular.ttf",
                                "Gamma": "Gamma-Regular.ttf"}
    assert set(payload["familyNames"]) == {"Alpha", "Beta", "Gamma"}  # the TTFs' own names
    summary = {entry["group"]: entry for entry in state.snapshot()["summary"]}["Arrows"]
    assert summary["order"] == ["Alpha", "Beta", "Gamma"]
    assert summary["covered"] == ARROWS_IN_FIXTURE


def test_a_glyph_can_be_pinned_to_a_candidate_and_released(tmp_path: Path) -> None:
    """Write [glyphs]; the pinned family serves the glyph; None goes back to the order."""
    state = _make_state(tmp_path)
    state.choose("Arrows", "Alpha", "add")
    state.choose("Arrows", "Beta", "add")
    status, payload = state.set_glyph(ARROW_LEFT, "Beta")
    assert status == HTTPStatus.OK
    glyph = {item["codepoint"]: item for item in payload["glyphs"]}[ARROW_LEFT]
    assert (glyph["source"], glyph["overridden"]) == ("Beta", True)
    data = tomllib.loads(state.config.path.read_text(encoding="utf-8"))
    assert data["glyphs"] == {"U+2190": {"family": "Beta"}}
    assert state.snapshot()["glyphOverrides"] == {"U+2190": "Beta"}
    status, payload = state.set_glyph(ARROW_LEFT, None)
    assert {item["codepoint"]: item for item in payload["glyphs"]}[ARROW_LEFT]["source"] == "Alpha"


def test_a_glyph_override_must_name_a_family_that_is_in_the_order_and_has_it(
    tmp_path: Path,
) -> None:
    """Refuse a family outside the order, one without the glyph, and atomic groups."""
    state = _make_state(tmp_path)
    state.choose("Arrows", "Alpha", "add")
    assert state.set_glyph(ARROW_LEFT, "Beta")[0] == HTTPStatus.CONFLICT  # not in the order
    state.choose("Arrows", "Beta", "add")
    assert state.set_glyph(ARROW_UP, "Alpha")[0] == HTTPStatus.CONFLICT  # no such glyph
    state.choose("Basic Latin", "Alpha", "add")  # alnum has its own order
    assert state.set_glyph(ord("M"), "Alpha")[0] == HTTPStatus.OK
    assert state.set_glyph(0x2500, "Alpha")[0] == HTTPStatus.CONFLICT  # atomic
    assert state.set_glyph(0x10FFFF, "Alpha")[0] == HTTPStatus.BAD_REQUEST  # in no group


def test_removing_a_family_drops_the_glyph_overrides_that_pointed_to_it(tmp_path: Path) -> None:
    """Never leave an override naming a family that left the group."""
    state = _make_state(tmp_path)
    state.choose("Arrows", "Alpha", "add")
    state.choose("Arrows", "Beta", "add")
    state.set_glyph(ARROW_LEFT, "Beta")
    state.choose("Arrows", "Beta", "remove")
    assert state.config.glyph_overrides == {}


def test_the_style_map_resolves_output_styles_and_takes_overrides(tmp_path: Path) -> None:
    """Show which file serves Regular and Bold, and let the user map one by hand."""
    state = _make_state(tmp_path)
    state.choose("Arrows", "Beta", "add")
    style_map = state.snapshot()["styleMap"]
    assert style_map["outputStyles"] == ["Regular", "Bold"]
    files = {item["file"]: item for item in style_map["families"]["Beta"]}
    assert files["Beta-Bold.ttf"]["family"] == "Test Family"  # the TTF's own, not the folder's
    assert files["Beta-Bold.ttf"]["style"] == "Bold"
    assert style_map["entries"]["Regular"]["Beta"]["file"] == "Beta-Regular.ttf"
    assert style_map["entries"]["Bold"]["Beta"]["file"] == "Beta-Bold.ttf"
    assert not style_map["entries"]["Bold"]["Beta"]["overridden"]
    assert state.set_style("Bold", "Beta", "Beta-Regular.ttf")[0] == HTTPStatus.OK
    entry = state.snapshot()["styleMap"]["entries"]["Bold"]["Beta"]
    assert entry["file"] == "Beta-Regular.ttf"
    assert entry["overridden"]
    assert state.set_style("Bold", "Beta", "nope.ttf")[0] == HTTPStatus.BAD_REQUEST
    assert state.set_style("Wobbly", "Beta", None)[0] == HTTPStatus.BAD_REQUEST
    state.set_style("Bold", "Beta", None)
    assert not state.snapshot()["styleMap"]["entries"]["Bold"]["Beta"]["overridden"]


def test_hand_edits_survive_a_choice_made_afterwards(tmp_path: Path) -> None:
    """Re-read the file before writing, so a hand edit made while running is kept."""
    state = _make_state(tmp_path)
    path = state.config.path
    path.write_text(path.read_text(encoding="utf-8").replace(
        'family = "Console Mono"', 'family = "Console Mono"\nstyles = ["Regular", "Italic"]'),
        encoding="utf-8")
    later = path.stat().st_mtime_ns + 1_000_000_000
    os.utime(path, ns=(later, later))
    assert state.choose("Arrows", "Beta", "add")[0] == HTTPStatus.OK
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["output"]["styles"] == ["Regular", "Italic"]
    assert data["groups"] == {"Arrows": ["Beta"]}


def test_a_hand_edit_is_seen_by_the_version_poll(tmp_path: Path) -> None:
    """Bump the version and show the new choices when the file is edited by hand."""
    state = _make_state(tmp_path)
    before = state.current_version()
    path = state.config.path
    path.write_text(path.read_text(encoding="utf-8") + 'Arrows = ["Beta", "Alpha"]\n',
                    encoding="utf-8")
    later = path.stat().st_mtime_ns + 1_000_000_000
    os.utime(path, ns=(later, later))
    assert state.current_version() == before + 1
    assert state.snapshot()["choices"] == {"Arrows": ["Beta", "Alpha"]}


def test_an_invalid_hand_edit_is_reported_and_never_overwritten(tmp_path: Path) -> None:
    """Keep the broken file as it is, answer 500 to a choice, and report the error."""
    state = _make_state(tmp_path)
    path = state.config.path
    path.write_text("[groups\n", encoding="utf-8")
    later = path.stat().st_mtime_ns + 1_000_000_000
    os.utime(path, ns=(later, later))
    assert state.snapshot()["configError"] is not None
    status, payload = state.choose("Arrows", "Beta", "add")
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "cannot load" in payload["error"]
    assert path.read_text(encoding="utf-8") == "[groups\n"


def test_snapshot_flags_uneven_families(tmp_path: Path) -> None:
    """Name the groups on which a family's styles disagree."""
    snapshot = _make_state(tmp_path).snapshot()
    assert snapshot["uneven"]["Beta"] == ["Arrows"]
    assert snapshot["uneven"]["Alpha"] == []


def test_glyphs_lists_only_the_present_code_points(tmp_path: Path) -> None:
    """Report, per style file, which code points of the group the font holds."""
    state = _make_state(tmp_path)
    status, payload = state.glyphs("Beta", "Arrows")
    assert status == HTTPStatus.OK
    assert payload["styles"] == {"Beta-Bold.ttf": [ARROW_LEFT, ARROW_UP, ARROW_RIGHT],
                                 "Beta-Regular.ttf": [ARROW_LEFT, ARROW_UP]}
    assert state.glyphs("Nowhere", "Arrows")[0] == HTTPStatus.NOT_FOUND
    assert state.glyphs("Beta", "nonsense")[0] == HTTPStatus.BAD_REQUEST


def test_glyphs_that_leave_the_base_cell_carry_a_fit_plan(tmp_path: Path) -> None:
    """Report clipping and its correction in both the group and the composition views."""
    fonts = tmp_path / "fonts"
    for label in ("Alpha", "Beta"):
        (fonts / label).mkdir(parents=True)
    # Alpha is the base: a 600 x 1000 cell (ascent 800, descent -200)
    build_font(fonts / "Alpha" / "Alpha-Regular.ttf", codepoints=[ord("M"), ARROW_UP])
    # Beta's left arrow is 800 wide in a 600 cell; its up arrow fits
    build_font(fonts / "Beta" / "Beta-Regular.ttf", codepoints=[ord("M"), ARROW_LEFT, ARROW_UP],
               ink={ARROW_LEFT: (-100, 100, 700, 500), ARROW_UP: (100, 0, 500, 700)})
    path = tmp_path / "font_composer.toml"
    path.write_text('[cell]\nbase = "Alpha"\n', encoding="utf-8")
    state = ConsoleState(fonts, Config.load(path), catalog=sample_catalog())
    state.choose("Arrows", "Beta", "add")
    status, glyphs = state.glyphs("Beta", "Arrows")
    assert status == HTTPStatus.OK
    plan = glyphs["fit"]["Beta-Regular.ttf"][str(ARROW_LEFT)]
    assert plan["kind"] == "category"
    assert plan["clipped"]
    assert plan["sx"] == plan["sy"] < 1.0  # in proportion, never stretched
    # the arrow that fits is scaled with its category: it shares the floor, not the extra
    shared = glyphs["fit"]["Beta-Regular.ttf"][str(ARROW_UP)]
    assert shared["kind"] == "category"
    assert not shared["clipped"]
    assert plan["sx"] < shared["sx"] == shared["sy"] < 1.0
    status, payload = state.composition("Arrows")
    by_cp = {glyph["codepoint"]: glyph for glyph in payload["glyphs"]}
    assert by_cp[ARROW_LEFT]["fit"]["kind"] == "category"
    assert by_cp[ARROW_UP]["fit"]["sx"] == shared["sx"]


def test_official_names_are_served_per_group(tmp_path: Path) -> None:
    """Return the names of a group's code points, as strings keyed by code point."""
    names_path = tmp_path / "NamesList.txt"
    names_path.write_text("2190\tLEFTWARDS ARROW\n2191\tUPWARDS ARROW\n0041\tLATIN A\n",
                          encoding="utf-8")
    fonts = tmp_path / "fonts"
    (fonts / "Alpha").mkdir(parents=True)
    build_font(fonts / "Alpha" / "Alpha-Regular.ttf", codepoints=[ord("M")])
    config_path = tmp_path / "font_composer.toml"
    config_path.write_text("", encoding="utf-8")
    state = ConsoleState(fonts, Config.load(config_path), UnicodeNames(names_path),
                         catalog=sample_catalog())
    status, payload = state.glyph_names("Arrows")
    assert status == HTTPStatus.OK
    assert payload["names"] == {"8592": "LEFTWARDS ARROW", "8593": "UPWARDS ARROW"}
    assert state.glyph_names("nonsense")[0] == HTTPStatus.BAD_REQUEST


def test_box_lines_that_overshoot_the_block_on_purpose_do_not_shrink_the_family(
    tmp_path: Path,
) -> None:
    """Fit connectors by their frame (the full block); the overshoot is cut by the cell."""
    fonts = tmp_path / "fonts"
    for label in ("Alpha", "Beta"):
        (fonts / label).mkdir(parents=True)
    build_font(fonts / "Alpha" / "Alpha-Regular.ttf", codepoints=[ord("M")])  # 600 x 1000 cell
    # Beta: a full block exactly its cell, and a vertical line 0.2 em past it both ways
    build_font(fonts / "Beta" / "Beta-Regular.ttf", codepoints=[ord("M"), 0x2588, 0x2502],
               ink={0x2588: (0, -200, 600, 800), 0x2502: (250, -400, 350, 1000)})
    config_path = tmp_path / "font_composer.toml"
    config_path.write_text('[cell]\nbase = "Alpha"\n', encoding="utf-8")
    state = ConsoleState(fonts, Config.load(config_path), UnicodeNames(tmp_path / "none.txt"),
                         catalog=sample_catalog())
    state.choose("Box Drawing", "Beta", "add")  # refused: atomic and incomplete; fit is independent
    status, glyphs = state.glyphs("Beta", "Box Drawing")
    assert status == HTTPStatus.OK
    line = glyphs["fit"]["Beta-Regular.ttf"][str(0x2502)]
    assert line["sy"] == pytest.approx(1.0)  # not shrunk to swallow the overshoot
    assert line["clip"]  # drawn cut at the cell edge, as the renderer will


def test_only_regular_and_bold_are_included_until_the_user_picks_more(tmp_path: Path) -> None:
    """List what the fonts hold; Regular and Bold are the ones considered by default."""
    state = _make_state(tmp_path)
    options = state.snapshot()["styleTypes"]["options"]
    assert options == [{"name": "Regular", "included": True, "similar": []},
                       {"name": "Bold", "included": True, "similar": []}]
    assert state.set_style_included("Bold", included=False)[0] == HTTPStatus.OK
    snapshot = state.snapshot()
    assert snapshot["styleMap"]["outputStyles"] == ["Regular"]
    assert snapshot["styleTypes"]["options"][1]["included"] is False
    assert state.config.setting("output", "styles", []) == ["Regular"]
    assert state.set_style_included("Bold", included=True)[0] == HTTPStatus.OK
    assert state.snapshot()["styleMap"]["outputStyles"] == ["Regular", "Bold"]
    assert state.set_style_included("Hairline", included=True)[0] == HTTPStatus.BAD_REQUEST


def test_similar_styles_are_one_entry_when_consolidated(tmp_path: Path) -> None:
    """Merge SemiBold, Black (and Medium) into one entry; Thin Italic into Light Italic."""
    state = _make_state(tmp_path)
    fonts = tmp_path / "fonts"
    for style, weight, italic in (("Black", 900, False), ("SemiBold", 600, False),
                                  ("Thin Italic", 100, True), ("Light Oblique", 300, True)):
        build_font(fonts / "Gamma" / f"Gamma-{style.replace(' ', '')}.ttf",
                   codepoints=[ord("M")],
                   spec=FontSpec(names=NameSpec(style=style, weight=weight, italic=italic)))
    state.refresh()
    merged = state.snapshot()["styleTypes"]
    assert merged["consolidate"] is True
    by_name = {item["name"]: item for item in merged["options"]}
    assert by_name["SemiBold"]["similar"] == ["Black"]
    assert by_name["Light Italic"]["similar"] == ["Light Oblique", "Thin Italic"]
    assert "Black" not in by_name
    # including a spelling is including the entry it is merged into, and leaving the entry
    # out takes the spelling with it
    assert state.set_style_included("Black", included=True)[0] == HTTPStatus.OK
    assert "SemiBold" in state.snapshot()["styleMap"]["outputStyles"]
    assert state.set_style_included("SemiBold", included=False)[0] == HTTPStatus.OK
    assert "SemiBold" not in state.snapshot()["styleMap"]["outputStyles"]
    assert state.set_consolidate(enabled=False)[0] == HTTPStatus.OK
    names = [item["name"] for item in state.snapshot()["styleTypes"]["options"]]
    assert {"Black", "SemiBold", "Thin Italic", "Light Oblique"} <= set(names)
    assert state.set_style_included("Black", included=True)[0] == HTTPStatus.OK
    assert "Black" in state.snapshot()["styleMap"]["outputStyles"]  # on its own, unmerged


def _add_weights(state: ConsoleState, family: str, styles: tuple[tuple[str, int], ...]) -> None:
    """Give a family these upright styles (name, weight), then rescan."""
    for style, weight in styles:
        build_font(state.fonts_dir / family / f"{family}-{style}.ttf", codepoints=[ord("M")],
                   spec=FontSpec(names=NameSpec(family=family, style=style, weight=weight)))
    state.refresh()


def _included(state: ConsoleState) -> set[str]:
    """Return the names of the style entries the list shows as included."""
    options = state.snapshot()["styleTypes"]["options"]
    return {option["name"] for option in options if option["included"]}


def test_every_style_of_an_included_entry_stays_included_when_consolidation_is_off(
    tmp_path: Path,
) -> None:
    """Regular (Book, Retina), SemiBold (Medium, Black) and Bold, spelled out one by one."""
    state = _make_state(tmp_path)
    (state.fonts_dir / "Delta").mkdir()
    _add_weights(state, "Delta", (("Regular", 400), ("Book", 400), ("Retina", 400),
                                  ("Medium", 500), ("SemiBold", 600), ("Black", 900),
                                  ("Bold", 700)))
    assert state.set_style_included("SemiBold", included=True)[0] == HTTPStatus.OK
    assert _included(state) == {"Regular", "SemiBold", "Bold"}
    assert state.snapshot()["styleMap"]["outputStyles"] == ["Regular", "SemiBold", "Bold"]
    assert state.set_consolidate(enabled=False)[0] == HTTPStatus.OK
    spelled = {"Regular", "Book", "Retina", "Medium", "SemiBold", "Black", "Bold"}
    assert _included(state) == spelled
    assert set(state.snapshot()["styleMap"]["outputStyles"]) == spelled
    # each is its own now: leaving one out leaves the others as they were
    assert state.set_style_included("Black", included=False)[0] == HTTPStatus.OK
    assert _included(state) == spelled - {"Black"}
    assert state.set_style_included("Black", included=True)[0] == HTTPStatus.OK
    assert _included(state) == spelled


def test_every_style_of_an_excluded_entry_stays_excluded_when_consolidation_is_off(
    tmp_path: Path,
) -> None:
    """Leaving the SemiBold entry out leaves Medium and Black out, until one is included."""
    state = _make_state(tmp_path)
    (state.fonts_dir / "Delta").mkdir()
    _add_weights(state, "Delta", (("Regular", 400), ("Medium", 500), ("SemiBold", 600),
                                  ("Black", 900), ("Bold", 700)))
    assert state.set_style_included("SemiBold", included=True)[0] == HTTPStatus.OK
    assert state.set_style_included("SemiBold", included=False)[0] == HTTPStatus.OK
    assert state.set_consolidate(enabled=False)[0] == HTTPStatus.OK
    assert _included(state) == {"Regular", "Bold"}
    assert state.set_style_included("Medium", included=True)[0] == HTTPStatus.OK
    assert _included(state) == {"Regular", "Medium", "Bold"}
    # on again: an entry is included when any of its styles is
    assert state.set_consolidate(enabled=True)[0] == HTTPStatus.OK
    assert _included(state) == {"Regular", "SemiBold", "Bold"}


def test_a_list_that_names_only_entries_is_spelled_out_when_consolidation_goes_off(
    tmp_path: Path,
) -> None:
    """A configuration written when only the entry was saved still expands, in the file too."""
    config = '[output]\nstyles = ["Regular", "SemiBold", "Bold"]\n\n[cell]\nbase = "Alpha"\n'
    state = _make_state(tmp_path, config)
    (state.fonts_dir / "Delta").mkdir()
    _add_weights(state, "Delta", (("Regular", 400), ("Book", 400), ("Medium", 500),
                                  ("SemiBold", 600), ("Black", 900), ("Bold", 700)))
    assert _included(state) == {"Regular", "SemiBold", "Bold"}
    assert state.set_consolidate(enabled=False)[0] == HTTPStatus.OK
    assert _included(state) == {"Regular", "Book", "Medium", "SemiBold", "Black", "Bold"}
    data = tomllib.loads((tmp_path / "font_composer.toml").read_text(encoding="utf-8"))
    assert {"Book", "Medium", "Black"} <= set(data["output"]["styles"])
    assert data["output"]["consolidate_styles"] is False


def test_a_style_can_be_built_under_a_name_of_its_own(tmp_path: Path) -> None:
    """Keep the style tracked by its name; the custom name is a second, unique, name."""
    state = _make_state(tmp_path)
    assert state.choose("Arrows", "Beta", "add")[0] == HTTPStatus.OK
    assert state.set_style_name("Bold", "Strong")[0] == HTTPStatus.OK
    snapshot = state.snapshot()
    assert snapshot["styleMap"]["outputStyles"] == ["Regular", "Bold"]  # still tracked as Bold
    assert snapshot["styleMap"]["names"] == {"Bold": "Strong"}
    assert snapshot["styleMap"]["entries"]["Bold"]["Beta"]["file"] == "Beta-Bold.ttf"
    path = tmp_path / "font_composer.toml"
    assert tomllib.loads(path.read_text(encoding="utf-8"))["output"]["style-names"] == {
        "Bold": "Strong"}
    assert "# my notes" in path.read_text(encoding="utf-8")
    # unique among the names styles go by, whether given by the fonts or by the user
    for taken in ("Strong", "strong", "bold", "BO LD", "Stro-ng"):
        status, payload = state.set_style_name("Regular", taken)
        assert status == HTTPStatus.BAD_REQUEST, taken
        assert "already in use" in payload["error"]
    for bad in ("", "  ", "---", "A/B", "x" * 41):
        assert state.set_style_name("Regular", bad)[0] == HTTPStatus.BAD_REQUEST, bad
    assert state.set_style_name("Hairline", "Thin")[0] == HTTPStatus.BAD_REQUEST
    # its own name takes the custom name away, as does null
    assert state.set_style_name("Bold", "bold")[0] == HTTPStatus.OK
    assert state.snapshot()["styleMap"]["names"] == {}
    assert state.set_style_name("Bold", "Strong")[0] == HTTPStatus.OK
    assert state.set_style_name("Bold", None)[0] == HTTPStatus.OK
    assert "style-names" not in tomllib.loads(path.read_text(encoding="utf-8"))["output"]


def test_a_custom_name_may_not_be_a_name_the_other_listing_shows(tmp_path: Path) -> None:
    """Medium is merged into SemiBold; calling another style Medium would clash unmerged."""
    state = _make_state(tmp_path)
    (state.fonts_dir / "Delta").mkdir()
    _add_weights(state, "Delta", (("Medium", 500), ("SemiBold", 600)))
    status, payload = state.set_style_name("Regular", "Medium")
    assert status == HTTPStatus.BAD_REQUEST
    assert "already in use" in payload["error"]
