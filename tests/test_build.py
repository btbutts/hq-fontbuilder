"""Tests for font_composer.builder: donors, fitting, missing styles, verification."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from support import FontSpec, MetricSpec, NameSpec, build_font, sample_catalog

from font_composer.builder.build import BuildOptions, run_build
from font_composer.common.unicode.groups import build_catalog

ARROW_LEFT, ARROW_UP, BOX_VERTICAL, FULL_BLOCK = 0x2190, 0x2191, 0x2502, 0x2588
REGULAR_WEIGHT = 400
CELL = 600  # advance of the base font: 600 x (800 + 200) font units at 1000 per em


def _config(tmp_path: Path, body: str = "") -> Path:
    path = tmp_path / "font_composer.toml"
    path.write_text(
        '[output]\nfamily = "Test Mono"\n\n[cell]\nbase = "Base"\n'
        f"{body}", encoding="utf-8")
    return path


def _families(tmp_path: Path) -> Path:
    """Make a base family and a donor with an arrow that is too wide for the cell."""
    fonts = tmp_path / "fonts"
    for label in ("Base", "Donor"):
        (fonts / label).mkdir(parents=True)
    build_font(fonts / "Base" / "Base-Regular.ttf", codepoints=[ord("M"), ARROW_LEFT],
               ink={ord("M"): (50, 0, 550, 700), ARROW_LEFT: (100, 300, 500, 400)})
    build_font(fonts / "Donor" / "Donor-Regular.ttf", codepoints=[ord("M"), ARROW_LEFT, ARROW_UP],
               ink={ARROW_LEFT: (-100, 300, 900, 500), ARROW_UP: (200, 0, 400, 800)})
    return fonts


def _with_bold(fonts: Path) -> None:
    """Add a family that has a Bold, so that Bold is a style the fonts hold."""
    (fonts / "Heavy").mkdir()
    build_font(fonts / "Heavy" / "Heavy-Bold.ttf", codepoints=[ord("M")],
               spec=FontSpec(names=NameSpec(style="Bold", weight=700)))


def _bounds(font: TTFont, codepoint: int) -> tuple[float, float, float, float] | None:
    glyph_set = font.getGlyphSet()
    pen = BoundsPen(glyph_set)
    glyph_set[(font.getBestCmap() or {})[codepoint]].draw(pen)
    return pen.bounds


def _build(tmp_path: Path, config: Path, fonts: Path, on_missing: str = "fail") -> tuple[int, str]:
    lines: list[str] = []
    status = run_build(BuildOptions(config, fonts, tmp_path / "out", on_missing),
                       say=lines.append, ask=lambda _prompt: "", interactive=False,
                       catalog=sample_catalog())
    return status, "\n".join(lines)


def test_a_group_is_drawn_from_its_donor_and_the_rest_stays_the_base(tmp_path: Path) -> None:
    """Served code points come from the donor, fitted; the others are the base's own."""
    fonts = _families(tmp_path)
    config = _config(tmp_path, '[groups]\nArrows = ["Donor"]\n')
    status, report = _build(tmp_path, config, fonts)
    assert status == 0, report
    font = TTFont(tmp_path / "out" / "TestMono-Regular.ttf")
    cmap = font.getBestCmap() or {}
    assert {ord("M"), ARROW_LEFT, ARROW_UP} <= set(cmap)  # the arrow up only the donor has
    assert all(width == CELL for width, _ in font["hmtx"].metrics.values())
    post: Any = font["post"]
    assert post.isFixedPitch == 1
    assert _bounds(font, ord("M")) == (50, 0, 550, 700)  # the base's own glyph, untouched
    x0, _, x1, _ = _bounds(font, ARROW_LEFT) or (0, 0, 0, 0)
    assert x0 >= 0 and x1 <= CELL  # the donor's 1000-wide arrow was fitted into the cell
    assert (tmp_path / "out" / "NOTICE").read_text(encoding="utf-8").startswith("Test Mono")


def test_a_connector_donor_is_fitted_by_its_frame_and_still_joins(tmp_path: Path) -> None:
    """A taller donor's line is mapped onto the base cell and cut at its edges."""
    fonts = _families(tmp_path)
    (fonts / "Tall").mkdir()
    spec = FontSpec(metrics=MetricSpec(ascent=900, descent=-300))  # a 1200-unit cell height
    box = list(range(0x2500, 0x2580))
    build_font(fonts / "Tall" / "Tall-Regular.ttf", codepoints=[ord("M"), FULL_BLOCK, *box],
               spec=spec,
               ink={FULL_BLOCK: (0, -300, 600, 900), BOX_VERTICAL: (250, -400, 350, 1000)})
    config = _config(tmp_path, '[groups]\n"Box Drawing" = ["Tall"]\n')
    status, report = _build(tmp_path, config, fonts)
    assert status == 0, report
    font = TTFont(tmp_path / "out" / "TestMono-Regular.ttf")
    bounds = _bounds(font, BOX_VERTICAL)
    assert bounds is not None
    assert (bounds[1], bounds[3]) == (-200, 800)  # exactly the base cell, top to bottom


def test_an_incomplete_atomic_group_refuses_the_build(tmp_path: Path) -> None:
    """Half a box-drawing set is never written."""
    fonts = _families(tmp_path)
    (fonts / "Half").mkdir()
    build_font(fonts / "Half" / "Half-Regular.ttf", codepoints=[ord("M"), BOX_VERTICAL])
    config = _config(tmp_path, '[groups]\n"Box Drawing" = ["Half"]\n')
    status, report = _build(tmp_path, config, fonts)
    assert status == 1
    assert "atomic" in report


def test_a_missing_style_stops_the_build_unless_told_otherwise(tmp_path: Path) -> None:
    """No Bold anywhere: fail by default, nearest or synthesize on request."""
    fonts = _families(tmp_path)
    _with_bold(fonts)
    config = _config(tmp_path, '[groups]\nArrows = ["Donor"]\n')
    status, report = _build(tmp_path, config, fonts)
    assert status == 1
    assert "no Bold style" in report
    status, report = _build(tmp_path, config, fonts, on_missing="nearest")
    assert status == 0, report
    regular = _bounds(TTFont(tmp_path / "out" / "TestMono-Regular.ttf"), ARROW_UP)
    plain = _bounds(TTFont(tmp_path / "out" / "TestMono-Bold.ttf"), ARROW_UP)
    assert plain == regular  # the nearest style as it is
    status, report = _build(tmp_path, config, fonts, on_missing="synthesize")
    assert status == 0, report
    bold = _bounds(TTFont(tmp_path / "out" / "TestMono-Bold.ttf"), ARROW_UP)
    assert regular is not None
    assert bold is not None
    assert bold[2] - bold[0] > regular[2] - regular[0]  # emboldened: wider stem


def test_asking_saves_the_answer_in_the_configuration(tmp_path: Path) -> None:
    """On a terminal the choice is asked once and kept in ``[styles.<Output>]``."""
    fonts = _families(tmp_path)
    _with_bold(fonts)
    config = _config(tmp_path, '[groups]\nArrows = ["Donor"]\n')
    lines: list[str] = []
    answers = iter(["s", "s"])  # synthesize for the base and for the donor
    status = run_build(BuildOptions(config, fonts, tmp_path / "out"), say=lines.append,
                       ask=lambda _prompt: next(answers), interactive=True,
                       catalog=sample_catalog())
    assert status == 0, "\n".join(lines)
    styles = tomllib.loads(config.read_text(encoding="utf-8"))["styles"]["Bold"]
    assert styles == {"Base": "synthesize:Base-Regular.ttf",
                      "Donor": "synthesize:Donor-Regular.ttf"}
    assert _build(tmp_path, config, fonts)[0] == 0  # nothing to ask the second time


def test_an_unknown_base_family_is_reported(tmp_path: Path) -> None:
    """Refuse a configuration whose base family is not in the fonts directory."""
    fonts = _families(tmp_path)
    config = _config(tmp_path)
    config.write_text(config.read_text(encoding="utf-8").replace("Base", "Nobody"),
                      encoding="utf-8")
    status, report = _build(tmp_path, config, fonts)
    assert status == 1
    assert "Nobody" in report


def test_a_style_is_built_under_its_custom_name_and_keeps_its_slant(tmp_path: Path) -> None:
    """File, names and weight follow the custom name; the italic flag follows the style."""
    fonts = _families(tmp_path)
    build_font(fonts / "Base" / "Base-Italic.ttf", codepoints=[ord("M"), ARROW_LEFT],
               ink={ord("M"): (50, 0, 550, 700), ARROW_LEFT: (100, 300, 500, 400)},
               spec=FontSpec(names=NameSpec(family="Base", style="Italic", italic=True)))
    config = tmp_path / "font_composer.toml"
    config.write_text(
        '[output]\nfamily = "Test Mono"\nstyles = ["Regular", "Italic"]\n'
        'style-names = { Regular = "Book", Italic = "Slanted" }\n\n[cell]\nbase = "Base"\n',
        encoding="utf-8")
    status, report = _build(tmp_path, config, fonts)
    assert status == 0, report
    out = tmp_path / "out"
    assert sorted(path.name for path in out.glob("*.ttf")) == ["TestMono-Book.ttf",
                                                              "TestMono-Slanted.ttf"]
    slanted = TTFont(out / "TestMono-Slanted.ttf")
    name: Any = slanted["name"]
    assert name.getDebugName(17) == "Slanted"
    os2: Any = slanted["OS/2"]
    assert os2.usWeightClass == REGULAR_WEIGHT
    assert os2.fsSelection & 0x01  # still italic, though no longer called Italic
    assert not os2.fsSelection & 0x40
    book: Any = TTFont(out / "TestMono-Book.ttf")["OS/2"]
    assert book.fsSelection & 0x40


def test_two_styles_under_one_name_refuse_the_build(tmp_path: Path) -> None:
    """A hand-edited configuration may name two styles alike; nothing is written."""
    fonts = _families(tmp_path)
    _with_bold(fonts)
    config = tmp_path / "font_composer.toml"
    config.write_text(
        '[output]\nfamily = "Test Mono"\nstyle-names = { Bold = "Regular" }\n\n'
        '[cell]\nbase = "Base"\n', encoding="utf-8")
    status, report = _build(tmp_path, config, fonts, on_missing="nearest")
    assert status == 1
    assert "one name" in report
    assert not (tmp_path / "out").exists()


def test_a_generated_pin_draws_a_code_point_of_a_block_that_has_no_order(tmp_path: Path) -> None:
    """Honour [generated_glyphs] on its own: Basic Latin has no order, M is pinned to Donor."""
    fonts = _families(tmp_path)
    config = _config(tmp_path, '[generated_glyphs]\n"U+004D" = ["Donor"]\n')
    status, report = _build(tmp_path, config, fonts)
    assert status == 0, report
    font = TTFont(tmp_path / "out" / "TestMono-Regular.ttf")
    assert _bounds(font, ord("M")) is None  # the donor's M is empty; the base's had ink


def test_a_pin_of_a_family_that_is_gone_is_a_warning_not_a_failure(tmp_path: Path) -> None:
    """Skip a generated pin naming a missing family; a block order naming one still fails."""
    fonts = _families(tmp_path)
    config = _config(tmp_path, '[generated_glyphs]\n"U+004D" = ["Gone"]\n')
    status, report = _build(tmp_path, config, fonts)
    assert status == 0, report
    assert "Gone" in report
    config = _config(tmp_path, '[groups]\nArrows = ["Gone"]\n')
    status, report = _build(tmp_path, config, fonts)
    assert status == 1
    assert "unknown famil" in report


def test_the_build_needs_the_block_list(tmp_path: Path) -> None:
    """Say what is missing instead of building with no categories."""
    fonts = _families(tmp_path)
    config = _config(tmp_path, "")
    lines: list[str] = []
    status = run_build(BuildOptions(config, fonts, tmp_path / "out", "fail"), say=lines.append,
                       ask=lambda _prompt: "", interactive=False,
                       catalog=build_catalog([], {}))
    assert status == 1
    assert "Blocks.txt" in "\n".join(lines)
