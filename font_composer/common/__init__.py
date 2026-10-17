"""Modules shared by the composer console, the builder and the CLI entry points.

``config`` loads and saves the TOML configuration, ``composition`` resolves a glyph group
through its inheritance order and the pins, and ``paths`` names the project's directories.
The rest is in four packages: ``unicode`` (the Unicode data files, the blocks and the
overlay categories), ``fonts`` (reading font files: the library of families, ink,
styles, ``inspect``), ``fitting`` (fitting donor glyphs to the base cell) and ``cli``
(what the commands share to present themselves on a terminal and to serve).
"""
