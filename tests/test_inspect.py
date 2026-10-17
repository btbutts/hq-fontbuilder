"""Tests for font_composer.common.fonts.inspect: metadata and the error path."""

from __future__ import annotations

from pathlib import Path

from support import FontSpec, MetricSpec, NameSpec, build_font

from font_composer.common.fonts.inspect import (
    FontError,
    FontInfo,
    FontMetrics,
    FontNames,
    read_font,
)

SPEC = FontSpec(names=NameSpec(family="Specimen Mono", style="Book", weight=450),
                metrics=MetricSpec(upm=2048, ascent=1901, descent=-483, advance=1233))


def test_metadata(tmp_path: Path) -> None:
    """Read family, style, weight, metrics and the cmap of a tiny font."""
    path = build_font(tmp_path / "test.ttf", codepoints=[0x41, 0x2500, ord("M")], spec=SPEC)
    result = read_font(path)
    assert isinstance(result, FontInfo)
    assert result.names == FontNames(family="Specimen Mono", style="Book",
                                     weight=450, width=5, italic=False)
    assert result.metrics == FontMetrics(units_per_em=2048, ascent=1901, descent=-483,
                                         is_fixed_pitch=True, cell_advance=1233)
    assert not result.is_variable
    assert not result.named_instances
    assert result.codepoints == frozenset({0x41, 0x2500, ord("M")})


def test_italic_and_proportional_flags(tmp_path: Path) -> None:
    """Read the italic bit and a cleared fixed-pitch flag."""
    spec = FontSpec(names=NameSpec(italic=True), metrics=MetricSpec(fixed=False))
    path = build_font(tmp_path / "italic.ttf", codepoints=[0x41], spec=spec)
    result = read_font(path)
    assert isinstance(result, FontInfo)
    assert result.names.italic
    assert not result.metrics.is_fixed_pitch


def test_an_oblique_that_only_sets_the_italic_angle_is_italic(tmp_path: Path) -> None:
    """Count post.italicAngle as slant, as obliques often set nothing else."""
    spec = FontSpec(names=NameSpec(angle_only=True))
    path = build_font(tmp_path / "oblique.ttf", codepoints=[0x41], spec=spec)
    result = read_font(path)
    assert isinstance(result, FontInfo)
    assert result.names.italic


def test_cell_advance_falls_back_to_modal(tmp_path: Path) -> None:
    """Use the modal advance when the font has no ``M`` glyph."""
    spec = FontSpec(metrics=MetricSpec(advance=500))
    codepoints = [0x2500, 0x2501]
    path = build_font(tmp_path / "nom.ttf", codepoints=codepoints, spec=spec)
    result = read_font(path)
    assert isinstance(result, FontInfo)
    assert result.metrics.cell_advance == spec.metrics.advance
    assert result.modal_advance == spec.metrics.advance
    # Only cmap-reachable glyphs count, so .notdef is absent.
    assert result.advance_histogram == {spec.metrics.advance: len(codepoints)}


def test_corrupt_file_is_an_error_with_reason(tmp_path: Path) -> None:
    """Return a FontError carrying the reason for a non-font file."""
    path = tmp_path / "broken.ttf"
    path.write_bytes(b"this is not a font")
    result = read_font(path)
    assert isinstance(result, FontError)
    assert result.path == path
    assert "TTLibError" in result.reason


def test_missing_file_is_an_error(tmp_path: Path) -> None:
    """Return a FontError for a file that does not exist."""
    result = read_font(tmp_path / "missing.ttf")
    assert isinstance(result, FontError)
    assert "FileNotFoundError" in result.reason
