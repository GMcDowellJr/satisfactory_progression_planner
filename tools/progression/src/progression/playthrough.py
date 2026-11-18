"""A playthrough's declared state: which milestones, research and alternates it holds.

Site-planner reframe A15.2 Q2 (Greg, 2026-11-17): availability follows the
milestones OWNED, not the tier. "Phase N" or "tier N" is a shortcut for every
milestone up to N. Milestones within a phase need not be taken in order, or at
all, so the input is a declared set. Reconciliation R5.

This module holds state; it does not read a save, infer purchases, or decide
what to buy next. Every id is validated against the reference layer and an
unknown or mistyped one is refused by name:

    milestones   progression-type schematics (Milestone, Tutorial, Custom) bought
    research     MAM schematics completed
    alternates   alternate recipes selected from hard drives (by recipe id)

`through_tier` fills `milestones` with every progression-type schematic whose
tech_tier is at most N, the same set `unlocks.schematics_at_tier` returns, so a
state built that way is exactly what `unlocks.at_tier(N)` assumes. Named
milestones are added to it, which is how "start of phase 2 with steel" is
spelled: `through_tier=2, milestones=("Schematic_3-?_C", ...)`.

Hard-drive alternates are held by recipe id because a drive offers recipes, not
schematics. Scanned-but-unclaimed offers are not state here (A15.2 B5:
deferred).
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

from production_adapter.contracts import RecipeId
from production_adapter.gamedata import load_recipe_rows, load_schematic_rows

from .unlocks import PROGRESSION_TYPES, SchematicId, schematics_at_tier

#: MAM research is the only research the state holds; hard-drive schematics
#: (EST_Alternate) are held through `alternates`, by recipe.
RESEARCH_TYPE = "EST_MAM"


class PlaythroughError(ValueError):
    """A declared state names something the reference layer does not have."""


@dataclass(frozen=True)
class PlaythroughState:
    """Sorted, de-duplicated ids. Build it with `playthrough()`, which validates."""

    milestones: tuple[SchematicId, ...]
    research: tuple[SchematicId, ...] = ()
    alternates: tuple[RecipeId, ...] = ()
    #: The shortcut used, if any; reported, never re-applied.
    through_tier: int | None = None

    @property
    def owned_schematics(self) -> frozenset[SchematicId]:
        return frozenset(self.milestones) | frozenset(self.research)


def playthrough(
    repo_root: str | pathlib.Path,
    *,
    through_tier: int | None = None,
    milestones: tuple[SchematicId, ...] | list[SchematicId] = (),
    research: tuple[SchematicId, ...] | list[SchematicId] = (),
    alternates: tuple[RecipeId, ...] | list[RecipeId] = (),
) -> PlaythroughState:
    """Declare a state. Refuses an empty declaration and any unknown or mistyped id."""
    if through_tier is None and not milestones:
        raise PlaythroughError(
            "declare through_tier and/or milestones: a state with no milestones "
            "would unlock nothing, not even Starting Blueprints"
        )
    if through_tier is not None and through_tier < 0:
        raise PlaythroughError(f"through_tier must be non-negative, got {through_tier}")

    types = {s.schematic_id: s.schematic_type for s in load_schematic_rows(repo_root)}
    _check(types, milestones, PROGRESSION_TYPES, "milestones",
           "a Milestone, Tutorial or Custom schematic")
    _check(types, research, frozenset({RESEARCH_TYPE}), "research", "a MAM schematic")

    alternate_ids = {r.recipe_id for r in load_recipe_rows(repo_root) if r.is_alternate}
    not_alternates = sorted(set(alternates) - alternate_ids)
    if not_alternates:
        raise PlaythroughError(f"alternates names recipes that are not alternates: {not_alternates}")

    owned = set(milestones)
    if through_tier is not None:
        owned |= set(schematics_at_tier(repo_root, through_tier))
    return PlaythroughState(
        milestones=tuple(sorted(owned)),
        research=tuple(sorted(set(research))),
        alternates=tuple(sorted(set(alternates))),
        through_tier=through_tier,
    )


def _check(types: dict[str, str], ids, allowed: frozenset[str], field: str, what: str) -> None:
    unknown = sorted(i for i in ids if i not in types)
    if unknown:
        raise PlaythroughError(f"{field}: not in schematics.csv: {unknown}")
    wrong = sorted(i for i in ids if types[i] not in allowed)
    if wrong:
        raise PlaythroughError(f"{field}: not {what}: {[(i, types[i]) for i in wrong]}")
