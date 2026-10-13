"""Command line entry point: ``python -m font_composer <command> ...``.

Commands:

* ``inspect FILE...`` — print each font's metadata and per-group coverage.
* ``compose [--fonts-dir DIR] [--config FILE] [--host H] [--port N]`` — run the
  font-composer web console (watches the fonts directory, hosts the selection UI,
  writes the config). Every option has a default, so ``compose`` alone starts it.
* ``build`` — assemble the composed fonts (not implemented yet).

This module is a thin orchestrator: it parses the command line and delegates to
:mod:`font_composer.common` (inspect), :mod:`font_composer.composer` (compose) and
:mod:`font_composer.builder` (build).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from font_composer import __version__
from font_composer.builder.build import build
from font_composer.common.config import Config, ConfigError
from font_composer.common.groups import GROUPS, coverage
from font_composer.common.inspect import FontError, FontInfo, read_font
from font_composer.common.library import FontLibrary
from font_composer.common.paths import DEFAULT_CONFIG, DEFAULT_FONTS_DIR
from font_composer.composer.web.ports import PORT_RANGES, PortUnavailableError
from font_composer.composer.web.server import DEFAULT_HOST, serve

if TYPE_CHECKING:
    from collections.abc import Sequence


_PORT_MAX = 65535

_PROG = "python -m font_composer"

_PORT_RANGES_TEXT = " and ".join(f"{low}-{high}" for low, high in PORT_RANGES)

_MAIN_EXAMPLES = f"""\
examples:
  {_PROG} compose
      start the web console; every option has a default
  {_PROG} compose --help
      all the options of the console
  {_PROG} inspect fonts/DejaVu/DejaVuSansMono.ttf
      print one font's metadata and coverage
"""

_COMPOSE_DESCRIPTION = """\
Run the font-composer web console. It watches the fonts directory, shows what each
family covers, and records your choices in the config. Every option is optional.
"""

_COMPOSE_EXAMPLES = f"""\
examples:
  {_PROG} compose
      watch fonts/, keep the choices in composer.toml, and listen on localhost
      on a free port
  {_PROG} compose --port 8800
      always use port 8800; stop with an error if it is in use
  {_PROG} compose --fonts-dir ~/Fonts --config ~/my-font.toml
      take the families from another directory, keep the choices elsewhere
  {_PROG} compose --host 192.168.1.20
      listen on one interface address only (no authentication: use with care)
  {_PROG} compose --monitor
      print every request line without end (a log you can scroll back through)

keys, while it runs on a terminal:
  Q  stop the console        R  reload it (restart with the same command line)

defaults:
  --fonts-dir  {DEFAULT_FONTS_DIR}
  --config     {DEFAULT_CONFIG}
  --host       {DEFAULT_HOST}, which is both 127.0.0.1 and ::1
  --port       the port saved in the config if it is free; else the first free one
               of {_PORT_RANGES_TEXT}, in steps of 5 (the last digit is 0 or 5).
               The port in use is saved in the config for next time.
"""


def _port(text: str) -> int:
    """Parse a TCP port number for argparse."""
    try:
        value = int(text)
    except ValueError:
        value = 0
    if not 0 < value <= _PORT_MAX:
        message = f"{text!r} is not a port number (1-{_PORT_MAX})"
        raise argparse.ArgumentTypeError(message)
    return value


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(
        prog=_PROG,
        description="Compose one monospace terminal font from per-group donors.",
        epilog=_MAIN_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect", help="print one font's coverage",
        description="Print each font's metadata and per-group coverage.",
        epilog=f"example:\n  {_PROG} inspect fonts/DejaVu/DejaVuSansMono.ttf\n",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    inspect_parser.add_argument("files", nargs="+", type=Path, help="font files to read")

    compose_parser = subparsers.add_parser(
        "compose", help="run the font-composer web console (writes the .toml config)",
        description=_COMPOSE_DESCRIPTION,
        epilog=_COMPOSE_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    compose_parser.add_argument(
        "--fonts-dir", type=Path, default=DEFAULT_FONTS_DIR, metavar="DIR",
        help="directory of family folders to watch (default: fonts/ next to font_composer/)")
    compose_parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG, metavar="FILE",
        help="the .toml to read and write (default: composer.toml next to font_composer/)")
    compose_parser.add_argument(
        "--host", default=DEFAULT_HOST, metavar="HOST",
        help=f"address or name to listen on (default: {DEFAULT_HOST}, which is both "
             "127.0.0.1 and ::1; the console has no authentication)")
    compose_parser.add_argument(
        "--monitor", action="store_true",
        help="print every request line, as it comes and without end, instead of the "
             "scrolling tail of the last few (what a terminal gets by default)")
    compose_parser.add_argument(
        "--port", type=_port, default=None, metavar="PORT",
        help="port to listen on (default: the port saved in the config if free, else "
             "a free one is chosen; an error if PORT is in use)")

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


def _first_family_with_regular(fonts_dir: Path) -> str:
    """Return the label of the first family that has a Regular cut, or an empty string."""
    for family in FontLibrary.scan(fonts_dir).families:
        if family.regular_style() is not None:
            return family.label
    return ""


def _reload() -> None:
    """Replace this process with a new one run with the same command line."""
    os.execv(sys.executable, [sys.executable, "-m", "font_composer", *sys.argv[1:]])


def run_compose(
    fonts_dir: Path, config_path: Path, host: str, port: int | None, *, monitor: bool = False,
) -> int:
    """Run the font-composer web console until interrupted."""
    if fonts_dir == DEFAULT_FONTS_DIR:
        fonts_dir.mkdir(exist_ok=True)
    if not fonts_dir.is_dir():
        print(f"font_composer: fonts directory not found: {fonts_dir}", file=sys.stderr)
        return 1
    # The base family of a new configuration is only needed (and the scan only paid
    # for) when the file does not exist yet.
    default_base = "" if config_path.exists() else _first_family_with_regular(fonts_dir)
    try:
        config = Config.load(config_path, default_base=default_base)
        reload = serve(fonts_dir, config, host, port, monitor)
    except (ConfigError, PortUnavailableError) as exc:
        print(f"font_composer: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"font_composer: cannot listen on {host}: {exc}", file=sys.stderr)
        return 1
    if reload:
        _reload()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line tool and return its exit status."""
    args = parse_args(argv)
    if args.command == "inspect":
        return run_inspect(args.files)
    if args.command == "compose":
        return run_compose(args.fonts_dir, args.config, args.host, args.port,
                           monitor=args.monitor)
    return build()


if __name__ == "__main__":
    sys.exit(main())
