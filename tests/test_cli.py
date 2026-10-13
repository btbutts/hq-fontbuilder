"""Tests for font_composer.__main__: defaults, help text and the busy-port error."""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING

import pytest

from font_composer.__main__ import main, parse_args
from font_composer.common.paths import DEFAULT_CONFIG, DEFAULT_FONTS_DIR, PROJECT_ROOT

if TYPE_CHECKING:
    from pathlib import Path


def test_compose_needs_no_options() -> None:
    """Start with the fonts/ and composer.toml next to the font_composer package."""
    args = parse_args(["compose"])
    assert args.fonts_dir == DEFAULT_FONTS_DIR == PROJECT_ROOT / "fonts"
    assert args.config == DEFAULT_CONFIG == PROJECT_ROOT / "composer.toml"
    assert args.host == "localhost"
    assert args.port is None
    assert (PROJECT_ROOT / "font_composer").is_dir()


def test_compose_help_has_examples(capsys: pytest.CaptureFixture[str]) -> None:
    """Show examples and the defaults in the help."""
    with pytest.raises(SystemExit):
        parse_args(["compose", "--help"])
    out = capsys.readouterr().out
    assert "examples:" in out
    assert "python -m font_composer compose --port 8800" in out
    assert "18700-19000" in out


def test_port_must_be_a_port_number() -> None:
    """Reject text and out-of-range values for --port."""
    for value in ("abc", "0", "70000"):
        with pytest.raises(SystemExit):
            parse_args(["compose", "--port", value])


def test_requested_port_in_use_exits_with_a_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Report a taken --port and start nothing."""
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        status = main(["compose", "--fonts-dir", str(fonts),
                       "--config", str(tmp_path / "c.toml"), "--port", str(port)])
    assert status == 1
    err = capsys.readouterr().err
    assert f"port {port} is already in use" in err
    assert "drop --port" in err


def test_missing_fonts_dir_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Say so when --fonts-dir does not exist (only the default one is created)."""
    status = main(["compose", "--fonts-dir", str(tmp_path / "nope"),
                   "--config", str(tmp_path / "c.toml")])
    assert status == 1
    assert "fonts directory not found" in capsys.readouterr().err
