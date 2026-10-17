"""Plan how donor glyphs are fitted to the base cell: shared by the console and the build.

The console previews the fit and the build applies it, so both ask the same functions.
Reading outlines is the slow part and a font file rarely changes, so the ink of a group
is cached by ``(file, size, mtime, group)``.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from font_composer.common.fit import (
    BLEED,
    EPS,
    Box,
    CellSpec,
    ClassFit,
    FitPlan,
    class_blocks,
    class_fit,
    fit_class,
    is_joined,
    overflow_of,
    plan_fit,
    plan_in_class,
)
from font_composer.common.ink import read_ink

if TYPE_CHECKING:
    from collections.abc import Iterable

    from font_composer.common.groups import Catalog, GlyphGroup
    from font_composer.common.library import Family, StyleEntry


@dataclass(frozen=True)
class FitTarget:
    """What donor glyphs are fitted to: the base cell, and the catalog that names the classes."""

    base: CellSpec
    catalog: Catalog


@lru_cache(maxsize=512)
def _group_ink(
    path: str, size: int, mtime_ns: int, ranges: tuple[tuple[int, int], ...],
) -> tuple[dict[int, Box], Box | None]:
    """Read one font file's ink for some code point ranges (cached by file and ranges)."""
    del size, mtime_ns  # part of the cache key only
    points = frozenset(cp for low, high in ranges for cp in range(low, high + 1))
    try:
        return read_ink(Path(path), points)
    except (OSError, ValueError):
        return {}, None


def cell_of(style: StyleEntry) -> CellSpec:
    """Return a style file's character cell in em."""
    metrics = style.info.metrics
    upm = float(metrics.units_per_em) or 1.0
    return CellSpec(metrics.cell_advance / upm, metrics.ascent / upm, metrics.descent / upm)


def ink_of(style: StyleEntry, group: GlyphGroup) -> tuple[dict[int, Box], Box | None]:
    """Return the ink boxes of a style file's glyphs of one group, and its frame (cached)."""
    path = style.info.path
    try:
        stat = path.stat()
    except OSError:
        return {}, None
    return _group_ink(str(path), stat.st_size, stat.st_mtime_ns, group.ranges)


def class_fit_of(
    family: Family, name: str, base: CellSpec, catalog: Catalog, block_id: str,
) -> ClassFit | None:
    """Find the shared scale of a family's glyphs in one category class.

    It is taken from the family's reference style over every glyph the family has in the
    class (the block ``block_id`` itself, for a class of one block), so it does not depend
    on which families a group inherits from, and every style of the family gets the same
    one. The pieces that join their neighbours are not part of it: they are not scaled.
    """
    reference = family.regular_style()
    if reference is None:
        return None
    inks: list[Box] = []
    frame = None
    for member in class_blocks(name, block_id):
        block = catalog.by_id(member)
        if block is None:
            continue
        boxes, frame = ink_of(reference, block)
        inks.extend(box for codepoint, box in boxes.items() if not is_joined(codepoint))
    if name == "connectors" and frame is not None:
        # Box lines may run past the full block on purpose, so that neighbours overlap
        # (Fira Code's by 0.2 em); the renderer cuts them at the cell. The family is
        # fitted by its frame, never by the overshoot of its lines.
        inks = [frame]
    return class_fit(name, inks, cell_of(reference), frame, base)


def connector_map(donor: CellSpec, frame: Box | None, base: CellSpec) -> FitPlan:
    """Return the one map that puts a donor's box-drawing frame exactly on the base cell.

    Exact in x so that a line meets the line of the next cell, exact in y so that vertical
    lines meet the rows above and below. The frame is the donor's full block when that
    lies beyond its cell (Source Code Pro's is 1.4 em tall on a 1.257 em line), else its
    cell. Every glyph of the donor's connector groups gets this map, so they still join
    each other; the glyph is then cut at the cell edge for what overshoots on purpose.
    A donor that already is the base cell gets the identity map (and still the cut).
    """
    bottom, top = donor.descent, donor.ascent
    if frame is not None and (frame.y1 > top + BLEED or frame.y0 < bottom - BLEED):
        bottom, top = frame.y0, frame.y1
    if donor.width <= 0 or top <= bottom:
        return FitPlan("connector")
    sx = base.width / donor.width
    sy = base.height / (top - bottom)
    dy = (base.ascent + base.descent) / 2 - (top + bottom) / 2 * sy
    plan = FitPlan("connector", sx, sy, 0.0, dy)
    moved = plan.apply(Box(0.0, bottom, donor.width, top))
    shift = max(abs(moved.x0), abs(moved.x1 - donor.width),
                abs(moved.y0 - bottom), abs(moved.y1 - top))
    return plan if shift > BLEED else FitPlan("connector")


def connector_reach(
    ink: Box, donor: CellSpec, frame: Box | None,
) -> tuple[bool, bool, bool, bool]:
    """Tell which edges of its cell a donor's connector glyph reaches: left, right, bottom, top.

    Those are the edges it has to still reach after the fit, to join its neighbours.
    """
    bottom, top = donor.descent, donor.ascent
    if frame is not None and (frame.y1 > top + BLEED or frame.y0 < bottom - BLEED):
        bottom, top = frame.y0, frame.y1
    return (ink.x0 <= EPS, ink.x1 >= donor.width - EPS,
            ink.y0 <= bottom + EPS, ink.y1 >= top - EPS)


def _plan_connectors(
    ink: dict[int, Box], frame: Box | None, donor: CellSpec, base: CellSpec,
    codepoints: Iterable[int],
) -> dict[int, FitPlan]:
    """Give every box-drawing or block glyph the donor's one frame map (see above)."""
    mapping = connector_map(donor, frame, base)
    plans: dict[int, FitPlan] = {}
    for codepoint in codepoints:
        box = ink.get(codepoint)
        overflow = overflow_of(box, base.box) if box is not None else 0.0
        plans[codepoint] = FitPlan("connector", mapping.sx, mapping.sy, mapping.dx, mapping.dy,
                                   overflow, 0.0)
    return plans


def plan_glyphs(
    family: Family, group: GlyphGroup, style: StyleEntry, codepoints: Iterable[int],
    target: FitTarget,
) -> dict[int, FitPlan]:
    """Plan the fit of some glyphs of one style file onto the base cell.

    Every glyph is of a category fitted together (text, symbols, box drawing) and gets
    the shared scale of its family, in proportion; one that is not scaled and fits is left
    out. Only the pieces that join their neighbours are fitted to the cell, one by one.
    """
    base = target.base
    ink, frame = ink_of(style, group)
    donor = cell_of(style)
    name = fit_class(group.block)
    if name == "connectors":
        return _plan_connectors(ink, frame, donor, base, codepoints)
    shared = class_fit_of(family, name, base, target.catalog, group.block)
    plans: dict[int, FitPlan] = {}
    for codepoint in codepoints:
        if is_joined(codepoint) or shared is None:
            letter = unicodedata.category(chr(codepoint))[0] in "LM"
            plan = plan_fit(ink.get(codepoint), donor, frame, base, on_baseline=letter)
        else:
            plan = plan_in_class(ink.get(codepoint), shared, base)
            if name == "symbols" and plan.identity and plan.overflow <= EPS:
                continue
        if plan.kind != "fits":
            plans[codepoint] = plan
    return plans
