"""Tests for font_composer.common.planner: how the glyphs of a block are fitted to the base cell."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from support import FontSpec, MetricSpec, build_font, sample_catalog

from font_composer.common.fit import CellSpec
from font_composer.common.library import FontLibrary
from font_composer.common.planner import FitTarget, plan_glyphs

if TYPE_CHECKING:
    from pathlib import Path

    from font_composer.common.library import Family

BASE = CellSpec(width=0.6, ascent=0.8, descent=-0.2)
TALL = FontSpec(metrics=MetricSpec(ascent=1200, descent=-300))  # a 1.5 em line, base is 1.0 em
RULE, ARROW, SMALL = 0x2192, 0x2190, 0x2191
SEPARATOR = 0xE0B0
ICON = 0xE900


def _donor(tmp_path: Path, ink: dict[int, tuple[int, int, int, int]]) -> Family:
    """Make one tall-celled family whose glyphs have this ink; return it."""
    folder = tmp_path / "Tall"
    folder.mkdir()
    build_font(folder / "Tall-Regular.ttf", codepoints=list(ink), spec=TALL, ink=ink)
    family = FontLibrary.scan(tmp_path).family("Tall")
    assert family is not None
    return family


def _plans(family: Family, block: str, codepoints: list[int]) -> dict:
    catalog = sample_catalog()
    group = catalog.by_id(block)
    style = family.regular_style()
    assert group is not None
    assert style is not None
    return plan_glyphs(family, group, style, codepoints, FitTarget(BASE, catalog))


def test_a_symbol_that_spans_the_cell_is_scaled_in_proportion_not_stretched(
    tmp_path: Path,
) -> None:
    """Keep the shape of an arrow whose font has a taller line than the base."""
    family = _donor(tmp_path, {RULE: (0, 500, 600, 700), SMALL: (200, 0, 400, 600)})
    plans = _plans(family, "Arrows", [RULE, SMALL])
    for plan in plans.values():
        assert plan.kind == "category"
        assert plan.sx == pytest.approx(plan.sy)


def test_every_glyph_of_a_block_gets_the_same_scale_when_none_needs_more(tmp_path: Path) -> None:
    """Shrink look-alikes together: the arrow that pokes out and the ones that do not."""
    family = _donor(tmp_path, {ARROW: (-100, 100, 700, 500), SMALL: (100, 0, 500, 700)})
    plans = _plans(family, "Arrows", [ARROW, SMALL])
    assert plans[SMALL].sx == pytest.approx(0.9)  # the floor: the whole block loses a little
    assert plans[ARROW].sx == pytest.approx(0.6 / 0.8)  # the one that still pokes out, alone
    assert plans[ARROW].residual == pytest.approx(0.0, abs=0.002)


def test_powerline_separators_still_join_their_neighbours(tmp_path: Path) -> None:
    """Fit a separator to the whole cell, as before: it must meet the next cell."""
    family = _donor(tmp_path, {SEPARATOR: (0, -300, 600, 1200), ICON: (100, 100, 500, 600)})
    plans = _plans(family, "Private Use Area", [SEPARATOR, ICON])
    assert plans[SEPARATOR].kind == "frame"
    assert plans[SEPARATOR].sy != pytest.approx(plans[SEPARATOR].sx)
    assert ICON not in plans or plans[ICON].sx == pytest.approx(plans[ICON].sy)
