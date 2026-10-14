"""Assemble one output style: draw every glyph, then write the TrueType font.

The composed font is built from scratch with ``FontBuilder`` (TrueType outlines, no
hinting, no layout tables: terminals do no shaping, which also drops the ligatures of
Fira Code and JetBrains Mono). Its cell, line metrics and weight come from the base
family's file for that style; every glyph has the base cell's advance. A code point that
a group's inheritance order serves is drawn from its donor, fitted by the same plan the
console previews; every other code point the base font has keeps the base glyph.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fontTools.fontBuilder import FontBuilder

from font_composer.builder.draw import CellBox, DrawSpec, Source, draw_glyph, draw_named
from font_composer.common.fit import (
    CONNECTOR_GROUPS,
    EPS,
    Box,
    CellSpec,
    FitPlan,
    overflow_of,
    plan_fit,
)
from font_composer.common.planner import cell_of, connector_reach, ink_of, plan_glyphs

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from font_composer.builder.donors import Donor
    from font_composer.common.groups import GlyphGroup
    from font_composer.common.library import FontLibrary
    from font_composer.common.styles import StyleTarget

MAX_GLYPHS = 65535
NOTDEF = ".notdef"
PANOSE_MONOSPACED = 9
_BMP_MAX = 0xFFFF
_FS_ITALIC = 0x01
_FS_REGULAR = 0x40
_RIBBI = {"regular": ("Regular", 0x40), "bold": ("Bold", 0x20), "italic": ("Italic", 0x01),
          "bold italic": ("Bold Italic", 0x21)}


@dataclass(frozen=True)
class Wanted:
    """A code point the groups serve: who may serve it, in order, and whether it is pinned."""

    codepoint: int
    group: GlyphGroup
    candidates: tuple[str, ...]
    pinned: bool


@dataclass(frozen=True)
class Naming:
    """What an output style is called and where it goes."""

    style: str
    target: StyleTarget | None
    family_name: str
    out_dir: Path
    #: the copyright string of the font (name ID 0)
    notice: str = ""

    @property
    def path(self) -> Path:
        """The file the style is written to: ``<Family>-<Style>.ttf``."""
        stem = f"{self.family_name.replace(' ', '')}-{self.style.replace(' ', '')}"
        return self.out_dir / f"{stem}.ttf"

    @property
    def weight(self) -> int:
        """The weight class of the style (Regular when the name is not recognised)."""
        return self.target.weight if self.target is not None else 400

    @property
    def italic(self) -> bool:
        """Whether the style is slanted: what it is, not what the user calls it."""
        return self.target is not None and self.target.italic


@dataclass(frozen=True)
class StyleBuild:
    """Everything one output style needs."""

    naming: Naming
    library: FontLibrary
    base: Donor
    donors: Mapping[str, Donor]
    wanted: Mapping[int, Wanted]
    fit_to_base: bool = True


@dataclass
class Layout:
    """What was written: the code point map, where glyphs came from, what must still join."""

    cmap: dict[int, str] = field(default_factory=dict)
    #: code point -> family label it was drawn from (base glyphs are not listed)
    drawn_from: dict[int, str] = field(default_factory=dict)
    #: connector code point -> the cell edges it must still reach (left, right, bottom, top)
    joins: dict[int, tuple[bool, bool, bool, bool]] = field(default_factory=dict)


@dataclass
class BuiltFont:
    """The result of one output style, for verification and the report."""

    style: str
    path: Path | None = None
    layout: Layout = field(default_factory=Layout)
    #: code point -> the fit plan applied (only those that changed the glyph)
    plans: dict[int, FitPlan] = field(default_factory=dict)
    cell: CellBox | None = None
    problems: list[str] = field(default_factory=list)
    #: label -> what file serves the style and why, for the report
    used_files: dict[str, str] = field(default_factory=dict)


def _glyph_name(codepoint: int) -> str:
    return f"uni{codepoint:04X}" if codepoint <= _BMP_MAX else f"u{codepoint:05X}"


def _bounds(glyph: Any) -> tuple[int, int, int, int] | None:
    """Return a glyph's ink bounds in font units (None when it has no outline)."""
    if getattr(glyph, "numberOfContours", 0) == 0:
        return None
    glyph.recalcBounds(None)
    return glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax


def _is_letter(codepoint: int) -> bool:
    return unicodedata.category(chr(codepoint))[0] in "LM"


class _Sources:
    """The donor files open for one output style."""

    def __init__(self, weight: int) -> None:
        self._weight = weight
        self._open: dict[Path, Source] = {}

    def get(self, donor: Donor) -> Source:
        """Return the opened source of a donor's file."""
        path = donor.entry.info.path
        if path not in self._open:
            self._open[path] = Source(path, self._weight, variable=donor.entry.info.is_variable)
        return self._open[path]

    def close(self) -> None:
        """Close every file."""
        for source in self._open.values():
            source.close()


class _Drawer:
    """Draws glyphs into the units and cell of one output style."""

    def __init__(self, upm: int, cell: CellBox, base_cell: CellSpec) -> None:
        self.upm = upm
        self.cell = cell
        self.base_cell = base_cell

    def base_glyph(self, source: Source, name: str) -> Any:
        """Draw one of the base font's own glyphs, unchanged but for the units."""
        return draw_named(source, name, DrawSpec(self.upm, None, self.cell))

    def donor_glyph(
        self, source: Source, codepoint: int, plan: FitPlan | None, *, embolden: bool,
    ) -> tuple[Any, FitPlan | None]:
        """Draw a donor glyph; a synthesized bold is re-fitted when it grew past the cell.

        Returns the glyph and the plan that was finally applied.
        """
        clamp = plan is not None and plan.clip
        spec = DrawSpec(self.upm, plan, self.cell, embolden=embolden, clamp=clamp)
        glyph = draw_glyph(source, codepoint, spec)
        bounds = _bounds(glyph) if embolden else None
        if bounds is None:
            return glyph, plan
        ink = Box(*(value / self.upm for value in bounds))
        if overflow_of(ink, self.base_cell.box) <= EPS:
            return glyph, plan
        extra = plan_fit(ink, self.base_cell, None, self.base_cell,
                         on_baseline=_is_letter(codepoint))
        combined = (plan if plan is not None else FitPlan("fits")).then(extra)
        spec = DrawSpec(self.upm, combined, self.cell, embolden=True, clamp=clamp)
        return draw_glyph(source, codepoint, spec), combined


def _choose_donors(
    build: StyleBuild, sources: _Sources, result: BuiltFont,
) -> dict[int, tuple[str, Wanted]]:
    """Pick, for every wanted code point, the family whose file for this style serves it."""
    style = build.naming.style
    chosen: dict[int, tuple[str, Wanted]] = {}
    for codepoint, want in sorted(build.wanted.items()):
        label = next((name for name in want.candidates
                      if name in build.donors
                      and sources.get(build.donors[name]).has(codepoint)), None)
        where = f"U+{codepoint:04X} ({want.group.id})"
        if label is None:
            reason = "pinned to" if want.pinned else "no family of the order has it in"
            result.problems.append(
                f"{where}: {reason} the {style} style files of {', '.join(want.candidates)}")
        elif want.group.atomic and label != want.candidates[0]:
            result.problems.append(
                f"{where} is atomic: {want.candidates[0]}'s {style} file lacks it, so the "
                "group cannot come from one family")
        else:
            chosen[codepoint] = (label, want)
    return chosen


def _plan_chosen(
    build: StyleBuild, chosen: dict[int, tuple[str, Wanted]], base_cell: CellSpec,
) -> dict[int, FitPlan]:
    """Plan the fit of every chosen glyph, per family and group, on the donor's style file."""
    grouped: dict[tuple[str, str], list[int]] = {}
    groups: dict[str, GlyphGroup] = {}
    for codepoint, (label, want) in chosen.items():
        grouped.setdefault((label, want.group.id), []).append(codepoint)
        groups[want.group.id] = want.group
    plans: dict[int, FitPlan] = {}
    for (label, group_id), codepoints in grouped.items():
        family = build.library.family(label)
        if family is not None:
            plans.update(plan_glyphs(family, groups[group_id], build.donors[label].entry,
                                     codepoints, base_cell))
    return plans


def _note_joins(donor: Donor, group: GlyphGroup, codepoint: int, layout: Layout) -> None:
    """Remember which cell edges a donor's connector reaches, for the verification."""
    ink, frame = ink_of(donor.entry, group)
    box = ink.get(codepoint)
    if box is not None:
        layout.joins[codepoint] = connector_reach(box, cell_of(donor.entry), frame)


def _draw_wanted(
    build: StyleBuild, sources: _Sources, drawer: _Drawer, result: BuiltFont,
) -> dict[str, Any]:
    """Draw every code point a group serves; return ``glyph name -> glyph``."""
    chosen = _choose_donors(build, sources, result)
    plans = _plan_chosen(build, chosen, drawer.base_cell) if build.fit_to_base else {}
    glyphs: dict[str, Any] = {}
    for codepoint, (label, want) in chosen.items():
        donor = build.donors[label]
        if want.group.id in CONNECTOR_GROUPS:
            _note_joins(donor, want.group, codepoint, result.layout)
        glyph, applied = drawer.donor_glyph(sources.get(donor), codepoint, plans.get(codepoint),
                                            embolden=donor.synthesize)
        name = _glyph_name(codepoint)
        glyphs[name] = glyph
        result.layout.cmap[codepoint] = name
        result.layout.drawn_from[codepoint] = label
        if applied is not None:
            result.plans[codepoint] = applied
    return glyphs


def _copy_base(
    base: Source, drawer: _Drawer, covered: set[int], layout: Layout,
) -> dict[str, Any]:
    """Draw the base font's own glyphs for every code point no group serves."""
    glyphs: dict[str, Any] = {}
    if NOTDEF in base.glyphs:
        glyphs[NOTDEF] = drawer.base_glyph(base, NOTDEF)
    names: dict[str, str] = {}
    for codepoint, name in sorted(base.cmap.items()):
        if codepoint in covered or name not in base.glyphs:
            continue
        if name not in names:
            names[name] = name if name != NOTDEF else _glyph_name(codepoint)
            glyphs[names[name]] = drawer.base_glyph(base, name)
        layout.cmap[codepoint] = names[name]
    return glyphs


def _style_names(naming: Naming) -> dict[str, str]:
    """Return the name table strings of a style; non-RIBBI styles go in the family name."""
    family, style = naming.family_name, naming.style
    names = {"uniqueFontIdentifier": f"{family}:{style}:font-composer",
             "fullName": f"{family} {style}",
             "psName": f"{family.replace(' ', '')}-{style.replace(' ', '')}",
             "version": "Version 1.000", "copyright": naming.notice,
             "licenseDescription": ("Composed from fonts that each keep their own licence; "
                                    "see the NOTICE file that comes with this font.")}
    ribbi = _RIBBI.get(style.strip().lower())
    if ribbi is not None:
        names.update(familyName=family, styleName=ribbi[0])
    else:
        names.update(familyName=f"{family} {style}", styleName="Regular",
                     typographicFamily=family, typographicSubfamily=style)
    return names


def build_style(build: StyleBuild) -> BuiltFont:
    """Draw and write one output style; problems are collected, never raised."""
    naming = build.naming
    result = BuiltFont(style=naming.style)
    sources = _Sources(naming.weight)
    try:
        base = sources.get(build.base)
        metrics = build.base.entry.info.metrics
        cell = CellBox(metrics.cell_advance, metrics.ascent, metrics.descent)
        result.cell = cell
        drawer = _Drawer(metrics.units_per_em, cell, cell_of(build.base.entry))
        drawn = _draw_wanted(build, sources, drawer, result)
        glyphs = _copy_base(base, drawer, set(result.layout.cmap), result.layout)
        glyphs.update(drawn)
        if len(glyphs) > MAX_GLYPHS:
            result.problems.append(f"{len(glyphs)} glyphs: a TrueType font holds {MAX_GLYPHS}")
        if not result.problems:
            _write(build, base, glyphs, result)
            result.path = naming.path
    finally:
        sources.close()
    return result


def _write(
    build: StyleBuild, base: Source, glyphs: dict[str, Any], result: BuiltFont,
) -> None:
    """Put the glyphs, metrics and names in a font and save it."""
    cell = result.cell
    assert cell is not None
    order = [NOTDEF, *[name for name in glyphs if name != NOTDEF]]
    builder = FontBuilder(int(base.upm), isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(result.layout.cmap)
    builder.setupGlyf({name: glyphs[name] for name in order})
    builder.setupHorizontalMetrics({
        name: (cell.width, (_bounds(glyphs[name]) or (0,))[0]) for name in order})
    builder.setupHorizontalHeader(ascent=cell.ascent, descent=cell.descent, lineGap=0)
    builder.setupNameTable(_style_names(build.naming))
    selection = _setup_os2(builder, build.naming, base, cell)
    builder.setupPost(isFixedPitch=1, keepGlyphNames=True)
    builder.setupMaxp()
    head: Any = builder.font["head"]
    head.macStyle = (0x01 if selection & 0x20 else 0) | (0x02 if selection & 0x01 else 0)
    path = build.naming.path
    path.parent.mkdir(parents=True, exist_ok=True)
    builder.save(path)


def _setup_os2(builder: FontBuilder, naming: Naming, base: Source, cell: CellBox) -> int:
    """Write the OS/2 table from the base font's; return its ``fsSelection``."""
    base_os2: Any = base.font["OS/2"]
    ribbi = _RIBBI.get(naming.style.strip().lower(), ("Regular", 0x40))
    # the slant is the style's own (a style renamed "Slanted" is still italic); the bold bit
    # belongs to the RIBBI name only
    selection = ribbi[1] | (_FS_ITALIC if naming.italic else 0)
    if selection != _FS_REGULAR:
        selection &= ~_FS_REGULAR  # REGULAR is for a style that is neither italic nor bold
    selection |= base_os2.fsSelection & 0x80  # keep USE_TYPO_METRICS
    builder.setupOS2(
        usWeightClass=naming.weight, usWidthClass=5, fsSelection=selection, fsType=0,
        sTypoAscender=base_os2.sTypoAscender, sTypoDescender=base_os2.sTypoDescender,
        sTypoLineGap=base_os2.sTypoLineGap, usWinAscent=base_os2.usWinAscent,
        usWinDescent=base_os2.usWinDescent, xAvgCharWidth=cell.width,
        sxHeight=getattr(base_os2, "sxHeight", 0), sCapHeight=getattr(base_os2, "sCapHeight", 0),
        version=4)
    os2: Any = builder.font["OS/2"]
    os2.panose.bProportion = PANOSE_MONOSPACED
    return int(selection)
