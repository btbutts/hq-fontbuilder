"""Load and save the TOML composer configuration.

``tomlkit`` reads and writes the file, so everything the console does not own
(``[output]``, ``[cell]``, ``[styles.*]``, ``[group-options.*]``, ``[glyphs]``), and every
comment and blank line, survives a save untouched. Saving is atomic: the new content
goes to a temporary file in the same directory and is renamed over the old one.

Besides ``[groups]`` the console writes ``[server] port``, the port it last listened
on, so that the same port is tried first the next time.

The file is meant to be hand-edited while the console runs, so :meth:`Config.update_choice`
re-reads it before applying a choice (a hand edit is never overwritten with a stale
in-memory copy), and :meth:`Config.refresh_if_changed` lets the console pick edits up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from pathlib import Path

_FileStamp = tuple[int, int]

_PORT_LIMIT = 65536

_HEADER = """\
font-composer configuration. The web console only writes the [groups] table; the other
sections are yours to edit, also while the console runs (comments are kept). The console
also keeps the port it listens on in [server], to reuse it next time."""


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
    groups.add(tomlkit.comment("group id = family folder; written by the console"))
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


class Config:
    """A parsed composer.toml plus its path; only ``[groups]`` is ever mutated."""

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

    @property
    def saved_port(self) -> int | None:
        """The console port saved by an earlier run (``[server] port``), if it is valid."""
        server = self.data.get("server")
        port = server.get("port") if isinstance(server, dict) else None
        if isinstance(port, int) and not isinstance(port, bool) and 0 < port < _PORT_LIMIT:
            return port
        return None

    def set_port(self, port: int) -> None:
        """Save the port the console listens on, when it differs from the saved one.

        Like :meth:`update_choice` it re-reads the file first, and raises
        :class:`ConfigError` when the file does not parse or cannot be written.
        """
        self.refresh_if_changed()
        if self.saved_port == port:
            return
        server = self.data.get("server")
        if not isinstance(server, dict):
            server = tomlkit.table()
            self.data["server"] = server
        server["port"] = port
        self.save()

    def choose(self, group: str, family: str | None) -> None:
        """Set (or, with ``family=None``, clear) the family chosen for a group."""
        if family is None:
            self.groups.pop(group, None)
        else:
            self.groups[group] = family

    def update_choice(self, group: str, family: str | None) -> None:
        """Apply one choice on top of the file as it is now, and save.

        The file is re-read first so edits made by hand since the last load are kept;
        when it no longer parses, nothing is written and :class:`ConfigError` tells why.
        """
        self.refresh_if_changed()
        self.choose(group, family)
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
