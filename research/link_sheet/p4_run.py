#!/usr/bin/env python3
"""P4 at 1/min across per-raw sites: what moves between them (site planner A13).

Research driver, not tool code. Greg, 2026-11-01 22:25: logistics as a REPORT
after the solve (option A), distances by the corridor tool, all modes, the
1/min run; then (22:40) the fixed-rate portfolio mode, and Phase 4.

    bill      each Project Assembly phase-4 part at 1/min: bill units 1.0,
              PortfolioRequest.target_scale 1.0 (A13). PA parts only: no
              milestones, no step build-up, no carry-forward floor (those are
              the step planner's, research/step_planner/, and dominate its
              P4 draws)
    tier      8 (the phase-4 parts' recipes; delivering P4 opens tier 9),
              standard recipes only
    probe     one site holding every socket in the world: the raws the bill
              draws, with no transfers (also the cross-check: the sum of the
              per-site draws must equal it)
    sites     per raw drawn, the single-raw neighborhood with the most
              capacity at the declared extractors (A12.3's "best single
              same-raw neighbourhood", radius 350 m, min 1 node, no dedupe);
              equal capacity keeps the first in socket order. Capacity only,
              never location: so this is close to a WORST case for distance
    water     every site declared able to pump Water (Greg 2026-11-01 17:28:
              water essentially unlimited)
    power     outside this sheet: a standing grid of POWER_OUTSIDE_MW, no
              generators in the solve, so no fuel moves. Plant fuel (A12:
              most of P4's crude at the step planner's rates) is NOT here

Rule breaks, declared (research, not tools/): `max` picks the site per raw;
the extractor table and the outside grid are constants below.

    uv run python -I research/link_sheet/p4_run.py --out research/link_sheet/p4_run.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
for _src in ("production_adapter", "progression", "realization"):
    _p = str(REPO / "tools" / _src / "src")
    if _p not in sys.path:
        sys.path.insert(0, _p)
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

from production_adapter import (  # noqa: E402
    PortfolioRequest, PortfolioSite, PowerBalance, Scenario, load,
)
from production_adapter.gamedata import load_logistics  # noqa: E402
from production_adapter.lp_backend import LpBackend, PowerStatistic  # noqa: E402
from progression import at_tier, pumped_caps, site_extraction  # noqa: E402
from progression.district import WATER  # noqa: E402
from progression.power import load_power_tables  # noqa: E402
from progression import stock  # noqa: E402

import neighborhoods  # noqa: E402
import site_card  # noqa: E402

PHASE = 4
TIER = 8
RADIUS_M = 350.0
GOAL = "resources"
WORLD = "default_502094"
#: declared, not derived (rule break): the P4 extractor tier as the step
#: planner's nodes.py has it (Miner Mk.3), oil pumps, resource wells
EXTRACTORS = (
    (("resource_node", "Desc_LiquidOil_C"), "Build_OilPump_C"),
    (("resource_node", None), "Build_MinerMk3_C"),
    (("fracking_satellite", None), "Build_FrackingExtractor_C"),
)
#: power outside the sheet; large so it never binds
POWER_OUTSIDE_MW = 1.0e7


def sites_for(specs, data, rates, sockets, tables, scenario):
    out = []
    for spec in specs:
        _, _, _, definition, caps = site_card.site_caps(spec, data, rates, sockets)
        seg = site_extraction(definition, rates, tables.extractors, scenario=data.scenario,
                              supply=(), water=True)
        out.append(PortfolioSite(spec.label, pumped_caps(caps), seg))
    return tuple(out)


def solve(specs, data, rates, sockets, tables, scenario, held, bill):
    return LpBackend(power_statistic=PowerStatistic.MEAN).solve_portfolio(PortfolioRequest(
        sites=sites_for(specs, data, rates, sockets, tables, scenario),
        bill=bill, allowed_recipes=held.allowed_recipes, weights=site_card.GOALS[GOAL],
        power=PowerBalance(generators=(), grid_mw=POWER_OUTSIDE_MW, spare_mw=0.0),
        target_scale=1.0,
    ), data)


def raw_draw(plan) -> dict[str, float]:
    return {r.item_id: r.rate_per_min for r in plan.raw_inputs}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, required=True)
    a = ap.parse_args(argv)
    scenario = Scenario()
    data = load(REPO, scenario)
    _, rates = load_logistics(REPO)
    sockets = site_card.load_sockets(REPO, WORLD)
    tables = load_power_tables(REPO)
    held = at_tier(REPO, TIER)
    pa = stock.load_project_assembly(REPO, data)
    bill = tuple((r.item_id, 1.0) for r in pa if r.phase == PHASE)

    # probe: one site, every socket a declared extractor can work
    workable = tuple(s.socket_id for s in sockets
                     if s.source_kind in ("resource_node", "fracking_satellite") and s.item_id)
    probe_spec = site_card.SiteSpec("world", workable, EXTRACTORS, 1.0)
    probe = solve((probe_spec,), data, rates, sockets, tables, scenario, held, bill)
    drawn = {i: r for i, r in raw_draw(probe.sites[0].plan).items() if r > 1e-9}

    # per raw: single-raw neighborhoods, the one with the most capacity
    by_id = {s.socket_id: s for s in sockets}
    specs, picks = [], []
    for item, rate in drawn.items():
        if item == WATER:
            continue
        kinds = sorted({s.source_kind for s in sockets if s.item_id == item
                        and s.source_kind in ("resource_node", "fracking_satellite")})
        pol = neighborhoods.Policy(tuple((k, item) for k in kinds), RADIUS_M, 1, None)
        name = data.items[item].display_name
        ranked = []
        for nb in neighborhoods.discover(sockets, pol):
            spec = site_card.SiteSpec(name, nb.socket_ids, EXTRACTORS, 1.0)
            caps = site_card.site_caps(spec, data, rates, sockets)[4]
            ranked.append((sum(c.rate_per_min for c in caps if c.item_id == item), nb))
        # rule break (declared): most capacity first; stable, so equal
        # capacity keeps socket order. A12.3: while the draw is over what is
        # picked, the next neighborhood sharing no socket is forced on it
        ranked.sort(key=lambda x: -x[0])
        taken: set[str] = set()
        got = 0.0
        n = 0
        for cap, nb in ranked:
            if got >= rate:
                break
            if taken & set(nb.socket_ids):
                continue
            n += 1
            taken |= set(nb.socket_ids)
            got += cap
            spec = site_card.SiteSpec(f"{name} {n}", nb.socket_ids, EXTRACTORS, 1.0)
            specs.append(spec)
            picks.append({"label": spec.label, "item_id": item, "draw_world_per_min": rate,
                          "capacity_per_min": cap, "seed_socket_id": nb.seed_socket_id,
                          "east_m": nb.east_m, "north_m": nb.north_m,
                          "elevation_m": by_id[nb.seed_socket_id].elevation_m,
                          "socket_ids": list(nb.socket_ids)})

    for x in picks:
        print(f"  {x['label']:<16} draw {x['draw_world_per_min']:9.2f}  cap {x['capacity_per_min']:9.2f}"
              f"  at ({x['east_m']:.0f}, {x['north_m']:.0f})")
    r = solve(tuple(specs), data, rates, sockets, tables, scenario, held, bill)
    doc = {
        "schema": "link-sheet-run/0 (research)",
        "phase": PHASE, "tier": TIER, "target_scale": 1.0, "goal": GOAL, "radius_m": RADIUS_M,
        "bill": [{"item_id": i, "name": data.items[i].display_name, "per_min": u} for i, u in bill],
        "probe_draw_per_min": drawn,
        "sites": picks,
        "site_draw_per_min": {s.label: raw_draw(s.plan) for s in r.sites},
        "transfers": [{"source": t.source, "destination": t.destination, "item_id": t.item_id,
                       "name": data.items[t.item_id].display_name, "form": data.items[t.item_id].form,
                       "rate_per_min": t.rate_per_min} for t in r.transfers],
        "transfer_volume_per_min": r.transfer_volume_per_min,
        "scale": r.scale,
    }
    a.out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"scale {r.scale}; sites {len(specs)}; transfers {len(r.transfers)}; "
          f"volume {r.transfer_volume_per_min:.3f}/min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
