"""What a declared playthrough state makes available, at milestone resolution.

Reconciliation R5; site-planner reframe A15.2 (Greg, 2026-11-17):

    Q2   availability follows the milestones owned; "tier N" is a shortcut for
         every milestone up to N (`playthrough(through_tier=N)`)
    B2   which extractor and belt marks are considered follows what is
         unlocked: at the start of phase 2 with steel there is no Miner Mk.2
         (Advanced Steel Production) and no Belt Mk.3 (Logistics Mk.3), though
         both are tier 4
    B5   recipe status: OWNED / IN_POOL / MAM_RESEARCH / LOCKED. "Eligible" and
         "accessible" collapse to the pool (Q3)

A filter and a report. It chooses nothing: no mark is preferred here (that is
`infrastructure`'s declared policy) and no alternate is recommended.

The grant joins are `unlocks.recipe_grants`, `unlocks.extractors_open` and
`unlocks.generators_open`, the same functions `at_tier` and the tier filters
use, with "owned" in place of "reached at tier N". So for
`playthrough(through_tier=N)` with nothing else declared, the owned recipe set
equals `at_tier(N).recipe_ids` by construction, and a test pins it.

What this does NOT do, said on every report:

- walk `schematic_dependencies.csv`. MAM_RESEARCH means some MAM schematic
  unlocks the recipe, not that its research prerequisites are met;
- model hard-drive odds or scanned-but-unclaimed offers (A15.2 B5, deferred);
- decide pool membership finer than the tier band. The pool is read at the
  highest tech tier among the milestones owned (LP formulation §19: automatic
  entry by tier band).
"""
from __future__ import annotations

import enum
import pathlib
from dataclasses import dataclass

from production_adapter.contracts import AllowedRecipes, ItemId, ProducerClass, RecipeId, RecipeMode
from production_adapter.gamedata import Capability, load_logistics, load_schematic_rows

from .playthrough import PlaythroughState
from .pool import PoolAvailability, available_at
from .unlocks import (
    PROGRESSION_TYPES, UnlockDataError, extractors_open, generators_open, recipe_grants,
)


class RecipeStatus(enum.Enum):
    OWNED = "owned"                # buildable now
    IN_POOL = "in_pool"            # an alternate the next hard drive can offer
    MAM_RESEARCH = "mam_research"  # some MAM schematic unlocks it (prerequisites not walked)
    LOCKED = "locked"              # needs progression first


@dataclass(frozen=True)
class Availability:
    state: PlaythroughState
    pool_tier: int
    recipe_ids: tuple[RecipeId, ...]                  # OWNED production recipes
    status: dict[RecipeId, RecipeStatus]
    extractors: dict[ItemId, tuple[ProducerClass, ...]]
    logistics: tuple[Capability, ...]                 # the marks the owned milestones unlock
    pool: PoolAvailability

    @property
    def allowed_recipes(self) -> AllowedRecipes:
        """Ready to hand to a solve. Explicit, never a mode."""
        return AllowedRecipes(mode=RecipeMode.EXPLICIT, recipe_ids=self.recipe_ids)

    def with_status(self, status: RecipeStatus) -> tuple[RecipeId, ...]:
        return tuple(sorted(r for r, s in self.status.items() if s is status))

    def capabilities(self, capability_type: str) -> tuple[Capability, ...]:
        """Available marks of one kind ("belt", "conveyor_lift", "pipeline",
        "miner"), lowest capacity first. Ordered by capacity, never by parsing
        the mark's name."""
        return tuple(sorted(
            (c for c in self.logistics if c.capability_type == capability_type),
            key=lambda c: c.capacity_per_min,
        ))

    def report(self) -> str:
        counts = {s: len(self.with_status(s)) for s in RecipeStatus}
        marks = ", ".join(
            f"{kind} {'/'.join(c.mark for c in self.capabilities(kind)) or 'none'}"
            for kind in ("belt", "conveyor_lift", "pipeline", "miner")
        )
        shortcut = (f"through tier {self.state.through_tier} + named"
                    if self.state.through_tier is not None else "named only")
        return "\n".join([
            f"state: {len(self.state.milestones)} milestones ({shortcut}), "
            f"{len(self.state.research)} research, {len(self.state.alternates)} alternates",
            f"  recipes: {counts[RecipeStatus.OWNED]} owned, {counts[RecipeStatus.IN_POOL]} in "
            f"the pool (read at tier {self.pool_tier}), {counts[RecipeStatus.MAM_RESEARCH]} by "
            f"MAM research, {counts[RecipeStatus.LOCKED]} locked",
            f"  logistics: {marks}",
            "  not modelled: research prerequisites (schematic_dependencies is not "
            "walked), hard-drive odds, scanned-but-unclaimed offers.",
        ])


def availability(repo_root: str | pathlib.Path, state: PlaythroughState) -> Availability:
    owned = state.owned_schematics
    progression_owned = frozenset(state.milestones)

    def owns(s) -> bool:
        return s.schematic_id in owned

    research_owned = frozenset(state.research)
    recipes, by_progression, by_research = recipe_grants(
        repo_root, lambda s: s.schematic_id in progression_owned)
    _, by_owned_research, _ = recipe_grants(repo_root, lambda s: s.schematic_id in research_owned)
    base = {r for r, alt in recipes.items() if not alt}
    # Progression-type schematics grant base recipes only (the at_tier rule,
    # LP §18). Completed MAM research grants what it unlocks, alternate or not:
    # research recipes such as Turbofuel are not hard-drive loot. Computed from
    # the research set directly: Compacted Coal is also listed under a
    # progression-type schematic, so "all grants minus progression grants"
    # would drop it (caught by test, 2026-11-17).
    owned_recipes = (by_progression & base) | by_owned_research | set(state.alternates)

    tiers = [s.tech_tier for s in load_schematic_rows(repo_root)
             if s.schematic_id in progression_owned and s.schematic_type == "EST_Milestone"]
    pool_tier = max(tiers, default=0)
    pool = available_at(repo_root, pool_tier)
    in_pool = set(pool.recipe_ids)  # automatic entry only (LP §19)

    status: dict[RecipeId, RecipeStatus] = {}
    for recipe_id, is_alternate in recipes.items():
        if recipe_id in owned_recipes:
            status[recipe_id] = RecipeStatus.OWNED
        elif is_alternate and recipe_id in in_pool:
            status[recipe_id] = RecipeStatus.IN_POOL
        elif recipe_id in by_research or (is_alternate and recipe_id in pool.research_gated):
            status[recipe_id] = RecipeStatus.MAM_RESEARCH
        else:
            status[recipe_id] = RecipeStatus.LOCKED

    return Availability(
        state=state,
        pool_tier=pool_tier,
        recipe_ids=tuple(sorted(owned_recipes)),
        status=status,
        extractors=extractors_open(repo_root, owns),
        logistics=_logistics(repo_root, owned),
        pool=pool,
    )


def generators_available(
    repo_root: str | pathlib.Path,
    state: PlaythroughState,
    generator_classes: tuple[ProducerClass, ...],
) -> tuple[ProducerClass, ...]:
    """The given generator classes the state can build, in the order given."""
    owned = state.owned_schematics
    return generators_open(repo_root, lambda s: s.schematic_id in owned, generator_classes)


def _logistics(repo_root, owned: frozenset[str]) -> tuple[Capability, ...]:
    """Capabilities whose unlocking milestone is owned. The join is the
    milestone named in the table's `unlock` text against
    `schematics.display_name` (progression types, same tech tier); a name that
    matches zero or several schematics is refused rather than picked."""
    by_name: dict[str, list] = {}
    for s in load_schematic_rows(repo_root):
        if s.schematic_type in PROGRESSION_TYPES:
            by_name.setdefault(s.display_name, []).append(s)
    caps, _ = load_logistics(repo_root)
    out = []
    for c in caps:
        hits = [s for s in by_name.get(c.unlock_milestone, []) if s.tech_tier == c.unlock_tier]
        if len(hits) != 1:
            raise UnlockDataError(
                f"{c.capability_id}: unlock milestone {c.unlock_milestone!r} at tier "
                f"{c.unlock_tier} matches {len(hits)} schematics"
            )
        if hits[0].schematic_id in owned:
            out.append(c)
    return tuple(out)
