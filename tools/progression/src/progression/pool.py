"""Which alternates are *obtainable* at a tier — not which ones you hold.

Greg's framing, and it is a different question from `unlocks.at_tier`: whether a
recipe is in the hard-drive pool is a fact about progression, while whether you have
pulled it is a fact about your run. The first is what a plan should be allowed to
reach for, because an alternate in the pool is something you can go and get. The
second is only needed when you want to know what you can build *right now*.

Scope, decided deliberately: **automatic pool entry only.** Every row in
`alternate_recipe_unlocks.csv` carries `eligibility_type: automatic_hub` — 79
alternates that enter the pool on reaching a tier band, with no research. The
remaining ~31 alternates enter only through MAM research, and MAM research is not
free: widening the pool while your drive count is low costs you odds on the drives
you still want. That is an advisory about run state, not a filter, so it is not
modelled here and is reported as unaccounted instead.

### The P4 join

`alternate_recipe_unlocks.csv` keys on slugs (`cast_screws`) while `recipes.csv`
uses `Recipe_Alternate_Screw_C`. That gap is the session handoff's open item P4, and
it has blocked progression-gated recipe sets since it was recorded.

It resolves on normalised display names: the unlock table's `recipe_name` is
"Cast Screws" and the recipe's `display_name` is "Alternate: Cast Screws". Stripping
the prefix and comparing alphanumerics matches **all 79 rows, with nothing
ambiguous and nothing unmatched**. `resolve_slugs` is that join, and it raises rather
than dropping a row, so a future game build that breaks the match fails loudly
instead of quietly shrinking the pool.

### What is NOT used, and why

`alternate_choices.csv` looks like the better source — it keys on `recipe_ids`
directly and carries `tech_tier` and `dependency_schematic_ids`. Its ids are sound
(109, no orphans) and its progression columns are not: 98 of 107 recipe rows carry
truncated dependency fragments such as `'1_C'` and `'Research_Quartz_1_1_C;4_C'`,
and its `tech_tier` places 71 alternates at tier 0 while marking every one of them
MAM-gated, which cannot be true because there is no MAM at tier 0. Recorded as a
defect at section 19 of the formulation record; not read here.
"""
from __future__ import annotations

import csv
import pathlib
import re
from dataclasses import dataclass

from production_adapter.contracts import RecipeId

REFERENCE_SUBPATH = pathlib.Path("planning_data") / "game" / "reference"

#: The only eligibility this module models. Anything else needs research.
AUTOMATIC_ELIGIBILITY = "automatic_hub"


class PoolDataError(RuntimeError):
    """The pool tables cannot be resolved against the recipe table."""


def _normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower().replace("alternate:", ""))


def _rows(path: pathlib.Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise PoolDataError(f"missing reference table: {path}")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _band_max_tier(cluster_id: str) -> int:
    """`tier_3_4` -> 4, `tier_9` -> 9, `pre_tier_1_2` -> 0.

    The cluster table carries a `sort_order` but no tier column, so the band is read
    off the identifier. `resolve_clusters` asserts the result is monotonic in
    `sort_order`, which is what keeps this from being a guess.
    """
    if cluster_id.startswith("pre_"):
        return 0
    digits = [int(part) for part in cluster_id.split("_") if part.isdigit()]
    if not digits:
        raise PoolDataError(f"cannot read a tier band from cluster id {cluster_id!r}")
    return max(digits)


def resolve_clusters(repo_root: str | pathlib.Path) -> dict[str, int]:
    """Cluster id -> the highest tech tier in its band."""
    rows = _rows(pathlib.Path(repo_root) / REFERENCE_SUBPATH / "progression_clusters.csv")
    bands = {r["progression_cluster_id"]: _band_max_tier(r["progression_cluster_id"]) for r in rows}
    ordered = sorted(rows, key=lambda r: int(r["sort_order"]))
    tiers = [bands[r["progression_cluster_id"]] for r in ordered]
    if tiers != sorted(tiers):
        raise PoolDataError(
            f"tier bands read from cluster ids are not monotonic in sort_order: {tiers}"
        )
    return bands


def resolve_slugs(repo_root: str | pathlib.Path) -> dict[str, RecipeId]:
    """The P4 join: unlock-table slug -> `Recipe_*_C`. Raises on any failure."""
    ref = pathlib.Path(repo_root) / REFERENCE_SUBPATH
    by_name: dict[str, list[RecipeId]] = {}
    for row in _rows(ref / "recipes.csv"):
        by_name.setdefault(_normalise(row["display_name"]), []).append(row["recipe_id"])

    resolved: dict[str, RecipeId] = {}
    for row in _rows(ref / "alternate_recipe_unlocks.csv"):
        candidates = by_name.get(_normalise(row["recipe_name"]), [])
        if len(candidates) != 1:
            raise PoolDataError(
                f"slug {row['recipe_id']!r} ({row['recipe_name']!r}) matched "
                f"{len(candidates)} recipes: {candidates}"
            )
        resolved[row["recipe_id"]] = candidates[0]
    return resolved


@dataclass(frozen=True)
class PoolAvailability:
    """Alternates obtainable at a tier, and what this does not account for."""

    tier: int
    recipe_ids: tuple[RecipeId, ...]
    by_cluster: dict[str, tuple[RecipeId, ...]]
    not_yet: tuple[RecipeId, ...]       # automatic, but in a later band
    research_gated: tuple[RecipeId, ...]  # never automatic; needs MAM

    def report(self) -> str:
        return (
            f"pool at tier {self.tier}: {len(self.recipe_ids)} alternates obtainable "
            f"without research, {len(self.not_yet)} in later tier bands.\n"
            f"  unaccounted: {len(self.research_gated)} alternates enter the pool only "
            "through MAM research. Researching them widens the pool, which costs odds "
            "on the drives you have not pulled yet — an advisory about run state, not "
            "a filter, and not modelled here."
        )


def available_at(repo_root: str | pathlib.Path, tier: int) -> PoolAvailability:
    """Alternates in the hard-drive pool at `tier`, by automatic entry only."""
    if tier < 0:
        raise ValueError(f"tier must be non-negative, got {tier}")
    ref = pathlib.Path(repo_root) / REFERENCE_SUBPATH

    bands = resolve_clusters(repo_root)
    slugs = resolve_slugs(repo_root)
    alternates = {
        row["recipe_id"] for row in _rows(ref / "recipes.csv") if row["is_alternate"] == "true"
    }

    available: set[RecipeId] = set()
    later: set[RecipeId] = set()
    by_cluster: dict[str, set[RecipeId]] = {}
    automatic: set[RecipeId] = set()

    for row in _rows(ref / "alternate_recipe_unlocks.csv"):
        if row["eligibility_type"] != AUTOMATIC_ELIGIBILITY:
            continue
        recipe_id = slugs[row["recipe_id"]]
        cluster = row["progression_cluster_id"]
        if cluster not in bands:
            raise PoolDataError(f"unknown progression cluster {cluster!r}")
        automatic.add(recipe_id)
        if bands[cluster] <= tier:
            available.add(recipe_id)
            by_cluster.setdefault(cluster, set()).add(recipe_id)
        else:
            later.add(recipe_id)

    return PoolAvailability(
        tier=tier,
        recipe_ids=tuple(sorted(available)),
        by_cluster={k: tuple(sorted(v)) for k, v in sorted(by_cluster.items())},
        not_yet=tuple(sorted(later)),
        research_gated=tuple(sorted(alternates - automatic)),
    )
