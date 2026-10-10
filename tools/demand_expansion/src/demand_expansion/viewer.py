"""The viewer's data: every supported multiplier combination, computed here.

Plan package 06, built after the reports proved insufficient on their own
(Greg, 2026-10-10: "first screen phase with drill down / nested parts",
"self contained", then "changeable recipe and elevator parts multipliers").

The page is static and carries no engine. Instead it carries the result of
the engine for every combination of the game's option sets (record 3.2.1):
recipe cost 1 / 1.25 / 1.5 / 1.75 / 2 (the sub-1x settings need a floor the
record leaves open and are not offered) and Space Elevator deliverable 0.25
to 100. Per-unit coefficients depend only on the recipe multiplier; phase
tables depend on both. Fifty phase tables and five coefficient sets, about a
megabyte, so a switch on the page is a lookup and every figure it shows was
produced by the same code the tests pin. No rule is re-implemented in
JavaScript.

This module produces the payload as data and writes nothing; the CLI's
`viewer` command inlines it into `tools/demand_expansion/viewer/template.html`.
"""
from __future__ import annotations

from production_adapter.gamedata import GameBuild, ProjectAssemblyRequirement
from production_adapter.scenario import Scenario

from .aggregate import aggregate
from .graph import RecipeGraph
from .report import build_dataset, config_id, route_table_sha256

#: Record 3.2.1's option sets, less the sub-1x recipe settings.
RECIPE_MULTIPLIERS: tuple[float, ...] = (1.0, 1.25, 1.5, 1.75, 2.0)
PROJECT_ASSEMBLY_MULTIPLIERS: tuple[float, ...] = (0.25, 0.5, 0.75, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0)


def _key(x: float) -> str:
    return f"{x:g}"


def viewer_payload(
    graph: RecipeGraph,
    deliveries: tuple[ProjectAssemblyRequirement, ...],
    build: GameBuild,
    recipe_multipliers: tuple[float, ...] = RECIPE_MULTIPLIERS,
    project_assembly_multipliers: tuple[float, ...] = PROJECT_ASSEMBLY_MULTIPLIERS,
) -> dict:
    """Everything the page needs, JSON-ready, deterministic (no clock)."""
    data = graph.data
    names = {i: it.display_name for i, it in data.items.items()}
    by_recipe: dict[str, dict] = {}
    by_combo: dict[str, dict] = {}
    for r in recipe_multipliers:
        scenario = Scenario(recipe_input_multiplier=r)
        ds = build_dataset(graph, deliveries, build, scenario)
        by_recipe[_key(r)] = {
            "config_id": ds.config_id,
            # [source, target, per_unit, direct_per_unit, depth, supplied_by initial]
            "coefficients": [
                [c["source_item_id"], c["target_item_id"], c["per_target"],
                 c["direct_per_target"], c["depth"], c["supplied_by"][0]]
                for c in ds.coefficients
            ],
            "unresolved_targets": [
                [u["item_id"], u["refusal"]] for u in ds.unresolved if u["kind"] == "target"
            ],
        }
        for pa in project_assembly_multipliers:
            sc = Scenario(recipe_input_multiplier=r, project_assembly_requirement_multiplier=pa)
            pd = aggregate(graph, deliveries, sc)
            cells = []
            for item in sorted(pd.cells):
                for c in pd.item(item):
                    cells.append([
                        item, c.phase, float(c.quantity), float(c.previous), c.growth.kind,
                        None if c.growth.ratio is None else float(c.growth.ratio),
                        float(c.cumulative), float(c.remaining),
                        c.complete, c.cumulative_complete, c.remaining_complete,
                    ])
            by_combo[f"{_key(r)}|{_key(pa)}"] = {
                "config_id": config_id(graph.routes, sc, pd.fluid_rounding_unit),
                "phases": cells,
                "deliveries": [
                    [d.phase, d.item_id, d.quantity_1x, float(d.quantity), d.refusal]
                    for d in pd.deliveries
                ],
                "complete": {str(p): pd.complete[p] for p in pd.phases},
            }
    phase_names = {}
    delivery_unlocks = {}
    for d in deliveries:
        phase_names[str(d.phase)] = d.phase_name
        delivery_unlocks[str(d.phase)] = d.delivery_unlocks
    return {
        "names": names,
        "resources": sorted(data.resource_items),
        "coproduct_leaves": sorted(graph.coproduct_leaves),
        "phase_names": phase_names,
        "delivery_unlocks": delivery_unlocks,
        "recipe_multipliers": [_key(r) for r in recipe_multipliers],
        "pa_multipliers": [_key(pa) for pa in project_assembly_multipliers],
        "provenance": {
            "game_version": build.game_version,
            "build_number": build.build_number,
            "game_build_id": build.game_build_id,
            "docs_sha256": build.docs_sha256,
            "route_table": graph.routes.name,
            "route_table_sha256": route_table_sha256(graph.routes),
            "fluid_rounding_unit": Scenario().fluid_rounding_unit,
            "alternates": [a.recipe_id for a in graph.routes.alternates],
        },
        "by_recipe": by_recipe,
        "by_combo": by_combo,
    }
