"""Command line entry point: ``python -m font_composer <command> ...``.

Commands:

* ``inspect FILE...`` — print each font's metadata and per-block coverage.
* ``compose [--fonts-dir DIR] [--output-dir DIR] [--config FILE] [--host H] [--port N]``
  — run the font-composer web console (watches the fonts directory, hosts the
  selection UI, writes the config). Every option has a default, so ``compose`` alone
  starts it.
* ``build [--config FILE] [--fonts-dir DIR] [--output-dir DIR] [--on-missing MODE]``
  — write the composed fonts and a NOTICE file to the output directory.

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
from font_composer.builder.build import ON_MISSING, BuildOptions, run_build
from font_composer.common.cli.ports import PORT_RANGES, PortUnavailableError
from font_composer.common.cli.session import reload_process
from font_composer.common.config import Config, ConfigError
from font_composer.common.fonts.inspect import FontError, FontInfo, read_font
from font_composer.common.fonts.library import FontLibrary
from font_composer.common.paths import DEFAULT_CONFIG, DEFAULT_FONTS_DIR, DEFAULT_OUTPUT_DIR
from font_composer.common.unicode.blocks import ensure_blocks_list
from font_composer.common.unicode.groups import Catalog, coverage
from font_composer.common.unicode.names import ensure_names_list
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

_BUILD_DESCRIPTION = """\
Write one TrueType font per output style of the config ([output] styles), named
<Family>-<Style>.ttf, and a NOTICE file that names the fonts they are made of. Code
points that no glyph group serves keep the glyph of the base family ([cell] base).
"""

_BUILD_EXAMPLES = f"""\
examples:
  {_PROG} build
      build with font_composer.toml; fonts are read from and written to the
      directories the config names (fonts/ and output/ by default)
  {_PROG} build --output-dir /tmp/fonts --on-missing nearest
      write somewhere else, and never ask: use the nearest style of a family
      that lacks one
  {_PROG} build --show-proof
      then show a page that draws tables with the box glyphs of the written
      fonts, so you can see that they join (open the address it prints); a
      running console shows it, else the build serves it until you quit
"""

_COMPOSE_DESCRIPTION = """\
Run the font-composer web console. It watches the fonts directory, shows what each
family covers, and records your choices in the config. Every option is optional.
"""

_COMPOSE_EXAMPLES = f"""\
examples:
  {_PROG} compose
      watch fonts/, keep the choices in font_composer.toml, and listen on localhost
      on a free port
  {_PROG} compose --port 8800
      always use port 8800; stop with an error if it is in use
  {_PROG} compose --fonts-dir ~/Fonts --config ~/my-font.toml
      take the families from another directory, keep the choices elsewhere
  {_PROG} compose --output-dir ~/ComposedFonts
      write ~/ComposedFonts to the config as where `build` puts the fonts (the
      console never creates it; `build` does, and uses it unless told otherwise)
  {_PROG} compose --host 192.168.1.20
      listen on one interface address only (no authentication: use with care)
  {_PROG} compose --monitor
      print every request line without end (a log you can scroll back through)

keys, while it runs on a terminal:
  Q  stop the console        R  reload it (restart with the same command line)

defaults (the directories: what the config names, else these):
  --fonts-dir  {DEFAULT_FONTS_DIR}
  --output-dir {DEFAULT_OUTPUT_DIR}
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
        description="Print each font's metadata and per-block coverage.",
        epilog=f"example:\n  {_PROG} inspect fonts/DejaVu/DejaVuSansMono.ttf\n",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    inspect_parser.add_argument("files", nargs="+", type=Path, help="font files to read")

    compose_parser = subparsers.add_parser(
        "compose", help="run the font-composer web console (writes the .toml config)",
        description=_COMPOSE_DESCRIPTION,
        epilog=_COMPOSE_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    compose_parser.add_argument(
        "--fonts-dir", type=Path, default=None, metavar="DIR",
        help="directory of family folders to watch; saved to the config, which the build "
             "reads (default: the one in the config, else fonts/ next to font_composer/)")
    compose_parser.add_argument(
        "--output-dir", type=Path, default=None, metavar="DIR",
        help="where the build will write the composed fonts; the console only saves it to "
             "the config ([output] dir) and never creates it (default: the one in the "
             "config, else output/ next to font_composer/)")
    compose_parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG, metavar="FILE",
        help="the .toml to read and write (default: font_composer.toml next to font_composer/)")
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

    build_parser = subparsers.add_parser(
        "build", help="write the composed fonts described by the config",
        description=_BUILD_DESCRIPTION, epilog=_BUILD_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    build_parser.add_argument(
        "--fonts-dir", type=Path, default=None, metavar="DIR",
        help="directory of family folders; overrides [fonts] dir of the config (default: "
             "the one in the config, else fonts/ next to font_composer/)")
    build_parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG, metavar="FILE",
        help="the .toml the console wrote (default: font_composer.toml next to "
             "font_composer/)")
    build_parser.add_argument(
        "--output-dir", type=Path, default=None, metavar="DIR",
        help="where the fonts and the NOTICE file are written, created when missing; "
             "overrides [output] dir of the config (default: the one in the config, else "
             "output/ next to font_composer/)")
    build_parser.add_argument(
        "--on-missing", choices=ON_MISSING, default="ask",
        help="what to do when a family has no style of the wanted weight: ask on the "
             "terminal (default; the answer is saved in the config), use the nearest "
             "style, synthesize a bold from the nearest lighter one, or fail")
    build_parser.add_argument(
        "--show-proof", action="store_true",
        help="after the build, show a page that draws tables with the box glyphs of the "
             "written fonts, so you can see that they join. A console (compose) that is "
             "already running shows it, and the address is printed; otherwise the build "
             "serves it until you quit (Q, or Ctrl-C)")
    build_parser.add_argument(
        "--port", type=_port, default=None, metavar="PORT",
        help="with --show-proof: the port of the console that shows the page, or of the "
             "server the build starts for it (default: the port saved in the config, if a "
             "console is on it or it is free, else a free one)")
    return parser.parse_args(argv)


def _print_font_info(info: FontInfo, catalog: Catalog) -> None:
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
    print("  block coverage:")
    shown = [(group, coverage(info.codepoints, group)) for group in catalog.blocks]
    shown = [(group, cell) for group, cell in shown if cell[0]]
    width = max((len(group.id) for group, _ in shown), default=0)
    for group, (present, total) in shown:
        marker = " (atomic)" if group.atomic else ""
        print(f"    {group.id:<{width}}  {present:>5}/{total}{marker}")


def run_inspect(files: Sequence[Path]) -> int:
    """Print the metadata and per-block coverage of each font file."""
    status = 0
    catalog = Catalog.load()
    for path in files:
        result = read_font(path)
        if isinstance(result, FontError):
            print(f"{result.path}\n  ERROR: {result.reason}")
            status = 1
        else:
            _print_font_info(result, catalog)
    return status


def _first_family_with_regular(fonts_dir: Path) -> str:
    """Return the label of the first family that has a Regular cut, or an empty string."""
    for family in FontLibrary.scan(fonts_dir).families:
        if family.regular_style() is not None:
            return family.label
    return ""


def _compose_config(args: argparse.Namespace) -> tuple[Config, Path]:
    """Load (or create) the configuration and settle the fonts directory.

    The fonts and output directories are the command line's, else the configuration's,
    else the defaults; the first two are saved to the configuration, which is where the
    build looks, and so is a default the file did not name yet.
    """
    config_path: Path = args.config
    given: Path | None = args.fonts_dir
    if config_path.exists():
        config = Config.load(config_path)
    else:
        first = given or DEFAULT_FONTS_DIR
        if first == DEFAULT_FONTS_DIR:
            first.mkdir(exist_ok=True)
        config = Config.load(config_path, default_base=_first_family_with_regular(first))
    fonts_dir = given or config.directory("fonts") or DEFAULT_FONTS_DIR
    output_dir = args.output_dir or config.directory("output") or DEFAULT_OUTPUT_DIR
    config.set_directories(fonts=fonts_dir, output=output_dir)
    return config, fonts_dir


def run_compose(args: argparse.Namespace) -> int:
    """Run the font-composer web console until interrupted."""
    try:
        config, fonts_dir = _compose_config(args)
    except ConfigError as exc:
        print(f"font_composer: {exc}", file=sys.stderr)
        return 1
    if fonts_dir == DEFAULT_FONTS_DIR:
        fonts_dir.mkdir(exist_ok=True)
    if not fonts_dir.is_dir():
        print(f"font_composer: fonts directory not found: {fonts_dir}", file=sys.stderr)
        return 1
    try:
        reload = serve(fonts_dir, config, args.host, args.port, args.monitor)
    except (ConfigError, PortUnavailableError) as exc:
        print(f"font_composer: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"font_composer: cannot listen on {args.host}: {exc}", file=sys.stderr)
        return 1
    if reload:
        reload_process()
    return 0


def _warn(message: str) -> None:
    """Print a message about a file that could not be fetched."""
    print(message, file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line tool and return its exit status."""
    args = parse_args(argv)
    if args.command == "inspect":
        return run_inspect(args.files)
    if args.command in {"compose", "build"}:
        # glyph names and block categories for the console and the build; not fatal here
        ensure_names_list(say=_warn)
        ensure_blocks_list(say=_warn)
    if args.command == "compose":
        return run_compose(args)
    return run_build(BuildOptions(args.config, args.fonts_dir, args.output_dir,
                                  args.on_missing, show_proof=args.show_proof, port=args.port))


if __name__ == "__main__":
    sys.exit(main())
