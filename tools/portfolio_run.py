#!/usr/bin/env python3
"""A bounded portfolio: several declared sites share one bill. What each makes,
what moves between them, and what each would manage alone.

Site-planner reframe, Amendment 1 (adopted by Greg, 2026-10-19; holds until
something proves it wrong): demand is the Project Assembly + milestone bill
(P1); power stays outside the solve and is reported per site (P2); transfers
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
    power     per site, machine-time MW at the scenario multiplier (mean) +
              extractors at nameplate: REPORTED, not a constraint (P2)

**It cannot choose, and that is the guardrail.** Sites, tier, declared
recipes, bill phases and tiers, scenario and goal are inputs. No min, max or
sort here (asserted by tests/test_portfolio_run.py): sites in declaration
order, bill items in bill order, transfers in the solver's order.

    uv run python tools/portfolio_run.py --tier 6 --bill-phase 3 --bill-tier 5 \\
        --bill-tier 6 --recipe-multiplier 1.0 --clock 1.0 \\
        --site oil:1697.17,-2033.86,500 --site copper:3555.0,1498.0,500 \\
        --extractor resource_node=Build_MinerMk1_C \\
        --extractor resource_node:Desc_LiquidOil_C=Build_OilPump_C
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
    PortfolioRequest, PortfolioResponse, PortfolioSite, ResourceCap, Scenario, load,
)
from production_adapter.gamedata import ReferenceData, load_logistics  # noqa: E402
from production_adapter.lp_backend import LpBackend, PowerStatistic  # noqa: E402
from progression import (  # noqa: E402
    at_tier, available_at, bill_units, discover, extraction_nameplate_mw, recipe_ids_by_name,
    unlocks,
)
from progression import stock  # noqa: E402
from progression.power import load_power_tables  # noqa: E402

import site_card  # noqa: E402

#: A1 P5, stated in every report
VOLUME_ASSUMPTION = "transfer volume counts one item as one m3 (A1 P5)"
NOT_ASSESSED = ("power (reported, not constrained: A1 P2)", "routes", "belts", "pipes",
                "node reachability", "buildable area")


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
    caps: tuple[ResourceCap, ...]
    extraction_mw: float


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
    #: each site alone on the same bill items: (label, scale)
    alone: tuple[tuple[str, float], ...]


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
    """Each raw's caps summed over the sites, in the first site's order."""
    total: dict[str, float] = {}
    for caps in caps_by_site:
        for c in caps:
            total[c.item_id] = total.get(c.item_id, 0.0) + c.rate_per_min
    return tuple(ResourceCap(c.item_id, total[c.item_id]) for c in caps_by_site[0])


def run(
    specs: tuple[site_card.SiteSpec, ...], *, tier: int, scenario: Scenario, goal: str,
    bill_phases: tuple[int, ...], bill_tiers: tuple[int, ...],
    declared_recipe_names: tuple[str, ...] = (), world_config_id: str = "default_502094",
    power_statistic: PowerStatistic = PowerStatistic.MEAN, repo: pathlib.Path = REPO,
) -> PortfolioRun:
    if goal not in site_card.GOALS:
        raise PortfolioRunError(f"no goal {goal!r}; known: {list(site_card.GOALS)}")
    if not specs:
        raise PortfolioRunError("a portfolio needs at least one site")
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
        records.append(SiteRecord(spec, caps, extraction_nameplate_mw(definition, tables.extractors)))

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

    backend = LpBackend(power_statistic=power_statistic)
    weights = site_card.GOALS[goal]
    response = backend.solve_portfolio(PortfolioRequest(
        sites=tuple(PortfolioSite(r.spec.label, r.caps) for r in records),
        bill=target, allowed_recipes=held.allowed_recipes, weights=weights,
    ), data)
    alone = tuple(
        (r.spec.label, backend.solve_portfolio(PortfolioRequest(
            sites=(PortfolioSite(r.spec.label, r.caps),), bill=target,
            allowed_recipes=held.allowed_recipes, weights=weights,
        ), data).scale)
        for r in records
    )
    return PortfolioRun(
        tier=tier, declared_recipes=held.declared, scenario=data.scenario, goal=goal,
        bill_phases=bill_phases, bill_tiers=bill_tiers, bill=bill, blocked=blocked,
        sites=tuple(records), response=response, alone=alone,
    )


# -- report -------------------------------------------------------------------

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
        "",
        f"bill scale together {r.scale:.6f}/min"
        + (f" (horizon {r.horizon_min:.1f} min)" if r.horizon_min else " (some bill item cannot be made)"),
    ]
    for label, scale in pr.alone:
        out.append(f"  {label} alone: {scale:.6f}/min")
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
        bound = {b.item_id for b in plan.binding}
        for c in rec.caps:
            if c.rate_per_min > 0.0:
                out.append(f"  {_n(data, c.item_id):18s} {draw.get(c.item_id, 0.0):9.2f} / "
                           f"{c.rate_per_min:g}" + ("  BINDING" if c.item_id in bound else ""))
        sent = [t for t in r.transfers if t.source == plan.label]
        got = [t for t in r.transfers if t.destination == plan.label]
        out.append("  ships out: " + (", ".join(f"{_n(data, t.item_id)} {t.rate_per_min:.3f} -> "
                                                f"{t.destination}" for t in sent) or "nothing"))
        out.append("  receives:  " + (", ".join(f"{_n(data, t.item_id)} {t.rate_per_min:.3f} <- "
                                                f"{t.source}" for t in got) or "nothing"))
        out.append(f"  power (reported, not constrained): machines {plan.plan.power.scenario_mw:.1f} MW "
                   f"machine-time + extractors {rec.extraction_mw:.1f} MW nameplate")
        out.append("  recipes: " + ", ".join(
            f"{data.recipes[u.recipe_id].display_name} {u.machine_equivalents:.2f}"
            for u in plan.plan.recipes))
    out += ["", f"transfer volume {r.transfer_volume_per_min:.3f}/min ({VOLUME_ASSUMPTION})"]
    return "\n".join(out)


def _site_arg(text: str) -> tuple[str, float, float, float]:
    label, sep, rest = text.partition(":")
    parts = rest.split(",")
    if not sep or len(parts) != 3:
        raise argparse.ArgumentTypeError(f"expected LABEL:EAST,NORTH,RADIUS, got {text!r}")
    return label, float(parts[0]), float(parts[1]), float(parts[2])


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
    args = ap.parse_args(argv)
    if not args.bill_phase and not args.bill_tier:
        ap.error("declare the bill: --bill-phase and/or --bill-tier")
    sockets = site_card.load_sockets(REPO, args.world)
    specs = tuple(
        site_card.SiteSpec(
            label=label,
            socket_ids=site_card.sockets_within(sockets, east, north, radius),
            extractors=tuple(args.extractor), extraction_clock=args.clock,
        )
        for label, east, north, radius in args.site
    )
    scenario = Scenario(recipe_input_multiplier=args.recipe_multiplier)
    pr = run(specs, tier=args.tier, scenario=scenario, goal=args.goal,
             bill_phases=tuple(args.bill_phase), bill_tiers=tuple(args.bill_tier),
             declared_recipe_names=tuple(args.recipe), world_config_id=args.world)
    print(report(pr, load(REPO, scenario)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
