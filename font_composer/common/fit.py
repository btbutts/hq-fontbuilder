"""Does a donor glyph fit the cell of the composed font, and what to do when it does not.

Everything is in em, y up, x from the cell's left edge; the cell of a font is
``[0, width] x [descent, ascent]`` (``descent`` negative), the same cell a console
gives each character. A glyph is judged by its *ink* (the outline's bounding box), not
by its advance width. The causes found by measuring every glyph of the fonts in use
fall in a few classes, each with its own correction:

``fits``      inside the cell (to within ``EPS``); nothing to do.
``bleed``     past the cell by at most ``BLEED``: below half a pixel at ordinary sizes,
              and what fonts do on purpose so neighbours do not show a seam. Kept.
``frame``     a glyph designed to span the cell so that neighbours join: box drawing,
              blocks, powerline separators, the pieces of braces and integrals. Such a
              glyph needs fitting even when it does not overflow (a narrow donor's
              separator leaves a gap beside its neighbour). A connector is a glyph
              that spans the donor's cell across, or reaches both its top and bottom, or
              reaches the edge of the donor's *frame* where that lies outside the cell
              (the full block U+2588 of Source Code Pro is 1.4 em tall on a 1.257 em
              line). Letters are never connectors, and an icon that merely touches the
              descent line is not. The donor's cell (or its frame, for the fonts that
              have one beyond the cell) is fitted exactly onto the base cell: in x so
              that joins left and right meet, in y so that lines neither leave a gap
              nor hang into the rows above and below (a renderer that does not clip
              would let them overstrike the neighbours' descenders). Strokes change by
              the same ratio, a few percent. Every connector of a font gets the same
              map, so they still join each other. When the donor's reference is within
              ``BLEED`` of the base cell, no fit is made for any of them.
``oversize``  a symbol wider or taller than the cell (``↔ ⇔ ⌫ ☑ ❤``, a ``‿`` meant to
              touch its neighbours). Scaled uniformly to fit and kept where it was as
              far as the cell allows. A letter is scaled about the baseline instead, so
              it still sits on it.
``offset``    small enough but sitting partly outside (a font whose line box differs
              from the base's, e.g. Nerd Font icons 0.03 em below the descent). Moved
              the least that brings it inside.

A family's glyphs of one *category* are also fitted together, because shrinking only the
glyph that offends would make it smaller than its look-alikes (``ĺ`` against ``ľ``).
:func:`class_fit` finds the one scale that brings the offenders of a category inside the
cell, :func:`plan_in_class` applies it to every glyph of that category (anchored so that
glyphs keep their place: the baseline for text, the centre of the frame for box
drawing) and adds the least extra shift or shrink a glyph still needs. The scale is
floored (``CLASS_FLOORS``): a few outliers, such as an accented Greek capital taller than
any letter, must not make a whole alphabet visibly smaller; they are fitted on their own.
Categories that are not fitted together (punctuation, arrows, dingbats ... whose glyphs
differ in size by nature) use :func:`plan_fit` per glyph.

:func:`plan_fit` returns the affine map ``x' = sx*x + dx``, ``y' = sy*y + dy`` that the
build applies to the outline with a transform pen, and the preview draws with an SVG
matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable

EPS = 0.004
BLEED = 0.02
_EDGE = 0.01          # how near an edge a glyph must come to "reach" it
_OVERLAP = 0.05       # how far a rule may overlap its neighbours and still join them
_SAME_CELL = 0.002    # em: cells closer than this are the same cell
_SPANS = 0.45         # of the reference's height a connecting glyph covers at least

Kind = Literal["fits", "bleed", "frame", "oversize", "offset", "category", "connector"]


@dataclass(frozen=True)
class Box:
    """A rectangle in em: ``x0 <= x1`` and ``y0 <= y1``."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        """Horizontal extent."""
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        """Vertical extent."""
        return self.y1 - self.y0


@dataclass(frozen=True)
class CellSpec:
    """A font's character cell: advance width, ascent and (negative) descent, in em."""

    width: float
    ascent: float
    descent: float

    @property
    def height(self) -> float:
        """Line height, ascent plus descent depth."""
        return self.ascent - self.descent

    @property
    def box(self) -> Box:
        """The cell as a box."""
        return Box(0.0, self.descent, self.width, self.ascent)


@dataclass(frozen=True)
class FitPlan:
    """How one glyph relates to the base cell and the correction that fixes it."""

    kind: Kind
    sx: float = 1.0
    sy: float = 1.0
    dx: float = 0.0
    dy: float = 0.0
    #: how far the original ink leaves the base cell, in em (0 when it fits)
    overflow: float = 0.0
    #: how far the corrected ink still leaves it (clipped excess of a frame glyph)
    residual: float = 0.0

    @property
    def clip(self) -> bool:
        """True for a connector the renderer is expected to cut at the cell edge.

        Its overshoot is deliberate (it makes neighbours overlap), so the fitted preview
        does not draw what lies outside the cell.
        """
        return self.kind == "connector"

    @property
    def identity(self) -> bool:
        """True when the correction changes nothing."""
        return (self.sx, self.sy, self.dx, self.dy) == (1.0, 1.0, 0.0, 0.0)

    def then(self, other: FitPlan) -> FitPlan:
        """Return the map that does this correction first and ``other`` after it."""
        return FitPlan(self.kind, other.sx * self.sx, other.sy * self.sy,
                       other.sx * self.dx + other.dx, other.sy * self.dy + other.dy)

    def apply(self, box: Box) -> Box:
        """Return ``box`` after the correction."""
        return Box(self.sx * box.x0 + self.dx, self.sy * box.y0 + self.dy,
                   self.sx * box.x1 + self.dx, self.sy * box.y1 + self.dy)


def overflow_of(ink: Box, cell: Box) -> float:
    """Return how far ``ink`` leaves ``cell`` on its worst side (0 when inside)."""
    return max(0.0, cell.x0 - ink.x0, ink.x1 - cell.x1, cell.y0 - ink.y0, ink.y1 - cell.y1)


def _connector_reference(
    ink: Box, donor: CellSpec, frame: Box | None,
) -> tuple[float, float] | None:
    """Return the vertical extent ``(bottom, top)`` a connector was designed on, or None.

    A glyph that reaches the edge of the donor's frame (where the frame lies beyond
    the cell) was designed on the frame; one that reaches both the top and bottom of the
    cell, on the cell. One that only spans the cell across (a horizontal rule, a half
    block) belongs to the family of its font: the frame if it has one beyond the
    cell, else the cell.
    """
    frame_beyond = frame is not None and (frame.y1 > donor.ascent + BLEED
                                          or frame.y0 < donor.descent - BLEED)
    if frame is not None and frame_beyond:
        reaches = ink.y1 >= frame.y1 - _EDGE or ink.y0 <= frame.y0 + _EDGE
        if reaches and ink.height >= _SPANS * frame.height:
            return frame.y0, frame.y1
    both = ink.y0 <= donor.descent + _EDGE and ink.y1 >= donor.ascent - _EDGE
    if both:
        return donor.descent, donor.ascent
    spans_across = (-_OVERLAP <= ink.x0 <= _EDGE
                    and donor.width - _EDGE <= ink.x1 <= donor.width + _OVERLAP)
    if spans_across:
        if frame is not None and frame_beyond:
            return frame.y0, frame.y1
        return donor.descent, donor.ascent
    return None


def _frame_plan(
    ink: Box, donor: CellSpec, frame: Box | None, base: CellSpec,
) -> FitPlan | None:
    """Plan for a connector glyph, or None when it is not one or needs no fitting.

    The fit is a property of the donor's connector family, not of one glyph: whether it
    is made depends on how far the reference (the donor's frame or cell) is from the
    base cell, so that every box line of a font is fitted, or none, and they still
    meet each other.
    """
    reference = _connector_reference(ink, donor, frame) if donor.width > 0 else None
    if reference is None:
        return None
    bottom, top = reference
    sx = base.width / donor.width
    sy = base.height / (top - bottom)
    centre_from = (bottom + top) / 2 * sy
    plan = FitPlan("frame", sx, sy, 0.0, (base.ascent + base.descent) / 2 - centre_from)
    moved = plan.apply(Box(0.0, bottom, donor.width, top))
    shift = max(abs(moved.x0), abs(moved.x1 - donor.width),
                abs(moved.y0 - bottom), abs(moved.y1 - top))
    return plan if shift > BLEED else None


def _nudge(low: float, high: float, lo_limit: float, hi_limit: float) -> float:
    """Return the smallest shift that brings ``[low, high]`` inside the limits."""
    if low < lo_limit:
        return lo_limit - low
    if high > hi_limit:
        return hi_limit - high
    return 0.0


def _contain_plan(ink: Box, base: CellSpec, *, on_baseline: bool) -> FitPlan:
    """Plan for a glyph that is just too big or sits partly outside."""
    cell = base.box
    if ink.width <= cell.width + EPS and ink.height <= cell.height + EPS and not on_baseline:
        return FitPlan("offset", dx=_nudge(ink.x0, ink.x1, cell.x0, cell.x1),
                       dy=_nudge(ink.y0, ink.y1, cell.y0, cell.y1))
    scale = min(1.0, cell.width / ink.width, cell.height / ink.height)
    if on_baseline:
        # a letter: scale about the baseline (and the horizontal middle of its ink)
        above = base.ascent / ink.y1 if ink.y1 > base.ascent else 1.0
        below = base.descent / ink.y0 if ink.y0 < base.descent else 1.0
        scale = min(scale, above, below)
        centre_x = (ink.x0 + ink.x1) / 2
        dx = centre_x * (1 - scale)
        dx += _nudge(scale * ink.x0 + dx, scale * ink.x1 + dx, cell.x0, cell.x1)
        return FitPlan("oversize", scale, scale, dx, 0.0)
    centre_x, centre_y = (ink.x0 + ink.x1) / 2, (ink.y0 + ink.y1) / 2
    moved = Box(centre_x - ink.width * scale / 2, centre_y - ink.height * scale / 2,
                centre_x + ink.width * scale / 2, centre_y + ink.height * scale / 2)
    return FitPlan("oversize", scale, scale,
                   moved.x0 - scale * ink.x0 + _nudge(moved.x0, moved.x1, cell.x0, cell.x1),
                   moved.y0 - scale * ink.y0 + _nudge(moved.y0, moved.y1, cell.y0, cell.y1))


def plan_fit(
    ink: Box | None,
    donor: CellSpec,
    frame: Box | None,
    base: CellSpec,
    *,
    on_baseline: bool = False,
) -> FitPlan:
    """Classify one glyph against the base cell and plan its correction.

    ``ink`` is the outline's bounds (None for a blank glyph), ``donor`` the cell of the
    font it comes from, ``frame`` that font's full block (None if it has none) and
    ``on_baseline`` whether the glyph is a letter that has to stay on the baseline.
    """
    if ink is None or ink.width <= 0 or ink.height <= 0:
        return FitPlan("fits")
    overflow = overflow_of(ink, base.box)
    connector = None if on_baseline else _frame_plan(ink, donor, frame, base)
    if connector is not None:
        residual = overflow_of(connector.apply(ink), base.box)
        return FitPlan("frame", connector.sx, connector.sy, connector.dx, connector.dy,
                       overflow, residual)
    if overflow <= EPS:
        return FitPlan("fits")
    if overflow <= BLEED:
        return FitPlan("bleed", overflow=overflow, residual=overflow)
    plan = _contain_plan(ink, base, on_baseline=on_baseline)
    residual = overflow_of(plan.apply(ink), base.box)
    return FitPlan(plan.kind, plan.sx, plan.sy, plan.dx, plan.dy, overflow, residual)


# ---- categories fitted together ------------------------------------------------------

#: The most a whole category may shrink, as a scale. Text may lose 5%: that brings 95-99%
#: of the letters of the fonts measured inside the cell; box drawing, whose donors draw
#: on frames up to 1.4 em tall, may lose a quarter.
CLASS_FLOORS: dict[str, float] = {"text": 0.95, "connectors": 0.75}

TEXT_GROUPS = ("alnum", "ascii-symbols", "latin-1", "latin-ext", "latin-ext-b",
               "latin-ext-additional", "greek", "cyrillic")
CONNECTOR_GROUPS = ("box-drawing", "block-elements")


def fit_class(group_id: str) -> str | None:
    """Return the category class a glyph group is fitted in, or None (fitted singly)."""
    if group_id in TEXT_GROUPS:
        return "text"
    if group_id in CONNECTOR_GROUPS:
        return "connectors"
    return None


def class_groups(name: str) -> tuple[str, ...]:
    """Return the ids of the glyph groups that make up a category class."""
    return TEXT_GROUPS if name == "text" else CONNECTOR_GROUPS


@dataclass(frozen=True)
class ClassFit:
    """The shared map of one family's glyphs of one category class."""

    name: str
    plan: FitPlan
    #: the scale the worst glyph needed, before the floor (informational)
    needed: float

    @property
    def scale(self) -> float:
        """The scale every glyph of the class gets."""
        return self.plan.sx


def _limit(span: tuple[float, float], anchor: tuple[float, float],
           bounds: tuple[float, float]) -> float:
    """Largest scale at which ``span`` stays inside ``bounds`` about an anchor.

    ``anchor`` is ``(source, target)``: the point of the glyph that stays matched to a
    point of the cell. A bound the anchor already violates cannot be helped by scaling
    and is ignored.
    """
    source, target = anchor
    limit = 1.0
    for value, bound, upper in ((span[1], bounds[1], True), (span[0], bounds[0], False)):
        distance = value - source
        room = bound - target
        if distance != 0 and (distance > 0) == upper and (room >= 0) == upper:
            limit = min(limit, room / distance)
    return limit


def _anchors(
    name: str, donor: CellSpec, frame: Box | None, base: CellSpec,
) -> tuple[float, float, float, float]:
    """Return ``(from_x, to_x, from_y, to_y)``: the points that stay matched."""
    if name == "text":
        return donor.width / 2, base.width / 2, 0.0, 0.0
    bottom, top = donor.descent, donor.ascent
    if frame is not None and (frame.y1 > top + BLEED or frame.y0 < bottom - BLEED):
        bottom, top = frame.y0, frame.y1
    return donor.width / 2, base.width / 2, (bottom + top) / 2, (base.ascent + base.descent) / 2


def _same_cell(a: CellSpec, b: CellSpec) -> bool:
    """Tell whether two fonts give a character the same cell (to within 0.002 em)."""
    return (abs(a.width - b.width) < _SAME_CELL and abs(a.ascent - b.ascent) < _SAME_CELL
            and abs(a.descent - b.descent) < _SAME_CELL)


def class_fit(
    name: str, inks: Iterable[Box], donor: CellSpec, frame: Box | None, base: CellSpec,
) -> ClassFit:
    """Find the scale of a category class: just enough for its offenders, never below floor.

    Text is anchored on the baseline and free to slide sideways, so only its width and its
    height above and below the baseline limit it; connectors keep their place relative to
    the cell, so every edge limits them.
    """
    from_x, to_x, from_y, to_y = _anchors(name, donor, frame, base)
    cell = base.box
    if name == "connectors" and _same_cell(donor, base):
        # a font that is the cell: its box drawing was made for it and already joins
        return ClassFit(name, FitPlan("category"), 1.0)
    needed = 1.0
    for ink in inks:
        if name == "text":
            needed = min(needed, cell.width / ink.width if ink.width > 0 else 1.0,
                         _limit((ink.y0, ink.y1), (0.0, 0.0), (cell.y0, cell.y1)))
        else:
            needed = min(needed,
                         _limit((ink.x0, ink.x1), (from_x, to_x), (cell.x0, cell.x1)),
                         _limit((ink.y0, ink.y1), (from_y, to_y), (cell.y0, cell.y1)))
    scale = max(CLASS_FLOORS[name], needed)
    plan = FitPlan("category", scale, scale, to_x - scale * from_x, to_y - scale * from_y)
    return ClassFit(name, plan, needed)


def plan_in_class(ink: Box | None, shared: ClassFit, base: CellSpec) -> FitPlan:
    """Plan one glyph of a category: the shared map, plus the least it still needs.

    A text glyph that still leaves the cell slides sideways and, if that is not
    enough, shrinks about the baseline (so the letter stays on it). A connector gets
    only the shared map, so that all of them keep lining up.
    """
    plan = shared.plan
    kind: Kind = "connector" if shared.name == "connectors" else "category"
    if ink is None or ink.width <= 0 or ink.height <= 0:
        return FitPlan(kind, plan.sx, plan.sy, plan.dx, plan.dy)
    overflow = overflow_of(ink, base.box)
    if shared.name == "text" and overflow_of(plan.apply(ink), base.box) > EPS:
        extra = _contain_plan(plan.apply(ink), base, on_baseline=True)
        plan = plan.then(extra)
    return FitPlan(kind, plan.sx, plan.sy, plan.dx, plan.dy, overflow,
                   overflow_of(plan.apply(ink), base.box))
