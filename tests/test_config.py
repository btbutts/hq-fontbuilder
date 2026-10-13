"""Tests for font_composer.common.config: defaults, round-trips, the groups table."""

from __future__ import annotations

import tomllib
from pathlib import Path

from font_composer.common.config import Config

SAVED_PORT = 8710

HAND_EDITED = """\
[output]
family = "Console Mono"
styles = ["Regular", "Bold"]

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
    path = tmp_path / "composer.toml"
    config = Config.load(path, default_base="FiraCode")
    assert path.is_file()
    assert config.data["output"]["family"] == "Console Mono"
    assert config.data["output"]["styles"] == ["Regular", "Bold"]
    assert config.data["cell"]["base"] == "FiraCode"
    assert config.choices == {}
    # The written file parses again.
    reloaded = tomllib.loads(path.read_text(encoding="utf-8"))
    assert reloaded == config.data


def test_round_trip_preserves_unknown_sections(tmp_path: Path) -> None:
    """Keep hand-edited sections byte-value identical after a choose and save."""
    path = tmp_path / "composer.toml"
    path.write_text(HAND_EDITED, encoding="utf-8")
    config = Config.load(path)
    config.choose("arrows", "DejaVu")
    config.save()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["output"] == {"family": "Console Mono", "styles": ["Regular", "Bold"]}
    assert data["cell"] == {"base": "FiraCode", "fit": "base"}
    assert data["group-options"] == {"geometric": {"scale": "fit-height", "align": "center"}}
    assert data["glyphs"] == {"U+2714": {"family": "DejaVu"}}
    assert data["styles"] == {"Bold": {"DejaVu": "Bold"}}
    assert data["groups"] == {"alnum": "FiraCode", "arrows": "DejaVu"}


def test_choose_replaces_and_clears(tmp_path: Path) -> None:
    """One family per group: choosing another replaces; None clears."""
    path = tmp_path / "composer.toml"
    config = Config.load(path, default_base="FiraCode")
    config.choose("arrows", "DejaVu")
    config.choose("arrows", "JetBrainsMono")
    assert config.choices == {"arrows": "JetBrainsMono"}
    config.choose("arrows", None)
    assert config.choices == {}
    config.save()
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["groups"] == {}


def test_save_is_atomic_and_leaves_no_tmp(tmp_path: Path) -> None:
    """Leave no temporary file behind after saving."""
    path = tmp_path / "composer.toml"
    config = Config.load(path, default_base="FiraCode")
    config.choose("dingbats", "DejaVu")
    config.save()
    assert not (tmp_path / "composer.toml.tmp").exists()


def test_saved_port_round_trip_keeps_the_rest(tmp_path: Path) -> None:
    """Add [server] port without touching comments or other sections."""
    path = tmp_path / "composer.toml"
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
    path = tmp_path / "composer.toml"
    for value in ('"http"', "0", "70000", "true", "-5"):
        path.write_text(f"[server]\nport = {value}\n", encoding="utf-8")
        assert Config.load(path).saved_port is None, value
