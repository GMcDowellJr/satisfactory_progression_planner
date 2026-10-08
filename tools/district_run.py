#!/usr/bin/env python3
"""Run a declared district: compose its caps, solve supply-side, print, export.

Crossover A26/A27. A joint above several packages, so it lives at tools/ root
like goal_run.py. It composes what the declaration states with what each
layer returns, and adds no arithmetic of its own:

    caps      progression.district.resource_caps(definition, extraction_rates)
    recipes   progression.at_tier(RECIPE_TIER, declared=<names resolved>)
    bill      progression.district.bill_units over the declaration's
              BILL_PHASES (Project Assembly rows, scenario-scaled) and
              BILL_TIERS (schematic costs); BILL_TARGETS take their units
              from it and are refused when the bill has none (A31)
    solve     LpBackend.solve_district (A27.2: weighted outputs with floors,
              goal as the tie-break), with power in the solve (A29) unless
              --no-power: generators from the declaration's GENERATORS, grid
              and spare as declared, extraction at nameplate from the nodes
    realize   realization.realize over the plan with the declaration's BUSES
              (one recipe per item, declared) and its nodes: whole machines,
              explicit clocks, power at those clocks (v5.5 Stage 5; A32).
              The power balance is RE-READ at the realized draw as a report
              (A29.3 O29): generators stay the solve's, rounded up
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
import math
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
from production_adapter import DistrictTarget  # noqa: E402
from progression import (  # noqa: E402
    DistrictDefinition, at_tier, bill_units, discover, extraction_nameplate_mw,
    recipe_ids_by_name, resource_caps, resources_in_reference_order, unlocks,
)
from progression import stock  # noqa: E402
from progression.power import load_power_tables  # noqa: E402
from realization import NodeDeclaration, RealizationRequest, realize  # noqa: E402

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
    #: the whole bill, every item, as composed (A31); targets took theirs from it
    bill: dict[str, float]
    #: discovery (O34): which bill items this site can make at all, bill order
    reach: tuple
    request: DistrictRequest
    response: DistrictResponse
    #: the Stage 0 row, when asked for; None when the demands are infeasible
    baseline: SolveResponse | None = None
    baseline_error: str | None = None
    #: realization over the plan, when the declaration carries BUSES
    realization: object | None = None   # realization.RealizationReport


def run(decl, *, case: str, goal: str = "balanced", baseline: bool = False,
        power: bool = True, realization: bool = True, repo: pathlib.Path = REPO) -> DistrictRun:
    if case not in decl.EXTRACTION_CLOCK_CASES:
        raise DistrictRunError(
            f"{decl.LABEL}: no extraction clock case {case!r}; "
            f"declared: {list(decl.EXTRACTION_CLOCK_CASES)}"
        )
    if goal not in GOALS:
        raise DistrictRunError(f"no goal {goal!r}; known: {list(GOALS)}")
    data = load(repo, decl.SCENARIO)
    capabilities, rates = load_logistics(repo)
    definition = DistrictDefinition(
        nodes=decl.NODES, extractor_class=decl.EXTRACTOR,
        extraction_clock=decl.EXTRACTION_CLOCK_CASES[case],
        reserve_fraction=decl.RESERVE, label=f"{decl.LABEL} [{case}]",
    )
    caps = resource_caps(definition, rates, resources_in_reference_order(data))
    declared = recipe_ids_by_name(data, decl.DECLARED_RECIPE_NAMES)
    tier = at_tier(repo, decl.RECIPE_TIER, declared=declared)
    pa = stock.load_project_assembly(repo, data)
    costs = unlocks.schematic_costs(repo)
    sources = [
        (f"project assembly phase {ph}", tuple(
            (r.item_id, data.scenario.apply_project_assembly_quantity(r.quantity_1x))
            for r in pa if r.phase == ph
        ))
        for ph in decl.BILL_PHASES
    ] + [
        (sid, costs[sid])
        for sid in unlocks.schematics_in_tiers(repo, decl.BILL_TIERS) if sid in costs
    ]
    bill = bill_units(tuple(sources))
    reach = discover(data, tier.recipe_ids, caps, tuple(bill))
    unreachable = [i for i, _ in decl.BILL_TARGETS if not any(r.makeable for r in reach if r.item_id == i)]
    if unreachable:
        raise DistrictRunError(
            f"{decl.LABEL}: bill products {unreachable} cannot be made here at all "
            "(discovery): " + "; ".join(
                f"{r.item_id} needs {list(r.missing_raws)}" for r in reach if r.item_id in unreachable
            )
        )
    missing = [i for i, _ in decl.BILL_TARGETS if i not in bill]
    if missing:
        raise DistrictRunError(
            f"{decl.LABEL}: bill products {missing} have no units in the bill from phases "
            f"{decl.BILL_PHASES} and tiers {decl.BILL_TIERS}; declare them as EXTRAS or widen the bill"
        )
    targets = tuple(
        DistrictTarget(i, weight=w, bill_units=bill[i]) for i, w in decl.BILL_TARGETS
    ) + tuple(decl.EXTRAS)
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
        targets=targets, allowed_recipes=tier.allowed_recipes,
        resource_caps=caps, weights=GOALS[goal], power=balance,
    )
    backend = LpBackend(power_statistic=PowerStatistic.MEAN)
    response = backend.solve_district(request, data)

    base, base_err = None, None
    if baseline:
        demand = SolveRequest(
            outputs=tuple(OutputTarget(i, r) for i, r in decl.V544_SHIPPED_RATES),
            allowed_recipes=tier.allowed_recipes, weights=GOALS[goal],
        )
        try:
            base = backend.solve(demand, data)
        except Infeasible as e:
            base_err = str(e)
    report = None
    if realization and getattr(decl, "BUSES", None):
        nodes = tuple(
            NodeDeclaration(
                item_id=n.item_id,
                extractor_class=n.extractor_class or definition.extractor_class,
                purity=n.purity, count=n.count,
                clock_percent=definition.extraction_clock * 100.0,
            )
            for n in definition.nodes
        )
        report = realize(
            response.plan, data, capabilities, rates,
            RealizationRequest(design_tier=decl.DESIGN_TIER, buses=decl.BUSES, nodes=nodes),
        )
    return DistrictRun(
        decl=decl, case=case, goal=goal, definition=definition, caps=caps,
        recipe_ids=tier.recipe_ids, bill=bill, reach=reach, request=request, response=response,
        baseline=base, baseline_error=base_err, realization=report,
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
    out += ["", f"bill: {len(dr.bill)} items from phases {list(dr.decl.BILL_PHASES)} and tiers "
            f"{list(dr.decl.BILL_TIERS)}; {sum(1 for t in r.targets if t.bill_units)} made here; "
            f"discovery: {sum(1 for x in dr.reach if x.makeable)} makeable here at all"]
    chosen = {t.item_id for t in r.targets}
    for x in dr.reach:
        if x.makeable:
            tag = "TARGET" if x.item_id in chosen else "makeable, not selected"
        elif x.no_recipe:
            tag = "no enabled recipe"
        else:
            tag = "needs " + ", ".join(_name(data.items, i) for i in x.missing_raws)
        out.append(f"  {_name(data.items, x.item_id):26s} {dr.bill[x.item_id]:8g}  {tag}")
    if r.scale is not None:
        out.append(f"  scale {r.scale:.6f} of the bill per minute"
                   + (f"; horizon {r.horizon_min:.1f} min to cover it at this rate" if r.horizon_min else
                      "; a bill product cannot be made: see binding caps"))
    out += ["", f"targets (request order); weighted output {r.weighted_output:.4f}"]
    for t in r.targets:
        flag = "excluded" if t.excluded else ("AT FLOOR" if t.at_floor else "")
        floor = "" if t.minimum_rate is None else f" floor {t.minimum_rate:g}"
        bill = "" if t.bill_units is None else f"  bill {t.bill_units:g} share {t.share:.6f}"
        out.append(f"  {_name(data.items, t.item_id):26s} {t.rate_per_min:9.4f}/min  w={t.weight:g}{floor}{bill}  {flag}")
    unit = "bill scale" if r.scale is not None else "weighted output"
    out += ["", f"binding caps (shadow price = {unit} per extra unit/min, from the first stage)"]
    if not r.binding:
        out.append("  none")
    for b in r.binding:
        out.append(f"  {_name(data.items, b.item_id):18s} cap {b.cap_per_min:g}  shadow {b.shadow_price + 0.0:.4g}")
    out += ["", "power"]
    if r.power is None:
        out.append("  outside the solve (--no-power): the LP figure below excludes extraction, D5")
    else:
        pw = r.power
        out.append(f"  lanes {pw.lane_mw:.2f} + extraction (nameplate) {pw.extraction_mw:.2f} + spare "
                   f"{pw.spare_mw:.2f}  <=  grid {pw.grid_mw:.2f} + generated {pw.generated_mw:.2f}; "
                   f"margin {pw.margin_mw:.2f} MW" + ("  BINDING" if pw.binding else ""))
        if pw.binding:
            out.append(f"  shadow price {pw.shadow_price + 0.0:.4g} {unit} per MW of supply")
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
    if dr.realization is not None:
        rz = dr.realization
        out += ["", f"realization (design tier {rz.design_tier}): whole machines, explicit clocks, "
                f"power at clock; {len(rz.buses)} buses"]
        counts: dict[str, int] = {}
        for bus in rz.buses:
            for lane in bus.lanes:
                counts[lane.producer_class] = counts.get(lane.producer_class, 0) + lane.machines
                out.append(f"  {bus.bus_id:26s} {lane.machines:3d} x {lane.producer_class:24s} "
                           f"@ {lane.clock_percent:6.2f}%  {lane.output_rate_per_min:9.4f}/min  "
                           f"{lane.power_mw:8.2f} MW")
        out.append("  machines: " + ", ".join(f"{n} {c}" for c, n in counts.items()))
        out.append(f"  realized machine power {rz.total_power_mw:.2f} MW beside the LP's "
                   f"{r.plan.power.scenario_mw:.2f} MW machine-time (same scenario multiplier)")
        if r.power is not None:
            pw = r.power
            gens = sum(math.ceil(u.count - 1e-9) for u in pw.generators)
            gen_mw = sum(math.ceil(u.count - 1e-9) * (u.mw / u.count) for u in pw.generators if u.count > 0)
            margin = gen_mw + pw.grid_mw - rz.total_power_mw - pw.extraction_mw - pw.spare_mw
            out.append(f"  balance re-read at the realized draw (A29.3 O29, report only): "
                       f"{gens} whole generators {gen_mw:.2f} MW + grid {pw.grid_mw:.2f} - lanes "
                       f"{rz.total_power_mw:.2f} - extraction {pw.extraction_mw:.2f} - spare "
                       f"{pw.spare_mw:.2f} = margin {margin:.2f} MW")
        for w in rz.warnings:
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
        "bill": {"phases": list(dr.decl.BILL_PHASES), "tiers": list(dr.decl.BILL_TIERS),
                 "units": dict(dr.bill), "scale": dr.response.scale,
                 "horizon_min": dr.response.horizon_min},
        "discovery": [dataclasses.asdict(x) for x in dr.reach],
        "targets": [dataclasses.asdict(t) for t in dr.response.targets],
        "weighted_output": dr.response.weighted_output,
        "binding": [dataclasses.asdict(b) for b in dr.response.binding],
        "power": None if dr.response.power is None else dataclasses.asdict(dr.response.power),
        "plan": dataclasses.asdict(dr.response.plan),
        "baseline": None if dr.baseline is None else dataclasses.asdict(dr.baseline),
        "realization": None if dr.realization is None else {
            "design_tier": dr.realization.design_tier,
            "total_power_mw": dr.realization.total_power_mw,
            "buses": [
                {"bus_id": b.bus_id, "item_id": b.item_id, "recipe_id": b.recipe_id,
                 "supply_per_min": b.supply_per_min,
                 "lanes": [{"recipe_id": l.recipe_id, "producer_class": l.producer_class,
                            "machines": l.machines, "clock_percent": l.clock_percent,
                            "output_rate_per_min": l.output_rate_per_min, "power_mw": l.power_mw}
                           for l in b.lanes]}
                for b in dr.realization.buses
            ],
            "warnings": list(dr.realization.warnings),
        },
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
    ap.add_argument("--no-realize", action="store_true", help="skip realization over the plan")
    ap.add_argument("--export", type=pathlib.Path, default=None, help="write the plan JSON here")
    args = ap.parse_args(argv)
    decl = declaration(args.declaration)
    dr = run(decl, case=args.case, goal=args.goal, baseline=args.baseline, power=not args.no_power,
             realization=not args.no_realize)
    data = load(REPO, decl.SCENARIO)
    print(report(dr, data))
    if args.export:
        export(dr, data, args.export)
        print(f"\nexported: {args.export}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
