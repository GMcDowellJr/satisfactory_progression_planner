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

from production_adapter.contracts import (
    AllowedRecipes, ItemId, ProducerClass, RecipeId, RecipeMode,
)

from .pool import PoolAvailability, available_at

REFERENCE_SUBPATH = pathlib.Path("planning_data") / "game" / "reference"

#: Schematic types that a tech tier accounts for. MAM is player-driven research and
#: Alternate is hard-drive loot; neither is implied by reaching a tier.
PROGRESSION_TYPES = frozenset({"EST_Milestone", "EST_Tutorial", "EST_Custom"})

#: Types whose presence on a granted recipe means the tier may be overstating it.
RESEARCH_TYPES = frozenset({"EST_MAM", "EST_Alternate"})

SchematicId = str


class UnlockDataError(RuntimeError):
    """The reference layer is missing something this module requires."""


def _reached_at_tier(schematic: dict[str, str], tier: int) -> bool:
    """Whether reaching `tier` accounts for this schematic.

    Extracted 2026-09-22 so the tier filter exists ONCE. `at_tier` resolves it to
    recipes and `schematics_at_tier` to schematic ids, and two copies of a filter
    is how the provenance work's three-lists defect started.
    """
    return (
        schematic["schematic_type"] in PROGRESSION_TYPES
        and int(schematic["tech_tier"]) <= tier
    )


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
        if schematic["schematic_type"] in RESEARCH_TYPES:
            by_research.add(recipe_id)
        if _reached_at_tier(schematic, tier):
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


# --------------------------------------------------------------------------
# tier -> schematics, and what they cost. Added 2026-09-22 for the stock pass.
# --------------------------------------------------------------------------
#
# THE PARKED QUESTION IS ANSWERED. "Whether `unlocks.py` or
# `progression_clusters.csv` already resolves a capability to a numeric tier"
# stood open because that store had not been read. It has now:
# `schematics.csv` carries `tech_tier` as an integer column and this module has
# filtered on it since it was written. Nothing new was needed — the resolution
# existed and returned recipes, and what the stock pass needs is the same
# filter returning schematic ids.
#
# These two RESOLVE and READ. They do not sum: summing quantities is the stock
# pass's, and a filter that started returning bills would have stopped being a
# filter, which this module's own docstring is emphatic about.


def schematics_at_tier(
    repo_root: str | pathlib.Path,
    tier: int,
) -> tuple[SchematicId, ...]:
    """Every schematic reaching `tier` accounts for. CUMULATIVE, not incremental.

    `tech_tier <= tier`, so this is everything bought on the way to the tier and
    not the tier's own row. That is the right shape for a whole-game bill and
    the wrong shape for "what do I still owe" — the difference is what the
    player has already bought, which is state this layer does not hold and does
    not ask for.

    Same three types as `at_tier`: Milestone, Tutorial and Custom. MAM and
    hard-drive schematics are player-driven and are not implied by reaching a
    tier, so their costs are not in a tier's bill either.
    """
    if tier < 0:
        raise ValueError(f"tier must be non-negative, got {tier}")
    ref = pathlib.Path(repo_root) / REFERENCE_SUBPATH
    return tuple(sorted(
        s["schematic_id"]
        for s in _rows(ref / "schematics.csv")
        if _reached_at_tier(s, tier)
    ))


def schematic_costs(
    repo_root: str | pathlib.Path,
) -> dict[SchematicId, tuple[tuple[ItemId, float], ...]]:
    """What each schematic costs to buy. A READ of `schematic_costs.csv`.

    A schematic ABSENT from the result costs nothing, and that is a measured
    claim rather than a convenient reading: every one of the 42 Milestones and
    6 Tutorials carries cost rows, and the 91 uncosted progression-type
    schematics are Custom — starting blueprints, cosmetics, FICSMAS. Asserted
    by `tests/test_progression_unlocks.py`, so a future extraction that drops
    milestone costs fails a test instead of quietly shrinking every bill.

    Costs are in ITEMS and are NOT scenario-scaled. Two Custom rows are priced
    in `Desc_ResourceSinkCoupon_C`, which is not in items.csv because a coupon
    is not a part; the stock pass reports those the same way it reports the
    Portable Miner, by naming them rather than dropping them.
    """
    ref = pathlib.Path(repo_root) / REFERENCE_SUBPATH
    by_schematic: dict[SchematicId, list[tuple[ItemId, float]]] = {}
    for row in _rows(ref / "schematic_costs.csv"):
        by_schematic.setdefault(row["schematic_id"], []).append(
            (row["item_id"], float(row["amount"]))
        )
    return {k: tuple(sorted(v)) for k, v in by_schematic.items()}


def schematics_in_tiers(
    repo_root: str | pathlib.Path,
    tiers: tuple[int, ...],
    exclude: tuple[SchematicId, ...] = (),
) -> tuple[SchematicId, ...]:
    """The schematics whose tech_tier is IN `tiers`. Incremental, not cumulative.

    D3 P6 (Greg, 2026-09-23): which schematics a stage buys stays the caller's
    declaration, and this is an optional helper for building one — the same
    shape as `goal_run.goals_for_phases`. Which tiers a stage covers is
    declared too: the Project Assembly table's `delivery_unlocks` is prose,
    and so is not parsed into a mapping. What the player has already bought is
    caller state; pass the set still owed.

    Same three types as `_reached_at_tier`. A filter: it returns ids and never
    a quantity, which `unlock_cost` sums.

    Only as right as the `tech_tier` column. Schematic_3-2_C (Logistics Mk.2)
    reads tier 2, 4-2_C reads 3 and 5-3_C reads 4. The class names look like
    pre-1.0 numbering with a correct 1.0 tier; that is an INFERENCE, open until
    read in game (D3 note section 6).

    `exclude` (crossover A19, Greg 2026-09-24: "include every milestone and
    allow for exclusion later"): schematics the player will not buy. Every
    one of the tiers' schematics is in by default; an excluded id that the
    tiers do not contain is REFUSED, so a typo cannot silently exclude
    nothing.
    """
    wanted = set(tiers)
    for tier in wanted:
        if tier < 0:
            raise ValueError(f"tier must be non-negative, got {tier}")
    ref = pathlib.Path(repo_root) / REFERENCE_SUBPATH
    found = tuple(sorted(
        s["schematic_id"]
        for s in _rows(ref / "schematics.csv")
        if s["schematic_type"] in PROGRESSION_TYPES and int(s["tech_tier"]) in wanted
    ))
    unknown = [x for x in exclude if x not in found]
    if unknown:
        raise UnlockDataError(
            f"exclude names {unknown}, which tiers {tuple(tiers)} do not contain"
        )
    return tuple(x for x in found if x not in set(exclude))


def extractors_open_at_tier(
    repo_root: str | pathlib.Path,
    tier: int,
) -> dict[ItemId, tuple[ProducerClass, ...]]:
    """Per raw resource, the extractor classes whose BUILD recipe is unlocked by
    a schematic reached at `tier`. Crossover A19.

    Joins resource_extraction_map.csv (resource -> extractor, in table order)
    to building_recipes.csv (building class -> build recipe) and
    schematic_recipe_unlocks.csv, through `Build_X_C -> Desc_X_C` (the join
    `ConstructionData.for_producer` asserts). A resource with no open
    extractor is absent. A filter: it returns classes and chooses none.
    """
    if tier < 0:
        raise ValueError(f"tier must be non-negative, got {tier}")
    ref = pathlib.Path(repo_root) / REFERENCE_SUBPATH
    reached = {
        s["schematic_id"] for s in _rows(ref / "schematics.csv") if _reached_at_tier(s, tier)
    }
    open_recipes = {
        r["recipe_id"] for r in _rows(ref / "schematic_recipe_unlocks.csv")
        if r["schematic_id"] in reached
    }
    open_buildings = {
        r["building_class"] for r in _rows(ref / "building_recipes.csv")
        if r["recipe_id"] in open_recipes
    }
    by_item: dict[ItemId, list[ProducerClass]] = {}
    for r in _rows(ref / "resource_extraction_map.csv"):
        extractor = r["extractor_class"]
        if "Desc_" + extractor[len("Build_"):] in open_buildings:
            by_item.setdefault(r["item_id"], []).append(extractor)
    return {item: tuple(classes) for item, classes in by_item.items()}
