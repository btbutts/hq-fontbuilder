"""Tests for the default style rules (common.styles) and inheritance (common.composition)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from support import FontSpec, NameSpec, build_font

from font_composer.common.composition import resolve_group
from font_composer.common.groups import GlyphGroup
from font_composer.common.library import FontLibrary
from font_composer.common.styles import (
    parse_style_name,
    resolve_style,
    similar_weight,
    style_type_name,
)

if TYPE_CHECKING:
    from pathlib import Path

PUNCTUATION = GlyphGroup("punctuation", "General Punctuation", ((0x2000, 0x209F),))


def _family_dir(root: Path, label: str, styles: list[tuple[str, int, bool]],
                codepoints: list[int]) -> None:
    folder = root / label
    folder.mkdir(parents=True)
    for style, weight, italic in styles:
        build_font(folder / f"{label}-{style.replace(' ', '')}.ttf", codepoints=codepoints,
                   spec=FontSpec(names=NameSpec(style=style, weight=weight, italic=italic)))


@pytest.mark.parametrize(("name", "weight", "italic"), [
    ("Regular", 400, False), ("Book", 400, False), ("Roman", 400, False),
    ("Italic", 400, True), ("Oblique", 400, True), ("Bold", 700, False),
    ("Bold Italic", 700, True), ("BoldOblique", 700, True), ("Demi Bold", 600, False),
    ("SemiBold Italic", 600, True), ("Medium", 500, False), ("Black", 900, False),
    ("Extra-Light", 200, False), ("ultra_light italic", 200, True),
])
def test_style_names_become_weight_and_slant(name: str, weight: int, italic: bool) -> None:
    """Treat the usual spellings of one style as the same style."""
    target = parse_style_name(name)
    assert target is not None
    assert (target.weight, target.italic) == (weight, italic)


def test_similar_weights_are_one_family_of_styles() -> None:
    """Thin, ExtraLight and Light are alike; so are Medium, SemiBold and Black."""
    assert {similar_weight(weight) for weight in (100, 200, 300)} == {300}
    assert {similar_weight(weight) for weight in (500, 600, 900)} == {600}
    assert similar_weight(400) != similar_weight(500)
    assert similar_weight(700) not in {similar_weight(600), similar_weight(900)}


def test_unknown_style_name_is_none() -> None:
    """Say so for a name the rules do not know, rather than guessing."""
    assert parse_style_name("Wobbly") is None


def test_donor_is_picked_by_weight_and_slant_not_by_name(tmp_path: Path) -> None:
    """Match Bold with Heavy-named 700, Italic with Oblique, nearest weight otherwise."""
    _family_dir(tmp_path, "Fam", [("Book", 400, False), ("Demi", 600, False),
                                   ("Heavy", 700, False), ("Slanted", 400, True)], [0x41])
    family = FontLibrary.scan(tmp_path).family("Fam")
    assert family is not None
    bold = resolve_style(family, parse_style_name("Bold"))
    assert bold.entry is not None
    assert bold.entry.file_name == "Fam-Heavy.ttf"
    assert "matches" in bold.reason
    regular = resolve_style(family, parse_style_name("Regular"))
    assert regular.entry is not None
    assert regular.entry.file_name == "Fam-Book.ttf"
    italic = resolve_style(family, parse_style_name("Italic"))
    assert italic.entry is not None
    assert italic.entry.file_name == "Fam-Slanted.ttf"
    medium = resolve_style(family, parse_style_name("Medium"))  # 500: Demi is a similar style
    assert medium.entry is not None
    assert medium.entry.file_name == "Fam-Demi.ttf"
    assert "similar" in medium.reason
    light = resolve_style(family, parse_style_name("Light"))  # 300: nothing alike, nearest
    assert light.entry is not None
    assert light.entry.file_name == "Fam-Book.ttf"
    assert "nearest" in light.reason


def test_no_slant_is_synthesised(tmp_path: Path) -> None:
    """A family with no italic has no donor for an italic target, until it is mapped."""
    _family_dir(tmp_path, "Fam", [("Regular", 400, False), ("Bold", 700, False)], [0x41])
    family = FontLibrary.scan(tmp_path).family("Fam")
    assert family is not None
    choice = resolve_style(family, parse_style_name("Bold Italic"))
    assert choice.entry is None
    assert "no italic" in choice.reason
    forced = resolve_style(family, parse_style_name("Bold Italic"), "Fam-Bold.ttf")
    assert forced.entry is not None
    assert forced.overridden


def test_override_may_name_a_file_or_a_style_name(tmp_path: Path) -> None:
    """Accept either spelling in the configuration; report one that matches nothing."""
    _family_dir(tmp_path, "Fam", [("Regular", 400, False), ("Light", 300, False)], [0x41])
    family = FontLibrary.scan(tmp_path).family("Fam")
    assert family is not None
    target = parse_style_name("Regular")
    by_name = resolve_style(family, target, "Light")
    assert by_name.entry is not None
    assert by_name.entry.file_name == "Fam-Light.ttf"
    missing = resolve_style(family, target, "Nope.ttf")
    assert missing.entry is not None  # falls back to the default rules ...
    assert not missing.overridden
    assert "not found" in missing.reason  # ... and says why


def test_inheritance_fills_in_what_the_first_family_lacks(tmp_path: Path) -> None:
    """Take a code point from the first family that has it, in the order chosen."""
    first, second = 0x2010, 0x2011
    _family_dir(tmp_path, "A", [("Regular", 400, False)], [ord("M"), first])
    _family_dir(tmp_path, "B", [("Regular", 400, False)], [ord("M"), first, second])
    library = FontLibrary.scan(tmp_path)
    composition = resolve_group(PUNCTUATION, ["A", "B"], library, {})
    by_cp = {glyph.codepoint: glyph for glyph in composition.glyphs}
    assert by_cp[first].source == "A"
    assert by_cp[first].candidates == ("A", "B")
    assert by_cp[second].source == "B"
    assert composition.missing == PUNCTUATION.total - 2
    assert composition.contributions(["A", "B"]) == {"A": 1, "B": 1}
    reversed_order = resolve_group(PUNCTUATION, ["B", "A"], library, {})
    assert {g.codepoint: g.source for g in reversed_order.glyphs}[first] == "B"


def test_a_glyph_override_picks_one_of_the_candidates(tmp_path: Path) -> None:
    """Honour [glyphs] when the family has the glyph; report it when it does not."""
    shared, only_a = 0x2010, 0x2012
    _family_dir(tmp_path, "A", [("Regular", 400, False)], [ord("M"), shared, only_a])
    _family_dir(tmp_path, "B", [("Regular", 400, False)], [ord("M"), shared])
    library = FontLibrary.scan(tmp_path)
    composition = resolve_group(PUNCTUATION, ["A", "B"], library, {shared: "B", only_a: "B"})
    by_cp = {glyph.codepoint: glyph for glyph in composition.glyphs}
    assert by_cp[shared].source == "B"
    assert by_cp[shared].overridden
    assert by_cp[only_a].source == "A"
    assert not by_cp[only_a].overridden
    assert [item.codepoint for item in composition.invalid_overrides] == [only_a]


def test_a_style_type_is_what_the_numbers_say() -> None:
    """Spell weights and slants one way: ``bold`` and ``Bold``, Oblique and Italic agree."""
    assert style_type_name(700, italic=False) == "Bold"
    assert style_type_name(400, italic=True) == "Italic"
    assert style_type_name(300, italic=True) == "Light Italic"
    assert style_type_name(450, italic=False) == "Regular"
    assert style_type_name(650, italic=False) == "SemiBold"
