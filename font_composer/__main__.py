"""Command line entry point: ``python -m font_composer <command> ...``.

Commands:

* ``inspect FILE...`` — print each font's metadata and per-group coverage.
* ``compose --fonts-dir DIR --config FILE [--port N]`` — run the font-composer web
  console (watches the fonts directory, hosts the selection UI, writes the config).
* ``build`` — assemble the composed fonts (not implemented yet).

This module is a thin orchestrator: it parses the command line and delegates to
:mod:`font_composer.common` (inspect), :mod:`font_composer.composer` (compose) and
:mod:`font_composer.builder` (build).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from font_composer import __version__
from font_composer.builder.build import build
from font_composer.common.config import Config, ConfigError
from font_composer.common.groups import GROUPS, coverage
from font_composer.common.inspect import FontError, FontInfo, read_font
from font_composer.common.library import FontLibrary
from font_composer.composer.web.server import serve

if TYPE_CHECKING:
    from collections.abc import Sequence


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        prog="font_composer",
        description="Compose one monospace terminal font from per-group donors.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="print one font's coverage")
    inspect_parser.add_argument("files", nargs="+", type=Path, help="font files to read")

    compose_parser = subparsers.add_parser(
        "compose", help="run the font-composer web console (writes the .toml config)")
    compose_parser.add_argument("--fonts-dir", type=Path, required=True,
                                help="directory of family folders to watch")
    compose_parser.add_argument("--config", type=Path, required=True,
                                help="composer.toml to read and write")
    compose_parser.add_argument("--port", type=int, default=8765,
                                help="port (default 8765)")

    subparsers.add_parser("build", help="assemble the composed fonts (not implemented yet)")
    return parser.parse_args(argv)


def _print_font_info(info: FontInfo) -> None:
    """Print one font's metadata and coverage table."""
    names, metrics = info.names, info.metrics
    print(f"{info.path}")
    print(f"  family: {names.family}   style: {names.style}")
    print(f"  weight: {names.weight}  width: {names.width}  "
          f"italic: {'yes' if names.italic else 'no'}")
    print(f"  units/em: {metrics.units_per_em}  ascent: {metrics.ascent}  "
          f"descent: {metrics.descent}")
    print(f"  fixed pitch: {'yes' if metrics.is_fixed_pitch else 'no'}  "
          f"variable: {'yes' if info.is_variable else 'no'}")
    if info.named_instances:
        print(f"  named instances: {', '.join(info.named_instances)}")
    modal = info.modal_advance
    glyphs = sum(info.advance_histogram.values())
    print(f"  cell advance: {metrics.cell_advance}  (modal advance {modal} over "
          f"{glyphs} glyphs)")
    if len(info.advance_histogram) > 1:
        histogram = "  ".join(f"{advance}x{count}"
                               for advance, count in info.advance_histogram.items())
        print(f"  advance histogram: {histogram}")
    print(f"  code points: {len(info.codepoints)}")
    print("  group coverage:")
    width = max(len(group.id) for group in GROUPS)
    for group in GROUPS:
        present, total = coverage(info.codepoints, group)
        marker = " (atomic)" if group.atomic else ""
        print(f"    {group.id:<{width}}  {present:>5}/{total}{marker}")


def run_inspect(files: Sequence[Path]) -> int:
    """Print the metadata and per-group coverage of each font file."""
    status = 0
    for path in files:
        result = read_font(path)
        if isinstance(result, FontError):
            print(f"{result.path}\n  ERROR: {result.reason}")
            status = 1
        else:
            _print_font_info(result)
    return status


def run_compose(fonts_dir: Path, config_path: Path, port: int) -> int:
    """Run the font-composer web console until interrupted."""
    library = FontLibrary.scan(fonts_dir)
    default_base = ""
    for family in library.families:
        if family.regular_style() is not None:
            default_base = family.label
            break
    try:
        config = Config.load(config_path, default_base=default_base)
    except ConfigError as exc:
        print(f"font_composer: {exc}", file=sys.stderr)
        return 1
    serve(fonts_dir, config, port)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line tool and return its exit status."""
    args = parse_args(argv)
    if args.command == "inspect":
        return run_inspect(args.files)
    if args.command == "compose":
        return run_compose(args.fonts_dir, args.config, args.port)
    return build()


if __name__ == "__main__":
    sys.exit(main())
