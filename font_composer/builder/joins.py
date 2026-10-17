"""Check that the box glyphs of a written font meet each other.

Two neighbouring cells of a box join when the ink of one at the edge they share is the
ink of the other: the same stroke, at the same place, of the same width. So every glyph
of Box Drawing is measured where it touches the four edges of the cell (its *ports*,
in em), and the ports that are meant to be one line are compared: the right and left
ports of the horizontal lines, the top and bottom ports of the vertical ones. A light
line, a heavy line and a double line are different lines. A ``seam`` is a line whose
ports do not agree: its ``spread`` is how far the worst two miss each other, which is
what a gap or a step in a drawn table would measure.

That is every table that can be drawn (a thin grid, a thick one, a thick half against a
thin half, from the top down or from side to side), since the table joins exactly where
its facing ports do. The halves and quarters of Block Elements are compared by the
line at which they divide the cell.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, NamedTuple

from fontTools.pens.basePen import decomposeQuadraticSegment
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen

if TYPE_CHECKING:
    from fontTools.ttLib import TTFont

    from font_composer.common.fitting.fit import Box

#: em: a miss smaller than this cannot be shown by any screen
JOIN_WARNING = 0.002
#: em: a miss this large shows as a hairline gap or step at ordinary sizes
JOIN_GAP = 0.01
_SAME_LINE = 0.02     # ports this close are the same line (a light and a heavy one are not)
_INSET = 0.0005       # em inside the edge where the ink is looked at
_MIN_SPAN = 0.01      # a smaller piece of ink on an edge is a corner touching it, not a line
_CURVE_STEPS = 8

LINES = range(0x2500, 0x2580)
#: the arcs, the diagonals and the dashed lines: they are measured, but a miss is only a warning
SOFT = frozenset((*range(0x2504, 0x250C), *range(0x254C, 0x2550), *range(0x256D, 0x2574)))
# Block Elements that are one rectangle, by the line they divide the cell at
_SPLITS_X = {0x258C: "x1", 0x2596: "x1", 0x2598: "x1",    # end at the vertical middle line
             0x2590: "x0", 0x2597: "x0", 0x259D: "x0"}    # start at it
_SPLITS_Y = {0x2584: "y1", 0x2596: "y1", 0x2597: "y1",    # end at the horizontal middle line
             0x2580: "y0", 0x2598: "y0", 0x259D: "y0"}    # start at it

Span = tuple[float, float]
Segment = tuple[float, float, float, float]
Point = tuple[float, float]


class Member(NamedTuple):
    """One glyph's contribution to a line: where it touches ``edge``, in em."""

    codepoint: int
    edge: str
    start: float


@dataclass(frozen=True)
class Seam:
    """A line whose glyphs do not agree where it is."""

    members: tuple[Member, ...]
    #: em: the largest difference between the glyphs' places for it
    spread: float

    @property
    def soft(self) -> bool:
        """True when a member is an arc, a diagonal or a dashed line (a miss is a warning)."""
        return any(member.codepoint in SOFT for member in self.members)


def _flatten_quad(origin: Point, off: Point, end: Point) -> list[Segment]:
    """Return the straight pieces a quadratic curve is drawn as."""
    pieces: list[Segment] = []
    previous = origin
    for step in range(1, _CURVE_STEPS + 1):
        t = step / _CURVE_STEPS
        u = 1 - t
        point = (u * u * origin[0] + 2 * u * t * off[0] + t * t * end[0],
                 u * u * origin[1] + 2 * u * t * off[1] + t * t * end[1])
        pieces.append((previous[0], previous[1], point[0], point[1]))
        previous = point
    return pieces


def _flatten_cubic(origin: Point, off1: Point, off2: Point, end: Point) -> list[Segment]:
    """Return the straight pieces a cubic curve is drawn as."""
    pieces: list[Segment] = []
    previous = origin
    for step in range(1, _CURVE_STEPS + 1):
        t = step / _CURVE_STEPS
        u = 1 - t
        point = tuple(u**3 * origin[i] + 3 * u * u * t * off1[i] + 3 * u * t * t * off2[i]
                      + t**3 * end[i] for i in (0, 1))
        pieces.append((previous[0], previous[1], point[0], point[1]))
        previous = (point[0], point[1])
    return pieces


def _outline(glyph_set: Any, name: str, scale: float) -> list[Segment]:
    """Return a glyph's outline, in em, as straight segments."""
    pen = DecomposingRecordingPen(glyph_set)
    glyph_set[name].draw(pen)
    segments: list[Segment] = []
    start = current = (0.0, 0.0)
    for operator, args in pen.value:
        if operator == "moveTo":
            start = current = args[0]
        elif operator == "lineTo":
            segments.append((current[0], current[1], args[0][0], args[0][1]))
            current = args[0]
        elif operator == "qCurveTo" and args[-1] is not None:
            for off, end in decomposeQuadraticSegment(args):
                segments.extend(_flatten_quad(current, off, end))
                current = end
        elif operator == "curveTo":
            segments.extend(_flatten_cubic(current, *args))
            current = args[-1]
        elif operator in {"closePath", "endPath"}:
            segments.append((current[0], current[1], start[0], start[1]))
            current = start
    return [(x0 * scale, y0 * scale, x1 * scale, y1 * scale) for x0, y0, x1, y1 in segments]


def _crossings(segments: list[Segment], value: float, *, vertical: bool) -> list[tuple[float, int]]:
    """Return where the outline crosses ``x = value`` (``y = value``): (position, direction)."""
    found: list[tuple[float, int]] = []
    for x0, y0, x1, y1 in segments:
        across0, across1, along0, along1 = (x0, x1, y0, y1) if vertical else (y0, y1, x0, x1)
        if across0 != across1 and min(across0, across1) <= value < max(across0, across1):
            position = along0 + (value - across0) / (across1 - across0) * (along1 - along0)
            found.append((position, 1 if across1 > across0 else -1))
    return sorted(found)


def _ink_along(segments: list[Segment], value: float, *, vertical: bool) -> list[Span]:
    """Return where the ink lies along the line ``x = value`` (``y = value`` if not vertical).

    The ink is where the outline's winding number is not zero, as a renderer fills it.
    """
    spans: list[Span] = []
    winding, start = 0, 0.0
    for position, direction in _crossings(segments, value, vertical=vertical):
        if winding == 0:
            start = position
        winding += direction
        if winding == 0:
            spans.append((start, position))
    return [span for span in spans if span[1] - span[0] >= _MIN_SPAN]


def _ports(segments: list[Segment], cell: Box) -> dict[str, list[Span]]:
    """Return the ink at each of the four edges of the cell, in em along the edge."""
    return {
        "left": _ink_along(segments, cell.x0 + _INSET, vertical=True),
        "right": _ink_along(segments, cell.x1 - _INSET, vertical=True),
        "bottom": _ink_along(segments, cell.y0 + _INSET, vertical=False),
        "top": _ink_along(segments, cell.y1 - _INSET, vertical=False),
    }


def _same_line(first: tuple[Span, ...], other: tuple[Span, ...]) -> bool:
    return len(first) == len(other) and all(
        abs(a[0] - b[0]) <= _SAME_LINE and abs(a[1] - b[1]) <= _SAME_LINE
        for a, b in zip(first, other, strict=True))


def _spread(spans: list[tuple[Span, ...]]) -> float:
    """Return the most any end of the line is placed differently by two of its glyphs."""
    return max(max(group[i][end] for group in spans) - min(group[i][end] for group in spans)
               for i in range(len(spans[0])) for end in (0, 1))


def _seams_of(members: list[tuple[Member, tuple[Span, ...]]]) -> list[Seam]:
    """Group ports into lines, and return the lines whose ports disagree."""
    lines: list[list[tuple[Member, tuple[Span, ...]]]] = []
    for item in sorted(members, key=lambda entry: entry[0].start):
        for line in lines:
            if _same_line(line[0][1], item[1]):
                line.append(item)
                break
        else:
            lines.append([item])
    seams = []
    for line in lines:
        spread = _spread([spans for _member, spans in line])
        if len(line) > 1 and spread > JOIN_WARNING:
            seams.append(Seam(tuple(member for member, _spans in line), spread))
    return seams


def _line_seams(font: TTFont, cell: Box, upm: float) -> list[Seam]:
    """Find the seams among the lines of Box Drawing: horizontal ones, then vertical ones."""
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap() or {}
    across: list[tuple[Member, tuple[Span, ...]]] = []
    down: list[tuple[Member, tuple[Span, ...]]] = []
    for codepoint in LINES:
        name = cmap.get(codepoint)
        if name is None:
            continue
        for edge, spans in _ports(_outline(glyph_set, name, 1 / upm), cell).items():
            if not spans:
                continue
            target = across if edge in {"left", "right"} else down
            target.append((Member(codepoint, edge, spans[0][0]), tuple(spans)))
    return [*_seams_of(across), *_seams_of(down)]


def _bounds_em(glyph_set: Any, name: str, upm: float) -> dict[str, float] | None:
    """Return a glyph's bounds in em as ``x0, y0, x1, y1`` (None for an empty glyph)."""
    pen = BoundsPen(glyph_set)
    glyph_set[name].draw(pen)
    if pen.bounds is None:
        return None
    return dict(zip(("x0", "y0", "x1", "y1"), (value / upm for value in pen.bounds), strict=True))


def _split_seams(font: TTFont, upm: float) -> list[Seam]:
    """Find the seams among the halves and quarters of Block Elements.

    The glyphs that end at the middle of the cell and the ones that start at it must agree
    where the middle is, or a pair of them leaves a gap or overlaps.
    """
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap() or {}
    seams = []
    for splits, label in ((_SPLITS_X, "x"), (_SPLITS_Y, "y")):
        found = []
        for codepoint, side in splits.items():
            bounds = _bounds_em(glyph_set, cmap[codepoint], upm) if codepoint in cmap else None
            if bounds is not None:
                found.append(Member(codepoint, f"split {label}", bounds[side]))
        places = [member.start for member in found]
        if len(found) > 1 and max(places) - min(places) > JOIN_WARNING:
            seams.append(Seam(tuple(found), max(places) - min(places)))
    return seams


def find_seams(font: TTFont, cell: Box, upm: float) -> list[Seam]:
    """Return every line of the font's box glyphs whose glyphs miss each other.

    ``cell`` is the cell of the font in em and ``upm`` its units per em. Lines that miss
    by no more than :data:`JOIN_WARNING` are not reported.
    """
    return [*_line_seams(font, cell, upm), *_split_seams(font, upm)]
