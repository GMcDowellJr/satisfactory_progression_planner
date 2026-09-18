"""Which recipes a tech tier grants — and, loudly, which ones it does not.

The production adapter is forbidden to know what a tier is: `gamedata.py` reads six
reference tables and none of them is a schematic, and the boundary invariant in
`docs/decisions/production_solver_selection.md` section 6 is that "the adapter never
sees a progression concept". So this lives outside it, imports
`production_adapter.contracts` for its types, and is imported by the adapter never.
Same one-way shape as the demand expansion module in section 11.1 of the formulation
record.

What this does and does not do, because "unlocks" sits close enough to "planner" to
wander:

    does       resolve a tech tier into the recipe ids that tier grants, and report
               what it could not account for
    does not   walk `schematic_dependencies.csv`, or infer anything from one unlock
               to another. It is a filter, not a progression model.
    does not   decide which schematics to pursue, or value them

The rule, arrived at by measurement rather than assumption (formulation record
section 18):

    a recipe is granted at tier N when some schematic of type Milestone, Tutorial or
    Custom, with tech_tier <= N, unlocks it, AND recipes.csv does not flag it as an
    alternate

Milestone and Tutorial alone are not enough. `Recipe_IngotIron_C`,
`Recipe_IronPlate_C` and `Recipe_IronRod_C` come from "Starting Blueprints", an
EST_Custom schematic, so a Milestone-only filter returns a recipe set that cannot
smelt iron. Custom carries cosmetics and FICSMAS too; those are harmless because
nothing targets them.

**Tier is not the whole of availability.** 46 of the 181 base recipes are reachable
only through MAM research, which is player-driven. This module withholds them and
says so on every call rather than letting their absence be inferred from silence.
`declared` is the escape hatch: the caller names what they have actually researched
or holds as an alternate. Nothing here guesses it.
"""
from __future__ import annotations

import csv
import pathlib
from dataclasses import dataclass

from production_adapter.contracts import AllowedRecipes, RecipeId, RecipeMode

from .pool import PoolAvailability, available_at

REFERENCE_SUBPATH = pathlib.Path("planning_data") / "game" / "reference"

#: Schematic types that a tech tier accounts for. MAM is player-driven research and
#: Alternate is hard-drive loot; neither is implied by reaching a tier.
PROGRESSION_TYPES = frozenset({"EST_Milestone", "EST_Tutorial", "EST_Custom"})

#: Types whose presence on a granted recipe means the tier may be overstating it.
RESEARCH_TYPES = frozenset({"EST_MAM", "EST_Alternate"})


class UnlockDataError(RuntimeError):
    """The reference layer is missing something this module requires."""


def _rows(path: pathlib.Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise UnlockDataError(f"missing reference table: {path}")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


@dataclass(frozen=True)
class TierUnlocks:
    """What tier N grants, what it withholds, and what it is unsure about."""

    tier: int
    recipe_ids: tuple[RecipeId, ...]
    declared: tuple[RecipeId, ...]
    withheld_research: tuple[RecipeId, ...]    # base recipes reachable only via MAM
    withheld_alternates: tuple[RecipeId, ...]  # alternates not enabled
    uncertain: tuple[RecipeId, ...]            # granted, but also research-gated
    pool: PoolAvailability | None = None       # set when include_pool was asked for

    @property
    def allowed_recipes(self) -> AllowedRecipes:
        """Ready to hand to `SolveRequest`. Explicit, never a mode."""
        return AllowedRecipes(mode=RecipeMode.EXPLICIT, recipe_ids=self.recipe_ids)

    def report(self) -> str:
        """The completeness statement. Printed on every use, by intention."""
        lines = [
            f"tier {self.tier}: {len(self.recipe_ids)} recipes enabled"
            + (f", {len(self.declared)} of them declared" if self.declared else ""),
            f"  withheld: {len(self.withheld_research)} base recipes reachable only "
            "through MAM research, and "
            f"{len(self.withheld_alternates)} alternates. A tech tier does not imply "
            "either — name what you have with `declared`.",
        ]
        if self.pool is not None:
            lines.append("  " + self.pool.report().replace("\n  ", "\n  "))
        if self.uncertain:
            lines.append(
                f"  uncertain: {len(self.uncertain)} granted recipes are also unlocked "
                "by research or hard-drive schematics, so the tier may be overstating "
                f"them: {', '.join(self.uncertain)}"
            )
        lines.append(
            "  this filter does not walk schematic dependencies; it resolves a tier, "
            "it does not model progression."
        )
        return "\n".join(lines)


def at_tier(
    repo_root: str | pathlib.Path,
    tier: int,
    declared: tuple[RecipeId, ...] | list[RecipeId] = (),
    include_pool: bool = False,
) -> TierUnlocks:
    """Resolve a tech tier into a recipe set. Raises rather than guessing.

    `declared` is added verbatim — MAM research completed, alternates held. It is
    validated against `recipes.csv` and otherwise not interpreted.

    `include_pool` widens the answer from "what you can build now" to "what a plan
    may reach for": the alternates obtainable at this tier without research, per
    `pool.available_at`. An alternate in the pool is something you can go and get,
    so a plan that uses one is actionable rather than fictional. Default False,
    because it changes what the returned set means and no existing caller asked
    for it.
    """
    if tier < 0:
        raise ValueError(f"tier must be non-negative, got {tier}")
    ref = pathlib.Path(repo_root) / REFERENCE_SUBPATH

    recipes = {r["recipe_id"]: r["is_alternate"] == "true" for r in _rows(ref / "recipes.csv")}
    schematics = {s["schematic_id"]: s for s in _rows(ref / "schematics.csv")}

    granted: set[RecipeId] = set()
    by_research: set[RecipeId] = set()
    for row in _rows(ref / "schematic_recipe_unlocks.csv"):
        recipe_id = row["recipe_id"]
        if recipe_id not in recipes:
            continue  # building and customiser recipes; not production
        schematic = schematics.get(row["schematic_id"])
        if schematic is None:
            raise UnlockDataError(
                f"{row['schematic_id']} unlocks {recipe_id} but is absent from schematics.csv"
            )
        kind = schematic["schematic_type"]
        if kind in RESEARCH_TYPES:
            by_research.add(recipe_id)
        if kind in PROGRESSION_TYPES and int(schematic["tech_tier"]) <= tier:
            granted.add(recipe_id)

    base = {r for r, is_alt in recipes.items() if not is_alt}
    alternates = {r for r, is_alt in recipes.items() if is_alt}
    granted &= base

    declared = tuple(declared)
    unknown = [r for r in declared if r not in recipes]
    if unknown:
        raise ValueError(f"declared recipe ids not in recipes.csv: {sorted(unknown)}")

    pool = available_at(repo_root, tier) if include_pool else None
    enabled = granted | set(declared) | (set(pool.recipe_ids) if pool else set())
    return TierUnlocks(
        tier=tier,
        recipe_ids=tuple(sorted(enabled)),
        declared=tuple(sorted(declared)),
        withheld_research=tuple(sorted((base - enabled) & by_research)),
        withheld_alternates=tuple(sorted(alternates - enabled)),
        uncertain=tuple(sorted(granted & by_research - set(declared))),
        pool=pool,
    )
