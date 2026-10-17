"""Build mode: write the composed fonts described by font_composer.toml.

The pipeline, once per run and then once per output style:

1. resolve every glyph group through its inheritance order and the ``[glyphs]`` pins
   (:mod:`font_composer.common.composition`), refusing an atomic group that is not whole;
2. choose the style file of every donor family (and of the base family) for the output
   style, asking what to do about a missing weight (:mod:`font_composer.builder.donors`);
3. draw the glyphs, fitted as the console previews them, over the base font's own
   (:mod:`font_composer.builder.assemble`);
4. reopen what was written and verify it (:mod:`font_composer.builder.verify`);
5. write a ``NOTICE`` file naming the fonts the result is made of.

Code points that no group serves keep the base font's glyph.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

from fontTools.ttLib import TTFont

from font_composer.builder.assemble import (
    BuiltFont,
    Naming,
    StyleBuild,
    Wanted,
    build_style,
)
from font_composer.builder.donors import (
    BuildStopError,
    Decision,
    Donor,
    Gap,
    override_text,
    resolve_donor,
    synthesize_start,
)
from font_composer.builder.proof import ProofFont
from font_composer.builder.verify import verify_font
from font_composer.common.composition import resolve_group
from font_composer.common.config import DEFAULT_STYLES, Config, ConfigError
from font_composer.common.fonts.library import FontLibrary
from font_composer.common.fonts.styles import output_styles, parse_style_name, same_style_name
from font_composer.common.paths import DEFAULT_FONTS_DIR, DEFAULT_OUTPUT_DIR
from font_composer.common.unicode.groups import Catalog
from font_composer.composer.web import proof

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from font_composer.common.fonts.library import Family, StyleEntry
    from font_composer.common.unicode.groups import GlyphGroup

ON_MISSING = ("ask", "nearest", "synthesize", "fail")
DEFAULT_FAMILY = "Console Mono"
_RESERVED = "reserved font name"


@dataclass(frozen=True)
class BuildOptions:
    """The command line of a build.

    ``fonts_dir`` and ``output_dir`` are overrides: unset, the configuration file's
    ``[fonts] dir`` and ``[output] dir`` decide, and the defaults next to the package
    are the last resort.
    """

    config_path: Path
    fonts_dir: Path | None = None
    output_dir: Path | None = None
    on_missing: str = "ask"
    #: after the build, show a page that draws the box glyphs of the written fonts
    show_proof: bool = False
    #: the port for that page when the build serves it itself (None: as the console chooses)
    port: int | None = None


@dataclass
class Plan:
    """What the configuration asks for, resolved against the scanned fonts."""

    catalog: Catalog
    wanted: dict[int, Wanted] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _pins_in(
    group: GlyphGroup, pins: Mapping[int, list[str]], library: FontLibrary, plan: Plan,
) -> dict[int, tuple[str, ...]]:
    """Return the generated pins of a block; a family that is gone is dropped with a warning."""
    here: dict[int, tuple[str, ...]] = {}
    for codepoint, families in pins.items():
        if not group.contains(codepoint):
            continue
        known = tuple(label for label in families if library.family(label) is not None)
        if len(known) < len(families):
            gone = ", ".join(sorted(set(families) - set(known)))
            plan.warnings.append(f"U+{codepoint:04X}: generated pin names {gone}, which is "
                                 "not in the fonts directory")
        if known:
            here[codepoint] = known
    return here


def plan_wanted(config: Config, library: FontLibrary, catalog: Catalog) -> Plan:
    """Resolve every block of the configuration into the code points it serves."""
    plan = Plan(catalog)
    overrides = config.glyph_overrides
    choices = config.choices
    pins = config.overlay.pins
    for group in catalog.blocks:
        order = choices.get(group.id, [])
        here = _pins_in(group, pins, library, plan)
        if not order and not here:
            continue
        unknown = [label for label in order if library.family(label) is None]
        if unknown:
            plan.errors.append(f"{group.id}: unknown famil{'ies' if len(unknown) > 1 else 'y'} "
                               f"{', '.join(unknown)}")
            continue
        composition = resolve_group(group, order, library, overrides, here)
        sources = {glyph.source for glyph in composition.glyphs}
        if group.atomic and composition.glyphs:
            if len(sources) > 1:
                plan.errors.append(f"{group.id} is atomic but comes from {sorted(sources)}")
                continue
            if composition.missing:
                plan.errors.append(f"{group.id} is atomic but {composition.missing} of its "
                                   f"{group.total} code points are missing")
                continue
        for glyph in composition.glyphs:
            rest = tuple(label for label in glyph.candidates if label != glyph.source)
            plan.wanted[glyph.codepoint] = Wanted(
                glyph.codepoint, group, (glyph.source, *rest), glyph.overridden)
        plan.warnings.extend(
            f"U+{item.codepoint:04X}: pin to {item.family} ignored ({item.reason})"
            for item in composition.invalid_overrides)
    return plan


def _describe_gap(gap: Gap, say: Callable[[str], None]) -> list[StyleEntry]:
    """Print what is missing and the files of the family; return them, lightest first."""
    family, target = gap.family, gap.target
    wanted = (f"weight {target.weight}, {'italic' if target.italic else 'upright'}"
              if target is not None else "style not recognised")
    say(f"\n{family.display_name} ({family.label}) has no {gap.output} style ({wanted}).")
    say(f"  {gap.reason}")
    files = sorted(family.styles, key=lambda style: style.info.names.weight)
    for index, style in enumerate(files, start=1):
        names = style.info.names
        say(f"  {index}) use {style.file_name} as it is "
            f"({names.style}, weight {names.weight}{', italic' if names.italic else ''})"
            f"{'  <- nearest' if style is gap.nearest else ''}")
    return files


def _prompt_decision(
    gap: Gap, say: Callable[[str], None], ask: Callable[[str], str],
) -> Decision | None:
    """Ask on the terminal what to do about a missing style."""
    files = _describe_gap(gap, say)
    start = synthesize_start(gap.family, gap.target)
    can_synthesize = (start is not None and gap.target is not None
                      and start.info.names.weight < gap.target.weight)
    if can_synthesize and start is not None:
        say(f"  s) synthesize {gap.output} from {start.file_name} (its outline emboldened)")
    say("  q) stop the build")
    default = files.index(gap.nearest) + 1 if gap.nearest in files else None
    hint = f" (default {default})" if default else ""
    while True:
        answer = ask(f"Choose [number{', s' if can_synthesize else ''}, q]{hint}: ")
        answer = answer.strip().lower() or (str(default) if default else "")
        if answer == "q":
            return None
        if answer == "s" and can_synthesize and start is not None:
            return Decision(start, synthesize=True)
        if answer.isdigit() and 1 <= int(answer) <= len(files):
            return Decision(files[int(answer) - 1])
        say("  not one of the choices")


def make_decider(
    options: BuildOptions, config: Config, say: Callable[[str], None],
    ask: Callable[[str], str], *, interactive: bool,
) -> Callable[[Gap], Decision | None]:
    """Return the function that settles a missing style as ``--on-missing`` says."""

    def decide(gap: Gap) -> Decision | None:
        mode = options.on_missing
        if mode == "ask" and not interactive:
            name = gap.family.display_name
            say(f"  {name}: no {gap.output} style ({gap.reason}); not a terminal, "
                f"so not asking. Set [styles.{gap.output}] {gap.family.label} in the "
                "configuration, or pass --on-missing nearest|synthesize.")
            return None
        if mode == "ask":
            decision = _prompt_decision(gap, say, ask)
            if decision is not None:
                text = override_text(decision)
                config.update(lambda cfg: cfg.set_style_override(gap.output, gap.family.label,
                                                                 text))
                say(f"  saved: [styles.{gap.output}] {gap.family.label} = {text!r}")
            return decision
        if mode == "synthesize":
            start = synthesize_start(gap.family, gap.target)
            if (start is not None and gap.target is not None
                    and start.info.names.weight < gap.target.weight):
                return Decision(start, synthesize=True)
        if mode in {"nearest", "synthesize"} and gap.nearest is not None:
            return Decision(gap.nearest)
        return None

    return decide


def _text(font: TTFont, name_id: int) -> str:
    table: Any = font["name"]
    value = table.getDebugName(name_id)
    return str(value).strip() if value else ""


def _file_notice(entry: StyleEntry) -> tuple[list[str], bool]:
    """Return the NOTICE lines of one font file, and whether it names a Reserved Font Name."""
    font = TTFont(entry.info.path, fontNumber=0, lazy=True)
    try:
        texts = (("copyright", _text(font, 0)), ("licence", _text(font, 13)),
                 ("url", _text(font, 14)))
    finally:
        font.close()
    lines = [f"    - {entry.file_name}"]
    lines.extend(f"        {title}: {' '.join(text.split())}" for title, text in texts if text)
    reserved = any(_RESERVED in text.lower() for title, text in texts if title != "url")
    return lines, reserved


def _notice(
    family_name: str, used: dict[str, set[str]], library: FontLibrary, config: Config,
    groups_of: dict[str, set[str]],
) -> tuple[str, list[str]]:
    """Build the NOTICE text, and warnings about licences that need a look."""
    warnings: list[str] = []
    lines = [family_name, "",
             "This font family was composed by font-composer. Every glyph comes from one of",
             "the fonts below and stays under the licence of that font. Check each licence",
             "(and any Reserved Font Name) before distributing the result.", ""]
    for label in sorted(used):
        family: Family | None = library.family(label)
        if family is None:
            continue
        role = ["base: cell, metrics and every glyph not served by a group"
                ] if label == config.base_family else []
        if groups_of.get(label):
            role.append("groups: " + ", ".join(sorted(groups_of[label])))
        lines.extend([f"* {family.display_name} (folder {label})", "    " + "; ".join(role)])
        for entry in (style for style in family.styles if style.file_name in used[label]):
            file_lines, reserved = _file_notice(entry)
            lines.extend(file_lines)
            if reserved:
                warnings.append(f"{entry.file_name} mentions a Reserved Font Name: the composed "
                                "font may not keep the name of that font; check its licence")
        lines.append("")
    return "\n".join(lines), warnings


def _report(
    built: BuiltFont, errors: list[str], warnings: list[str], say: Callable[[str], None],
) -> None:
    """Print what one output style came to."""
    counts: dict[str, int] = {}
    for label in built.layout.drawn_from.values():
        counts[label] = counts.get(label, 0) + 1
    kinds: dict[str, int] = {}
    for fit in built.plans.values():
        if not fit.identity:
            kinds[fit.kind] = kinds.get(fit.kind, 0) + 1
    say(f"\n{built.style}: {built.path}")
    say(f"  {len(built.layout.cmap)} code points; {len(built.layout.drawn_from)} from donors "
        f"({', '.join(f'{label} {count}' for label, count in sorted(counts.items()))})")
    if kinds:
        say("  fitted: " + ", ".join(f"{kind} {count}" for kind, count in sorted(kinds.items())))
    for note in built.used_files.values():
        say(f"  {note}")
    for text in warnings:
        say(f"  warning: {text}")
    for text in errors:
        say(f"  ERROR: {text}")


def family_names(library: FontLibrary, labels: set[str]) -> list[str]:
    """Return the display names of the families a build used."""
    names = []
    for label in labels:
        family = library.family(label)
        names.append(family.display_name if family is not None else label)
    return sorted(names)


def _resolve_donors(
    config: Config, library: FontLibrary, labels: set[str],
    decide: Callable[[Gap], Decision | None],
) -> dict[str, dict[str, Donor]]:
    """Return, per output style, the donor of every family that is used."""
    result: dict[str, dict[str, Donor]] = {}
    included = config.setting("output", "styles", list(DEFAULT_STYLES))
    consolidate = config.setting("output", "consolidate_styles", True)
    for style in output_styles(library, included, consolidate=consolidate):
        overrides = config.style_overrides.get(style, {})
        donors: dict[str, Donor] = {}
        for label in sorted(labels):
            family = library.family(label)
            if family is not None:
                donors[label] = resolve_donor(family, style, overrides.get(label), decide)[0]
        result[style] = donors
    return result


@dataclass
class _Run:
    """What the output styles of one build share."""

    options: BuildOptions
    config: Config
    library: FontLibrary
    plan: Plan
    say: Callable[[str], None]
    copyright_line: str = ""
    notice_warnings: list[str] = field(default_factory=list)


def _write_style(run: _Run, style: str, donors: dict[str, Donor]) -> Path | None:
    """Build, verify and report one output style; return the file written, None if it failed."""
    naming = Naming(run.config.style_names.get(style, style), parse_style_name(style),
                    run.config.setting("output", "family", DEFAULT_FAMILY),
                    run.options.output_dir or DEFAULT_OUTPUT_DIR, run.copyright_line)
    fit_to_base = run.config.setting("cell", "fit", "base") == "base"
    build = StyleBuild(naming, run.library, donors[run.config.base_family], donors,
                       run.plan.wanted, run.plan.catalog, fit_to_base=fit_to_base)
    built = build_style(build)
    built.used_files = {label: f"{label}: {donor.entry.file_name} ({donor.note})"
                        for label, donor in sorted(donors.items())}
    errors = list(built.problems)
    warnings = [*run.plan.warnings, *run.notice_warnings]
    if built.path is not None and not errors and built.cell is not None:
        found = verify_font(built.path, built.layout, built.cell.width)
        errors.extend(found.errors)
        warnings.extend(found.warnings)
        if found.errors:
            built.path.unlink(missing_ok=True)
    _report(built, errors, warnings, run.say)
    return None if errors else built.path


def _groups_of(plan: Plan) -> dict[str, set[str]]:
    """Return, per family label, the ids of the groups it serves code points of."""
    groups: dict[str, set[str]] = {}
    for want in plan.wanted.values():
        groups.setdefault(want.candidates[0], set()).add(want.group.id)
    return groups


def _load(
    options: BuildOptions, say: Callable[[str], None],
) -> tuple[BuildOptions, Config, FontLibrary] | None:
    """Read the configuration and scan the fonts; None (after saying why) when not usable.

    Returns the options with both directories settled: the command line, else the
    configuration file, else the defaults.
    """
    if not options.config_path.is_file():
        say(f"font_composer: no configuration at {options.config_path}; run "
            "'python -m font_composer compose' and make your choices first")
        return None
    try:
        config = Config.load(options.config_path)
    except ConfigError as exc:
        say(f"font_composer: {exc}")
        return None
    fonts_dir = options.fonts_dir or config.directory("fonts") or DEFAULT_FONTS_DIR
    output_dir = options.output_dir or config.directory("output") or DEFAULT_OUTPUT_DIR
    library = FontLibrary.scan(fonts_dir)
    base = library.family(config.base_family)
    if base is None or base.regular_style() is None:
        say(f"font_composer: the base family {config.base_family!r} ([cell] base) is not in "
            f"{fonts_dir}")
        return None
    return replace(options, fonts_dir=fonts_dir, output_dir=output_dir), config, library


def _clashing_names(config: Config, styles: list[str]) -> list[str]:
    """Return the names that more than one output style is built under (none is the aim)."""
    names = config.style_names
    built = [names.get(style, style) for style in styles]
    return sorted({name for name in built
                   if sum(same_style_name(name, other) for other in built) > 1})


def _prepare(
    run: _Run, ask: Callable[[str], str], *, interactive: bool,
) -> tuple[dict[str, dict[str, Donor]], str] | None:
    """Choose every donor file (asking about gaps) and write the notice text.

    Returns the donors per output style and the NOTICE text, or None (after saying why)
    when a donor could not be settled.
    """
    config, library, plan = run.config, run.library, run.plan
    labels = {want.candidates[0] for want in plan.wanted.values()} | {config.base_family}
    decide = make_decider(run.options, config, run.say, ask, interactive=interactive)
    try:
        donors_of = _resolve_donors(config, library, labels, decide)
    except BuildStopError as exc:
        run.say(f"font_composer: {exc}")
        return None
    clashes = _clashing_names(config, list(donors_of))
    if clashes:
        run.say(f"font_composer: these styles would be built under one name: {clashes}; "
                "rename one of them in [output] style-names")
        return None
    notice, run.notice_warnings = _notice(
        config.setting("output", "family", DEFAULT_FAMILY),
        {label: {donors[label].entry.file_name for donors in donors_of.values()}
         for label in labels},
        library, config, _groups_of(plan))
    run.copyright_line = (f"Composed by font-composer from "
                          f"{', '.join(family_names(library, labels))}; see NOTICE.")
    return donors_of, notice


def _start(
    options: BuildOptions, say: Callable[[str], None], catalog: Catalog | None,
) -> _Run | None:
    """Load and plan a build; None (after saying why) when it cannot go on."""
    loaded = _load(options, say)
    if loaded is None:
        return None
    settled, config, library = loaded
    found = catalog if catalog is not None else Catalog.load()
    if not found.blocks:
        say("font_composer: the Unicode block list is not available (src/char-sets/Blocks.txt "
            "could not be read or downloaded); the glyph categories need it")
        return None
    plan = plan_wanted(config, library, found)
    for text in plan.errors:
        say(f"ERROR: {text}")
    if plan.errors:
        return None
    return _Run(settled, config, library, plan, say)


def _show_proof(written: list[ProofFont], total: int, run: _Run) -> None:
    """Show the proof page of the fonts that were written.

    A console that is already running, on the port asked for or the one it saved, is handed
    the fonts and serves the page; the address is printed and that is all. Otherwise the build
    serves the page itself, until the user quits.
    """
    say = run.say
    if not written:
        say("font_composer: no font was written, so there is nothing to show a proof of")
        return
    url = proof.reuse_console(written, run.options.port or run.config.saved_port)
    if url is not None:
        say(f"\nThe proof of the rendered fonts are viewable at: {url}\n"
            "It is shown by the font_composer console that is already running, until that "
            "console is stopped.")
        return
    names = ", ".join(font.style for font in written)
    failed = "" if len(written) == total else "; see the report above"
    styles = f"styles: {names} ({len(written)} of {total} written{failed})"
    proof.serve_proof(written, say, details=[styles], port=run.options.port,
                      saved_port=run.config.saved_port)


def run_build(
    options: BuildOptions,
    say: Callable[[str], None] = print,
    ask: Callable[[str], str] = input,
    *,
    interactive: bool | None = None,
    catalog: Catalog | None = None,
) -> int:
    """Run a build; return the process exit status (0 only when nothing failed)."""
    run = _start(options, say, catalog)
    if run is None:
        return 1
    prepared = _prepare(run, ask, interactive=sys.stdin.isatty() if interactive is None
                        else interactive)
    if prepared is None:
        return 1
    donors_of, notice = prepared
    out_dir = run.options.output_dir or DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {style: _write_style(run, style, donors) for style, donors in donors_of.items()}
    (out_dir / "NOTICE").write_text(notice, encoding="utf-8")
    say(f"\nNOTICE: {out_dir / 'NOTICE'}")
    if run.options.show_proof:
        _show_proof([ProofFont(style, path) for style, path in results.items()
                     if path is not None], len(results), run)
    return 0 if all(path is not None for path in results.values()) else 1
