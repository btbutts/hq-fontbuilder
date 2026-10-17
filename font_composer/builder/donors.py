"""Choose, for every output style, the style file each donor family serves it with.

The default rules are those of :mod:`font_composer.common.fonts.styles` (the same the console
shows): a file or style named in ``[styles.<Output>]`` wins, else the style with the same
slant and the same (or a similar) weight. When a family has no style of the wanted weight
(no Bold, say) the build does not quietly settle for the nearest one: it is a *gap*, and a
decision is needed. The decision is one of

* use a style file of the family as it is (the nearest weight is offered first);
* ``synthesize``: embolden a style file of the family (the build draws it again with its
  outline offset), for a heavier target only;
* stop.

A decision made on the terminal is written to ``[styles.<Output>]`` so that it is asked
once. In the configuration the value is a file name or style name, ``synthesize`` (the
nearest lighter style, emboldened) or ``synthesize:<file or style name>``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from font_composer.common.fonts.styles import (
    StyleChoice,
    StyleTarget,
    find_style,
    parse_style_name,
    resolve_style,
    similar_weight,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from font_composer.common.fonts.library import Family, StyleEntry

SYNTHESIZE = "synthesize"


@dataclass(frozen=True)
class Donor:
    """The style file that serves one output style for one family, and how."""

    entry: StyleEntry
    #: draw the outline emboldened (a heavier target than the file)
    synthesize: bool
    #: what was decided and why, for the report
    note: str


@dataclass(frozen=True)
class Gap:
    """A family that has no style of exactly the wanted weight and slant."""

    output: str
    family: Family
    target: StyleTarget | None
    #: what the default rules would use, if anything
    nearest: StyleEntry | None
    reason: str


@dataclass(frozen=True)
class Decision:
    """What to do about a gap: the style file to use and whether to embolden it."""

    entry: StyleEntry
    synthesize: bool = False


class BuildStopError(Exception):
    """The user, or the configuration, declined to go on; the message says why."""


def parse_override(value: str) -> tuple[bool, str | None]:
    """Split a ``[styles.<Output>]`` value into ``(synthesize, file or style name)``."""
    if value == SYNTHESIZE:
        return True, None
    if value.startswith(f"{SYNTHESIZE}:"):
        return True, value.split(":", 1)[1].strip() or None
    return False, value


def override_text(decision: Decision) -> str:
    """Return the ``[styles.<Output>]`` value that records a decision."""
    name = decision.entry.file_name
    return f"{SYNTHESIZE}:{name}" if decision.synthesize else name


def target_of(output: str) -> StyleTarget | None:
    """Turn an output style name into weight and slant (None when unrecognised)."""
    return parse_style_name(output)


def find_gap(
    family: Family, output: str, override: str | None,
) -> tuple[Donor | None, Gap | None]:
    """Resolve a family for an output style: ``(donor, None)`` or ``(None, gap)``."""
    target = target_of(output)
    if override:
        synthesize, name = parse_override(override)
        entry = find_style(family, name) if name else synthesize_start(family, target)
        if entry is not None:
            how = "emboldened" if synthesize else "as is"
            return Donor(entry, synthesize, f"set in the configuration ({how})"), None
    choice: StyleChoice = resolve_style(family, target)
    matched = (choice.entry is not None and target is not None
               and similar_weight(choice.entry.info.names.weight) == similar_weight(target.weight))
    if matched and choice.entry is not None:
        return Donor(choice.entry, False, choice.reason), None
    reason = choice.reason
    if override:
        reason = f"[styles.{output}] {family.label} = {override!r} does not name a style; {reason}"
    return None, Gap(output, family, target, choice.entry, reason)


def synthesize_start(family: Family, target: StyleTarget | None) -> StyleEntry | None:
    """Return the style a synthesized bold starts from: same slant, the heaviest below."""
    if target is None:
        return None
    pool = [style for style in family.styles
            if style.info.names.italic == target.italic
            and style.info.names.weight <= target.weight]
    if not pool:
        pool = [style for style in family.styles if style.info.names.italic == target.italic]
    return max(pool, key=lambda style: style.info.names.weight, default=None)


def resolve_donor(
    family: Family, output: str, override: str | None,
    decide: Callable[[Gap], Decision | None],
) -> tuple[Donor, Decision | None]:
    """Return the donor of a family for an output style, asking ``decide`` about a gap.

    The second item is the decision taken, when there was a gap (so it can be saved).
    """
    donor, gap = find_gap(family, output, override)
    if donor is not None:
        return donor, None
    assert gap is not None
    decision = decide(gap)
    if decision is None:
        msg = f"{family.display_name} has no {output} style: {gap.reason}"
        raise BuildStopError(msg)
    how = "emboldened" if decision.synthesize else "as is"
    note = f"chosen for the missing {output}: {decision.entry.file_name} ({how})"
    return Donor(decision.entry, decision.synthesize, note), decision
