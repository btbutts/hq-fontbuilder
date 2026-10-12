"""Tests for the fonts-dir scan (common.library) and the console matrix (composer.state)."""

from __future__ import annotations

from pathlib import Path

from support import FontSpec, NameSpec, build_font

from font_composer.common.groups import GROUPS_BY_ID
from font_composer.common.library import REGULAR_WEIGHT, FontLibrary
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


def test_coverage_is_the_union_across_styles(tmp_path: Path) -> None:
    """Complete a group in the family cell even when no single style has it all."""
    library = FontLibrary.scan(_make_fonts_dir(tmp_path))
    matrix = coverage_matrix(library)
    box_drawing = GROUPS_BY_ID["box-drawing"]
    assert matrix["Alpha"]["box-drawing"] == (box_drawing.total,) * 2
    assert matrix["Beta"]["box-drawing"] == (0, box_drawing.total)
    # Per-style detail stays partial: half the group each.
    alpha = library.family("Alpha")
    assert alpha is not None
    for style in alpha.styles:
        assert style.group_coverage["box-drawing"] == (box_drawing.total // 2,
                                                       box_drawing.total)
    assert full_coverage_families(library, box_drawing) == ["Alpha"]


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
