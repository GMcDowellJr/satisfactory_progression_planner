#!/usr/bin/env python3
"""Factory planner (supply side): what one factory can deliver from what it has.

Site-planner reframe A15.2 (decided by Greg, 2026-11-17), reconciliation R7.

    A1   a sibling track: one scope plans the run, another takes that plan as
         input, or takes a per-factory plan at run time where the user lists
         what is available and the goals
    B1   supply side is the preferred method for the current factory: maximise
         the scale of a DECLARED goal mix within the factory's supply. Nothing
         invents a mix; an undeclared one is refused
    B2   extractors at the highest mark the playthrough has (the supply), then
         stepped down where the higher mark does not help (Q1)

A joint at tools/ root, like portfolio_run: it composes and adds no solver.

    state      progression.playthrough + availability (milestones owned, R5)
    sockets    site_card.load_sockets / site_caps (one reader, refusals as there)
    marks      progression.infrastructure (R6), HIGHEST_THEN_STEP_DOWN declared
    solve      LpBackend.solve_portfolio with ONE site: the same call the site
               card's self-powered ceiling makes (reframe A5.1), so reframe
               A2/A3/A4/A7/A11/A13 apply unchanged
    power      "grid" (A3: generators the state can build, a declared standing
               grid) or "report_need" (A11), with A11's refusals

Per-socket draws for the step-down are read at an EQUAL SHARE of each raw's
cap (the choice-free reading `progression.extraction_at_share` uses, reframe
A6): the solve sees a raw's sockets as one cap and does not say which socket
it would work. Stated on every report.

Input: `factory-inputs/1` (every key required, unknown keys refused, like
portfolio-inputs/2). Output: `factory-plan/1`. The run-plan track (R9) will
write factory-inputs/1 documents; a hand-written one is the run-time path.

    uv run python tools/factory_run.py --inputs factory.json [--export plan.json]
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

from production_adapter import (  # noqa: E402
    PortfolioRequest, PortfolioSite, PowerBalance, ResourceCap, Scenario, load,
)
from production_adapter.gamedata import load_generators, load_logistics  # noqa: E402
from production_adapter.lp_backend import LpBackend, PowerStatistic  # noqa: E402
from progression import (  # noqa: E402
    availability, discover, generators_available, nameplate_mw, playthrough, pumped_caps,
    site_extraction,
)
from progression.byproducts import Byproduct, ledger, report_lines  # noqa: E402
from progression.district import WATER  # noqa: E402
from progression.infrastructure import (  # noqa: E402
    POLICIES, BeltChoice, MarkChoice, belt_for, extractor_options, highest_extractor,
    step_down_extractor,
)
from progression.power import load_power_tables  # noqa: E402

import site_card  # noqa: E402

INPUTS_SCHEMA = "factory-inputs/1"
PLAN_SCHEMA = "factory-plan/1"
INPUT_KEYS = ("schema", "world_config_id", "playthrough", "scenario", "site", "goal_mix",
              "goal", "power_mode", "grid_mw", "spare_mw", "target_scale",
              "infrastructure_policy")
PLAYTHROUGH_KEYS = ("through_tier", "milestones", "research", "alternates")
SITE_KEYS = ("label", "socket_ids", "supply", "pumps_water")
SCENARIO_KEYS = ("recipe_input_multiplier", "machine_power_multiplier",
                 "project_assembly_requirement_multiplier", "fluid_input_floor",
                 "fluid_rounding_unit")
POWER_MODES = ("grid", "report_need")
FORM_SOLID = "solid"  # items.csv `form`: solid | liquid | gas

#: Which extractor family a socket kind takes, read against
#: resource_extraction_map.csv's `requires_activator` (R7): a well satellite's
#: extractor needs a pressurizer, a node's does not. Kinds the site card does
#: not extract (cores, geysers) never reach this.
ACTIVATED_BY_KIND = {"resource_node": False, "fracking_satellite": True}

SHARE_NOTE = ("per-socket draws are read at an equal share of each raw's cap (reframe A6's "
              "choice-free reading); the solve does not say which socket it would work")


class FactoryRunError(ValueError):
    """The declared factory cannot be run as declared; refused by name."""


@dataclass(frozen=True)
class SocketPlan:
    socket_id: str
    source_kind: str
    mark: MarkChoice
    lane: BeltChoice | None     # None: not drawn


@dataclass(frozen=True)
class FactoryRun:
    inputs: dict
    scale: float                                   # units of the goal mix per minute
    delivered: tuple[tuple[str, float], ...]       # item, per minute
    recipes: tuple                                 # RecipeUse, from the site's plan
    raw_draw: tuple[tuple[str, float], ...]
    binding: tuple                                 # BindingCap
    sockets: tuple[SocketPlan, ...]
    skipped: tuple[tuple[str, str], ...]           # sockets not extracted, with the reason
    extraction_mw_highest: float                   # by the draw, at the highest marks
    extraction_mw_chosen: float                    # by the draw, after the step-down
    lane_mw: float
    power_mode: str
    power: object                                  # DistrictPower
    availability_report: str
    warnings: tuple[str, ...]
    byproducts: tuple[Byproduct, ...] = ()   # reframe A16: default to the AWESOME Sink


def _keys(where: str, doc, keys) -> None:
    if not isinstance(doc, dict):
        raise FactoryRunError(f"{where}: an object is required")
    missing = [k for k in keys if k not in doc]
    extra = sorted(k for k in doc if k not in keys)
    if missing or extra:
        raise FactoryRunError(f"{where}: missing {missing}, not known {extra}")


def run_inputs(doc: dict, repo: pathlib.Path = REPO,
               power_statistic: PowerStatistic = PowerStatistic.MEAN) -> FactoryRun:
    """Run a factory-inputs/1 document. Shape checked here; content where it is owned."""
    _keys("inputs", doc, INPUT_KEYS)
    if doc["schema"] != INPUTS_SCHEMA:
        raise FactoryRunError(f"inputs schema {doc['schema']!r}, this reads {INPUTS_SCHEMA}")
    _keys("inputs.playthrough", doc["playthrough"], PLAYTHROUGH_KEYS)
    _keys("inputs.scenario", doc["scenario"], SCENARIO_KEYS)
    _keys("inputs.site", doc["site"], SITE_KEYS)
    if doc["infrastructure_policy"] not in POLICIES:
        raise FactoryRunError(f"infrastructure_policy {doc['infrastructure_policy']!r}; "
                              f"known: {list(POLICIES)}")
    if doc["power_mode"] not in POWER_MODES:
        raise FactoryRunError(f"power_mode {doc['power_mode']!r}; known: {list(POWER_MODES)}")
    if doc["goal"] not in site_card.GOALS:
        raise FactoryRunError(f"goal {doc['goal']!r}; known: {list(site_card.GOALS)}")
    mix = doc["goal_mix"]
    if not isinstance(mix, list) or not mix:
        raise FactoryRunError("goal_mix: declare at least one item; a mix is never invented (B1)")
    for n, m in enumerate(mix):
        _keys(f"inputs.goal_mix[{n}]", m, ("item_id", "units"))

    pt = doc["playthrough"]
    state = playthrough(repo, through_tier=pt["through_tier"], milestones=pt["milestones"],
                        research=pt["research"], alternates=pt["alternates"])
    scenario = Scenario(**doc["scenario"])
    site = doc["site"]
    return run_factory(
        repo, state=state, scenario=scenario, world_config_id=doc["world_config_id"],
        label=site["label"], socket_ids=tuple(site["socket_ids"]),
        supply=tuple((s["item_id"], s["rate_per_min"]) for s in site["supply"]),
        pumps_water=site["pumps_water"],
        goal_mix=tuple((m["item_id"], m["units"]) for m in mix), goal=doc["goal"],
        power_mode=doc["power_mode"], grid_mw=doc["grid_mw"], spare_mw=doc["spare_mw"],
        target_scale=doc["target_scale"], policy=doc["infrastructure_policy"],
        power_statistic=power_statistic, inputs=doc,
    )


def run_factory(
    repo: pathlib.Path, *, state, scenario: Scenario, world_config_id: str, label: str,
    socket_ids: tuple[str, ...], supply: tuple[tuple[str, float], ...], pumps_water: bool,
    goal_mix: tuple[tuple[str, float], ...], goal: str, power_mode: str, grid_mw: float,
    spare_mw: float, target_scale: float | None, policy: str,
    power_statistic: PowerStatistic = PowerStatistic.MEAN, inputs: dict | None = None,
) -> FactoryRun:
    if policy not in POLICIES:
        raise FactoryRunError(f"infrastructure policy {policy!r}; known: {list(POLICIES)}")
    need = power_mode == "report_need"
    if need and (grid_mw != 0.0 or pumps_water):
        raise FactoryRunError("report_need reports the whole need: no standing grid and no "
                              "pumped Water beside it (reframe A11)")
    if any(item == WATER for item, _ in supply):
        raise FactoryRunError("declared Water supply: Water is never free (reframe A4); "
                              "declare the site able to pump it")

    data = load(repo, scenario)
    avail = availability(repo, state)
    _, rates = load_logistics(repo)
    tables = load_power_tables(repo)
    sockets = site_card.load_sockets(repo, world_config_id)
    by_id = {s.socket_id: s for s in sockets}

    # B2, supply half: each extracted socket at the highest mark it can take
    highest: dict[tuple[str, str], str] = {}
    options_of: dict[str, tuple] = {}
    for sid in socket_ids:
        s = by_id.get(sid)
        if s is None or s.source_kind in site_card.NOT_EXTRACTED or s.item_id is None:
            continue  # unknown ids and non-extracted kinds are refused / reported by site_card
        if s.source_kind not in ACTIVATED_BY_KIND:
            raise FactoryRunError(f"{sid}: socket kind {s.source_kind!r} has no extractor family")
        opts = extractor_options(avail, s.item_id, s.purity, rates, tables.extractors, scenario,
                                 repo_root=repo, activated=ACTIVATED_BY_KIND[s.source_kind])
        options_of[sid] = opts
        key = (s.source_kind, s.item_id)
        top = highest_extractor(opts).extractor_class
        if highest.setdefault(key, top) != top:
            raise FactoryRunError(f"{key}: two highest marks {highest[key]} and {top}")

    spec = site_card.SiteSpec(label=label, socket_ids=socket_ids,
                              extractors=tuple(sorted(highest.items())), extraction_clock=1.0,
                              supply=supply)
    chosen, _, skipped, definition, caps = site_card.site_caps(spec, data, rates, sockets)
    segments = site_extraction(definition, rates, tables.extractors, scenario=data.scenario,
                               supply=supply, water=pumps_water)
    if pumps_water:
        caps = pumped_caps(caps)

    raws = {c.item_id for c in caps}
    for item, units in goal_mix:
        if item not in data.items:
            raise FactoryRunError(f"goal_mix: {item} is not an item")
        if item in raws:
            raise FactoryRunError(f"goal_mix: {item} is a raw resource, not a product")
        if not units > 0:
            raise FactoryRunError(f"goal_mix: {item} at {units!r} units; units must be positive")
    reach_caps = tuple(ResourceCap(c.item_id, float("inf")) if c.rate_per_min is None else c
                       for c in caps)
    unmade = [x for x in discover(data, avail.recipe_ids, reach_caps, tuple(i for i, _ in goal_mix))
              if not x.makeable]
    if unmade:
        raise FactoryRunError(
            "goal_mix items this factory cannot make with what it owns: "
            + "; ".join(f"{x.item_id} (" + ("no owned recipe makes it" if x.no_recipe else
                        f"needs {list(x.missing_raws)}") + ")" for x in unmade)
            + ". A mix is declared, never trimmed (B1).")

    if need:
        generators = ()
    else:
        rows = load_generators(repo)
        classes = tuple(dict.fromkeys(g.generator_class for g in rows))
        open_classes = generators_available(repo, state, classes)
        generators = tuple(g for g in rows if g.generator_class in open_classes)
    grid = PowerBalance(generators=generators, grid_mw=grid_mw, spare_mw=spare_mw,
                        report_need=need)

    response = LpBackend(power_statistic=power_statistic).solve_portfolio(PortfolioRequest(
        sites=(PortfolioSite(label, caps, segments),), bill=goal_mix,
        allowed_recipes=avail.allowed_recipes, weights=site_card.GOALS[goal], power=grid,
        target_scale=target_scale,
    ), data)
    plan = response.sites[0]
    draw = {r.item_id: r.rate_per_min for r in plan.plan.raw_inputs}

    # B2, realize half: per-socket draw at an equal share of the raw's cap
    cap_of = {c.item_id: c.rate_per_min for c in caps}
    socket_plans = []
    for s in chosen:
        if s.socket_id not in options_of:
            continue
        opts = options_of[s.socket_id]
        top = highest_extractor(opts)
        total = cap_of.get(s.item_id) or 0.0
        share = (draw.get(s.item_id, 0.0) / total) if total > 0 else 0.0
        socket_draw = min(top.nominal_rate_min, share * top.nominal_rate_min)
        mark = step_down_extractor(s.socket_id, s.item_id, s.purity, socket_draw, opts)
        lane = None
        if mark.chosen is not None:
            # items.csv `form`: solids ride belts, liquids and gases pipes
            kind = "belt" if data.items[s.item_id].form == FORM_SOLID else "pipeline"
            lane = belt_for(socket_draw, avail, kind)
        socket_plans.append(SocketPlan(s.socket_id, s.source_kind, mark, lane))

    mw_top = sum(p.mark.highest.mw_at(p.mark.draw_per_min) for p in socket_plans)
    mw_kept = sum(p.mark.chosen.mw_at(p.mark.draw_per_min) for p in socket_plans
                  if p.mark.chosen is not None)
    return FactoryRun(
        inputs=inputs if inputs is not None else {},
        scale=response.scale,
        delivered=tuple((i, units * response.scale) for i, units in goal_mix),
        recipes=plan.plan.recipes,
        raw_draw=tuple(sorted(draw.items())),
        binding=plan.binding,
        sockets=tuple(socket_plans),
        skipped=skipped,
        extraction_mw_highest=mw_top,
        extraction_mw_chosen=mw_kept,
        lane_mw=plan.lane_mw,
        power_mode=power_mode,
        power=response.power,
        availability_report=avail.report(),
        warnings=plan.plan.warnings + (SHARE_NOTE,),
        byproducts=ledger(repo, data, state, plan.plan.items,
                          {i: units * response.scale for i, units in goal_mix},
                          owned_recipes=avail.recipe_ids),
    )


def record(run: FactoryRun) -> dict:
    """The factory-plan/1 record: echoes its inputs, states its readings."""
    def mark(m: MarkChoice) -> dict:
        return {"draw_per_min": m.draw_per_min, "highest": m.highest.extractor_class,
                "chosen": m.chosen.extractor_class if m.chosen else None,
                "stepped_down": m.stepped_down, "reason": m.reason}
    return {
        "schema": PLAN_SCHEMA,
        "inputs": run.inputs,
        "scale_per_min": run.scale,
        "delivered": [{"item_id": i, "rate_per_min": r} for i, r in run.delivered],
        "recipes": [dataclasses.asdict(r) for r in run.recipes],
        "raw_draw": [{"item_id": i, "rate_per_min": r} for i, r in run.raw_draw],
        "binding": [dataclasses.asdict(b) for b in run.binding],
        "sockets": [{"socket_id": p.socket_id, "source_kind": p.source_kind, **mark(p.mark),
                     "lane": None if p.lane is None else
                     {"lanes": p.lane.lanes, "mark": p.lane.mark.mark,
                      "highest": p.lane.highest.mark, "kind": p.lane.mark.capability_type}}
                    for p in run.sockets],
        "not_extracted": [{"socket_id": s, "reason": r} for s, r in run.skipped],
        "extraction_mw": {"at_highest": run.extraction_mw_highest,
                          "after_step_down": run.extraction_mw_chosen},
        "lane_mw": run.lane_mw,
        "power_mode": run.power_mode,
        "power": None if run.power is None else dataclasses.asdict(run.power),
        "byproducts": [dataclasses.asdict(b) for b in run.byproducts],
        "warnings": list(run.warnings),
    }


def report(run: FactoryRun) -> str:
    lines = [f"factory: scale {run.scale:.6g} goal-mix units/min "
             f"({run.power_mode}; {len(run.sockets)} extracted sockets)"]
    lines += [f"  delivers {i}: {r:.4g}/min" for i, r in run.delivered]
    for p in run.sockets:
        m = p.mark
        kept = m.chosen.extractor_class if m.chosen else "nothing"
        lane = "" if p.lane is None else f"; {p.lane.lanes} x {p.lane.mark.capability_type} {p.lane.mark.mark}"
        lines.append(f"  {p.socket_id}: draw {m.draw_per_min:.4g}/min, {kept} "
                     f"(highest {m.highest.extractor_class}){lane}")
    lines.append(f"  extraction {run.extraction_mw_chosen:.4g} MW after step-down "
                 f"({run.extraction_mw_highest:.4g} MW at the highest marks), by the draw")
    lines += report_lines(run.byproducts)
    lines.append("  " + run.availability_report.replace("\n", "\n  "))
    lines += [f"  note: {w}" for w in run.warnings]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--inputs", required=True, type=pathlib.Path, help="a factory-inputs/1 file")
    ap.add_argument("--export", type=pathlib.Path, help="write the factory-plan/1 record here")
    args = ap.parse_args(argv)
    try:
        doc = json.loads(args.inputs.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        ap.error(f"--inputs: {e}")
    run = run_inputs(doc)
    print(report(run))
    if args.export:
        args.export.write_text(json.dumps(record(run), indent=1, default=str) + "\n",
                               encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
