"""Tests for font_composer.composer.state: choices, atomic refusal, hand edits, glyphs."""

from __future__ import annotations

import os
import tomllib
from http import HTTPStatus
from pathlib import Path

from support import FontSpec, NameSpec, build_font

from font_composer.common.config import Config
from font_composer.composer.state import ConsoleState

COMMENTED = """\
# my notes
[output]
family = "Console Mono"   # the name
styles = ["Regular"]

[cell]
base = "Alpha"

[groups]
"""


def _make_state(tmp_path: Path, config_text: str = COMMENTED) -> ConsoleState:
    """Build a console over two tiny families and a configuration file."""
    fonts = tmp_path / "fonts"
    (fonts / "Alpha").mkdir(parents=True)
    (fonts / "Beta").mkdir()
    # Alpha is complete for block-elements and half complete for box-drawing.
    build_font(fonts / "Alpha" / "Alpha-Regular.ttf",
               codepoints=[ord("M"), *range(0x2500, 0x2540), *range(0x2580, 0x25A0)])
    # Beta holds a bold-only gap: Bold has an arrow that Regular lacks.
    build_font(fonts / "Beta" / "Beta-Regular.ttf", codepoints=[ord("M"), 0x2190])
    build_font(fonts / "Beta" / "Beta-Bold.ttf", codepoints=[ord("M"), 0x2190, 0x2192],
               spec=FontSpec(names=NameSpec(style="Bold", weight=700)))
    path = tmp_path / "composer.toml"
    path.write_text(config_text, encoding="utf-8")
    return ConsoleState(fonts, Config.load(path))


def test_choice_is_saved_and_bumps_the_version(tmp_path: Path) -> None:
    """Write the choice to the file, keep comments, and tell the pages to refetch."""
    state = _make_state(tmp_path)
    before = state.version
    status, payload = state.choose("arrows", "Beta")
    assert status == HTTPStatus.OK
    assert payload["choices"] == {"arrows": "Beta"}
    assert state.version == before + 1
    text = state.config.path.read_text(encoding="utf-8")
    assert "# my notes" in text
    assert '# the name' in text
    assert tomllib.loads(text)["groups"] == {"arrows": "Beta"}


def test_atomic_group_is_refused_unless_the_reference_style_is_complete(tmp_path: Path) -> None:
    """Answer 409 for half a box-drawing set; accept the complete block elements."""
    state = _make_state(tmp_path)
    status, payload = state.choose("box-drawing", "Alpha")
    assert status == HTTPStatus.CONFLICT
    assert "atomic" in payload["error"]
    assert state.config.choices == {}
    status, _payload = state.choose("block-elements", "Alpha")
    assert status == HTTPStatus.OK


def test_unknown_group_and_family_are_rejected(tmp_path: Path) -> None:
    """Answer 400 for ids the console does not know."""
    state = _make_state(tmp_path)
    assert state.choose("nonsense", "Alpha")[0] == HTTPStatus.BAD_REQUEST
    assert state.choose("arrows", "Nowhere")[0] == HTTPStatus.BAD_REQUEST


def test_hand_edits_survive_a_choice_made_afterwards(tmp_path: Path) -> None:
    """Re-read the file before writing, so a hand edit made while running is kept."""
    state = _make_state(tmp_path)
    path = state.config.path
    path.write_text(path.read_text(encoding="utf-8").replace('"Regular"', '"Regular", "Bold"'),
                    encoding="utf-8")
    later = path.stat().st_mtime_ns + 1_000_000_000
    os.utime(path, ns=(later, later))
    status, _payload = state.choose("arrows", "Beta")
    assert status == HTTPStatus.OK
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["output"]["styles"] == ["Regular", "Bold"]
    assert data["groups"] == {"arrows": "Beta"}


def test_a_hand_edit_is_seen_by_the_version_poll(tmp_path: Path) -> None:
    """Bump the version and show the new choices when the file is edited by hand."""
    state = _make_state(tmp_path)
    before = state.current_version()
    path = state.config.path
    path.write_text(path.read_text(encoding="utf-8") + 'arrows = "Beta"\n', encoding="utf-8")
    later = path.stat().st_mtime_ns + 1_000_000_000
    os.utime(path, ns=(later, later))
    assert state.current_version() == before + 1
    assert state.snapshot()["choices"] == {"arrows": "Beta"}


def test_an_invalid_hand_edit_is_reported_and_never_overwritten(tmp_path: Path) -> None:
    """Keep the broken file as it is, answer 500 to a choice, and report the error."""
    state = _make_state(tmp_path)
    path = state.config.path
    path.write_text("[groups\n", encoding="utf-8")
    later = path.stat().st_mtime_ns + 1_000_000_000
    os.utime(path, ns=(later, later))
    assert state.snapshot()["configError"] is not None
    status, payload = state.choose("arrows", "Beta")
    assert status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "cannot load" in payload["error"]
    assert path.read_text(encoding="utf-8") == "[groups\n"


def test_snapshot_flags_uneven_families(tmp_path: Path) -> None:
    """Name the groups on which a family's styles disagree."""
    snapshot = _make_state(tmp_path).snapshot()
    assert snapshot["uneven"]["Beta"] == ["arrows"]
    assert snapshot["uneven"]["Alpha"] == []


def test_glyphs_lists_only_the_present_code_points(tmp_path: Path) -> None:
    """Report, per style file, which code points of the group the font holds."""
    state = _make_state(tmp_path)
    status, payload = state.glyphs("Beta", "arrows")
    assert status == HTTPStatus.OK
    assert payload["styles"] == {"Beta-Bold.ttf": [0x2190, 0x2192], "Beta-Regular.ttf": [0x2190]}
    assert state.glyphs("Nowhere", "arrows")[0] == HTTPStatus.NOT_FOUND
    assert state.glyphs("Beta", "nonsense")[0] == HTTPStatus.BAD_REQUEST
