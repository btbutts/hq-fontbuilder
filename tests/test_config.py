"""Tests for font_composer.common.config: defaults, round-trips, the groups table."""

from __future__ import annotations

import tomllib
from pathlib import Path

from font_composer.common.config import Config

SAVED_PORT = 8710

HAND_EDITED = """\
[output]
family = "Console Mono"

[cell]
base = "FiraCode"
fit = "base"

[groups]
alnum = "FiraCode"

[group-options.geometric]
scale = "fit-height"
align = "center"

[glyphs]
"U+2714" = { family = "DejaVu" }

[styles.Bold]
DejaVu = "Bold"
"""


def test_default_config_created_when_missing(tmp_path: Path) -> None:
    """Create a sensible default file on first load."""
    path = tmp_path / "font_composer.toml"
    config = Config.load(path, default_base="FiraCode")
    assert path.is_file()
    assert config.data["output"]["family"] == "Console Mono"
    assert config.data["output"]["styles"] == ["Regular", "Bold"]
    assert config.data["cell"]["base"] == "FiraCode"
    assert not config.choices
    # The written file parses again.
    reloaded = tomllib.loads(path.read_text(encoding="utf-8"))
    assert reloaded == config.data


def test_round_trip_preserves_unknown_sections(tmp_path: Path) -> None:
    """Keep hand-edited sections byte-value identical after a choose and save."""
    path = tmp_path / "font_composer.toml"
    path.write_text(HAND_EDITED, encoding="utf-8")
    config = Config.load(path)
    config.update(lambda c: c.set_families("arrows", ["DejaVu"]))
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["output"] == {"family": "Console Mono"}
    assert data["cell"] == {"base": "FiraCode", "fit": "base"}
    assert data["group-options"] == {"geometric": {"scale": "fit-height", "align": "center"}}
    assert data["glyphs"] == {"U+2714": {"family": "DejaVu"}}
    assert data["styles"] == {"Bold": {"DejaVu": "Bold"}}
    assert data["groups"] == {"alnum": "FiraCode", "arrows": ["DejaVu"]}


def test_a_group_holds_an_ordered_list_and_a_bare_string_is_a_list_of_one(
    tmp_path: Path,
) -> None:
    """Keep the order the families were given in; read the old string form."""
    path = tmp_path / "font_composer.toml"
    config = Config.load(path, default_base="FiraCode")
    config.set_families("arrows", ["DejaVu", "JetBrainsMono", "FiraCode"])
    assert config.choices == {"arrows": ["DejaVu", "JetBrainsMono", "FiraCode"]}
    config.set_families("arrows", ["FiraCode", "DejaVu"])
    assert config.choices["arrows"] == ["FiraCode", "DejaVu"]
    config.set_families("arrows", [])
    assert not config.choices
    path.write_text('[groups]\nalnum = "FiraCode"\npunctuation = ["A", "B"]\n', encoding="utf-8")
    assert Config.load(path).choices == {"alnum": ["FiraCode"], "punctuation": ["A", "B"]}


def test_glyph_overrides_round_trip_in_the_documented_shape(tmp_path: Path) -> None:
    """Write ``"U+2714" = { family = "DejaVu" }``; keep hand-written extras on removal."""
    path = tmp_path / "font_composer.toml"
    path.write_text('[glyphs]\n"U+2605" = { family = "A", scale = 0.9 }\n', encoding="utf-8")
    config = Config.load(path)
    assert config.glyph_overrides == {0x2605: "A"}
    config.update(lambda c: c.set_glyph_override(0x2714, "DejaVu"))
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["glyphs"]["U+2714"] == {"family": "DejaVu"}
    assert data["glyphs"]["U+2605"] == {"family": "A", "scale": 0.9}
    config.update(lambda c: c.set_glyph_override(0x2714, None))
    config.update(lambda c: c.set_glyph_override(0x2605, None))
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert "U+2714" not in data["glyphs"]
    assert data["glyphs"]["U+2605"] == {"scale": 0.9}


def test_style_overrides_round_trip(tmp_path: Path) -> None:
    """Write ``[styles.<Output>]`` family -> file, and drop the table when it empties."""
    path = tmp_path / "font_composer.toml"
    config = Config.load(path, default_base="A")
    config.update(lambda c: c.set_style_override("Bold", "DejaVu", "DejaVuSansMono-Bold.ttf"))
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["styles"] == {"Bold": {"DejaVu": "DejaVuSansMono-Bold.ttf"}}
    assert config.style_overrides == {"Bold": {"DejaVu": "DejaVuSansMono-Bold.ttf"}}
    config.update(lambda c: c.set_style_override("Bold", "DejaVu", None))
    assert "Bold" not in tomllib.loads(path.read_text(encoding="utf-8")).get("styles", {})


def test_save_is_atomic_and_leaves_no_tmp(tmp_path: Path) -> None:
    """Leave no temporary file behind after saving."""
    path = tmp_path / "font_composer.toml"
    config = Config.load(path, default_base="FiraCode")
    config.update(lambda c: c.set_families("dingbats", ["DejaVu"]))
    assert not (tmp_path / "font_composer.toml.tmp").exists()


def test_saved_port_round_trip_keeps_the_rest(tmp_path: Path) -> None:
    """Add [server] port without touching comments or other sections."""
    path = tmp_path / "font_composer.toml"
    path.write_text("# mine\n" + HAND_EDITED, encoding="utf-8")
    config = Config.load(path)
    assert config.saved_port is None
    config.set_port(SAVED_PORT)
    assert config.saved_port == SAVED_PORT
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# mine\n")
    data = tomllib.loads(text)
    assert data["server"] == {"port": SAVED_PORT}
    assert data["groups"] == {"alnum": "FiraCode"}
    assert Config.load(path).saved_port == SAVED_PORT


def test_unusable_saved_ports_are_ignored(tmp_path: Path) -> None:
    """Treat a non-integer or out-of-range [server] port as not saved."""
    path = tmp_path / "font_composer.toml"
    for value in ('"http"', "0", "70000", "true", "-5"):
        path.write_text(f"[server]\nport = {value}\n", encoding="utf-8")
        assert Config.load(path).saved_port is None, value


def test_style_settings_and_directories_are_kept_in_the_file(tmp_path: Path) -> None:
    """Save the included styles, the switch and the two directories; resolve the paths."""
    path = tmp_path / "font_composer.toml"
    config = Config.load(path, default_base="A")
    assert config.setting("output", "styles", []) == ["Regular", "Bold"]
    assert config.setting("output", "consolidate_styles", True) is True
    assert config.directory("fonts") is None
    config.update(lambda c: c.set_setting("output", "styles", ["Regular", "Black"]))
    config.update(lambda c: c.set_setting("output", "consolidate_styles", False))
    output = tomllib.loads(path.read_text(encoding="utf-8"))["output"]
    assert output["styles"] == ["Regular", "Black"]
    assert output["consolidate_styles"] is False
    config.update(lambda c: c.set_setting("output", "consolidate_styles", None))
    assert config.setting("output", "consolidate_styles", True) is True
    config.set_directories(fonts=tmp_path / "fonts", output=Path("/elsewhere/fonts-out"))
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["fonts"]["dir"] == "fonts"  # inside the folder of the file: relative
    assert data["output"]["dir"] == "/elsewhere/fonts-out"
    assert config.directory("fonts") == (tmp_path / "fonts").resolve()
    assert config.directory("output") == Path("/elsewhere/fonts-out")
    assert config.setting("output", "family", "x") == "Console Mono"


def test_style_names_round_trip_and_the_key_goes_when_it_empties(tmp_path: Path) -> None:
    """Write ``[output] style-names`` keyed by the name the fonts give, spaces included."""
    path = tmp_path / "font_composer.toml"
    config = Config.load(path, default_base="A")
    both = {"Light Italic": "Light Oblique", "Oblique": "Italic"}
    config.update(lambda c: c.set_setting("output", "style-names", both))
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["output"]["style-names"] == both
    assert data["output"]["styles"] == ["Regular", "Bold"]  # the rest of [output] is kept
    assert config.style_names == both
    assert Config.load(path).style_names == both
    config.update(lambda c: c.set_setting("output", "style-names", {}))
    assert "style-names" not in tomllib.loads(path.read_text(encoding="utf-8"))["output"]
    assert Config.load(path).style_names == {}


def test_generated_pins_round_trip_and_replace_only_their_code_points(tmp_path: Path) -> None:
    """Write the pins as lists under a warning, and let a replacement touch only its own."""
    path = tmp_path / "font_composer.toml"
    config = Config.load(path)
    config.overlay.replace_pins([0x41, 0x42], {0x41: ["A", "B"], 0x42: ["A"]})
    config.overlay.replace_pins([0x41], {})  # drops U+0041, keeps U+0042
    config.save()
    assert Config.load(path).overlay.pins == {0x42: ["A"]}
    text = path.read_text(encoding="utf-8")
    assert "Managed by font_composer" in text
    assert tomllib.loads(text)["generated_glyphs"] == {"U+0042": ["A"]}


def test_overlay_orders_exist_only_after_they_are_stored(tmp_path: Path) -> None:
    """Keep the optional table out of the file until the user asks for it."""
    config = Config.load(tmp_path / "font_composer.toml")
    assert config.overlay.orders is None
    config.overlay.set_order("overlay:powerline", ["A"])  # no section: nothing is written
    assert config.overlay.orders is None
    config.overlay.set_orders({"overlay:powerline": ["A"]})
    config.overlay.set_order("overlay:ascii-alnum", ["B", "A"])
    assert config.overlay.orders == {"overlay:powerline": ["A"],
                                     "overlay:ascii-alnum": ["B", "A"]}
    config.overlay.set_order("overlay:powerline", [])
    assert config.overlay.orders == {"overlay:ascii-alnum": ["B", "A"]}
    config.overlay.set_orders(None)
    assert config.overlay.orders is None


def test_block_names_with_spaces_are_written_as_quoted_keys(tmp_path: Path) -> None:
    """Save the official block names as they are."""
    path = tmp_path / "font_composer.toml"
    config = Config.load(path)
    config.set_families("Latin-1 Supplement", ["A"])
    config.set_families("Greek and Coptic", ["B"])
    config.save()
    assert tomllib.loads(path.read_text(encoding="utf-8"))["groups"] == {
        "Latin-1 Supplement": ["A"], "Greek and Coptic": ["B"]}
    assert Config.load(path).choices == {"Latin-1 Supplement": ["A"], "Greek and Coptic": ["B"]}
