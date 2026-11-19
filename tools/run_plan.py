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
    load_project_assembly, load_schematic_rows, load_schematic_unlock_rows,
)
from production_adapter.lp_backend import LpBackend, PowerStatistic  # noqa: E402
from progression import (  # noqa: E402
    PlaythroughState, RecipeStatus, availability, discover, playthrough,
)
from progression.byproducts import Byproduct, ledger, report_lines  # noqa: E402
from progression.power_stack import PowerStack, power_stack  # noqa: E402
from progression.power_stack import report_lines as stack_lines  # noqa: E402
from progression.timeline import StorageBank, container_options, pa_duration  # noqa: E402

PLAN_SCHEMA = "run-plan/1"
#: The declared run (reframe A20, 2026-11-18): what plan_phase takes, as a
#: document. Every key required and unknown keys refused, like factory-inputs/1,
#: so a browser form's gaps are refused here by name, not filled in JS.
INPUTS_SCHEMA = "run-inputs/1"
INPUT_KEYS = ("schema", "playthrough", "scenario", "phase", "horizon_min", "horizon_fraction",
              "power_statistic", "fuel_byproducts", "standing_generators", "generation_mix")
#: the same shapes as factory-inputs/1 (pinned equal by tests/test_run_inputs.py)
PLAYTHROUGH_KEYS = ("through_tier", "milestones", "research", "alternates")
SCENARIO_KEYS = ("recipe_input_multiplier", "machine_power_multiplier",
                 "project_assembly_requirement_multiplier", "fluid_input_floor",
                 "fluid_rounding_unit")
#: The factory track's declarations a hand-off needs beyond the run (A20): every
#: argument of to_factory_inputs, none taken from its keyword defaults.
HANDOFF_KEYS = ("world_config_id", "label", "socket_ids", "supply", "pumps_water", "power_mode",
                "power_statistic", "fuel_byproducts", "power_from_site", "goal", "grid_mw",
                "spare_mw", "infrastructure_policy", "fixed_rate")
FUEL_ROUTES = ("power", "package")   # progression.byproducts.FUEL_ROUTES (pinned by the test)

def power_note(statistic: PowerStatistic) -> str:
    return (f"power stack (reframe A18): the plan's machine power ({PowerStatistic(statistic).value}, "
            "as declared), carried by the generator class obtained last, earlier classes as "
            "backup; extractors and the fuel chains' own power are not in the need")


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
    #: what actually blocks it: the deepest items on its owned chains that no
    #: owned recipe makes, each with its producers as above. The part itself
    #: when no owned recipe makes it (Codex on PR #15, 2026-11-17: an owned
    #: Automated Wiring recipe was reported while Basic Steel Production was
    #: what was missing).
    needs: tuple[tuple[str, tuple[tuple[str, str, tuple[str, ...]], ...]], ...] = ()


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
    power_stack: PowerStack | None             # None when a part is blocked
    availability_report: str
    power_statistic: PowerStatistic
    #: declared generators already built (reframe A18), carried into the
    #: factory hand-off; never replaced by an empty set (Codex on PR #15)
    standing_generators: dict
    #: declared generation mix (reframe A19): class -> share of what standing
    #: units leave; None: the class obtained last carries it
    generation_mix: dict | None
    byproducts: tuple[Byproduct, ...] = ()   # reframe A16: default to the AWESOME Sink


def phase_bill(repo: pathlib.Path, data, phase: int) -> tuple[dict[str, float], dict[str, float], float]:
    """The phase's E-scaled bill, each part's one-machine minutes and the
    one-machine ceiling (B1, the prototype's bound), under `data`'s scenario."""
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
    return bill, one_machine, max(one_machine.values())


def phase_horizons(repo: pathlib.Path, scenario: Scenario,
                   fractions: tuple[float, ...]) -> list[dict]:
    """Per Project Assembly phase: the one-machine ceiling and the horizon each
    declared fraction of it gives (reframe A21: the page's horizon chips show
    these minutes; the page does not multiply)."""
    data = load(repo, scenario)
    phases = sorted({r.phase for r in load_project_assembly(repo, data)})
    out = []
    for n in phases:
        _, _, ceiling = phase_bill(repo, data, n)
        out.append({"phase": n, "ceiling_min": ceiling,
                    "horizons": [{"fraction": f, "horizon_min": f * ceiling} for f in fractions]})
    return out


def plan_phase(
    repo: pathlib.Path, *, state: PlaythroughState, scenario: Scenario, phase: int,
    horizon_min: float | None = None, horizon_fraction: float | None = None,
    power_statistic: PowerStatistic,
    fuel_byproducts: str,
    standing_generators: dict[str, int] | None = None,
    generation_mix: dict[str, float] | None = None,
) -> PhasePlan:
    """`power_statistic` is required (AGENTS.md: no default; LP D2 deferred).
    `fuel_byproducts` is "power" or "package" (reframe A18), required."""
    if (horizon_min is None) == (horizon_fraction is None):
        raise RunPlanError("declare exactly one of horizon_min and horizon_fraction")
    if horizon_min is not None and not horizon_min > 0:
        raise RunPlanError(f"horizon_min must be positive, got {horizon_min!r}")
    if horizon_fraction is not None and not 0 < horizon_fraction <= 1:
        raise RunPlanError(f"horizon_fraction must be in (0, 1], got {horizon_fraction!r}")

    data = load(repo, scenario)
    bill, one_machine, ceiling = phase_bill(repo, data, phase)
    horizon = horizon_min if horizon_min is not None else horizon_fraction * ceiling
    parts = tuple(PartTarget(i, q, one_machine[i], q / horizon) for i, q in bill.items())

    avail = availability(repo, state)
    open_caps = tuple(ResourceCap(i, float("inf")) for i in data.resource_items)
    reach = discover(data, avail.recipe_ids, open_caps, tuple(bill))
    unlocks_of: dict[str, list[str]] = {}
    names = {s.schematic_id: s.display_name for s in load_schematic_rows(repo)}
    for u in load_schematic_unlock_rows(repo):
        unlocks_of.setdefault(u.recipe_id, []).append(names.get(u.schematic_id, u.schematic_id))
    def producers_of(item):
        return tuple(
            (rc.recipe_id, avail.status.get(rc.recipe_id, RecipeStatus.LOCKED).value,
             tuple(sorted(unlocks_of.get(rc.recipe_id, ()))))
            for rc in data.recipes.values() if any(i == item for i, _ in rc.outputs))

    owned = set(avail.recipe_ids)
    reachable = {x.item_id for x in discover(data, avail.recipe_ids, open_caps, tuple(data.items))
                 if x.makeable} | set(data.resource_items)

    def roots(item, trail):
        """The deepest unreachable items under `item` along owned recipes."""
        if item in reachable:
            return []
        made_by = [rc for rc in data.recipes.values()
                   if rc.recipe_id in owned and any(i == item for i, _ in rc.outputs)]
        if not made_by:
            return [item]
        out = []
        for rc in made_by:
            for i, _ in rc.inputs:
                if i not in trail:
                    out += [r for r in roots(i, trail | {item}) if r not in out]
        return out or [item]

    blocked = tuple(
        BlockedPart(x.item_id, producers_of(x.item_id),
                    tuple((r, producers_of(r)) for r in roots(x.item_id, frozenset())))
        for x in reach if not x.makeable)

    response = None
    stack: PowerStack | None = None
    byproducts: tuple[Byproduct, ...] = ()
    if not blocked:
        response = LpBackend(power_statistic=power_statistic).solve(SolveRequest(
            outputs=tuple(OutputTarget(p.item_id, p.rate_per_min) for p in parts),
            allowed_recipes=avail.allowed_recipes,
        ), data)
        stack = power_stack(repo, data, state, response.power.scenario_mw,
                            avail.recipe_ids, standing_generators, generation_mix)
        byproducts = ledger(repo, data, state, response.items,
                            {p.item_id: p.rate_per_min for p in parts},
                            owned_recipes=avail.recipe_ids, fuel_route=fuel_byproducts)

    return PhasePlan(phase, state, data.scenario, ceiling, horizon, horizon / ceiling, parts,
                     blocked, response, stack, avail.report(),
                     PowerStatistic(power_statistic), dict(standing_generators or {}),
                     dict(generation_mix) if generation_mix else None,
                     byproducts)


def to_factory_inputs(
    plan: PhasePlan, *, world_config_id: str, label: str, socket_ids: tuple[str, ...],
    power_mode: str, power_statistic: PowerStatistic, fuel_byproducts: str,
    power_from_site: bool, goal: str = "balanced", supply: tuple = (), pumps_water: bool = False,
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
        "goal": goal, "power_mode": power_mode,
        "power_statistic": PowerStatistic(power_statistic).value,
        "grid_mw": grid_mw, "spare_mw": spare_mw,
        "target_scale": (largest / plan.horizon_min) if fixed_rate else None,
        "infrastructure_policy": infrastructure_policy,
        "fuel_byproducts": fuel_byproducts,
        "standing_generators": dict(plan.standing_generators),
        "generation_mix": None if plan.generation_mix is None else dict(plan.generation_mix),
        "power_from_site": power_from_site,
    }


def _keys(where: str, doc, keys) -> None:
    if not isinstance(doc, dict):
        raise RunPlanError(f"{where}: an object is required")
    missing = [k for k in keys if k not in doc]
    extra = sorted(k for k in doc if k not in keys)
    if missing or extra:
        raise RunPlanError(f"{where}: missing {missing}, not known {extra}")


def run_inputs(doc: dict, repo: pathlib.Path = REPO) -> PhasePlan:
    """Plan a run-inputs/1 document (A20). Shape is checked here; content where
    it is owned (playthrough ids, Scenario, horizon, power stack)."""
    _keys("inputs", doc, INPUT_KEYS)
    if doc["schema"] != INPUTS_SCHEMA:
        raise RunPlanError(f"inputs schema {doc['schema']!r}, this reads {INPUTS_SCHEMA}")
    _keys("inputs.playthrough", doc["playthrough"], PLAYTHROUGH_KEYS)
    _keys("inputs.scenario", doc["scenario"], SCENARIO_KEYS)
    phase = doc["phase"]
    if not isinstance(phase, int) or isinstance(phase, bool):
        raise RunPlanError(f"phase: a whole number, got {phase!r}")
    try:
        statistic = PowerStatistic(doc["power_statistic"])
    except ValueError:
        raise RunPlanError(f"power_statistic {doc['power_statistic']!r}; known: "
                           f"{[s.value for s in PowerStatistic]} (no default: LP D2)") from None
    if doc["fuel_byproducts"] not in FUEL_ROUTES:
        raise RunPlanError(f"fuel_byproducts {doc['fuel_byproducts']!r}; known: "
                           f"{list(FUEL_ROUTES)} (reframe A18: generator, or packaged)")
    standing = doc["standing_generators"]
    if not isinstance(standing, dict):
        raise RunPlanError("standing_generators: an object of generator class -> units built "
                           "({} declares none built)")
    mix = doc["generation_mix"]
    if mix is not None and (not isinstance(mix, dict) or not mix):
        raise RunPlanError("generation_mix: null (the class obtained last carries the rest) "
                           "or an object of generator class -> share (A19)")
    pt = doc["playthrough"]
    state = playthrough(repo, through_tier=pt["through_tier"], milestones=pt["milestones"],
                        research=pt["research"], alternates=pt["alternates"])
    return plan_phase(repo, state=state, scenario=Scenario(**doc["scenario"]), phase=phase,
                      horizon_min=doc["horizon_min"], horizon_fraction=doc["horizon_fraction"],
                      power_statistic=statistic, fuel_byproducts=doc["fuel_byproducts"],
                      standing_generators=standing, generation_mix=mix)


def handoff(run_doc: dict, decl: dict, repo: pathlib.Path = REPO) -> dict:
    """A1 hand-off from documents (A20): plan `run_doc` (run-inputs/1) and write
    the factory-inputs/1 for it with every factory declaration in `decl`
    (HANDOFF_KEYS, all required). A step with blocked parts is refused: the
    factory would refuse its goal mix anyway, and the blocked list says why."""
    _keys("handoff", decl, HANDOFF_KEYS)
    for k in ("pumps_water", "power_from_site", "fixed_rate"):
        if not isinstance(decl[k], bool):
            raise RunPlanError(f"handoff.{k}: true or false, declared")
    if not isinstance(decl["socket_ids"], list) or not decl["socket_ids"]:
        raise RunPlanError("handoff.socket_ids: declare at least one socket; nothing picks a site")
    if not isinstance(decl["supply"], list):
        raise RunPlanError("handoff.supply: a list of {item_id, rate_per_min} ([] declares none)")
    for n, s in enumerate(decl["supply"]):
        _keys(f"handoff.supply[{n}]", s, ("item_id", "rate_per_min"))
    plan = run_inputs(run_doc, repo)
    if plan.blocked:
        raise RunPlanError(f"phase {plan.phase} has blocked parts "
                           f"({', '.join(b.item_id for b in plan.blocked)}); a blocked step "
                           "cannot be handed to the factory track")
    return to_factory_inputs(
        plan, world_config_id=decl["world_config_id"], label=decl["label"],
        socket_ids=tuple(decl["socket_ids"]), power_mode=decl["power_mode"],
        power_statistic=decl["power_statistic"], fuel_byproducts=decl["fuel_byproducts"],
        power_from_site=decl["power_from_site"], goal=decl["goal"],
        supply=tuple((s["item_id"], s["rate_per_min"]) for s in decl["supply"]),
        pumps_water=decl["pumps_water"], grid_mw=decl["grid_mw"], spare_mw=decl["spare_mw"],
        infrastructure_policy=decl["infrastructure_policy"], fixed_rate=decl["fixed_rate"])


#: a storage-priority bank as the page declares it (reframe A21; A15.2 B3)
BANK_KEYS = ("name", "storage_item", "feed_per_min", "bank_intake_per_min", "bank_output_per_min",
             "container_class", "container_count", "pa_items", "splitter", "standard_share")


def storage_timeline(plan: PhasePlan, banks: list, repo: pathlib.Path = REPO) -> dict:
    """B3/Q6 on a planned step: the phase's duration with declared
    storage-priority banks, from `progression.timeline`.

    The bill and the PA lanes' full rates are the plan's parts (E-scaled bill,
    rate over the horizon). Each bank's capacity is its declared container type
    and count (Q6), which must be unlocked in the plan's state; the stack size
    is the storage item's. Every figure in the result is computed here, the
    bank properties included, so the page multiplies nothing."""
    if plan.blocked:
        raise RunPlanError(f"phase {plan.phase} has blocked parts; a blocked step has no duration")
    if not isinstance(banks, list):
        raise RunPlanError("banks: a list ([] gives the phase without banks)")
    data = load(repo, plan.scenario)
    built = []
    for n, b in enumerate(banks):
        _keys(f"banks[{n}]", b, BANK_KEYS)
        item = b["storage_item"]
        if item not in data.items:
            raise RunPlanError(f"banks[{n}].storage_item: {item!r} is not an item")
        stack = data.items[item].stack_size
        if data.items[item].form != "solid" or not stack:
            raise RunPlanError(f"banks[{n}].storage_item: {item} is not a stackable solid; "
                               "a storage container holds solids (items.csv form, stack size)")
        count = b["container_count"]
        if not isinstance(count, int) or isinstance(count, bool):
            raise RunPlanError(f"banks[{n}].container_count: a whole number, got {count!r}")
        options = container_options(repo, plan.state, stack, count)
        chosen = [o for o in options if o.building_class == b["container_class"]]
        if not chosen:
            raise RunPlanError(f"banks[{n}].container_class {b['container_class']!r} is not one "
                               f"this state can build: {[o.building_class for o in options]}")
        if not isinstance(b["pa_items"], list):
            raise RunPlanError(f"banks[{n}].pa_items: a list of PA parts")
        built.append(StorageBank(
            name=b["name"], storage_item=item, feed_per_min=b["feed_per_min"],
            bank_intake_per_min=b["bank_intake_per_min"],
            bank_output_per_min=b["bank_output_per_min"],
            capacity_units=chosen[0].capacity_units, pa_items=tuple(b["pa_items"]),
            splitter=b["splitter"], standard_share=b["standard_share"]))
    tl = pa_duration({p.item_id: p.bill_units for p in plan.parts},
                     {p.item_id: p.rate_per_min for p in plan.parts}, tuple(built))
    return {
        "duration_min": tl.duration_min, "baseline_min": tl.baseline_min, "delay_min": tl.delay_min,
        "banks": [{"name": x.name, "storage_item": x.storage_item, "splitter": x.splitter,
                   "capacity_units": x.capacity_units, "take_per_min": x.bank_take_per_min,
                   "fill_rate_per_min": x.fill_rate_per_min, "fill_min": x.fill_min,
                   "pa_share_filling": x.pa_share_filling, "pa_items": list(x.pa_items)}
                  for x in built],
        "parts": [dataclasses.asdict(p) for p in tl.parts],
        "stock_at_finish": [{"bank": bk, "item_id": i, "units": u} for bk, i, u in tl.stock_at_finish],
        "report": tl.report(),
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
        "power_statistic": plan.power_statistic.value,
        "standing_generators": dict(plan.standing_generators),
        "generation_mix": plan.generation_mix,
        "power_stack": None if plan.power_stack is None else dataclasses.asdict(plan.power_stack),
        "byproducts": [dataclasses.asdict(b) for b in plan.byproducts],
        "notes": [power_note(plan.power_statistic)],
    }


def report(plan: PhasePlan) -> str:
    lines = [f"phase {plan.phase}: horizon {plan.horizon_min:.1f} min "
             f"({100 * plan.horizon_fraction:.1f}% of the one-machine ceiling, "
             f"{plan.ceiling_min:.1f} min)"]
    for p in plan.parts:
        lines.append(f"  {p.item_id}: {p.bill_units:g} at {p.rate_per_min:.4g}/min "
                     f"(one machine: {p.one_machine_min:.1f} min)")
    for b in plan.blocked:
        for item, producers in b.needs:
            how = "; ".join(f"{rid} {st} via {', '.join(via) or 'nothing listed'}"
                            for rid, st, via in producers)
            head = "" if item == b.item_id else f"needs {item}: "
            lines.append(f"  BLOCKED {b.item_id}: {head}{how}")
    if plan.response is not None:
        lines.append(f"  machines' power {plan.response.power.scenario_mw:.4g} MW "
                     f"({plan.power_statistic.value})")
        for x in plan.response.raw_inputs:
            lines.append(f"  raw {x.item_id}: {x.rate_per_min:.4g}/min")
        lines += stack_lines(plan.power_stack)
        lines.append(f"  note: {power_note(plan.power_statistic)}")
    lines += report_lines(plan.byproducts)
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
    ap.add_argument("--power-statistic", required=True,
                    choices=[s.value for s in PowerStatistic],
                    help="which end of a variable-power recipe's range (no default: LP D2)")
    ap.add_argument("--fuel-byproducts", required=True, choices=["power", "package"],
                    help="leftover fuel to generators, or packaged (reframe A18)")
    ap.add_argument("--standing", action="append", default=[], metavar="CLASS=N",
                    help="generators already built, by class; they keep carrying load "
                         "(burners are backup), reframe A19")
    ap.add_argument("--mix", action="append", default=[], metavar="CLASS=SHARE",
                    help="how what standing units leave is supplied (shares sum to 1); "
                         "omitted: the class obtained last (reframe A19)")
    ap.add_argument("--export", type=pathlib.Path)
    args = ap.parse_args(argv)
    state = playthrough(REPO, through_tier=args.through_tier, milestones=args.milestone,
                        research=args.research, alternates=args.alternate)
    scenario = Scenario(recipe_input_multiplier=args.recipe_multiplier,
                        machine_power_multiplier=args.power_multiplier,
                        project_assembly_requirement_multiplier=args.pa_multiplier,
                        fluid_input_floor=args.fluid_input_floor)
    plan = plan_phase(REPO, state=state, scenario=scenario, phase=args.phase,
                      horizon_min=args.horizon_min, horizon_fraction=args.horizon_fraction,
                      power_statistic=PowerStatistic(args.power_statistic),
                      fuel_byproducts=args.fuel_byproducts,
                      standing_generators={k: int(v) for k, v in
                                           (s.split("=", 1) for s in args.standing)},
                      generation_mix={k: float(v) for k, v in
                                      (s.split("=", 1) for s in args.mix)} or None)
    print(report(plan))
    if args.export:
        args.export.write_text(json.dumps(record(plan), indent=1, default=str) + "\n",
                               encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
