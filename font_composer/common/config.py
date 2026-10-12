"""Load and save the TOML composer configuration.

``tomllib`` reads the file; a small writer writes it back. The parsed dictionary is
kept as-is and the console only ever mutates the ``[groups]`` table, so hand-edited
sections (``output``, ``cell``, ``styles.*``, ``group-options.*``, ``glyphs``)
round-trip untouched. Comments are not preserved. Saving is atomic: the new content
goes to a temporary file in the same directory and is renamed over the old one.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Raised when the configuration file cannot be parsed or written."""


def _toml_value(value: Any) -> str:
    """Render one TOML value (string, number, boolean, list or inline table)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        items = ", ".join(f"{_toml_key(key)} = {_toml_value(item)}" for key, item in value.items())
        return "{ " + items + " }"
    message = f"cannot write TOML value of type {type(value).__name__}: {value!r}"
    raise ConfigError(message)


def _toml_key(key: str) -> str:
    """Quote a TOML key when it is not a bare key."""
    if key and all(char.isalnum() or char in "-_" for char in key):
        return key
    return _toml_value(key)


def _emit_table(lines: list[str], prefix: list[str], table: dict[str, Any]) -> None:
    """Append one table's key/value lines and recurse into sub-tables."""
    scalars = [(key, value) for key, value in table.items() if not isinstance(value, dict)]
    sub_tables = [(key, value) for key, value in table.items() if isinstance(value, dict)]
    for key, value in scalars:
        lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
    for key, value in sub_tables:
        if lines and lines[-1]:
            lines.append("")
        lines.append(f"[{'.'.join([*prefix, _toml_key(key)])}]")
        _emit_table(lines, [*prefix, key], value)


def dumps(data: dict[str, Any]) -> str:
    """Serialize a parsed configuration dictionary to TOML text."""
    lines: list[str] = []
    _emit_table(lines, [], data)
    return "\n".join(lines) + "\n"


def default_config(base_family: str) -> dict[str, Any]:
    """Return the default configuration dictionary for a fresh composer.toml."""
    return {
        "output": {"family": "Console Mono", "styles": ["Regular", "Bold"]},
        "cell": {"base": base_family, "fit": "base"},
        "groups": {},
    }


class Config:
    """A parsed composer.toml plus its path; only ``[groups]`` is ever mutated."""

    def __init__(self, path: Path, data: dict[str, Any]) -> None:
        """Hold the parsed data; use :meth:`load` instead of calling this directly."""
        self.path = path
        self.data = data

    @classmethod
    def load(cls, path: Path, default_base: str = "") -> Config:
        """Load the configuration, creating a default one when the file is missing.

        ``default_base`` names the family that defines the cell in a freshly created
        configuration; it is ignored when the file already exists.
        """
        if not path.exists():
            config = cls(path, default_config(default_base))
            config.save()
            return config
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except (tomllib.TOMLDecodeError, OSError) as exc:
            message = f"cannot load {path}: {exc}"
            raise ConfigError(message) from exc
        if not isinstance(data, dict):
            message = f"cannot load {path}: top level is not a table"
            raise ConfigError(message)
        return cls(path, data)

    @property
    def groups(self) -> dict[str, Any]:
        """The (possibly empty) ``[groups]`` table, created on demand."""
        groups = self.data.setdefault("groups", {})
        if not isinstance(groups, dict):
            message = f"{self.path}: [groups] is not a table"
            raise ConfigError(message)
        return groups

    @property
    def choices(self) -> dict[str, str]:
        """The current group -> family choices as plain strings."""
        return {str(group): str(family) for group, family in self.groups.items()}

    @property
    def base_family(self) -> str:
        """The family that defines the cell, or an empty string if unset."""
        cell = self.data.get("cell")
        if isinstance(cell, dict):
            return str(cell.get("base", ""))
        return ""

    def choose(self, group: str, family: str | None) -> None:
        """Set (or, with ``family=None``, clear) the family chosen for a group."""
        if family is None:
            self.groups.pop(group, None)
        else:
            self.groups[group] = family

    def save(self) -> None:
        """Write the configuration atomically (temporary file plus rename)."""
        text = dumps(self.data)
        tmp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            tmp_path.write_text(text, encoding="utf-8")
            tmp_path.replace(self.path)
        except OSError as exc:
            message = f"cannot write {self.path}: {exc}"
            raise ConfigError(message) from exc
