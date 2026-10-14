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
3. among those, the weight equal to the target's; else a *similar* weight (see
   ``SIMILAR_WEIGHTS``: Thin, ExtraLight and Light are one family of styles, and so are
   Medium, SemiBold and Black), the nearest of them; else the nearest weight of all.
   When two are equally near the lighter one is taken.

The same classes decide which spellings the style list merges into one entry, so what
the list shows as one style is what the mapping serves with one file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import starmap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from font_composer.common.library import Family, FontLibrary, StyleEntry

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


# The name a weight class goes by as a style type, and the weights a font may carry
# between them (450 is Regular or Medium, whichever is nearer).
REGULAR = 400
TYPE_NAMES: dict[int, str] = {
    100: "Thin", 200: "ExtraLight", 300: "Light", 400: "Regular", 500: "Medium",
    600: "SemiBold", 700: "Bold", 800: "ExtraBold", 900: "Black", 950: "ExtraBlack",
}


#: Weights that count as the same style for matching and for the style list, each with the
#: one it is listed under. Thin and Light (and the ExtraLight between them) are one family
#: of styles; Medium, SemiBold and Black are another, listed as SemiBold. Regular, Bold and
#: ExtraBold stand alone.
SIMILAR_WEIGHTS: dict[int, int] = {
    100: 300, 200: 300, 300: 300,
    400: 400,
    500: 600, 600: 600, 900: 600, 950: 600,
    700: 700,
    800: 800,
}


def similar_weight(weight: int) -> int:
    """Return the weight a style is listed under: the main one of its similar weights."""
    nearest = min(SIMILAR_WEIGHTS, key=lambda known: abs(known - weight))
    return SIMILAR_WEIGHTS[nearest]


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
        prefix = f"configured style {override!r} not found in {family.display_name}; "
    if target is None:
        return StyleChoice(None, prefix + "style name not recognised; map it explicitly")
    pool = [style for style in family.styles if style.info.names.italic == target.italic]
    if not pool:
        kind = "italic" if target.italic else "upright"
        reason = f"{family.display_name} has no {kind} style; map one explicitly"
        return StyleChoice(None, prefix + reason)

    def distance(style: StyleEntry) -> tuple[int, int]:
        return abs(style.info.names.weight - target.weight), style.info.names.weight

    exact = [style for style in pool if style.info.names.weight == target.weight]
    if exact:
        return StyleChoice(min(exact, key=distance), prefix + f"weight {target.weight} matches")
    kin = [style for style in pool
           if similar_weight(style.info.names.weight) == similar_weight(target.weight)]
    if kin:
        best = min(kin, key=distance)
        return StyleChoice(best, prefix + f"similar style: weight {best.info.names.weight} "
                           f"for {target.weight}")
    best = min(pool, key=distance)
    return StyleChoice(best, prefix + f"nearest weight: {best.info.names.weight} "
                       f"for {target.weight}")


def nearest_weight(weight: int) -> int:
    """Return the standard weight class nearest to a font's weight."""
    return min(TYPE_NAMES, key=lambda known: abs(known - weight))


def style_type_name(weight: int, *, italic: bool) -> str:
    """Return the style type a weight and slant make: ``Bold``, ``Italic``, ``Light Italic``.

    Fonts spell one style many ways (``bold``, ``Bold``, ``Oblique`` for ``Italic``); a
    style type is what the numbers say, so each is listed once.
    """
    nearest = nearest_weight(weight)
    name = TYPE_NAMES[nearest]
    if not italic:
        return name
    return "Italic" if nearest == REGULAR else f"{name} Italic"


@dataclass(frozen=True)
class StyleOption:
    """A style type the user can include or leave out, as the fonts spell it or merged."""

    name: str
    weight: int
    italic: bool
    #: the other spellings merged into this one (empty when not consolidated)
    similar: tuple[str, ...] = ()

    @property
    def order(self) -> tuple[bool, int, str]:
        """Sort key: upright first, light to heavy."""
        return self.italic, self.weight, self.name

    @property
    def members(self) -> tuple[str, ...]:
        """The entry's own name and every spelling merged into it."""
        return (self.name, *self.similar)


def _compact(name: str) -> str:
    """Return a style name without case, spaces, hyphens and underscores."""
    return re.sub(r"[\s_\-]+", "", name.lower())


def same_style_name(first: str, second: str) -> bool:
    """Tell whether two style names are one name: they differ only in case, spaces, - or _."""
    return _compact(first) == _compact(second)


def _spellings(library: FontLibrary) -> dict[str, tuple[str, int, bool]]:
    """Return every style name the fonts carry: compact key -> (name, weight, italic)."""
    found: dict[str, tuple[str, int, bool]] = {}

    def note(name: str, weight: int, *, italic: bool) -> None:
        key = _compact(name)
        if key:
            found.setdefault(key, (name.strip(), weight, italic))

    for family in library.families:
        for style in family.styles:
            names = style.info.names
            note(names.style, names.weight, italic=names.italic)
            for instance in style.info.named_instances:
                target = parse_style_name(instance)
                if target is not None:
                    note(instance, target.weight, italic=target.italic)
    return found


def style_options(library: FontLibrary, *, consolidate: bool) -> list[StyleOption]:
    """List the styles the fonts hold, once each.

    Spelled as the fonts do (``Heavy``, ``Black``, ``Book``, ``Regular``), or, when
    ``consolidate`` is set, merged by what the numbers say with the same weight and slant
    rule the style mapping uses: ``Heavy`` and ``Black`` are one entry named ``SemiBold`` (with
    ``Medium``) that lists them as similar. Which is shown never changes how files are matched.
    """
    spellings = _spellings(library).values()
    if not consolidate:
        return sorted(starmap(StyleOption, spellings), key=lambda option: option.order)
    merged: dict[tuple[int, bool], list[tuple[str, int, bool]]] = {}
    for name, weight, italic in spellings:
        merged.setdefault((similar_weight(weight), italic), []).append((name, weight, italic))
    options = []
    for (weight, italic), members in merged.items():
        type_name = style_type_name(weight, italic=italic)
        compact = _compact(type_name)
        similar = sorted(name for name, _weight, _italic in members if _compact(name) != compact)
        options.append(StyleOption(type_name, weight, italic, tuple(similar)))
    return sorted(options, key=lambda option: option.order)


def is_included(option: StyleOption, included: Collection[str]) -> bool:
    """Tell whether a style entry is built: it, or a spelling merged into it, is included."""
    return option.name in included or any(name in included for name in option.similar)


def output_styles(
    library: FontLibrary, included: Collection[str], *, consolidate: bool = True,
) -> list[str]:
    """Return the styles that are built, in the shape the list is shown in.

    Consolidated, one entry stands for all its spellings, so including ``Black`` builds
    ``SemiBold``; not consolidated, each spelling the fonts carry is its own style.
    """
    options = style_options(library, consolidate=consolidate)
    return [option.name for option in options if is_included(option, included)]


#: The longest style name a user may give a style.
STYLE_NAME_MAX = 40
_FORBIDDEN_IN_NAMES = frozenset('<>:"/\\|?*')


def _name_shape_problem(text: str) -> str | None:
    """Say why a style name cannot be written to a file and a font's names, or None."""
    if not any(char.isalnum() for char in text):
        return "a style name needs at least one letter or digit"
    if len(text) > STYLE_NAME_MAX:
        return f"a style name has at most {STYLE_NAME_MAX} characters"
    if not text.isprintable() or any(char in _FORBIDDEN_IN_NAMES for char in text):
        return "a style name may not hold control characters or any of < > : \" / \\ | ? *"
    return None


def style_name_problem(
    library: FontLibrary, style: str, name: str, custom_names: Mapping[str, str],
) -> str | None:
    """Say why ``name`` cannot be what ``style`` is called, or None when it can.

    A style keeps the name the fonts give it (``Oblique``); a custom name is only what it is
    called in the built font and its file. Names are compared without case, spaces, hyphens
    and underscores, and a name may not be one that another style goes by: either a name the
    fonts carry (in either listing, consolidated or not, so that switching the listing never
    makes two styles one) or a custom name of another style. The style's own name is always
    fine (it takes the custom name away).
    """
    text = name.strip()
    problem = _name_shape_problem(text)
    if problem is not None or same_style_name(text, style):
        return problem
    key = _compact(text)
    taken = {_compact(spelling) for spelling, _weight, _italic in _spellings(library).values()}
    for consolidate in (False, True):
        for option in style_options(library, consolidate=consolidate):
            taken.update(_compact(member) for member in option.members)
    if key in taken:
        return f"'{text}' is already in use"
    for other, custom in custom_names.items():
        if other != style and _compact(custom) == key:
            return f"'{text}' is already in use"
    return None
