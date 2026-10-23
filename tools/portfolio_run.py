#!/usr/bin/env python3
"""A bounded portfolio: several declared sites share one bill. What each makes,
what moves between them, and what each would manage alone.

Site-planner reframe, Amendment 1 (adopted by Greg, 2026-10-19; holds until
something proves it wrong): demand is the Project Assembly + milestone bill
(P1); power is in the solve as one shared grid (A3, reversing P2); transfers
between the declared sites are free (P3) and raws may move (P6); the sites are
a bounded set the caller declares (P4); the volume tie-break counts one item
as one m3 (P5); the bill counts wherever it is made (P7). A joint at tools/
root like district_run.py and site_card.py, whose site composition it reuses:

    sites     site_card.site_caps per declared SiteSpec: closed caps
    bill      Project Assembly phases (scenario-scaled) + milestone costs of
              the declared tiers, summed by progression.district.bill_units
              (A31), the same composition district_run.py makes
    reach     discover() over the POOLED caps (with free transfers the sites
              reach together what any of them reaches); a bill item no site
              can reach is reported with its missing raws and the single
              alternates not held that would open it, and is left out of the
              scale (A34's rule in district_run)
    solve     LpBackend.solve_portfolio: max bill scale, then min volume
              moved, then goal cost, then total activity
    alone     the same bill on each site by itself, for comparison: what the
              portfolio adds over its parts
    power     A3 (P2 reversed by Greg, 2026-10-19): one shared grid IN the
              solve. Generators open at the tier (unlocks.generators_open_at_
              tier) may be built at any site, burning its supply; machines at
              100 % clock, mean draw
    need      site planner A11 (Greg 2026-10-23 16:30), power_mode
              "report_need": the grid row is left out, so the plan is bounded
              by the sites' caps alone, and its lanes + extraction + spare are
              reported as the NEED. Then, for every (generator, fuel) row of
              the generators open at the tier, the units that need takes and
              each fuel's feed rate, with where the fuel comes from at this
              tier: recipes held, recipes not held (and why), a socket supply
              across the sites, or none. Nothing is chosen among them. A
              standing grid or a pumping site beside it is refused (A11)
    extract   A4 (Greg, 2026-10-19): extractors charged by their DRAW on the
              grid, MW per unit = base MW / nominal rate, 100 % clock at most;
              nameplate reported beside it. Water only where a site is
              declared able to pump it (--water LABEL): uncapped, charged as
              Water Extractors by the draw, and reported as what is needed.
              A declared --supply of Water is refused: Water is never free

**It cannot choose, and that is the guardrail.** Sites, tier, declared
recipes, bill phases and tiers, scenario and goal are inputs. No min, max or
sort here (asserted by tests/test_portfolio_run.py): sites in declaration
order, bill items in bill order, transfers in the solver's order.

    uv run python tools/portfolio_run.py --tier 6 --bill-phase 3 --bill-tier 5 \\
        --bill-tier 6 --recipe-multiplier 1.0 --clock 1.0 \\
        --site oil:1697.17,-2033.86,500 --site copper:3555.0,1498.0,500 \\
        --extractor resource_node=Build_MinerMk1_C \\
        --extractor resource_node:Desc_LiquidOil_C=Build_OilPump_C \\
        --water copper

**The record (`--export PATH`, handoff 2026-10-19 15:56 next step; Greg,
2026-10-19: "build the json record").** One JSON document, the data contract
for the HTML layer: the inputs as declared, the bill with its scale, every
site's caps beside its draw, recipes, generators and power, the transfers,
the shared grid, and per site a LEDGER of every item it touches. Display
names ride along so a client needs no copy of the reference layer (as
district_run's A27.3 export). LF pinned.

Added 2026-10-23 (handoff 2026-10-19 18:28 action 1, "Step 1"; additive, the
schema tag stays portfolio-plan/1): each binding cap and the grid carry
`margin_text`, the report's own wording of the dual (shadow_text, A5), and
`assumptions.margin` its caveat; `items` gives every mentioned item's form
and, for solids, its stack size, so a client can turn a declared storage
into a fill time without a copy of items.csv; `provenance` says where and
when the record was made (null from record() unless supplied; export()
always supplies it).

**Inputs (`--inputs PATH`, 2026-10-23, handoff 14:48 action 2).** A
portfolio-inputs/2 document (/1 plus `power_mode`, A11) declares the whole run: sites by socket id (as
the picker, tools/site_planner_web/picker.html, writes them), every other
input, and the full Scenario. Every key is required and unknown keys are
refused (run_inputs). The CLI flags build the same document (inputs_doc),
so there is one path into run(), and the record's `inputs` echoes it.

The ledger exists because the portfolio solve drops each site's local
warnings (lp_backend: "the portfolio's ledger is the transfers"), and with
them D1's "unconsumed output is free" note. So a leftover, such as scenario
C's Polymer Resin from the Fuel refineries (A8.2), appears nowhere else.
Each row is accounting on the response, not a choice:

    left = produced + received - consumed - burned - shipped - to_bill

A raw's `produced` is its draw: the plan's flows count a raw drawn as
produced (the caps carry the same figure as `drawn_per_min`). `burned` is
generator fuel and supplemental (A3). Rows keep the solver's
item order; values are exact, so solver residue (~1e-9) is the client's to
round. A leftover is REPORTED; what to do with it is open (A8.5).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _src in ("production_adapter", "progression", "realization"):
    _path = str(REPO / "tools" / _src / "src")
    if _path not in sys.path:
        sys.path.insert(0, _path)
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

from production_adapter import (  # noqa: E402
    ExtractionSegment, PortfolioRequest, PortfolioResponse, PortfolioSite, PowerBalance,
    ResourceCap, Scenario, load,
)
from production_adapter.gamedata import ReferenceData, load_logistics  # noqa: E402
from production_adapter.lp_backend import Infeasible, LpBackend, PowerStatistic  # noqa: E402
from progression import (  # noqa: E402
    at_tier, available_at, bill_units, discover, generators_at_tier, nameplate_mw, pumped_caps,
    recipe_ids_by_name, site_extraction, unlocks,
)
from progression.district import WATER, WATER_EXTRACTOR  # noqa: E402
from progression import stock  # noqa: E402
from progression.power import load_power_tables  # noqa: E402

import shadow_text  # noqa: E402
import site_card  # noqa: E402

#: A1 P5, stated in every report
VOLUME_ASSUMPTION = "transfer volume counts one item as one m3 (A1 P5)"
#: A3, stated in every report
POWER_ASSUMPTION = ("one shared grid (A3); machines at 100 % clock, mean draw for variable "
                    "power; extractors by their draw, at most 100 % clock, nameplate beside "
                    "it (A4); Water pumped only where declared, charged as Water Extractors "
                    "(A4); generators open at the tier")
NOT_ASSESSED = ("routes", "belts", "pipes", "power lines", "node reachability", "buildable area",
                "clock / shard / Somersloop settings")
#: the record's schema tag; a client checks it before reading
RECORD_SCHEMA = "portfolio-plan/1"


class PortfolioRunError(ValueError):
    """A portfolio the run cannot use. Refused by name."""


@dataclasses.dataclass(frozen=True)
class BlockedBillItem:
    item_id: str
    units: float
    missing_raws: tuple[str, ...]
    opened_by: tuple[tuple[str, str], ...]


@dataclasses.dataclass(frozen=True)
class SiteRecord:
    spec: site_card.SiteSpec
    #: Water None where the site pumps it (A4)
    caps: tuple[ResourceCap, ...]
    #: the declared extractors at nameplate (A25.3 P2), reported beside the draw
    extraction_mw: float
    #: A4: what the solve charges by the draw; pumped Water last when declared
    segments: tuple[ExtractionSegment, ...] = ()
    pumps_water: bool = False


@dataclasses.dataclass(frozen=True)
class FuelSource:
    """Where a generator fuel comes from at the run's tier (A11 fuel join).
    `made_by` is every recipe that outputs it, in recipe-table order, each
    with whether it is held and, when not, why (`not_held_reason`); an
    empty tuple means no recipe makes it (gathered or extracted).
    `site_supply_per_min` is the sockets' cap pooled over the sites, None
    when no socket here carries it."""

    made_by: tuple[tuple[str, bool, str | None], ...]
    site_supply_per_min: float | None


@dataclasses.dataclass(frozen=True)
class GeneratorNeed:
    """One (generator, fuel) row at the need: `units` = need / MW per unit,
    exact; `units_whole` its ceiling (the count to build, each then below
    full burn); feed rates at `units`, i.e. at the need exactly."""

    generator_class: str
    fuel_item_id: str
    power_mw: float
    units: float
    units_whole: int
    fuel_per_min: float
    supplemental_per_min: tuple[tuple[str, float], ...]
    source: FuelSource


@dataclasses.dataclass(frozen=True)
class PowerNeed:
    need_mw: float
    lane_mw: float
    extraction_mw: float
    spare_mw: float
    #: every (generator, fuel) row of the classes open at the tier, in
    #: generator_fuels.csv order; empty when no generator is open
    generators: tuple[GeneratorNeed, ...]


#: A11: how power enters the run
POWER_MODES = ("grid", "report_need")


@dataclasses.dataclass(frozen=True)
class PortfolioRun:
    tier: int
    declared_recipes: tuple[str, ...]
    scenario: Scenario
    goal: str
    bill_phases: tuple[int, ...]
    bill_tiers: tuple[int, ...]
    #: the whole composed bill, first-seen order (A31)
    bill: dict
    blocked: tuple[BlockedBillItem, ...]
    sites: tuple[SiteRecord, ...]
    response: PortfolioResponse
    #: each site alone on the same bill items: (label, scale or the reason it has none)
    alone: tuple[tuple[str, float | str], ...]
    #: generator classes open at the tier (A3), in generator_fuels.csv order
    generators_open: tuple[str, ...] = ()
    #: per site, the bill items it cannot reach by itself (its own caps, the
    #: held recipes): why an alone scale is 0.0 when material is the reason
    alone_blocked: tuple[tuple[str, tuple[str, ...]], ...] = ()
    #: A11: "grid" (the row imposed, A3) or "report_need"
    power_mode: str = "grid"
    #: A11: the need and the generators it takes; None in grid mode
    power_need: PowerNeed | None = None


def compose_bill(repo: pathlib.Path, data: ReferenceData, phases: tuple[int, ...],
                 tiers: tuple[int, ...]) -> dict:
    """Project Assembly phases (scenario-scaled) + milestone costs of `tiers`,
    as district_run.py composes them (A31)."""
    pa = stock.load_project_assembly(repo, data)
    known = {r.phase for r in pa}
    stray = [ph for ph in phases if ph not in known]
    if stray:
        raise PortfolioRunError(f"no Project Assembly phase {stray}")
    costs = unlocks.schematic_costs(repo)
    sources = [
        (f"project assembly phase {ph}", tuple(
            (r.item_id, data.scenario.apply_project_assembly_quantity(r.quantity_1x))
            for r in pa if r.phase == ph
        ))
        for ph in phases
    ] + [
        (sid, costs[sid]) for sid in unlocks.schematics_in_tiers(repo, tiers) if sid in costs
    ]
    return bill_units(tuple(sources))


def pooled(caps_by_site: tuple[tuple[ResourceCap, ...], ...]) -> tuple[ResourceCap, ...]:
    """Each raw's caps summed over the sites, in the first site's order. For
    REACH only: a pumped raw (cap None, A4) is available in any amount, so
    its pooled cap is infinite; nothing sizes from this."""
    total: dict[str, float] = {}
    for caps in caps_by_site:
        for c in caps:
            rate = float("inf") if c.rate_per_min is None else c.rate_per_min
            total[c.item_id] = total.get(c.item_id, 0.0) + rate
    return tuple(ResourceCap(c.item_id, total[c.item_id]) for c in caps_by_site[0])


def run(
    specs: tuple[site_card.SiteSpec, ...], *, tier: int, scenario: Scenario, goal: str,
    bill_phases: tuple[int, ...], bill_tiers: tuple[int, ...],
    declared_recipe_names: tuple[str, ...] = (), world_config_id: str = "default_502094",
    power_statistic: PowerStatistic = PowerStatistic.MEAN, grid_mw: float = 0.0,
    spare_mw: float = 0.0, water_sites: tuple[str, ...] = (), repo: pathlib.Path = REPO,
    power_mode: str = "grid",
) -> PortfolioRun:
    """`grid_mw` is standing supply from outside these sites (an existing
    grid); 0.0 means none, which is the reading of A1 P1's "existing sites are
    not in the model". `spare_mw` is a margin held above the draw.
    `water_sites` are the labels of sites declared able to pump Water (A4);
    the world data does not say where water is, so nothing defaults it.
    `power_mode` (A11): "grid" imposes the shared row (A3); "report_need"
    leaves it out and reports the need (module docstring). The default is
    the behaviour every caller had before A11; an inputs document must
    state it."""
    if power_mode not in POWER_MODES:
        raise PortfolioRunError(f"no power mode {power_mode!r}; known: {list(POWER_MODES)}")
    need = power_mode == "report_need"
    if need and grid_mw != 0.0:
        raise PortfolioRunError("report_need reports the whole need: a standing grid beside it "
                                "is not modelled (A11); declare grid_mw 0")
    if need and water_sites:
        raise PortfolioRunError(f"report_need with water pumped at {list(water_sites)}: only the grid "
                                "row bounds a pumped raw (A4), so without it the plan is unbounded (A11)")
    if goal not in site_card.GOALS:
        raise PortfolioRunError(f"no goal {goal!r}; known: {list(site_card.GOALS)}")
    if not specs:
        raise PortfolioRunError("a portfolio needs at least one site")
    labels = [s.label for s in specs]
    stray = [w for w in water_sites if w not in labels]
    if stray:
        raise PortfolioRunError(f"water declared at sites that are not declared: {stray}")
    twice = [w for n, w in enumerate(water_sites) if w in water_sites[:n]]
    if twice:
        raise PortfolioRunError(f"water declared twice at {twice}")
    free = [s.label for s in specs if any(item == WATER for item, _ in s.supply)]
    if free:
        raise PortfolioRunError(
            f"declared Water supply at {free}: Water is never free (A4); declare the site "
            "able to pump it (--water LABEL) and the solve charges Water Extractor power"
        )
    data = load(repo, scenario)
    _, rates = load_logistics(repo)
    sockets = site_card.load_sockets(repo, world_config_id)
    claimed: dict[str, str] = {}
    for spec in specs:
        for sid in spec.socket_ids:
            if sid in claimed:
                raise PortfolioRunError(
                    f"socket {sid} is in both {claimed[sid]!r} and {spec.label!r}: "
                    "a socket is owned once in a portfolio (spec F1, F4)"
                )
            claimed[sid] = spec.label
    tables = load_power_tables(repo)
    records = []
    for spec in specs:
        _, _, _, definition, caps = site_card.site_caps(spec, data, rates, sockets)
        pumps = spec.label in water_sites
        segments = site_extraction(definition, rates, tables.extractors, scenario=data.scenario,
                                   supply=spec.supply, water=pumps)
        if pumps:
            caps = pumped_caps(caps)
        records.append(SiteRecord(spec, caps, nameplate_mw(segments), segments, pumps))

    held = at_tier(repo, tier, declared=recipe_ids_by_name(data, declared_recipe_names))
    bill = compose_bill(repo, data, bill_phases, bill_tiers)
    together = pooled(tuple(r.caps for r in records))
    reach = discover(data, held.recipe_ids, together, tuple(bill))
    blocked_ids = tuple(x.item_id for x in reach if not x.makeable)
    not_held = tuple(r for r in data.recipes if r in held.withheld_alternates)
    hints = site_card.unlock_hints(data, held.recipe_ids, not_held, together, blocked_ids)
    pool = available_at(repo, tier)
    blocked = tuple(
        BlockedBillItem(
            x.item_id, bill[x.item_id], x.missing_raws,
            tuple((r, site_card._source(r, pool)) for r in hints[x.item_id]),
        )
        for x in reach if not x.makeable
    )
    target = tuple((x.item_id, bill[x.item_id]) for x in reach if x.makeable)
    if not target:
        raise PortfolioRunError("no bill item can be made by these sites together")

    open_classes, generators = generators_at_tier(repo, tier)

    # A4: extraction is charged by the draw through each site's segments, so
    # the constant nameplate term is 0.0
    grid = PowerBalance(generators=() if need else generators, grid_mw=grid_mw, spare_mw=spare_mw,
                        report_need=need)

    backend = LpBackend(power_statistic=power_statistic)
    weights = site_card.GOALS[goal]
    response = backend.solve_portfolio(PortfolioRequest(
        sites=tuple(PortfolioSite(r.spec.label, r.caps, r.segments) for r in records),
        bill=target, allowed_recipes=held.allowed_recipes, weights=weights,
        power=grid,
    ), data)
    alone = tuple((r.spec.label, _alone(backend, r, target, held, weights, grid, data))
                  for r in records)
    alone_blocked = tuple(
        (r.spec.label, tuple(x.item_id for x in discover(data, held.recipe_ids, pooled((r.caps,)),
                                                          tuple(i for i, _ in target))
                             if not x.makeable))
        for r in records
    )
    power_need = power_need_of(response.power, generators, data, held, together) if need else None
    return PortfolioRun(
        tier=tier, declared_recipes=held.declared, scenario=data.scenario, goal=goal,
        bill_phases=bill_phases, bill_tiers=bill_tiers, bill=bill, blocked=blocked,
        sites=tuple(records), response=response, alone=alone, generators_open=open_classes,
        alone_blocked=alone_blocked, power_mode=power_mode, power_need=power_need,
    )


#: why a recipe is not held at the tier, from at_tier's own sets
NOT_HELD_RESEARCH = "MAM research"
NOT_HELD_ALTERNATE = "alternate, not declared"
NOT_HELD_TIER = "not unlocked by this tier"


def not_held_reason(recipe_id: str, held) -> str:
    """`held` is the run's unlocks.TierUnlocks: a recipe outside its set is
    research-gated, an alternate not declared, or a base recipe no schematic
    of this tier grants."""
    if recipe_id in held.withheld_research:
        return NOT_HELD_RESEARCH
    if recipe_id in held.withheld_alternates:
        return NOT_HELD_ALTERNATE
    return NOT_HELD_TIER


def fuel_source(fuel: str, data: ReferenceData, held, together: tuple[ResourceCap, ...]) -> FuelSource:
    """A11 fuel join: the recipes that output `fuel` (held or not, and why),
    and the sockets' pooled cap of it. Reported; nothing is picked."""
    kept = set(held.recipe_ids)
    made_by = tuple(
        (rid, rid in kept, None if rid in kept else not_held_reason(rid, held))
        for rid, r in data.recipes.items() if any(i == fuel for i, _ in r.outputs)
    )
    caps = {c.item_id: c.rate_per_min for c in together}
    return FuelSource(made_by, caps.get(fuel))


def power_need_of(pw, rows, data: ReferenceData, held, together: tuple[ResourceCap, ...]) -> PowerNeed:
    """The need (lanes + extraction + spare, the row's right-hand side the
    solve reported) and, per open (generator, fuel) row, what covering it
    takes. Whole units are the ceiling with a 1e-9 allowance, so a need of
    exactly 2 x 30 MW is 2 burners, not 3."""
    need = float(pw.need_mw)
    gens = []
    for g in rows:
        units = need / g.power_mw
        gens.append(GeneratorNeed(
            generator_class=g.generator_class, fuel_item_id=g.fuel_item_id, power_mw=g.power_mw,
            units=units, units_whole=math.ceil(units - 1.0e-9) if units > 1.0e-9 else 0,
            fuel_per_min=units * g.burn_rate_per_min,
            supplemental_per_min=tuple((i, units * r) for i, r in g.supplemental),
            source=fuel_source(g.fuel_item_id, data, held, together),
        ))
    return PowerNeed(need_mw=need, lane_mw=pw.lane_mw, extraction_mw=pw.extraction_mw,
                     spare_mw=pw.spare_mw, generators=tuple(gens))


# -- report -------------------------------------------------------------------

def _alone(backend, rec, target, held, weights, power, data) -> float | str:
    """One site on the bill by itself: its scale, or why it has none. With
    extraction charged by the draw (A4) an idle site draws nothing, so a site
    that can fuel no open generator has scale 0.0 rather than no plan;
    Infeasible remains possible (a declared spare with nothing to cover it)
    and is said so with the solver's reason."""
    try:
        return backend.solve_portfolio(PortfolioRequest(
            sites=(PortfolioSite(rec.spec.label, rec.caps, rec.segments),), bill=target,
            allowed_recipes=held.allowed_recipes, weights=weights, power=power,
        ), data).scale
    except Infeasible as exc:
        return f"infeasible: {exc}"


def _n(data: ReferenceData, item_id: str) -> str:
    item = data.items.get(item_id)
    return item.display_name if item else item_id


def _cap_margin(b, scale: float, data: ReferenceData) -> str:
    """A binding cap's dual as minutes to cover the bill (shadow_text.horizon).
    The report and the record both call this, so the two cannot word it
    differently."""
    return shadow_text.horizon(b.shadow_price, scale, 1.0, f"+1/min {_n(data, b.item_id)}",
                               b.shadow_price_high)


def _grid_margin(pw, scale: float) -> str | None:
    """The shared grid's dual in the same terms, per MW_STEP; None when the
    grid row is not binding (no dual to read)."""
    if not pw.binding:
        return None
    return shadow_text.horizon(pw.shadow_price, scale, shadow_text.MW_STEP,
                               f"+{shadow_text.MW_STEP:g} MW")


def report(pr: PortfolioRun, data: ReferenceData) -> str:
    r = pr.response
    out = [
        f"portfolio: {len(pr.sites)} sites; tier {pr.tier} + {len(pr.declared_recipes)} declared "
        f"recipes; recipe x{pr.scenario.recipe_input_multiplier:g}; goal {pr.goal!r} breaks ties",
        f"  bill: Project Assembly phases {list(pr.bill_phases)} + milestones of tiers "
        f"{list(pr.bill_tiers)}: {len(pr.bill)} items, delivered wherever made (A1 P7)",
        f"  status material_bound; not assessed: " + ", ".join(NOT_ASSESSED),
        f"  {VOLUME_ASSUMPTION}; transfers are free between these sites (A1 P3)",
        f"  power: {POWER_ASSUMPTION}",
        f"  {shadow_text.MARGIN_NOTE}",
        "",
        f"bill scale together {r.scale:.6f}/min"
        + (f" (horizon {r.horizon_min:.1f} min)" if r.horizon_min
           else " (the grid holds every machine at 0: no power source)"
           if r.power is not None and r.power.binding and r.power.shadow_price > 1e-12
           else " (some bill item cannot be made)"),
    ]
    blocked_alone = dict(pr.alone_blocked)
    for label, scale in pr.alone:
        line = f"  {label} alone: " + (scale if isinstance(scale, str) else f"{scale:.6f}/min")
        if blocked_alone.get(label):
            line += "; cannot make alone: " + ", ".join(_n(data, i) for i in blocked_alone[label])
        out.append(line)
    out += ["", "bill (bill order): units; made where, per minute"]
    made = {s.label: dict(s.delivered) for s in r.sites}
    for item, units in pr.bill.items():
        where = "; ".join(f"{s.label} {made[s.label][item]:.4f}" for s in r.sites if item in made[s.label])
        blocked = next((b for b in pr.blocked if b.item_id == item), None)
        if blocked is not None:
            hint = "".join(f"; or {data.recipes[rid].display_name} [{src}]" for rid, src in blocked.opened_by)
            where = "NOT MADE: needs " + (", ".join(_n(data, i) for i in blocked.missing_raws)
                                          or "no socket resource") + hint
        out.append(f"  {_n(data, item):28s} {units:8g}  {where}")
    for rec, plan in zip(pr.sites, r.sites):
        out += ["", f"site {plan.label}: {len(rec.spec.socket_ids)} sockets"]
        draw = {x.item_id: x.rate_per_min for x in plan.plan.raw_inputs}
        bound = {b.item_id: b for b in plan.binding}
        for c in rec.caps:
            if c.rate_per_min is None:
                out.append(f"  {_n(data, c.item_id):18s} {draw.get(c.item_id, 0.0):9.2f} / pumped")
            elif c.rate_per_min > 0.0:
                b = bound.get(c.item_id)
                out.append(f"  {_n(data, c.item_id):18s} {draw.get(c.item_id, 0.0):9.2f} / "
                           f"{c.rate_per_min:g}" + ("" if b is None else "  BINDING ("
                           + _cap_margin(b, r.scale, data) + ")"))
        sent = [t for t in r.transfers if t.source == plan.label]
        got = [t for t in r.transfers if t.destination == plan.label]
        out.append("  ships out: " + (", ".join(f"{_n(data, t.item_id)} {t.rate_per_min:.3f} -> "
                                                f"{t.destination}" for t in sent) or "nothing"))
        out.append("  receives:  " + (", ".join(f"{_n(data, t.item_id)} {t.rate_per_min:.3f} <- "
                                                f"{t.source}" for t in got) or "nothing"))
        gens = ", ".join(
            f"{u.count:.2f} x {u.generator_class.replace('Build_', '').replace('_C', '')} on "
            f"{_n(data, u.fuel_item_id)} ({u.mw:.0f} MW, {u.fuel_per_min:.1f}/min)"
            for u in plan.generators) or "none"
        out.append(f"  power: machines {plan.lane_mw:.1f} MW + extractors {plan.extraction_mw:.1f} MW "
                   f"drawn (nameplate {plan.extraction_nameplate_mw:.1f} MW); generators here: {gens}")
        for item, rate in plan.pumped:
            pump = next(e for e in rec.segments if e.item_id == item and e.cap_per_min is None)
            out.append(f"  pumped {_n(data, item)}: {rate:.1f}/min needed, {rate * pump.mw_per_unit:.1f} "
                       f"MW ({WATER_EXTRACTOR} by the draw; not counted, grouped or clocked)")
        if rec.pumps_water:
            # spec §10 D: water not verified makes the power alternative conditional
            out.append("  Water: DECLARED pumpable here, not verified by world data; "
                       "power that needs it is CONDITIONAL on that declaration")
        out.append("  recipes: " + ", ".join(
            f"{data.recipes[u.recipe_id].display_name} {u.machine_equivalents:.2f}"
            for u in plan.plan.recipes))
    out += ["", f"transfer volume {r.transfer_volume_per_min:.3f}/min ({VOLUME_ASSUMPTION})"]
    pw = r.power
    if pr.power_need is not None:
        out += [""] + power_need_lines(pr, data)
        return "\n".join(out)
    out += ["", "shared grid (A3): generators open at this tier: "
            + ", ".join(c.replace("Build_", "").replace("_C", "") for c in pr.generators_open),
            f"  machines {pw.lane_mw:.1f} + extractors {pw.extraction_mw:.1f} drawn"
            f" (nameplate {pw.extraction_nameplate_mw or 0.0:.1f}) + spare {pw.spare_mw:.1f}"
            f"  <=  generated {pw.generated_mw:.1f} + standing grid {pw.grid_mw:.1f};"
            f" margin {pw.margin_mw:.1f} MW"
            + ("" if not pw.binding else "  LIMITING" if pw.shadow_price > 1e-12
               else "  tight, not limiting (shadow 0: generators built to the draw)")]
    if pw.binding and pw.shadow_price > 1e-12:
        out.append("  " + _grid_margin(pw, r.scale))
    return "\n".join(out)


def _source_text(src: FuelSource, data: ReferenceData) -> str:
    parts = []
    held = [data.recipes[r].display_name for r, h, _ in src.made_by if h]
    later = [f"{data.recipes[r].display_name} [{why}]" for r, h, why in src.made_by if not h]
    if held:
        parts.append("made here by " + ", ".join(held))
    if later:
        parts.append("not held: " + ", ".join(later))
    if not src.made_by:
        parts.append("made by no recipe (gathered or extracted)")
    if src.site_supply_per_min is not None:
        parts.append(f"sockets here {src.site_supply_per_min:g}/min")
    return "; ".join(parts)


def power_need_lines(pr: PortfolioRun, data: ReferenceData) -> list[str]:
    """The A11 report: the need, then each open (generator, fuel) row."""
    pn = pr.power_need
    out = [f"power need (A11, report_need: the grid row is not imposed; the plan is bounded by "
           f"its caps): machines {pn.lane_mw:.2f} + extractors {pn.extraction_mw:.2f} drawn"
           f" + spare {pn.spare_mw:.2f} = {pn.need_mw:.2f} MW"]
    if not pn.generators:
        out.append("  no generator is open at this tier")
    for g in pn.generators:
        sup = "".join(f", + {_n(data, i)} {v:.1f}/min" for i, v in g.supplemental_per_min)
        out.append(f"  {g.generator_class.replace('Build_', '').replace('_C', '')} on "
                   f"{_n(data, g.fuel_item_id)}: {g.units:.2f} units ({g.units_whole} to build, "
                   f"{g.power_mw:g} MW each), feed {g.fuel_per_min:.1f}/min{sup}"
                   f"  [{_source_text(g.source, data)}]")
    out.append("  feed rates are at the need exactly; a fuel made in a constructor draws power "
               "of its own, which is not in the need (A11)")
    return out


# -- record ---------------------------------------------------------------------

def site_ledger(pr: PortfolioRun, label: str) -> tuple[dict, ...]:
    """One row per item the site's plan, its generators or the transfers
    touch, in first-seen order: plan items, generator fuels, transfers,
    bill deliveries. The identity in the module docstring gives `left`."""
    plan = next(s for s in pr.response.sites if s.label == label)
    rows: dict[str, dict] = {}

    def row(item: str) -> dict:
        if item not in rows:
            rows[item] = {"item_id": item, "produced": 0.0, "received": 0.0, "consumed": 0.0,
                          "burned": 0.0, "shipped": 0.0, "to_bill": 0.0}
        return rows[item]

    for f in plan.plan.items:
        row(f.item_id)["produced"] += f.produced_per_min
        row(f.item_id)["consumed"] += f.consumed_per_min
    for u in plan.generators:
        row(u.fuel_item_id)["burned"] += u.fuel_per_min
        for item, rate in u.supplemental_per_min:
            row(item)["burned"] += rate
    for t in pr.response.transfers:
        if t.source == label:
            row(t.item_id)["shipped"] += t.rate_per_min
        if t.destination == label:
            row(t.item_id)["received"] += t.rate_per_min
    for item, rate in plan.delivered:
        row(item)["to_bill"] += rate
    for r in rows.values():
        r["left"] = (r["produced"] + r["received"] - r["consumed"] - r["burned"]
                     - r["shipped"] - r["to_bill"])
    return tuple(rows.values())


def item_facts(data: ReferenceData, items) -> dict:
    """Per item: form (solid / liquid / gas) and stack size, from items.csv
    through gamedata. `stack_size` is the units per container slot and is
    given for solids only: a fluid's SS_FLUID 50000 is no slot of any
    storage container (fluids go to tanks, or are packaged first), so
    carrying it would invite a fill time that means nothing. Facts, not a
    storage choice: what storage is declared stays the client's input."""
    return {
        i: {"form": data.items[i].form,
            "stack_size": data.items[i].stack_size if data.items[i].form == "solid" else None}
        for i in items if i in data.items
    }


def provenance(repo: pathlib.Path = REPO) -> dict:
    """Where and when a record was made (AGENTS.md: every figure says where
    and when it was measured). Separate from the record's body so two runs
    of the same inputs can be compared with this key dropped. The commit is
    read with git where git can run; in Pyodide (no subprocess) or outside a
    checkout it is None with the reason, never guessed."""
    import datetime
    import platform

    import numpy
    import scipy

    out = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "implementation": sys.platform,
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "commit": None,
        "worktree_dirty": None,
        "commit_unavailable": None,
    }
    try:
        import subprocess

        def git(*args: str) -> str:
            return subprocess.run(("git", "-C", str(repo)) + args, check=True,
                                  capture_output=True, text=True).stdout.strip()

        out["commit"] = git("rev-parse", "HEAD")
        # tracked files only: an untracked scratch file does not change what ran
        out["worktree_dirty"] = bool(git("status", "--porcelain", "--untracked-files=no"))
    except Exception as exc:  # no git, no subprocess (Pyodide), not a checkout
        out["commit_unavailable"] = f"{type(exc).__name__}: {exc}".strip()[:200]
    return out


def record(pr: PortfolioRun, data: ReferenceData, prov: dict | None = None,
           inputs: dict | None = None) -> dict:
    """The run as one JSON-ready document (module docstring). `prov` is
    provenance() or None; None is written as null (not stated), which keeps
    record() deterministic for tests and for native-vs-Pyodide comparison.
    `inputs` is the portfolio-inputs document that made the run, echoed
    as given (null when the caller had none), so a record can be re-run."""
    r = pr.response
    items: dict[str, None] = dict.fromkeys(pr.bill)
    recipes: dict[str, None] = {}
    producers: dict[str, None] = {}
    sites = []
    for rec, plan in zip(pr.sites, r.sites):
        draw = {x.item_id: x.rate_per_min for x in plan.plan.raw_inputs}
        ledger = site_ledger(pr, plan.label)
        items.update(dict.fromkeys(c.item_id for c in rec.caps))
        items.update(dict.fromkeys(x["item_id"] for x in ledger))
        recipes.update(dict.fromkeys(u.recipe_id for u in plan.plan.recipes))
        producers.update(dict.fromkeys(u.producer_class for u in plan.plan.recipes))
        producers.update(dict.fromkeys(u.generator_class for u in plan.generators))
        sites.append({
            "label": plan.label,
            "socket_ids": list(rec.spec.socket_ids),
            "extractors": [{"source_kind": kind, "item_id": item, "extractor_class": cls}
                           for (kind, item), cls in rec.spec.extractors],
            "extraction_clock": rec.spec.extraction_clock,
            "declared_supply": [{"item_id": i, "rate_per_min": v} for i, v in rec.spec.supply],
            "pumps_water": rec.pumps_water,
            # rate_per_min None: pumped (A4), uncapped; 0.0 caps (a closed site's
            # raws it has no socket for) are kept, so the client sees the full set
            "caps": [{"item_id": c.item_id, "cap_per_min": c.rate_per_min,
                      "drawn_per_min": draw.get(c.item_id, 0.0)} for c in rec.caps],
            # margin_text: the report's wording of the dual (_cap_margin), so a
            # client never re-derives it (shadow prices in plain language, A5)
            "binding": [{**dataclasses.asdict(b), "margin_text": _cap_margin(b, r.scale, data)}
                        for b in plan.binding],
            "recipes": [dataclasses.asdict(u) for u in plan.plan.recipes],
            "generators": [dataclasses.asdict(u) for u in plan.generators],
            "lane_mw": plan.lane_mw,
            "extraction_mw": plan.extraction_mw,
            "extraction_nameplate_mw": plan.extraction_nameplate_mw,
            "pumped": [{"item_id": i, "rate_per_min": v} for i, v in plan.pumped],
            "ledger": list(ledger),
        })
    for b in pr.blocked:
        items.update(dict.fromkeys(b.missing_raws))
    if pr.power_need is not None:
        for g in pr.power_need.generators:
            items[g.fuel_item_id] = None
            items.update(dict.fromkeys(i for i, _ in g.supplemental_per_min))
            recipes.update(dict.fromkeys(rid for rid, _, _ in g.source.made_by))
            producers[g.generator_class] = None
    alone_blocked = dict(pr.alone_blocked)
    return {
        "schema": RECORD_SCHEMA,
        "game_build_id": data.game_build_id,
        "scenario": dataclasses.asdict(pr.scenario),
        "tier": pr.tier,
        "declared_recipes": list(pr.declared_recipes),
        "goal": {"name": pr.goal, **dataclasses.asdict(r.goal)},
        "generators_open": list(pr.generators_open),
        "status": site_card.CARD_STATUS,
        "not_assessed": list(NOT_ASSESSED),
        "assumptions": {"volume": VOLUME_ASSUMPTION, "power": POWER_ASSUMPTION,
                        "margin": shadow_text.MARGIN_NOTE},
        "provenance": prov,
        "inputs": inputs,
        "bill": {
            "phases": list(pr.bill_phases), "tiers": list(pr.bill_tiers),
            "units": dict(pr.bill), "scale": r.scale, "horizon_min": r.horizon_min,
            "blocked": [{"item_id": b.item_id, "units": b.units, "missing_raws": list(b.missing_raws),
                         "opened_by": [{"recipe_id": rid, "source": src} for rid, src in b.opened_by]}
                        for b in pr.blocked],
        },
        # a str is the reason a site has no scale alone (Infeasible), else its scale
        "alone": [{"label": label,
                   "scale": None if isinstance(v, str) else v,
                   "reason": v if isinstance(v, str) else None,
                   "cannot_make": list(alone_blocked.get(label, ()))}
                  for label, v in pr.alone],
        "sites": sites,
        "transfers": [dataclasses.asdict(t) for t in r.transfers],
        "transfer_volume_per_min": r.transfer_volume_per_min,
        "power": None if r.power is None else {**dataclasses.asdict(r.power),
                                               "margin_text": _grid_margin(r.power, r.scale)},
        # A11, additive: the mode, and in report_need the need and its generators
        "power_mode": pr.power_mode,
        "power_need": None if pr.power_need is None else {
            **dataclasses.asdict(pr.power_need),
            # source_text: the report's wording (_source_text), so a client never re-derives it
            "generators": [{**dataclasses.asdict(g), "source_text": _source_text(g.source, data)}
                           for g in pr.power_need.generators]},
        "items": item_facts(data, items),
        "names": {
            "items": {i: data.items[i].display_name for i in items if i in data.items},
            "recipes": {i: data.recipes[i].display_name for i in recipes if i in data.recipes},
            "producers": {p: p.replace("Build_", "").replace("_C", "") for p in producers},
        },
    }


def export(pr: PortfolioRun, data: ReferenceData, path: pathlib.Path,
           inputs: dict | None = None) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(record(pr, data, provenance(), inputs), f, indent=1)
        f.write("\n")


# -- inputs -----------------------------------------------------------------------

#: the inputs document's schema tag (handoff 2026-10-23 14:48 action 2: the
#: picker hands a run to portfolio_run as sites by socket id)
INPUTS_SCHEMA = "portfolio-inputs/2"
#: A11 added power_mode; a /1 document is refused by name (no default read in)
PAST_INPUTS = {"portfolio-inputs/1": "it has no power_mode (A11); add \"power_mode\": \"grid\" to run it "
                                     "as before, or \"report_need\", and set schema " + "portfolio-inputs/2"}
#: every key is required: an inputs document declares the whole run, so
#: nothing here falls back to a default the reader did not see
INPUT_KEYS = ("schema", "world_config_id", "tier", "declared_recipes", "scenario", "goal", "bill",
              "extraction_clock", "extractors", "power_mode", "grid_mw", "spare_mw", "sites")
SITE_KEYS = ("label", "socket_ids", "pumps_water", "supply")
EXTRACTOR_KEYS = ("source_kind", "item_id", "extractor_class")


def _keys(where: str, obj, want: tuple[str, ...]) -> None:
    if not isinstance(obj, dict):
        raise PortfolioRunError(f"{where}: expected an object, got {type(obj).__name__}")
    missing = [k for k in want if k not in obj]
    extra = [k for k in obj if k not in want]
    if missing or extra:
        raise PortfolioRunError(f"{where}: missing {missing}, not known {extra}")


def run_inputs(doc: dict, repo: pathlib.Path = REPO) -> tuple[PortfolioRun, Scenario]:
    """Run a portfolio-inputs/2 document. Its shape is checked here, every
    key required, unknown keys refused; its content is checked where it
    always is (run(), site_card: unknown or repeated sockets, Water, goal)."""
    if isinstance(doc, dict) and doc.get("schema") in PAST_INPUTS:
        raise PortfolioRunError(f"inputs schema {doc['schema']!r}: {PAST_INPUTS[doc['schema']]}")
    _keys("inputs", doc, INPUT_KEYS)
    if doc["schema"] != INPUTS_SCHEMA:
        raise PortfolioRunError(f"inputs schema {doc['schema']!r}, this reads {INPUTS_SCHEMA}")
    _keys("inputs.bill", doc["bill"], ("phases", "tiers"))
    scenario_keys = tuple(f.name for f in dataclasses.fields(Scenario))
    _keys("inputs.scenario", doc["scenario"], scenario_keys)
    if not isinstance(doc["extractors"], list) or not isinstance(doc["sites"], list):
        raise PortfolioRunError("inputs: extractors and sites are lists")
    for n, e in enumerate(doc["extractors"]):
        _keys(f"inputs.extractors[{n}]", e, EXTRACTOR_KEYS)
    for n, s in enumerate(doc["sites"]):
        _keys(f"inputs.sites[{n}]", s, SITE_KEYS)
    if not doc["bill"]["phases"] and not doc["bill"]["tiers"]:
        raise PortfolioRunError("inputs.bill: declare phases and/or tiers")
    extractors = tuple(((e["source_kind"], e["item_id"]), e["extractor_class"]) for e in doc["extractors"])
    specs = tuple(
        site_card.SiteSpec(
            label=s["label"], socket_ids=tuple(s["socket_ids"]), extractors=extractors,
            extraction_clock=doc["extraction_clock"],
            supply=tuple((x["item_id"], x["rate_per_min"]) for x in s["supply"]),
        )
        for s in doc["sites"]
    )
    scenario = Scenario(**doc["scenario"])
    pr = run(specs, tier=doc["tier"], scenario=scenario, goal=doc["goal"],
             bill_phases=tuple(doc["bill"]["phases"]), bill_tiers=tuple(doc["bill"]["tiers"]),
             declared_recipe_names=tuple(doc["declared_recipes"]),
             world_config_id=doc["world_config_id"], grid_mw=doc["grid_mw"],
             spare_mw=doc["spare_mw"], power_mode=doc["power_mode"],
             water_sites=tuple(s["label"] for s in doc["sites"] if s["pumps_water"]), repo=repo)
    return pr, scenario


def inputs_doc(specs: tuple[site_card.SiteSpec, ...], *, world_config_id: str, tier: int,
               declared_recipes: tuple[str, ...], scenario: Scenario, goal: str,
               bill_phases: tuple[int, ...], bill_tiers: tuple[int, ...], grid_mw: float,
               spare_mw: float, water_sites: tuple[str, ...], power_mode: str = "grid") -> dict:
    """The portfolio-inputs/2 document for a run declared by CLI flags, so
    both entry points go through run_inputs and every record echoes the
    inputs that made it. A circle site (--site) is written as the socket ids
    it caught."""
    first = specs[0]
    return {
        "schema": INPUTS_SCHEMA, "world_config_id": world_config_id, "tier": tier,
        "declared_recipes": list(declared_recipes), "scenario": dataclasses.asdict(scenario),
        "goal": goal, "bill": {"phases": list(bill_phases), "tiers": list(bill_tiers)},
        "extraction_clock": first.extraction_clock,
        "extractors": [{"source_kind": k, "item_id": i, "extractor_class": c}
                       for (k, i), c in first.extractors],
        "power_mode": power_mode, "grid_mw": grid_mw, "spare_mw": spare_mw,
        "sites": [{"label": s.label, "socket_ids": list(s.socket_ids),
                   "pumps_water": s.label in water_sites,
                   "supply": [{"item_id": i, "rate_per_min": v} for i, v in s.supply]}
                  for s in specs],
    }


def _site_arg(text: str) -> tuple[str, float, float, float]:
    label, sep, rest = text.partition(":")
    parts = rest.split(",")
    if not sep or len(parts) != 3:
        raise argparse.ArgumentTypeError(f"expected LABEL:EAST,NORTH,RADIUS, got {text!r}")
    return label, float(parts[0]), float(parts[1]), float(parts[2])


def _supply_arg(text: str) -> tuple[str, str, float]:
    site, sep, rest = text.partition(":")
    item, sep2, rate = rest.partition("=")
    if not sep or not sep2:
        raise argparse.ArgumentTypeError(f"expected LABEL:ITEM=RATE, got {text!r}")
    return site, item, float(rate)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--inputs", type=pathlib.Path, default=None,
                    help=f"run a {INPUTS_SCHEMA} JSON document instead of the flags below "
                         "(the picker writes one); mixing it with them is refused")
    ap.add_argument("--site", action="append", type=_site_arg,
                    help="LABEL:EAST_M,NORTH_M,RADIUS_M (repeat per site)")
    ap.add_argument("--world")
    ap.add_argument("--tier", type=int)
    ap.add_argument("--recipe", action="append", help="declared recipe display name")
    ap.add_argument("--extractor", action="append", type=site_card._extractor_arg)
    ap.add_argument("--clock", type=float)
    ap.add_argument("--recipe-multiplier", type=float)
    ap.add_argument("--bill-phase", action="append", type=int)
    ap.add_argument("--bill-tier", action="append", type=int)
    ap.add_argument("--goal", choices=tuple(site_card.GOALS), help="default balanced")
    ap.add_argument("--supply", action="append", type=_supply_arg,
                    help="LABEL:ITEM=RATE declared supply at a site no socket carries; "
                         "not Water (use --water)")
    ap.add_argument("--water", action="append",
                    help="LABEL of a site able to pump Water, charged as Water Extractors (A4)")
    ap.add_argument("--grid-mw", type=float,
                    help="standing supply from outside these sites (default 0: none)")
    ap.add_argument("--spare-mw", type=float, help="default 0")
    ap.add_argument("--power", choices=POWER_MODES,
                    help="grid: the shared row imposed (A3); report_need: report the need and the "
                         "generators it takes (A11). Default grid")
    ap.add_argument("--export", type=pathlib.Path, default=None,
                    help="write the run as one JSON record here (schema portfolio-plan/1)")
    args = ap.parse_args(argv)
    run_flags = ("site", "world", "tier", "recipe", "extractor", "clock", "recipe_multiplier",
                 "bill_phase", "bill_tier", "goal", "supply", "water", "grid_mw", "spare_mw", "power")
    if args.inputs is not None:
        given = ["--" + f.replace("_", "-") for f in run_flags if getattr(args, f) is not None]
        if given:
            ap.error(f"--inputs declares the whole run; also given: {given}")
        try:
            with open(args.inputs, encoding="utf-8") as f:
                doc = json.load(f)
        except FileNotFoundError:
            ap.error(f"--inputs: no file at {args.inputs} (a shell variable left unexpanded?)")
        except json.JSONDecodeError as exc:
            ap.error(f"--inputs: {args.inputs} is not JSON ({exc})")
    else:
        missing = ["--" + f.replace("_", "-") for f in ("site", "tier", "extractor", "clock",
                                                         "recipe_multiplier")
                   if getattr(args, f) is None]
        if missing:
            ap.error(f"required without --inputs: {missing}")
        if not args.bill_phase and not args.bill_tier:
            ap.error("declare the bill: --bill-phase and/or --bill-tier")
        world = args.world or "default_502094"
        supply, water = args.supply or [], args.water or []
        sockets = site_card.load_sockets(REPO, world)
        specs = tuple(
            site_card.SiteSpec(
                label=label,
                socket_ids=site_card.sockets_within(sockets, east, north, radius),
                extractors=tuple(args.extractor), extraction_clock=args.clock,
                supply=tuple((item, rate) for site, item, rate in supply if site == label),
            )
            for label, east, north, radius in args.site
        )
        labels = [label for label, _, _, _ in args.site]
        stray = [site for site, _, _ in supply if site not in labels]
        if stray:
            ap.error(f"--supply names sites that are not declared: {stray}")
        doc = inputs_doc(
            specs, world_config_id=world, tier=args.tier, declared_recipes=tuple(args.recipe or ()),
            scenario=Scenario(recipe_input_multiplier=args.recipe_multiplier),
            goal=args.goal or "balanced", bill_phases=tuple(args.bill_phase or ()),
            bill_tiers=tuple(args.bill_tier or ()), grid_mw=0.0 if args.grid_mw is None else args.grid_mw,
            spare_mw=0.0 if args.spare_mw is None else args.spare_mw, water_sites=tuple(water),
            power_mode=args.power or "grid",
        )
    pr, scenario = run_inputs(doc)
    data = load(REPO, scenario)
    print(report(pr, data))
    if args.export:
        export(pr, data, args.export, inputs=doc)
        print(f"\nexported: {args.export}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
