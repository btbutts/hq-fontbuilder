"""Tests for the fonts-dir scan (common.fonts.library) and the console matrix (composer.state)."""

from __future__ import annotations

from pathlib import Path

from support import FontSpec, NameSpec, build_font, sample_catalog

from font_composer.common.fonts.library import REGULAR_WEIGHT, FontLibrary
from font_composer.composer.state import coverage_matrix, full_coverage_families


def _make_fonts_dir(tmp_path: Path) -> Path:
    """Create two family folders: one with two styles, one with a corrupt file."""
    fonts = tmp_path / "fonts"
    alpha = fonts / "Alpha"
    alpha.mkdir(parents=True)
    # Regular covers the first half of box-drawing, Bold the rest; the union is full.
    build_font(alpha / "Alpha-Regular.ttf",
               codepoints=[*range(0x2500, 0x2540), ord("M")], spec=FontSpec())
    build_font(alpha / "Alpha-Bold.ttf",
               codepoints=[*range(0x2540, 0x2580), ord("M")],
               spec=FontSpec(names=NameSpec(weight=700)))
    beta = fonts / "Beta"
    beta.mkdir()
    build_font(beta / "Beta-Regular.ttf", codepoints=[0x41, ord("M")], spec=FontSpec())
    (beta / "Beta-Broken.ttf").write_bytes(b"junk")
    return fonts


def test_family_scan_and_labels(tmp_path: Path) -> None:
    """Use folder names as family labels and collect every style file."""
    library = FontLibrary.scan(_make_fonts_dir(tmp_path))
    assert [family.label for family in library.families] == ["Alpha", "Beta"]
    alpha = library.family("Alpha")
    assert alpha is not None
    assert [style.file_name for style in alpha.styles] == [
        "Alpha-Bold.ttf", "Alpha-Regular.ttf",
    ]
    regular = alpha.regular_style()
    assert regular is not None
    assert regular.info.names.weight == REGULAR_WEIGHT


def test_coverage_is_that_of_the_reference_style(tmp_path: Path) -> None:
    """Judge a family by one style file: no union that no single file holds."""
    library = FontLibrary.scan(_make_fonts_dir(tmp_path))
    catalog = sample_catalog()
    box_drawing = catalog.by_id("Box Drawing")
    assert box_drawing is not None
    matrix = coverage_matrix(library, catalog.blocks)
    # Regular has half of box drawing and Bold the other half: the family is not
    # complete, although the union of its files would be.
    assert matrix["Alpha"]["Box Drawing"] == (box_drawing.total // 2, box_drawing.total)
    assert matrix["Beta"]["Box Drawing"] == (0, box_drawing.total)
    assert full_coverage_families(library, box_drawing) == []
    alpha = library.family("Alpha")
    assert alpha is not None
    assert alpha.uneven_groups(catalog.blocks) == {"Box Drawing"}
    beta = library.family("Beta")
    assert beta is not None
    assert beta.uneven_groups(catalog.blocks) == frozenset()


def test_reference_style_is_the_upright_cut_nearest_regular(tmp_path: Path) -> None:
    """Prefer upright over italic, and the weight nearest 400 over the first file."""
    family = tmp_path / "fonts" / "Gamma"
    family.mkdir(parents=True)
    for name, weight, italic in (("A-Bold", 700, False), ("B-Italic", 400, True),
                                 ("C-Light", 300, False), ("D-Medium", 500, False)):
        build_font(family / f"{name}.ttf", codepoints=[ord("M")],
                   spec=FontSpec(names=NameSpec(weight=weight, italic=italic)))
    gamma = FontLibrary.scan(tmp_path / "fonts").family("Gamma")
    assert gamma is not None
    reference = gamma.regular_style()
    assert reference is not None
    assert reference.file_name == "C-Light.ttf"  # 300 and 500 tie; the first file wins


def test_unreadable_fonts_are_surfaced(tmp_path: Path) -> None:
    """List files that fail to read, with the reason; never skip them silently."""
    library = FontLibrary.scan(_make_fonts_dir(tmp_path))
    assert len(library.problems) == 1
    problem = library.problems[0]
    assert problem.path.name == "Beta-Broken.ttf"
    assert "TTLibError" in problem.reason
    beta = library.family("Beta")
    assert beta is not None
    assert len(beta.errors) == 1


def test_missing_fonts_dir_scans_empty(tmp_path: Path) -> None:
    """Scan a nonexistent directory into an empty library rather than failing."""
    library = FontLibrary.scan(tmp_path / "nowhere")
    assert not library.families
    assert not library.problems
