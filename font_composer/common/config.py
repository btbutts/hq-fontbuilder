"""Load and save the TOML composer configuration.

``tomlkit`` reads and writes the file, so everything the console does not own
(``[output]``, ``[cell]``, ``[styles.*]``, ``[group-options.*]``, ``[glyphs]``), and every
comment and blank line, survives a save untouched. Saving is atomic: the new content
goes to a temporary file in the same directory and is renamed over the old one.

What the console writes:

* ``[groups]``: a group id -> the ordered list of families it inherits from, first
  choice first (``arrows = ["DejaVu", "FiraCode"]``). A bare string is read as a list
  of one.
* ``[glyphs]``: a code point -> the family that serves it, taking precedence over the
  order (``"U+2714" = { family = "DejaVu" }``).
* ``[styles.<Output>]``: a family -> the style file (or style name) that serves that
  output style, replacing the default rules of :mod:`font_composer.common.styles`.
* ``[server] port``: the port it last listened on, tried first the next time.

The file is meant to be hand-edited while the console runs, so :meth:`Config.update_choice`
re-reads it before applying a choice (a hand edit is never overwritten with a stale
in-memory copy), and :meth:`Config.refresh_if_changed` lets the console pick edits up.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

if TYPE_CHECKING:
    from collections.abc import Callable, MutableMapping, Sequence
    from pathlib import Path

_FileStamp = tuple[int, int]

_PORT_LIMIT = 65536

_CODE_POINT_KEY = re.compile(r"^U\+([0-9A-Fa-f]{4,6})$")
_DEFAULT_OUTPUT_STYLES = ["Regular", "Bold"]

_HEADER = """\
font-composer configuration. The web console writes [groups] (the families of each glyph
group, in inheritance order), [glyphs] (single code points pinned to a family), [styles.*]
(which style file serves an output style) and [server] (the port). Everything is yours to
edit as well, also while the console runs; comments are kept."""


class ConfigError(Exception):
    """Raised when the configuration file cannot be parsed or written."""


def _default_document(base_family: str) -> tomlkit.TOMLDocument:
    """Return the default configuration for a fresh composer.toml."""
    document = tomlkit.document()
    for line in _HEADER.splitlines():
        document.add(tomlkit.comment(line))
    document.add(tomlkit.nl())

    output = tomlkit.table()
    output.add("family", "Console Mono")
    output.add("styles", ["Regular", "Bold"])
    document.add("output", output)
    document.add(tomlkit.nl())

    cell = tomlkit.table()
    cell.add(tomlkit.comment("family that defines the cell: advance, ascent, descent"))
    cell.add("base", base_family)
    cell.add("fit", "base")
    document.add("cell", cell)
    document.add(tomlkit.nl())

    groups = tomlkit.table()
    groups.add(tomlkit.comment('group id = ["first choice", "fills the gaps", ...]'))
    groups.add(tomlkit.comment("written by the console"))
    document.add("groups", groups)
    return document


def _stamp(path: Path) -> _FileStamp | None:
    """Return ``(mtime_ns, size)`` of the file, or None when it cannot be read."""
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def _parse(path: Path) -> tomlkit.TOMLDocument:
    """Read and parse the file; raise :class:`ConfigError` with the reason on failure."""
    try:
        return tomlkit.parse(path.read_text(encoding="utf-8"))
    except (TOMLKitError, OSError, ValueError) as exc:
        message = f"cannot load {path}: {exc}"
        raise ConfigError(message) from exc


def _family_list(value: Any) -> list[str]:
    """Read a ``[groups]`` value (a string, or a list of strings) as a list of families."""
    if isinstance(value, str):
        return [str(value)] if value else []
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str) and item]
    return []


def _table(parent: MutableMapping[str, Any], key: str) -> MutableMapping[str, Any]:
    """Return a sub-table of ``parent``, creating it when missing."""
    child = parent.get(key)
    if not isinstance(child, dict):
        child = tomlkit.table()
        parent[key] = child
    return child


class Config:
    """A parsed composer.toml plus its path; the console writes only its own tables."""

    def __init__(self, path: Path, data: MutableMapping[str, Any]) -> None:
        """Hold the parsed data; use :meth:`load` instead of calling this directly."""
        self.path = path
        self.data = data
        self._loaded_stamp = _stamp(path)

    @classmethod
    def load(cls, path: Path, default_base: str = "") -> Config:
        """Load the configuration, creating a default one when the file is missing.

        ``default_base`` names the family that defines the cell in a freshly created
        configuration; it is ignored when the file already exists.
        """
        if not path.exists():
            config = cls(path, _default_document(default_base))
            config.save()
            return config
        return cls(path, _parse(path))

    def refresh_if_changed(self) -> bool:
        """Re-read the file when it changed on disk; return True when it was re-read.

        Raises :class:`ConfigError` when the changed file does not parse; the data
        held so far is then left as it was.
        """
        stamp = _stamp(self.path)
        if stamp is None or stamp == self._loaded_stamp:
            return False
        self.data = _parse(self.path)
        self._loaded_stamp = stamp
        return True

    @property
    def groups(self) -> MutableMapping[str, Any]:
        """The (possibly empty) ``[groups]`` table, created on demand."""
        groups = self.data.get("groups")
        if groups is None:
            groups = tomlkit.table()
            self.data["groups"] = groups
        if not isinstance(groups, dict):
            message = f"{self.path}: [groups] is not a table"
            raise ConfigError(message)
        return groups

    @property
    def choices(self) -> dict[str, list[str]]:
        """The inheritance order of each group that has one: group id -> families."""
        result: dict[str, list[str]] = {}
        for group, value in self.groups.items():
            families = _family_list(value)
            if families:
                result[str(group)] = families
        return result

    @property
    def base_family(self) -> str:
        """The family that defines the cell, or an empty string if unset."""
        cell = self.data.get("cell")
        if isinstance(cell, dict):
            return str(cell.get("base", ""))
        return ""

    @property
    def saved_port(self) -> int | None:
        """The console port saved by an earlier run (``[server] port``), if it is valid."""
        server = self.data.get("server")
        port = server.get("port") if isinstance(server, dict) else None
        if isinstance(port, int) and not isinstance(port, bool) and 0 < port < _PORT_LIMIT:
            return port
        return None

    @property
    def glyph_overrides(self) -> dict[int, str]:
        """The ``[glyphs]`` entries as code point -> family; unreadable entries are skipped."""
        table = self.data.get("glyphs")
        result: dict[int, str] = {}
        if not isinstance(table, dict):
            return result
        for key, value in table.items():
            match = _CODE_POINT_KEY.match(str(key))
            family = value.get("family") if isinstance(value, dict) else value
            if match and isinstance(family, str) and family:
                result[int(match.group(1), 16)] = str(family)
        return result

    @property
    def output_styles(self) -> list[str]:
        """The style names of ``[output] styles`` (Regular and Bold when unset)."""
        output = self.data.get("output")
        styles = output.get("styles") if isinstance(output, dict) else None
        names = [str(item) for item in styles if isinstance(item, str)] \
            if isinstance(styles, list) else []
        return names or list(_DEFAULT_OUTPUT_STYLES)

    @property
    def style_overrides(self) -> dict[str, dict[str, str]]:
        """The ``[styles.<Output>]`` tables: output style -> family -> file or style name."""
        table = self.data.get("styles")
        result: dict[str, dict[str, str]] = {}
        if not isinstance(table, dict):
            return result
        for style, mapping in table.items():
            if isinstance(mapping, dict):
                result[str(style)] = {str(family): str(value) for family, value in mapping.items()
                                      if isinstance(value, str) and value}
        return result

    def set_families(self, group: str, families: Sequence[str]) -> None:
        """Set the inheritance order of a group; an empty list removes the group."""
        if families:
            self.groups[group] = list(families)
        else:
            self.groups.pop(group, None)

    def set_glyph_override(self, codepoint: int, family: str | None) -> None:
        """Pin a code point to a family, or (``None``) go back to the inheritance order."""
        key = f"U+{codepoint:04X}"
        table = _table(self.data, "glyphs")
        existing = table.get(key)
        if family is None:
            if isinstance(existing, dict) and set(existing) - {"family"}:
                existing.pop("family", None)  # keep the hand-written extras (scale ...)
            else:
                table.pop(key, None)
        elif isinstance(existing, dict):
            existing["family"] = family
        else:
            entry = tomlkit.inline_table()
            entry["family"] = family
            table[key] = entry

    def set_style_override(self, style: str, family: str, value: str | None) -> None:
        """Map an output style of a family to a style file, or (``None``) clear the mapping."""
        styles = _table(self.data, "styles")
        mapping = _table(styles, style)
        if value is None:
            mapping.pop(family, None)
            if not mapping:
                styles.pop(style, None)
        else:
            mapping[family] = value

    def update(self, mutate: Callable[[Config], None]) -> None:
        """Apply a change on top of the file as it is now, and save.

        The file is re-read first so edits made by hand since the last load are kept;
        when it no longer parses, nothing is written and :class:`ConfigError` tells why.
        """
        self.refresh_if_changed()
        mutate(self)
        self.save()

    def set_port(self, port: int) -> None:
        """Save the port the console listens on, when it differs from the saved one."""
        self.refresh_if_changed()
        if self.saved_port == port:
            return
        _table(self.data, "server")["port"] = port
        self.save()

    def save(self) -> None:
        """Write the configuration atomically (temporary file plus rename)."""
        text = tomlkit.dumps(self.data)
        tmp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            tmp_path.write_text(text, encoding="utf-8")
            tmp_path.replace(self.path)
        except OSError as exc:
            message = f"cannot write {self.path}: {exc}"
            raise ConfigError(message) from exc
        self._loaded_stamp = _stamp(self.path)
