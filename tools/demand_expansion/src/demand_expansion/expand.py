"""The engine: one target, one route table, one scenario -> quantities per unit.

Recursive expansion with memoisation per item. At each item the one enabled
recipe is taken (or refused by name), its scaled per-cycle inputs are divided
by the primary output's per-cycle count, and the children's own expansions are
added in proportion. The scenario's per-cycle, per-input rounding (record
3.2.5) is applied by `ReferenceData.with_scenario` BEFORE the division, which
is what makes a 1.25x setting compound unevenly through a chain rather than
scale it.

The coefficient is kept at every intermediate part, not just the leaves: the
Motor question is "Motors per rocket", and an ore-only answer would lose it.
"""
from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from production_adapter.contracts import ItemId, RecipeId
from production_adapter.gamedata import ReferenceData
from production_adapter.scenario import FLUID_ROUNDING_VARIANTS, Scenario

from .contracts import CycleDetected, Expansion, FluidRoundingUndeclared, NotExpandable
from .graph import RecipeGraph, route_for


class _Undeclared:
    """Sentinel: the caller said nothing about fluid rounding."""

    def __repr__(self) -> str:
        return "UNDECLARED"


UNDECLARED = _Undeclared()


def _frac(x: float) -> Fraction:
    """Exact from the stated decimal. `repr` of a float that came from "2.5" is
    "2.5"; the reference layer states counts, not computed floats."""
    return Fraction(repr(x))


def _scaled_data(graph: RecipeGraph, scenario: Scenario, fluid_rounding) -> tuple[ReferenceData, str | None]:
    if fluid_rounding is UNDECLARED:
        # The observed rule (Amendment 2, 2026-10-10). Until that read the engine
        # refused here, because the adapter's default was an assumption.
        fluid_rounding = scenario.fluid_rounding_unit
    if scenario.recipe_input_multiplier == 1.0:
        return graph.data, fluid_rounding
    if fluid_rounding not in FLUID_ROUNDING_VARIANTS:
        raise FluidRoundingUndeclared(
            f"fluid_rounding must be one of {FLUID_ROUNDING_VARIANTS}, got {fluid_rounding!r}"
        )
    declared = replace(scenario, fluid_rounding_unit=fluid_rounding)
    return graph.data.with_scenario(declared), fluid_rounding


def expand(
    graph: RecipeGraph,
    target: ItemId,
    scenario: Scenario = Scenario(),
    fluid_rounding=UNDECLARED,
) -> Expansion:
    """Quantities per one unit of `target`. See `contracts.Expansion`.

    `fluid_rounding` defaults to the scenario's `fluid_rounding_unit`, whose
    default is the observed rule ("mL", Amendment 2). "m3" is selectable only
    to reproduce figures computed before the 2026-10-10 read. At 1x nothing
    rounds and the value is recorded as given.
    """
    if graph.is_resource(target):
        raise NotExpandable(f"{target} is a resource; resources are leaves")
    data, fluid_unit = _scaled_data(graph, scenario, fluid_rounding)

    # per-item memo of (embedded, depth, cycles, coproducts) for ONE unit of it
    memo: dict[ItemId, tuple[dict, dict, dict, dict]] = {}

    def one_unit(item: ItemId, path: tuple[ItemId, ...]) -> tuple[dict, dict, dict, dict]:
        if item in memo:
            return memo[item]
        if item in path:
            raise CycleDetected(path[path.index(item):] + (item,))
        rid = route_for(graph, item, path)
        recipe = data.recipes[rid]
        out_amt = _frac(recipe.output_amounts[0][1])
        embedded: dict[ItemId, Fraction] = {}
        depth: dict[ItemId, int] = {}
        cycles: dict[RecipeId, Fraction] = {rid: 1 / out_amt}
        coproducts: dict[ItemId, Fraction] = {}
        for co_item, co_amt, _ in recipe.output_amounts[1:]:
            coproducts[co_item] = coproducts.get(co_item, Fraction(0)) + _frac(co_amt) / out_amt
        for in_item, in_amt, _ in recipe.input_amounts:
            per = _frac(in_amt) / out_amt
            embedded[in_item] = embedded.get(in_item, Fraction(0)) + per
            depth[in_item] = min(depth.get(in_item, 1), 1)
            if graph.is_resource(in_item):
                continue
            c_emb, c_dep, c_cyc, c_co = one_unit(in_item, path + (item,))
            for k, v in c_emb.items():
                embedded[k] = embedded.get(k, Fraction(0)) + per * v
            for k, v in c_dep.items():
                depth[k] = min(depth.get(k, v + 1), v + 1)
            for k, v in c_cyc.items():
                cycles[k] = cycles.get(k, Fraction(0)) + per * v
            for k, v in c_co.items():
                coproducts[k] = coproducts.get(k, Fraction(0)) + per * v
        memo[item] = (embedded, depth, cycles, coproducts)
        return memo[item]

    embedded, depth, cycles, coproducts = one_unit(target, ())
    rid = route_for(graph, target)
    recipe = data.recipes[rid]
    out_amt = _frac(recipe.output_amounts[0][1])
    direct: dict[ItemId, Fraction] = {}
    for in_item, in_amt, _ in recipe.input_amounts:
        direct[in_item] = direct.get(in_item, Fraction(0)) + _frac(in_amt) / out_amt
    return Expansion(
        target=target,
        route_table=graph.routes.name,
        recipe_input_multiplier=scenario.recipe_input_multiplier,
        fluid_rounding_unit=fluid_unit,
        direct=direct,
        embedded=dict(sorted(embedded.items())),
        depth=dict(sorted(depth.items())),
        recipe_cycles=dict(sorted(cycles.items())),
        coproducts=dict(sorted(coproducts.items())),
    )
