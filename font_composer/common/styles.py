"""Which style file of a family serves an output style.

Style *names* differ between families for the same thing (Oblique and Italic, Book and
Regular, Demi and SemiBold), so a donor file is never found by name. The fonts carry
numbers that mean the same everywhere: the OS/2 weight class (100 Thin ... 400 Regular
... 700 Bold ... 900 Black) and the italic/oblique flag. A wanted style name is turned
into such a pair once, and a donor is picked by it. The default rules, in order:

1. a ``[styles.<Output>]`` entry of the configuration naming a file (or a style name)
   of that family wins;
2. otherwise only styles with the same slant are considered: an italic target is never
   served by an upright file or the other way round (a synthesised slant looks wrong,
   so a family without an italic simply has no donor for an italic target until the
   user maps one explicitly);
3. among those, the weight equal to the target's, else the nearest; when two are
   equally near the lighter one is taken.

Medium (500) and Black (900) are therefore different styles, and a Regular target is
served by Book (400) but by SemiBold (600) only when nothing lighter is nearer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from font_composer.common.library import Family, StyleEntry

_ITALIC_WORDS = ("italic", "oblique", "slanted", "inclined")

# Compact lower-case style words (spaces, hyphens, underscores removed) -> weight class.
WEIGHT_WORDS: dict[str, int] = {
    "": 400, "regular": 400, "normal": 400, "book": 400, "roman": 400, "text": 400,
    "plain": 400,
    "thin": 100, "hairline": 100,
    "extralight": 200, "ultralight": 200,
    "light": 300,
    "medium": 500,
    "semibold": 600, "demibold": 600, "demi": 600,
    "bold": 700,
    "extrabold": 800, "ultrabold": 800,
    "black": 900, "heavy": 900,
    "extrablack": 950, "ultrablack": 950,
}


@dataclass(frozen=True)
class StyleTarget:
    """An output style as numbers: the name given, a weight class and the slant."""

    name: str
    weight: int
    italic: bool


@dataclass(frozen=True)
class StyleChoice:
    """The style file picked for a target, or None, and why."""

    entry: StyleEntry | None
    reason: str
    overridden: bool = False


def parse_style_name(name: str) -> StyleTarget | None:
    """Turn a style name such as ``Bold Italic`` into numbers; None if unrecognised."""
    compact = re.sub(r"[\s_\-]+", "", name.lower())
    italic = any(word in compact for word in _ITALIC_WORDS)
    for word in _ITALIC_WORDS:
        compact = compact.replace(word, "")
    weight = WEIGHT_WORDS.get(compact)
    if weight is None:
        return None
    return StyleTarget(name=name, weight=weight, italic=italic)


def find_style(family: Family, value: str) -> StyleEntry | None:
    """Find a style of a family by file name, else by its (unique) style name."""
    for style in family.styles:
        if style.file_name == value:
            return style
    wanted = value.strip().lower()
    named = [style for style in family.styles if style.info.names.style.lower() == wanted]
    return named[0] if len(named) == 1 else None


def resolve_style(
    family: Family, target: StyleTarget | None, override: str | None = None,
) -> StyleChoice:
    """Pick the style file of ``family`` that serves ``target`` by the rules above."""
    prefix = ""
    if override:
        entry = find_style(family, override)
        if entry is not None:
            return StyleChoice(entry, f"set in the configuration: {override}", overridden=True)
        prefix = f"configured style {override!r} not found in {family.label}; "
    if target is None:
        return StyleChoice(None, prefix + "style name not recognised; map it explicitly")
    pool = [style for style in family.styles if style.info.names.italic == target.italic]
    if not pool:
        kind = "italic" if target.italic else "upright"
        return StyleChoice(None, prefix + f"{family.label} has no {kind} style; map one explicitly")
    best = min(pool, key=lambda style: (abs(style.info.names.weight - target.weight),
                                        style.info.names.weight))
    weight = best.info.names.weight
    if weight == target.weight:
        return StyleChoice(best, prefix + f"weight {weight} matches")
    return StyleChoice(best, prefix + f"nearest weight: {weight} for {target.weight}")
