"""By-products: what a plan makes and nothing consumes, and where it goes.

Site-planner reframe A16 and A17, decided by Greg 2026-11-17.

    A16  "By products can be sent to AWESOME sink by default for now but
         should participate in production when available and appropriate to
         supply"
    A17  "Fluids need to be converted or packaged before they can go to sink.
         Fuel gets used for power. Heavy oil residue gets converted to fuel
         and the byproduct of that conversion goes to sink"

The solve still lets a by-product feed any owned recipe that consumes it where
that serves its objective (reframe A8.2 measured Polymer Resin going to
Residual Plastic). This module disposes of what is STILL left over, as a
chain:

    power        a fluid an owned generator burns. Fuel by Greg's ruling; the
                 other generator fluids (Turbofuel, Liquid Biofuel) follow the
                 same rule, which is Claude's reading of it (A17.2)
    convert      a fluid with a declared conversion (CONVERSIONS: Heavy Oil
                 Residue -> Residual Fuel). The products are disposed of in
                 turn: Fuel to power, any solid to the sink
    sink         a solid, AWESOME Sink owned (points per minute from items.csv)
    *_not_owned  the generator, recipe or sink is not unlocked yet; named
    needs_packaging  any other fluid. Packaging (canisters) is not modelled

A report, not a constraint. The plan was solved with unconsumed output FREE
(LP D1 stopgap); the conversion refineries' and generators' figures here are
what disposing of the leftover would take, P-scaled. Sink power is not in the
reference layer and is not charged.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

from production_adapter.contracts import ItemFlow, ItemId, ProducerClass, RecipeId
from production_adapter.gamedata import ReferenceData, load_generators, load_sink_points

from .playthrough import PlaythroughState
from .unlocks import buildings_unlocked

SINK_BUILDING = "Desc_ResourceSink_C"

SINK = "sink"
SINK_NOT_UNLOCKED = "sink_not_unlocked"
POWER = "power"
POWER_NOT_OWNED = "power_not_owned"
CONVERT = "convert"
CONVERT_NOT_OWNED = "convert_not_owned"
NEEDS_PACKAGING = "needs_packaging"

#: Greg, 2026-11-17 (A17): "Heavy oil residue gets converted to fuel". The
#: one declared conversion; a fluid is never routed through a recipe the
#: table does not name.
CONVERSIONS: dict[ItemId, RecipeId] = {
    "Desc_HeavyOilResidue_C": "Recipe_ResidualFuel_C",
}

_TOL = 1e-6


@dataclass(frozen=True)
class Byproduct:
    item_id: ItemId
    rate_per_min: float
    disposition: str
    sink_points_per_min: float | None = None       # SINK
    generator_class: ProducerClass | None = None   # POWER
    generators: float | None = None                # POWER: units at 100 %
    power_mw: float | None = None                  # POWER: generated
    recipe_id: RecipeId | None = None              # CONVERT
    machines: float | None = None                  # CONVERT: at 100 %
    machine_mw: float | None = None                # CONVERT: drawn, P-scaled
    downstream: tuple["Byproduct", ...] = ()       # CONVERT: its products


def sink_unlocked(repo_root: str | pathlib.Path, state: PlaythroughState) -> bool:
    owned = state.owned_schematics
    open_buildings, _ = buildings_unlocked(repo_root, lambda s: s.schematic_id in owned)
    return SINK_BUILDING in open_buildings


def ledger(
    repo_root: str | pathlib.Path,
    data: ReferenceData,
    state: PlaythroughState,
    items: tuple[ItemFlow, ...],
    delivered: dict[ItemId, float],
    owned_recipes: tuple[RecipeId, ...] = (),
) -> tuple[Byproduct, ...]:
    """Every item a plan makes beyond what it consumes and delivers, disposed
    of as A16/A17 say. `owned_recipes` gates a conversion (availability's
    owned set); generators and the sink are gated by the state's buildings."""
    owned = state.owned_schematics
    open_buildings, _ = buildings_unlocked(repo_root, lambda s: s.schematic_id in owned)
    ctx = _Ctx(
        data=data,
        points=load_sink_points(repo_root),
        can_sink=SINK_BUILDING in open_buildings,
        burners={},
        owned_recipes=frozenset(owned_recipes),
    )
    for g in load_generators(repo_root):
        built = "Desc_" + g.generator_class[len("Build_"):] in open_buildings
        ctx.burners.setdefault(g.fuel_item_id, []).append((g, built))
    out = []
    for f in items:
        left = f.produced_per_min - f.consumed_per_min - delivered.get(f.item_id, 0.0)
        if left > _TOL:
            out.append(_dispose(ctx, f.item_id, left, depth=0))
    return tuple(sorted(out, key=lambda b: b.item_id))


@dataclass
class _Ctx:
    data: ReferenceData
    points: dict[ItemId, int]
    can_sink: bool
    burners: dict
    owned_recipes: frozenset


def _dispose(ctx: _Ctx, item: ItemId, rate: float, depth: int) -> Byproduct:
    if depth > 4:
        raise ValueError(f"{item}: disposal chain deeper than 4; CONVERSIONS loops")
    if ctx.data.items[item].form == "solid":
        if ctx.can_sink:
            return Byproduct(item, rate, SINK, sink_points_per_min=rate * ctx.points.get(item, 0))
        return Byproduct(item, rate, SINK_NOT_UNLOCKED)
    burners = ctx.burners.get(item, [])
    if burners:
        built = [g for g, ok in burners if ok]
        if not built:
            return Byproduct(item, rate, POWER_NOT_OWNED, generator_class=burners[0][0].generator_class)
        if len({g.generator_class for g in built}) != 1:
            raise ValueError(f"{item}: burned by several owned generator classes; "
                             "which one is a choice this ledger does not make")
        g = built[0]
        units = rate / g.burn_rate_per_min
        return Byproduct(item, rate, POWER, generator_class=g.generator_class,
                         generators=units, power_mw=units * g.power_mw)
    recipe_id = CONVERSIONS.get(item)
    if recipe_id is not None:
        if recipe_id not in ctx.owned_recipes:
            return Byproduct(item, rate, CONVERT_NOT_OWNED, recipe_id=recipe_id)
        recipe = ctx.data.recipes[recipe_id]
        per_machine = dict(recipe.inputs)[item]
        machines = rate / per_machine
        others = [i for i, _ in recipe.inputs if i != item]
        if others:
            raise ValueError(f"{recipe_id} needs {others} beside {item}; a conversion "
                             "takes the by-product alone")
        downstream = tuple(_dispose(ctx, out, machines * r, depth + 1)
                           for out, r in recipe.outputs)
        return Byproduct(item, rate, CONVERT, recipe_id=recipe_id, machines=machines,
                         machine_mw=machines * recipe.power.mean_mw,
                         downstream=downstream)
    return Byproduct(item, rate, NEEDS_PACKAGING)


def flatten(byproducts: tuple[Byproduct, ...]) -> tuple[Byproduct, ...]:
    """Every step of every chain, depth first: for totals and reports."""
    out = []
    for b in byproducts:
        out.append(b)
        out.extend(flatten(b.downstream))
    return tuple(out)


def report_lines(byproducts: tuple[Byproduct, ...]) -> list[str]:
    """One line per disposal step, indented down each chain (reframe A16/A17)."""
    lines = []

    def walk(b, indent):
        if b.disposition == POWER:
            how = f"{b.generators:.3g} x {b.generator_class}, {b.power_mw:.4g} MW"
        elif b.disposition == CONVERT:
            how = f"{b.machines:.3g} x {b.recipe_id}, {b.machine_mw:.3g} MW drawn"
        elif b.disposition == SINK:
            how = f"{b.sink_points_per_min:.4g} points/min"
        else:
            how = ""
        lines.append(f"{indent}by-product {b.item_id}: {b.rate_per_min:.4g}/min -> "
                     f"{b.disposition}" + (f" ({how})" if how else ""))
        for d in b.downstream:
            walk(d, indent + "  ")

    for b in byproducts:
        walk(b, "  ")
    return lines
