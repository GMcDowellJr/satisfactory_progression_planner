#!/usr/bin/env python3
"""Run planner (demand side): what reaching a declared Project Assembly target takes.

Site-planner reframe A15.2 (decided by Greg, 2026-11-17), reconciliation R9.

    A1   one scope plans the run; the factory track can take that plan as input
         (`to_factory_inputs`) or be declared by hand at run time
    B1   demand side estimates what's next and what reaching a target takes.
         The reference for target determination is Greg's deployed prototype
         (eloquent-pothos-3073ca.netlify.app, read 2026-11-17):
           rate per part   = E-scaled bill / horizon
           horizon bound   = the "one-machine ceiling": the longest any part
                             takes on ONE machine of its recipe at 100 %
           horizon         = declared minutes, or a declared fraction of that
                             ceiling (the prototype's 1 %..100 % presets)
         Its arithmetic is NOT carried: it ceils solid inputs (at R = 1.25 an
         input of 1 becomes 2, against the in-game read of 1, demand §3.2.4),
         picks miners by phase index and expands standard recipes only. Here
         the repo's Scenario, availability and LP do the work.

What it adds over phase_run (deprecated, A15.3): availability by milestones
owned (R5) instead of a tier; the target is declared as a horizon rather than an
anchor rate; and a blocked part says which unlocks it waits on, so "what is
next" is answerable. It chooses no horizon, no recipe and no target.

The one-machine ceiling uses each Project Assembly part's BASE recipe (every PA
part has exactly one; refused otherwise). That is the prototype's rule. A held
alternate does not move the bound. The plan itself uses every owned recipe.

`demand_expansion` is not used here. It answers a different question
(quantity totals by declared route, exact fractions), and its role beside the
LP stays as recorded in docs/ARCHITECTURE.md §7.

    uv run python tools/run_plan.py --phase 2 --through-tier 4 --horizon-fraction 0.25
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys
from dataclasses import dataclass

REPO = pathlib.Path(__file__).resolve().parents[1]
for sub in ("production_adapter", "progression", "realization"):
    p = str(REPO / "tools" / sub / "src")
    if p not in sys.path:
        sys.path.insert(0, p)
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

from production_adapter import OutputTarget, ResourceCap, Scenario, SolveRequest, load  # noqa: E402
from production_adapter.gamedata import (  # noqa: E402
    load_generators, load_project_assembly, load_schematic_rows, load_schematic_unlock_rows,
)
from production_adapter.lp_backend import LpBackend, PowerStatistic  # noqa: E402
from progression import (  # noqa: E402
    PlaythroughState, RecipeStatus, availability, discover, generators_available, playthrough,
)
from progression.byproducts import Byproduct, ledger  # noqa: E402

PLAN_SCHEMA = "run-plan/1"

POWER_NOTE = ("power diagnostic: each generator and fuel alone covering the plan's machine power "
              "(mean); a fuel's own production power and the extractors are not included")


class RunPlanError(ValueError):
    """The declared target cannot be planned as declared; refused by name."""


@dataclass(frozen=True)
class PartTarget:
    item_id: str
    bill_units: float            # E-scaled
    one_machine_min: float       # the bill on one machine of the base recipe, 100 %
    rate_per_min: float          # bill / horizon


@dataclass(frozen=True)
class BlockedPart:
    item_id: str
    #: (recipe making the part, its status, schematics that unlock it)
    producers: tuple[tuple[str, str, tuple[str, ...]], ...]


@dataclass(frozen=True)
class PowerOption:
    generator_class: str
    fuel_item_id: str
    units: float
    fuel_per_min: float


@dataclass(frozen=True)
class PhasePlan:
    phase: int
    state: PlaythroughState
    scenario: Scenario
    ceiling_min: float
    horizon_min: float
    horizon_fraction: float      # horizon / ceiling
    parts: tuple[PartTarget, ...]
    blocked: tuple[BlockedPart, ...]
    response: object | None      # SolveResponse; None when a part is blocked
    power_options: tuple[PowerOption, ...]
    availability_report: str
    byproducts: tuple[Byproduct, ...] = ()   # reframe A16: default to the AWESOME Sink


def plan_phase(
    repo: pathlib.Path, *, state: PlaythroughState, scenario: Scenario, phase: int,
    horizon_min: float | None = None, horizon_fraction: float | None = None,
    power_statistic: PowerStatistic = PowerStatistic.MEAN,
) -> PhasePlan:
    if (horizon_min is None) == (horizon_fraction is None):
        raise RunPlanError("declare exactly one of horizon_min and horizon_fraction")
    if horizon_min is not None and not horizon_min > 0:
        raise RunPlanError(f"horizon_min must be positive, got {horizon_min!r}")
    if horizon_fraction is not None and not 0 < horizon_fraction <= 1:
        raise RunPlanError(f"horizon_fraction must be in (0, 1], got {horizon_fraction!r}")

    data = load(repo, scenario)
    rows = [r for r in load_project_assembly(repo, data) if r.phase == phase]
    if not rows:
        raise RunPlanError(f"no Project Assembly phase {phase}")
    bill: dict[str, float] = {}
    for r in rows:
        bill[r.item_id] = bill.get(r.item_id, 0.0) + data.scenario.apply_project_assembly_quantity(
            r.quantity_1x)

    one_machine: dict[str, float] = {}
    for item, q in bill.items():
        base = [rc for rc in data.recipes.values()
                if not rc.is_alternate and any(i == item for i, _ in rc.outputs)]
        if len(base) != 1:
            raise RunPlanError(f"{item}: {len(base)} base recipes make it; the one-machine "
                               "ceiling needs exactly one")
        rate = dict(base[0].outputs)[item]
        one_machine[item] = q / rate
    ceiling = max(one_machine.values())
    horizon = horizon_min if horizon_min is not None else horizon_fraction * ceiling
    parts = tuple(PartTarget(i, q, one_machine[i], q / horizon) for i, q in bill.items())

    avail = availability(repo, state)
    open_caps = tuple(ResourceCap(i, float("inf")) for i in data.resource_items)
    reach = discover(data, avail.recipe_ids, open_caps, tuple(bill))
    unlocks_of: dict[str, list[str]] = {}
    names = {s.schematic_id: s.display_name for s in load_schematic_rows(repo)}
    for u in load_schematic_unlock_rows(repo):
        unlocks_of.setdefault(u.recipe_id, []).append(names.get(u.schematic_id, u.schematic_id))
    blocked = tuple(
        BlockedPart(x.item_id, tuple(
            (rc.recipe_id, avail.status.get(rc.recipe_id, RecipeStatus.LOCKED).value,
             tuple(sorted(unlocks_of.get(rc.recipe_id, ()))))
            for rc in data.recipes.values() if any(i == x.item_id for i, _ in rc.outputs)))
        for x in reach if not x.makeable)

    response = None
    power_options: tuple[PowerOption, ...] = ()
    byproducts: tuple[Byproduct, ...] = ()
    if not blocked:
        response = LpBackend(power_statistic=power_statistic).solve(SolveRequest(
            outputs=tuple(OutputTarget(p.item_id, p.rate_per_min) for p in parts),
            allowed_recipes=avail.allowed_recipes,
        ), data)
        need = response.power.scenario_mw
        rows_g = load_generators(repo)
        classes = tuple(dict.fromkeys(g.generator_class for g in rows_g))
        open_classes = generators_available(repo, state, classes)
        power_options = tuple(
            PowerOption(g.generator_class, g.fuel_item_id, need / g.power_mw,
                        need / g.power_mw * g.burn_rate_per_min)
            for g in rows_g if g.generator_class in open_classes and g.power_mw > 0)
        byproducts = ledger(repo, data, state, response.items,
                            {p.item_id: p.rate_per_min for p in parts})

    return PhasePlan(phase, state, data.scenario, ceiling, horizon, horizon / ceiling, parts,
                     blocked, response, power_options, avail.report(), byproducts)


def to_factory_inputs(
    plan: PhasePlan, *, world_config_id: str, label: str, socket_ids: tuple[str, ...],
    power_mode: str, goal: str = "balanced", supply: tuple = (), pumps_water: bool = False,
    grid_mw: float = 0.0, spare_mw: float = 0.0,
    infrastructure_policy: str = "highest_then_step_down", fixed_rate: bool = True,
) -> dict:
    """A1: hand one run-plan step to the factory track as factory-inputs/1.

    The goal mix is the phase bill in PROPORTION, its largest part at 1 unit,
    so a scale of (largest bill / horizon) delivers the bill over the horizon.
    With `fixed_rate` the factory is asked for exactly that (refused if the
    site cannot carry it, A13); without it, the factory reports its maximum
    and the horizon it implies. The site, power mode and policy are the
    caller's declaration; nothing here picks a site.

    Proportions keep the scale readable (largest part = 1 unit). Until
    2026-11-17 they also avoided a solve_portfolio defect with large bill
    units under a fixed target (fixed in lp_backend._run that day).
    """
    s = plan.scenario
    if s.input_amount_floor is not None:
        raise RunPlanError("factory-inputs/1 carries fluid_input_floor, not the legacy floor")
    st = plan.state
    largest = max(p.bill_units for p in plan.parts)
    return {
        "schema": "factory-inputs/1", "world_config_id": world_config_id,
        "playthrough": {"through_tier": None, "milestones": list(st.milestones),
                        "research": list(st.research), "alternates": list(st.alternates)},
        "scenario": {"recipe_input_multiplier": s.recipe_input_multiplier,
                     "machine_power_multiplier": s.machine_power_multiplier,
                     "project_assembly_requirement_multiplier": s.project_assembly_requirement_multiplier,
                     "fluid_input_floor": s.fluid_input_floor,
                     "fluid_rounding_unit": s.fluid_rounding_unit},
        "site": {"label": label, "socket_ids": list(socket_ids),
                 "supply": [{"item_id": i, "rate_per_min": r} for i, r in supply],
                 "pumps_water": pumps_water},
        "goal_mix": [{"item_id": p.item_id, "units": p.bill_units / largest} for p in plan.parts],
        "goal": goal, "power_mode": power_mode, "grid_mw": grid_mw, "spare_mw": spare_mw,
        "target_scale": (largest / plan.horizon_min) if fixed_rate else None,
        "infrastructure_policy": infrastructure_policy,
    }


def record(plan: PhasePlan) -> dict:
    r = plan.response
    return {
        "schema": PLAN_SCHEMA,
        "phase": plan.phase,
        "playthrough": dataclasses.asdict(plan.state),
        "scenario": dataclasses.asdict(plan.scenario),
        "ceiling_min": plan.ceiling_min,
        "horizon_min": plan.horizon_min,
        "horizon_fraction": plan.horizon_fraction,
        "parts": [dataclasses.asdict(p) for p in plan.parts],
        "blocked": [dataclasses.asdict(b) for b in plan.blocked],
        "recipes": [] if r is None else [dataclasses.asdict(x) for x in r.recipes],
        "raw_inputs": [] if r is None else [dataclasses.asdict(x) for x in r.raw_inputs],
        "machines": [] if r is None else [dataclasses.asdict(x) for x in r.machines],
        "power_mw": None if r is None else r.power.scenario_mw,
        "power_options": [dataclasses.asdict(o) for o in plan.power_options],
        "byproducts": [dataclasses.asdict(b) for b in plan.byproducts],
        "notes": [POWER_NOTE],
    }


def report(plan: PhasePlan) -> str:
    lines = [f"phase {plan.phase}: horizon {plan.horizon_min:.1f} min "
             f"({100 * plan.horizon_fraction:.1f}% of the one-machine ceiling, "
             f"{plan.ceiling_min:.1f} min)"]
    for p in plan.parts:
        lines.append(f"  {p.item_id}: {p.bill_units:g} at {p.rate_per_min:.4g}/min "
                     f"(one machine: {p.one_machine_min:.1f} min)")
    for b in plan.blocked:
        how = "; ".join(f"{rid} {st} via {', '.join(via) or 'nothing listed'}"
                        for rid, st, via in b.producers)
        lines.append(f"  BLOCKED {b.item_id}: {how}")
    if plan.response is not None:
        lines.append(f"  machines' power {plan.response.power.scenario_mw:.4g} MW (mean)")
        for x in plan.response.raw_inputs:
            lines.append(f"  raw {x.item_id}: {x.rate_per_min:.4g}/min")
        for o in plan.power_options:
            lines.append(f"  power alone: {o.units:.2f} x {o.generator_class} on "
                         f"{o.fuel_item_id} at {o.fuel_per_min:.4g}/min")
        lines.append(f"  note: {POWER_NOTE}")
    for b in plan.byproducts:
        lines.append(f"  by-product {b.item_id}: {b.rate_per_min:.4g}/min -> {b.disposition}")
    lines.append("  " + plan.availability_report.replace("\n", "\n  "))
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--phase", type=int, required=True)
    ap.add_argument("--through-tier", type=int, help="every milestone up to this tier (Q2)")
    ap.add_argument("--milestone", action="append", default=[], help="a milestone owned (repeat)")
    ap.add_argument("--research", action="append", default=[])
    ap.add_argument("--alternate", action="append", default=[])
    when = ap.add_mutually_exclusive_group(required=True)
    when.add_argument("--horizon-min", type=float)
    when.add_argument("--horizon-fraction", type=float, help="of the one-machine ceiling")
    ap.add_argument("--recipe-multiplier", type=float, default=1.0)
    ap.add_argument("--power-multiplier", type=float, default=1.0)
    ap.add_argument("--pa-multiplier", type=float, default=1.0)
    ap.add_argument("--fluid-input-floor", type=float, default=None)
    ap.add_argument("--export", type=pathlib.Path)
    args = ap.parse_args(argv)
    state = playthrough(REPO, through_tier=args.through_tier, milestones=args.milestone,
                        research=args.research, alternates=args.alternate)
    scenario = Scenario(recipe_input_multiplier=args.recipe_multiplier,
                        machine_power_multiplier=args.power_multiplier,
                        project_assembly_requirement_multiplier=args.pa_multiplier,
                        fluid_input_floor=args.fluid_input_floor)
    plan = plan_phase(REPO, state=state, scenario=scenario, phase=args.phase,
                      horizon_min=args.horizon_min, horizon_fraction=args.horizon_fraction)
    print(report(plan))
    if args.export:
        args.export.write_text(json.dumps(record(plan), indent=1, default=str) + "\n",
                               encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
