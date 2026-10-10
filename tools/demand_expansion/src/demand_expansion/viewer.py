"""The viewer's data: reference facts, the route table, and the oracle.

Plan package 06. Greg, 2026-10-10: first screen a phase with drill-down,
self-contained, changeable multipliers, then switchable alternates.

Switchable alternates in any combination cannot be precomputed (deltas do
not compose when two alternates touch one chain), so the page carries a
JavaScript port of the four rules, `expand` and `aggregate`, and runs it
live. That port is checked, not trusted: the payload embeds this engine's
coefficients for every recipe multiplier and two phase tables, and the page
recomputes the default configuration on every load and compares. A
difference shows as a banner. `tests/test_demand_expansion_viewer_engine.py`
runs the same comparison in Node when Node is present.

Sub-1x recipe settings are not offered: the floor rule is open (§3.2.3).
"""
from __future__ import annotations

from production_adapter.contracts import RecipeId
from production_adapter.gamedata import GameBuild, ProjectAssemblyRequirement, RecipeUnlock
from production_adapter.scenario import Scenario

from .aggregate import aggregate
from .graph import RecipeGraph, primary_output
from .report import build_dataset, route_table_sha256

#: Record 3.2.1's option sets, less the sub-1x recipe settings.
RECIPE_MULTIPLIERS: tuple[float, ...] = (1.0, 1.25, 1.5, 1.75, 2.0)
PROJECT_ASSEMBLY_MULTIPLIERS: tuple[float, ...] = (0.25, 0.5, 0.75, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0)
#: Phase tables embedded as fixtures for the page's self-check.
FIXTURE_COMBOS: tuple[tuple[float, float], ...] = ((1.0, 1.0), (1.25, 2.0))


def _key(x: float) -> str:
    return f"{x:g}"


def _alternate_reason(graph: RecipeGraph, rid: RecipeId) -> str:
    """Why an alternate cannot be pinned on this table, or "" when it can.
    The same conditions `graph.build` refuses, stated up front for the list."""
    data = graph.data
    r = data.recipes[rid]
    item = primary_output(r)
    if item not in data.items:
        return "makes an item not listed in items.csv"
    if item in data.resource_items:
        return f"makes {data.items[item].display_name}, a resource; resources are leaves"
    if any(p.item_id == item for p in graph.routes.pins):
        return f"{data.items[item].display_name} carries a base-recipe pin on this table"
    return ""


def viewer_payload(
    graph: RecipeGraph,
    deliveries: tuple[ProjectAssemblyRequirement, ...],
    build: GameBuild,
    unlocks: dict[RecipeId, tuple[RecipeUnlock, ...]] | None = None,
    recipe_multipliers: tuple[float, ...] = RECIPE_MULTIPLIERS,
    project_assembly_multipliers: tuple[float, ...] = PROJECT_ASSEMBLY_MULTIPLIERS,
) -> dict:
    """Everything the page needs, JSON-ready, deterministic (no clock)."""
    data = graph.data
    unlocks = unlocks or {}
    recipes = {
        rid: {
            "n": r.display_name,
            "alt": r.is_alternate,
            "in": [[i, a, u] for i, a, u in r.input_amounts],
            "out": [[i, a, u] for i, a, u in r.output_amounts],
        }
        for rid, r in sorted(data.recipes.items())
    }
    alternates = []
    for rid, r in sorted(data.recipes.items()):
        if not r.is_alternate:
            continue
        item = primary_output(r)
        alternates.append([
            rid, r.display_name, item,
            "; ".join(f"T{u.tech_tier} {u.display_name}" for u in unlocks.get(rid, ())),
            _alternate_reason(graph, rid),
        ])
    oracle_coefficients: dict[str, list] = {}
    for r in recipe_multipliers:
        ds = build_dataset(graph, deliveries, build, Scenario(recipe_input_multiplier=r))
        oracle_coefficients[_key(r)] = [
            [c["source_item_id"], c["target_item_id"], c["per_target"],
             c["direct_per_target"], c["depth"],
             {"resource": "R", "coproduct": "C", "recipe": ""}[c["supplied_by"]]]
            for c in ds.coefficients
        ]
    oracle_phases: dict[str, dict] = {}
    for r, pa in FIXTURE_COMBOS:
        sc = Scenario(recipe_input_multiplier=r, project_assembly_requirement_multiplier=pa)
        pd = aggregate(graph, deliveries, sc)
        oracle_phases[f"{_key(r)}|{_key(pa)}"] = {
            "cells": [
                [item, c.phase, float(c.quantity), float(c.previous), c.growth.kind,
                 None if c.growth.ratio is None else float(c.growth.ratio),
                 float(c.cumulative), float(c.remaining), c.complete, c.cumulative_complete,
                 c.remaining_complete]
                for item in sorted(pd.cells) for c in pd.item(item)
            ],
            "complete": {str(p): pd.complete[p] for p in pd.phases},
        }
    return {
        "names": {i: it.display_name for i, it in data.items.items()},
        "resources": sorted(data.resource_items),
        "recipes": recipes,
        "routes": {
            "name": graph.routes.name,
            "exclusions": [e.recipe_id for e in graph.routes.exclusions],
            "pins": [[p.item_id, p.recipe_id] for p in graph.routes.pins],
            "alternates": [[a.item_id, a.recipe_id] for a in graph.routes.alternates],
        },
        "alternates": alternates,
        "deliveries": [
            [d.phase, d.phase_name, d.item_id, d.quantity_1x, d.delivery_unlocks] for d in deliveries
        ],
        "recipe_multipliers": [_key(r) for r in recipe_multipliers],
        "pa_multipliers": [_key(pa) for pa in project_assembly_multipliers],
        "fluid_rounding_unit": Scenario().fluid_rounding_unit,
        "provenance": {
            "game_version": build.game_version,
            "build_number": build.build_number,
            "game_build_id": build.game_build_id,
            "docs_sha256": build.docs_sha256,
            "route_table": graph.routes.name,
            "route_table_sha256": route_table_sha256(graph.routes),
        },
        "oracle": {"coefficients": oracle_coefficients, "phases": oracle_phases},
    }
