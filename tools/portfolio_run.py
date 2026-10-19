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
"""
from __future__ import annotations

import argparse
import dataclasses
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
) -> PortfolioRun:
    """`grid_mw` is standing supply from outside these sites (an existing
    grid); 0.0 means none, which is the reading of A1 P1's "existing sites are
    not in the model". `spare_mw` is a margin held above the draw.
    `water_sites` are the labels of sites declared able to pump Water (A4);
    the world data does not say where water is, so nothing defaults it."""
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
    grid = PowerBalance(generators=generators, grid_mw=grid_mw, spare_mw=spare_mw)

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
    return PortfolioRun(
        tier=tier, declared_recipes=held.declared, scenario=data.scenario, goal=goal,
        bill_phases=bill_phases, bill_tiers=bill_tiers, bill=bill, blocked=blocked,
        sites=tuple(records), response=response, alone=alone, generators_open=open_classes,
        alone_blocked=alone_blocked,
    )


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
                           + shadow_text.horizon(b.shadow_price, r.scale, 1.0,
                                                 f"+1/min {_n(data, c.item_id)}", b.shadow_price_high)
                           + ")"))
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
    out += ["", "shared grid (A3): generators open at this tier: "
            + ", ".join(c.replace("Build_", "").replace("_C", "") for c in pr.generators_open),
            f"  machines {pw.lane_mw:.1f} + extractors {pw.extraction_mw:.1f} drawn"
            f" (nameplate {pw.extraction_nameplate_mw or 0.0:.1f}) + spare {pw.spare_mw:.1f}"
            f"  <=  generated {pw.generated_mw:.1f} + standing grid {pw.grid_mw:.1f};"
            f" margin {pw.margin_mw:.1f} MW"
            + ("" if not pw.binding else "  LIMITING" if pw.shadow_price > 1e-12
               else "  tight, not limiting (shadow 0: generators built to the draw)")]
    if pw.binding and pw.shadow_price > 1e-12:
        out.append("  " + shadow_text.horizon(pw.shadow_price, r.scale, shadow_text.MW_STEP,
                                              f"+{shadow_text.MW_STEP:g} MW"))
    return "\n".join(out)


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
    ap.add_argument("--site", action="append", type=_site_arg, required=True,
                    help="LABEL:EAST_M,NORTH_M,RADIUS_M (repeat per site)")
    ap.add_argument("--world", default="default_502094")
    ap.add_argument("--tier", type=int, required=True)
    ap.add_argument("--recipe", action="append", default=[], help="declared recipe display name")
    ap.add_argument("--extractor", action="append", type=site_card._extractor_arg, required=True)
    ap.add_argument("--clock", type=float, required=True)
    ap.add_argument("--recipe-multiplier", type=float, required=True)
    ap.add_argument("--bill-phase", action="append", type=int, default=[])
    ap.add_argument("--bill-tier", action="append", type=int, default=[])
    ap.add_argument("--goal", default="balanced", choices=tuple(site_card.GOALS))
    ap.add_argument("--supply", action="append", type=_supply_arg, default=[],
                    help="LABEL:ITEM=RATE declared supply at a site no socket carries; "
                         "not Water (use --water)")
    ap.add_argument("--water", action="append", default=[],
                    help="LABEL of a site able to pump Water, charged as Water Extractors (A4)")
    ap.add_argument("--grid-mw", type=float, default=0.0,
                    help="standing supply from outside these sites (default 0: none)")
    ap.add_argument("--spare-mw", type=float, default=0.0)
    args = ap.parse_args(argv)
    if not args.bill_phase and not args.bill_tier:
        ap.error("declare the bill: --bill-phase and/or --bill-tier")
    sockets = site_card.load_sockets(REPO, args.world)
    specs = tuple(
        site_card.SiteSpec(
            label=label,
            socket_ids=site_card.sockets_within(sockets, east, north, radius),
            extractors=tuple(args.extractor), extraction_clock=args.clock,
            supply=tuple((item, rate) for site, item, rate in args.supply if site == label),
        )
        for label, east, north, radius in args.site
    )
    labels = [label for label, _, _, _ in args.site]
    stray = [site for site, _, _ in args.supply if site not in labels]
    if stray:
        ap.error(f"--supply names sites that are not declared: {stray}")
    scenario = Scenario(recipe_input_multiplier=args.recipe_multiplier)
    pr = run(specs, tier=args.tier, scenario=scenario, goal=args.goal,
             bill_phases=tuple(args.bill_phase), bill_tiers=tuple(args.bill_tier),
             declared_recipe_names=tuple(args.recipe), world_config_id=args.world,
             grid_mw=args.grid_mw, spare_mw=args.spare_mw, water_sites=tuple(args.water))
    print(report(pr, load(REPO, scenario)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
