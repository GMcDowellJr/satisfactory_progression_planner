"""Independent demand propagation, used ONLY to check a solver's arithmetic.

This exists because plan section 11 requires fixed-recipe results to reconcile
against independently calculated values before recipe-selection optimisation is
trusted. It reproduced Candidate A's Smart Plating result to four decimal places
during Phase 0.

Deliberately crippled, and it must stay that way.

    It refuses to choose. If an item can be produced by more than one enabled
    recipe it raises AmbiguousDemand rather than picking. Choosing between
    recipes is what a production solver does, and the entire point of Phase 0
    was not to write one.

    It has no CLI, no __main__, no entry point, and lives under tests/ with a
    leading underscore so it is not importable as a tool.

    It reports no power, no machine counts, no build costs.

If a future change needs it to select a recipe, that is the signal to use the
real solver, not to extend this. The structural guard is the AmbiguousDemand
raise: a thing that cannot choose cannot quietly become a second solver.
"""
from __future__ import annotations

import collections
import csv
import pathlib
from dataclasses import dataclass

REF = pathlib.Path(__file__).resolve().parents[1] / "planning_data" / "game" / "reference"
MAX_DEPTH = 64


class AmbiguousDemand(RuntimeError):
    """More than one enabled recipe produces an item. The oracle will not choose."""


class UnproducibleItem(RuntimeError):
    """No enabled recipe produces a non-raw item."""


@dataclass(frozen=True)
class OracleResult:
    recipe_multipliers: dict[str, float]   # recipe_id -> fractional machine equivalents
    raw_inputs: dict[str, float]           # resource item_id -> per-minute


def _rows(name):
    with open(REF / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load(allowed_recipes: set[str] | None):
    prod = collections.defaultdict(list)
    cons = collections.defaultdict(list)
    for r in _rows("recipe_io.csv"):
        (prod if r["direction"] == "output" else cons)[r["recipe_id"]].append(
            (r["item_id"], float(r["rate_per_min"]))
        )
    is_alt = {r["recipe_id"]: r["is_alternate"] == "true" for r in _rows("recipes.csv")}
    enabled = set(is_alt) if allowed_recipes is None else set(allowed_recipes)
    if allowed_recipes is None:
        enabled = {k for k, alt in is_alt.items() if not alt}
    unknown = enabled - set(is_alt)
    if unknown:
        raise ValueError(f"unknown recipe ids: {sorted(unknown)}")
    by_item = collections.defaultdict(list)
    for rid in enabled:
        for item, rate in prod[rid]:
            by_item[item].append((rid, rate))
    raw = {r["item_id"] for r in _rows("items.csv") if r["category"] == "resource"}
    return by_item, cons, raw


def demand(
    item_id: str,
    rate_per_min: float,
    allowed_recipes: set[str] | None = None,
    input_multiplier: float = 1.0,
) -> OracleResult:
    """Propagate demand for one item down to raw resources, fixed recipes only.

    `allowed_recipes=None` means every non-alternate recipe, which is the only
    configuration guaranteed to be unambiguous across the whole tree.
    """
    by_item, cons, raw = _load(allowed_recipes)
    multipliers: dict[str, float] = collections.defaultdict(float)
    raws: dict[str, float] = collections.defaultdict(float)

    def walk(item: str, rate: float, depth: int) -> None:
        if depth > MAX_DEPTH:
            raise RecursionError(f"demand cycle or excessive depth at {item}")
        if item in raw:
            raws[item] += rate
            return
        candidates = by_item.get(item, [])
        if not candidates:
            raise UnproducibleItem(f"no enabled recipe produces {item}")
        if len(candidates) > 1:
            raise AmbiguousDemand(
                f"{item} is produced by {len(candidates)} enabled recipes "
                f"({sorted(r for r, _ in candidates)}). This oracle does not choose — "
                "use the production solver."
            )
        rid, out_rate = candidates[0]
        mult = rate / out_rate
        multipliers[rid] += mult
        for in_item, in_rate in cons.get(rid, ()):
            walk(in_item, in_rate * mult * input_multiplier, depth + 1)

    walk(item_id, rate_per_min, 0)
    return OracleResult(dict(multipliers), dict(raws))
