"""Reference outputs as DATA: rows, provenance and a Markdown report.

Plan section 7 datasets A (dependency coefficients) and B (phase demand),
plus the unresolved list. This module produces rows and text and writes
nothing; `tools/demand_expansion_cli.py` serialises them, because this package
opens no file (boundary test) and the CSV/JSON writers that must pin LF live
where `tests/test_writers_emit_lf.py` scans.

Determinism is the gate (plan section 4, package 05): rows are sorted by their
identifiers, quantities carry an exact rational beside the float, and the
provenance stamp has no clock unless the caller passes one. Two runs over the
same inputs produce equal datasets, and a test says so.

Ordering is by id, never by size: analysis quantifies and never ranks
(demand-expansion record §5.5). The reader orders by looking.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction

from production_adapter.contracts import ItemId
from production_adapter.gamedata import GameBuild, ProjectAssemblyRequirement
from production_adapter.scenario import Scenario

from .aggregate import PhaseDemand, aggregate
from .contracts import DemandExpansionError, RouteTable
from .expand import UNDECLARED, expand
from .graph import RecipeGraph

COEFFICIENT_COLUMNS = (
    "config_id", "source_item_id", "source_name", "target_item_id", "target_name",
    "per_target", "per_target_exact", "direct_per_target", "direct_per_target_exact",
    "depth",
)
PHASE_COLUMNS = (
    "config_id", "item_id", "item_name", "phase", "phase_name",
    "quantity", "quantity_exact", "previous", "growth_kind", "growth_ratio",
    "cumulative", "remaining", "complete", "cumulative_complete", "remaining_complete",
)
UNRESOLVED_COLUMNS = ("config_id", "kind", "item_id", "item_name", "phase", "refusal")


def config_id(routes: RouteTable, scenario: Scenario, fluid_rounding_unit: str | None) -> str:
    """A stable identifier for one configuration: route table, the two
    material multipliers, the fluid variant. Power is not material (record
    3.3) and is not part of it."""
    return (
        f"{routes.name}"
        f"/recipe{scenario.recipe_input_multiplier:g}"
        f"/pa{scenario.project_assembly_requirement_multiplier:g}"
        f"/fluid-{fluid_rounding_unit or 'none'}"
    )


def route_table_sha256(routes: RouteTable) -> str:
    """Content hash of a route table: what was excluded and what was pinned,
    reasons included, so a reworded reason is a different table."""
    payload = {
        "name": routes.name,
        "exclusions": [[e.recipe_id, e.reason] for e in routes.exclusions],
        "pins": [[p.item_id, p.recipe_id, p.reason] for p in routes.pins],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def in_scope_targets(graph: RecipeGraph) -> tuple[ItemId, ...]:
    """SPECIFICATION §7: listed in items.csv, not a resource, has an enabled
    producer. An ambiguous producer is in scope and lands in `unresolved`.

    "Not a resource" needs no test here: `graph.build` never enables a recipe
    whose primary output is a resource, so no resource is a key of
    `producers`. A guard for it was removed on 2026-10-10 after a mutation
    check showed it could not fire; the scope test still asserts the property,
    now as a fact about `build`."""
    return tuple(sorted(i for i in graph.producers if i in graph.data.items))


def _name(graph: RecipeGraph, item_id: ItemId) -> str:
    item = graph.data.items.get(item_id)
    return item.display_name if item else item_id


def _num(x: Fraction) -> float:
    return float(x)


@dataclass(frozen=True)
class Dataset:
    config_id: str
    provenance: dict
    coefficients: tuple[dict, ...]
    phases: tuple[dict, ...]
    unresolved: tuple[dict, ...]
    phase_demand: PhaseDemand


def build_dataset(
    graph: RecipeGraph,
    deliveries: tuple[ProjectAssemblyRequirement, ...],
    build: GameBuild,
    scenario: Scenario = Scenario(),
    fluid_rounding=UNDECLARED,
    generated_at: str | None = None,
    repo_head: str | None = None,
) -> Dataset:
    """Datasets A and B for one configuration, with provenance.

    `generated_at` and `repo_head` are stamped as given and are the only
    non-deterministic fields; leave them None to compare two runs.
    """
    fluid_unit = scenario.fluid_rounding_unit if fluid_rounding is UNDECLARED else fluid_rounding
    cid = config_id(graph.routes, scenario, fluid_unit)

    coefficients: list[dict] = []
    unresolved: list[dict] = []
    for target in in_scope_targets(graph):
        try:
            e = expand(graph, target, scenario, fluid_rounding)
        except DemandExpansionError as err:
            unresolved.append({
                "config_id": cid, "kind": "target", "item_id": target,
                "item_name": _name(graph, target), "phase": "",
                "refusal": f"{type(err).__name__}: {err}",
            })
            continue
        for source, per in e.embedded.items():
            direct = e.direct.get(source, Fraction(0))
            coefficients.append({
                "config_id": cid,
                "source_item_id": source, "source_name": _name(graph, source),
                "target_item_id": target, "target_name": _name(graph, target),
                "per_target": _num(per), "per_target_exact": str(per),
                "direct_per_target": _num(direct), "direct_per_target_exact": str(direct),
                "depth": e.depth[source],
            })
    coefficients.sort(key=lambda r: (r["source_item_id"], r["target_item_id"]))

    pd = aggregate(graph, deliveries, scenario, fluid_rounding)
    phase_names = {d.phase: d.phase_name for d in deliveries}
    phases: list[dict] = []
    for item_id in sorted(pd.cells):
        for cell in pd.item(item_id):
            phases.append({
                "config_id": cid, "item_id": item_id, "item_name": _name(graph, item_id),
                "phase": cell.phase, "phase_name": phase_names[cell.phase],
                "quantity": _num(cell.quantity), "quantity_exact": str(cell.quantity),
                "previous": _num(cell.previous),
                "growth_kind": cell.growth.kind,
                "growth_ratio": "" if cell.growth.ratio is None else _num(cell.growth.ratio),
                "cumulative": _num(cell.cumulative), "remaining": _num(cell.remaining),
                "complete": cell.complete,
                "cumulative_complete": cell.cumulative_complete,
                "remaining_complete": cell.remaining_complete,
            })
    for u in pd.unresolved:
        unresolved.append({
            "config_id": cid, "kind": "delivery", "item_id": u.item_id,
            "item_name": _name(graph, u.item_id), "phase": u.phase, "refusal": u.refusal,
        })
    unresolved.sort(key=lambda r: (r["kind"], str(r["phase"]), r["item_id"]))

    provenance = {
        "config_id": cid,
        "game_build_id": build.game_build_id,
        "game_version": build.game_version,
        "build_number": build.build_number,
        "docs_sha256": build.docs_sha256,
        "reference_data_build_id": graph.data.game_build_id,
        "route_table": {
            "name": graph.routes.name,
            "sha256": route_table_sha256(graph.routes),
            "exclusions": [e.recipe_id for e in graph.routes.exclusions],
            "pins": [{"item_id": p.item_id, "recipe_id": p.recipe_id} for p in graph.routes.pins],
        },
        "scenario": {
            "recipe_input_multiplier": scenario.recipe_input_multiplier,
            "project_assembly_requirement_multiplier": scenario.project_assembly_requirement_multiplier,
            "fluid_rounding_unit": fluid_unit,
        },
        "counts": {
            "targets": len(in_scope_targets(graph)),
            "coefficient_rows": len(coefficients),
            "phase_rows": len(phases),
            "unresolved": len(unresolved),
        },
        "phases_complete": {str(p): pd.complete[p] for p in pd.phases},
        "repo_head": repo_head,
        "generated_at": generated_at,
    }
    return Dataset(cid, provenance, tuple(coefficients), tuple(phases), tuple(unresolved), pd)


def _fmt(x: float) -> str:
    return f"{x:,.4g}" if x != int(x) else f"{int(x):,}"


def markdown_report(ds: Dataset, graph: RecipeGraph) -> str:
    """Compact, human-readable, in id order. States what every figure rests on."""
    p = ds.provenance
    out: list[str] = []
    out.append(f"# Demand expansion — {ds.config_id}\n")
    out.append(
        f"Game {p['game_version']} build {p['build_number']} "
        f"(`{p['game_build_id']}`, docs sha256 `{p['docs_sha256'][:12]}…`). "
        f"Route table `{p['route_table']['name']}` "
        f"(sha256 `{p['route_table']['sha256'][:12]}…`), "
        f"recipe multiplier {p['scenario']['recipe_input_multiplier']:g}x, "
        f"Project Assembly multiplier {p['scenario']['project_assembly_requirement_multiplier']:g}x, "
        f"fluid rounding {p['scenario']['fluid_rounding_unit'] or 'none'}."
        + (f" Repo `{p['repo_head'][:12]}`." if p.get("repo_head") else "")
        + (f" Generated {p['generated_at']}." if p.get("generated_at") else "")
        + "\n"
    )
    out.append(
        f"{p['counts']['targets']} targets in scope, {p['counts']['coefficient_rows']} "
        f"coefficient rows, {p['counts']['phase_rows']} phase rows, "
        f"{p['counts']['unresolved']} unresolved. Quantities are units; there is no "
        "time in this report.\n"
    )
    pd = ds.phase_demand
    incomplete = [str(ph) for ph in pd.phases if not pd.complete[ph]]
    if incomplete:
        out.append(
            f"**Phase{'s' if len(incomplete) > 1 else ''} {', '.join(incomplete)} "
            "incomplete**: a delivery was refused (below). Every sum including "
            "that phase is a lower bound.\n"
        )
    if ds.unresolved:
        out.append("## Unresolved\n")
        out.append("| Kind | Item | Phase | Refusal |\n|---|---|---|---|")
        for u in ds.unresolved:
            out.append(f"| {u['kind']} | {u['item_name']} | {u['phase'] or ''} | {u['refusal']} |")
        out.append("")
    out.append("## Phase demand (incremental units per phase; last column: remaining after the phase)\n")
    header = "| Item | " + " | ".join(f"Phase {ph}" for ph in pd.phases) + " | Growth | Last |"
    out.append(header)
    out.append("|---|" + "---|" * (len(pd.phases) + 2))
    for item_id in sorted(pd.cells):
        cells = pd.item(item_id)
        growth = []
        for c in cells:
            if c.growth.kind == "ratio":
                growth.append(f"{float(c.growth.ratio):.3g}x")
            elif c.growth.kind == "new":
                growth.append("new")
            else:
                growth.append("·")
        qty = " | ".join(_fmt(float(c.quantity)) + ("" if c.complete else "+") for c in cells)
        out.append(
            f"| {_name(graph, item_id)} | {qty} | {' '.join(growth)} | "
            f"{pd.last_phase(item_id) or '–'} |"
        )
    out.append("\n`+` marks a phase that is incomplete. Growth reads left to right, one entry per phase: a ratio against the previous phase, `new`, or `·` for none.\n")
    out.append("## Dependency exposure (targets that embed each source, in id order)\n")
    by_source: dict[str, list[dict]] = {}
    for r in ds.coefficients:
        by_source.setdefault(r["source_item_id"], []).append(r)
    out.append("| Source | Targets | Deepest | Last phase |")
    out.append("|---|---|---|---|")
    for source in sorted(by_source):
        rows = by_source[source]
        out.append(
            f"| {_name(graph, source)} | {len(rows)} | {max(r['depth'] for r in rows)} | "
            f"{pd.last_phase(source) or '–'} |"
        )
    out.append("")
    return "\n".join(out)
