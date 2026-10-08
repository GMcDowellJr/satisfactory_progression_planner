#!/usr/bin/env python3
"""Run a declared district: compose its caps, solve supply-side, print, export.

Crossover A26/A27. A joint above several packages, so it lives at tools/ root
like goal_run.py. It composes what the declaration states with what each
layer returns, and adds no arithmetic of its own:

    caps      progression.district.resource_caps(definition, extraction_rates)
    recipes   progression.at_tier(RECIPE_TIER, declared=<names resolved>)
    solve     LpBackend.solve_district (A27.2: weighted outputs with floors,
              goal as the tie-break), with power in the solve (A29) unless
              --no-power: generators from the declaration's GENERATORS, grid
              and spare as declared, extraction at nameplate from the nodes
    baseline  LpBackend.solve on the declaration's V544 rates as DEMANDS,
              UNCAPPED, so the raw draw is the answer and the report puts it
              beside each cap: the Stage 0 "shared intermediates" row. Under
              the caps it is simply infeasible (measured 2026-10-08), which
              names nothing; the overdraw per resource does

    uv run python tools/district_run.py --case shipped
    uv run python tools/district_run.py --case readme --baseline
    uv run python tools/district_run.py --case shipped --export out.json

**It cannot choose, and that is the guardrail.** Targets, weights, floors,
nodes, clock cases and the recipe names are all read from the declaration;
the goal is a CLI argument naming a `production_cli.WEIGHT_PRESETS` entry and
its weights are printed (LP record 21 R2). No min, max or sort here
(asserted by tests/test_district_phase2.py); targets print in request order,
caps in declaration order.

**The export (A27.3, default taken 2026-10-08).** One JSON document: the
inputs as declared and composed, the plan, the per-target rates, the binding
caps, the goal and its weights, and an `unverified` list naming what no layer
checked (belts, pipes, routing: A24.1 S3, v5.5 rule 6). The PWA imports it;
nothing here knows where that is. LF pinned.
"""
from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _src in ("production_adapter", "progression", "realization"):
    _path = str(REPO / "tools" / _src / "src")
    if _path not in sys.path:
        sys.path.insert(0, _path)

from production_adapter import (  # noqa: E402
    DistrictRequest, DistrictResponse, OutputTarget, PowerBalance, SolveRequest, SolveResponse,
    Weights, load,
)
from production_adapter.gamedata import load_generators, load_logistics  # noqa: E402
from production_adapter.lp_backend import Infeasible, LpBackend, PowerStatistic  # noqa: E402
from progression import (  # noqa: E402
    DistrictDefinition, at_tier, extraction_nameplate_mw, recipe_ids_by_name, resource_caps,
    resources_in_reference_order,
)
from progression.power import load_power_tables  # noqa: E402

EXPORT_SCHEMA = "district-plan/1"
#: v5.5 rule 6: labelled, never implied buildable
UNVERIFIED = ("belts", "pipes", "pumps", "routing", "node reachability")
#: production_cli.WEIGHT_PRESETS, restated here rather than imported so the CLI
#: module's argument parsing is not executed on import. Same four, same values.
GOALS = {
    "balanced": Weights(),
    "resources": Weights(resources=1.0, power=0.0, buildings=0.0),
    "power": Weights(resources=0.0, power=1.0, buildings=0.0),
    "buildings": Weights(resources=0.0, power=0.0, buildings=1.0),
}


class DistrictRunError(ValueError):
    """A declaration or case the run cannot use."""


def _load(name: str, path: pathlib.Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def declaration(name: str):
    path = REPO / "tools" / "phases" / f"{name}.py"
    if not path.exists():
        raise DistrictRunError(f"no declaration {name}: {path} does not exist")
    return _load(f"phases_{name}", path)


@dataclasses.dataclass(frozen=True)
class DistrictRun:
    decl: object
    case: str
    goal: str
    definition: DistrictDefinition
    caps: tuple
    recipe_ids: tuple[str, ...]
    request: DistrictRequest
    response: DistrictResponse
    #: the Stage 0 row, when asked for; None when the demands are infeasible
    baseline: SolveResponse | None = None
    baseline_error: str | None = None


def run(decl, *, case: str, goal: str = "balanced", baseline: bool = False,
        power: bool = True, repo: pathlib.Path = REPO) -> DistrictRun:
    if case not in decl.EXTRACTION_CLOCK_CASES:
        raise DistrictRunError(
            f"{decl.LABEL}: no extraction clock case {case!r}; "
            f"declared: {list(decl.EXTRACTION_CLOCK_CASES)}"
        )
    if goal not in GOALS:
        raise DistrictRunError(f"no goal {goal!r}; known: {list(GOALS)}")
    data = load(repo, decl.SCENARIO)
    _, rates = load_logistics(repo)
    definition = DistrictDefinition(
        nodes=decl.NODES, extractor_class=decl.EXTRACTOR,
        extraction_clock=decl.EXTRACTION_CLOCK_CASES[case],
        reserve_fraction=decl.RESERVE, label=f"{decl.LABEL} [{case}]",
    )
    caps = resource_caps(definition, rates, resources_in_reference_order(data))
    declared = recipe_ids_by_name(data, decl.DECLARED_RECIPE_NAMES)
    unlocks = at_tier(repo, decl.RECIPE_TIER, declared=declared)
    balance = None
    if power:
        tables = load_power_tables(repo)
        generators = tuple(
            g for g in load_generators(repo) if g.generator_class in decl.GENERATORS
        )
        balance = PowerBalance(
            generators=generators, grid_mw=decl.GRID_MW, spare_mw=decl.SPARE_MW,
            extraction_mw=extraction_nameplate_mw(definition, tables.extractors),
        )
    request = DistrictRequest(
        targets=decl.TARGETS, allowed_recipes=unlocks.allowed_recipes,
        resource_caps=caps, weights=GOALS[goal], power=balance,
    )
    backend = LpBackend(power_statistic=PowerStatistic.MEAN)
    response = backend.solve_district(request, data)

    base, base_err = None, None
    if baseline:
        demand = SolveRequest(
            outputs=tuple(OutputTarget(i, r) for i, r in decl.V544_SHIPPED_RATES),
            allowed_recipes=unlocks.allowed_recipes, weights=GOALS[goal],
        )
        try:
            base = backend.solve(demand, data)
        except Infeasible as e:
            base_err = str(e)
    return DistrictRun(
        decl=decl, case=case, goal=goal, definition=definition, caps=caps,
        recipe_ids=unlocks.recipe_ids, request=request, response=response,
        baseline=base, baseline_error=base_err,
    )


# -- report -----------------------------------------------------------------

def _name(data_items, item_id: str) -> str:
    item = data_items.get(item_id)
    return item.display_name if item else item_id


def report(dr: DistrictRun, data) -> str:
    r = dr.response
    out = [
        f"{dr.definition.label}",
        f"  extractor {dr.definition.extractor_class} at {dr.definition.extraction_clock:.0%}, "
        f"reserve {dr.definition.reserve_fraction:.0%}; machine clock {dr.decl.MACHINE_CLOCK:.0%} "
        "(realization setting, not in this solve)",
        f"  scenario recipe x{data.scenario.recipe_input_multiplier:g}, "
        f"power x{data.scenario.machine_power_multiplier:g}; {len(dr.recipe_ids)} recipes enabled",
        f"  goal {dr.goal!r} as tie-break: weights resources={r.goal.resources:g} "
        f"power={r.goal.power:g} buildings={r.goal.buildings:g}",
        "", "caps (declaration order)",
    ]
    draw = {x.item_id: x.rate_per_min for x in r.plan.raw_inputs}
    for c in dr.caps:
        if c.rate_per_min > 0.0:
            out.append(f"  {_name(data.items, c.item_id):18s} {draw.get(c.item_id, 0.0):9.3f} / {c.rate_per_min:g}")
    out.append(f"  every other raw resource capped at 0 ({sum(1 for c in dr.caps if c.rate_per_min == 0.0)}: the district is closed)")
    out += ["", f"targets (request order); weighted output {r.weighted_output:.4f}"]
    for t in r.targets:
        flag = "excluded" if t.excluded else ("AT FLOOR" if t.at_floor else "")
        floor = "" if t.minimum_rate is None else f" floor {t.minimum_rate:g}"
        out.append(f"  {_name(data.items, t.item_id):26s} {t.rate_per_min:9.4f}/min  w={t.weight:g}{floor}  {flag}")
    out += ["", "binding caps (shadow price = weighted output per extra unit/min)"]
    if not r.binding:
        out.append("  none")
    for b in r.binding:
        out.append(f"  {_name(data.items, b.item_id):18s} cap {b.cap_per_min:g}  shadow {b.shadow_price:.4f}")
    out += ["", "power"]
    if r.power is None:
        out.append("  outside the solve (--no-power): the LP figure below excludes extraction, D5")
    else:
        pw = r.power
        out.append(f"  lanes {pw.lane_mw:.2f} + extraction (nameplate) {pw.extraction_mw:.2f} + spare "
                   f"{pw.spare_mw:.2f}  <=  grid {pw.grid_mw:.2f} + generated {pw.generated_mw:.2f}; "
                   f"margin {pw.margin_mw:.2f} MW" + ("  BINDING" if pw.binding else ""))
        if pw.binding:
            out.append(f"  shadow price {pw.shadow_price:.5f} weighted output per MW of supply")
        for u in pw.generators:
            supp = "".join(f", {_name(data.items, i)} {v:.2f}/min" for i, v in u.supplemental_per_min)
            out.append(f"  {u.generator_class:24s} {u.count:8.3f} x {u.mw:8.2f} MW; "
                       f"{_name(data.items, u.fuel_item_id)} {u.fuel_per_min:.2f}/min{supp}")
        if not pw.generators:
            out.append("  no generators built")
    out += ["", f"plan: {len(r.plan.recipes)} recipes, scenario power {r.plan.power.scenario_mw:.1f} MW "
            "(LP machine-time at mean power; extraction excluded, D5)"]
    for u in r.plan.recipes:
        out.append(f"  {u.recipe_id:46s} {u.machine_equivalents:8.3f} x {u.producer_class}")
    for w in r.plan.warnings:
        out.append(f"  ! {w}")
    if dr.baseline is not None or dr.baseline_error:
        out += ["", "Stage 0 baseline: v5.4.4 shipped rates as DEMANDS, uncapped; draw beside cap"]
        if dr.baseline_error:
            out.append(f"  infeasible: {dr.baseline_error}")
        else:
            b = dr.baseline
            bd = {x.item_id: x.rate_per_min for x in b.raw_inputs}
            for c in dr.caps:
                if bd.get(c.item_id, 0.0) > 0.0 or c.rate_per_min > 0.0:
                    over = "  OVER" if bd.get(c.item_id, 0.0) > c.rate_per_min + 1e-6 else ""
                    out.append(f"  {_name(data.items, c.item_id):18s} {bd.get(c.item_id, 0.0):9.3f} / {c.rate_per_min:g}{over}")
            out.append(f"  {len(b.recipes)} recipes, scenario power {b.power.scenario_mw:.1f} MW")
            for u in b.recipes:
                out.append(f"  {u.recipe_id:46s} {u.machine_equivalents:8.3f} x {u.producer_class}")
    out.append("")
    out.append("unverified: " + ", ".join(UNVERIFIED))
    return "\n".join(out)


# -- export (A27.3) -----------------------------------------------------------

def export(dr: DistrictRun, data, path: pathlib.Path) -> None:
    doc = {
        "schema": EXPORT_SCHEMA,
        "declaration": {"label": dr.decl.LABEL, "phase": dr.decl.PHASE, "tiers": list(dr.decl.TIERS),
                        "recipe_tier": dr.decl.RECIPE_TIER, "machine_clock": dr.decl.MACHINE_CLOCK},
        "case": dr.case,
        "game_build_id": data.game_build_id,
        "scenario": dataclasses.asdict(data.scenario),
        "district": {
            "label": dr.definition.label,
            "extractor_class": dr.definition.extractor_class,
            "extraction_clock": dr.definition.extraction_clock,
            "reserve_fraction": dr.definition.reserve_fraction,
            "nodes": [dataclasses.asdict(n) for n in dr.definition.nodes],
            "caps": [dataclasses.asdict(c) for c in dr.caps],
        },
        "recipe_ids": list(dr.recipe_ids),
        "goal": {"name": dr.goal, **dataclasses.asdict(dr.response.goal)},
        "targets": [dataclasses.asdict(t) for t in dr.response.targets],
        "weighted_output": dr.response.weighted_output,
        "binding": [dataclasses.asdict(b) for b in dr.response.binding],
        "power": None if dr.response.power is None else dataclasses.asdict(dr.response.power),
        "plan": dataclasses.asdict(dr.response.plan),
        "baseline": None if dr.baseline is None else dataclasses.asdict(dr.baseline),
        "baseline_error": dr.baseline_error,
        "unverified": list(UNVERIFIED),
    }
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--declaration", default="district_phase2",
                    help="module name under tools/phases/ (default district_phase2)")
    ap.add_argument("--case", required=True, help="an EXTRACTION_CLOCK_CASES key of the declaration")
    ap.add_argument("--goal", default="balanced", choices=tuple(GOALS))
    ap.add_argument("--baseline", action="store_true", help="also solve the V544 rates as demands")
    ap.add_argument("--no-power", action="store_true", help="leave power outside the solve (D5)")
    ap.add_argument("--export", type=pathlib.Path, default=None, help="write the plan JSON here")
    args = ap.parse_args(argv)
    decl = declaration(args.declaration)
    dr = run(decl, case=args.case, goal=args.goal, baseline=args.baseline, power=not args.no_power)
    data = load(REPO, decl.SCENARIO)
    print(report(dr, data))
    if args.export:
        export(dr, data, args.export)
        print(f"\nexported: {args.export}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
