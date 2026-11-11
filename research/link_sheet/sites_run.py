#!/usr/bin/env python3
"""P4 at 1/min over a DECLARED list of sites (a site-links 'Copy sites' paste).

Research driver (Greg, 2026-11-02 14:41: his test selection). Same bill,
tier, extractors, water and power as p4_run.py; only the sites differ.
Shared sockets, which portfolio_run refuses, are resolved here and reported:
a site wholly inside another is dropped; a socket in two sites stays with the
site listed first. Then: the max scale these sites carry (no target), and,
if that reaches 1.0, the target_scale 1.0 plan with its transfers.

    uv run python -I research/link_sheet/sites_run.py research/link_sheet/greg_test_sites.json --out X.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import p4_run as P  # noqa: E402

from production_adapter import PortfolioRequest, PowerBalance, Scenario, load  # noqa: E402
from production_adapter.gamedata import load_logistics  # noqa: E402
from production_adapter.lp_backend import Infeasible, LpBackend, PowerStatistic  # noqa: E402
from progression import at_tier, stock  # noqa: E402

import site_card  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sites", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    a = ap.parse_args(argv)
    raw = json.loads(a.sites.read_text(encoding="utf-8"))
    sets = [set(s["socket_ids"]) for s in raw]
    resolution = []
    keep = []
    for i, s in enumerate(raw):
        sup = [raw[j]["label"] for j in range(len(raw)) if j != i and sets[i] < sets[j]]
        if sup:
            resolution.append(f"dropped {s['label']}: wholly inside {sup[0]}")
            continue
        keep.append(s)
    taken: dict[str, str] = {}
    sites = []
    for s in keep:
        mine = []
        for sid in s["socket_ids"]:
            if sid in taken:
                resolution.append(f"{sid}: stays with {taken[sid]}, removed from {s['label']}")
                continue
            taken[sid] = s["label"]
            mine.append(sid)
        sites.append((s["label"], tuple(mine)))

    scenario = Scenario()
    data = load(P.REPO, scenario)
    _, rates = load_logistics(P.REPO)
    sockets = site_card.load_sockets(P.REPO, P.WORLD)
    from progression.power import load_power_tables
    tables = load_power_tables(P.REPO)
    held = at_tier(P.REPO, P.TIER)
    pa = stock.load_project_assembly(P.REPO, data)
    bill = tuple((r.item_id, 1.0) for r in pa if r.phase == P.PHASE)
    specs = tuple(site_card.SiteSpec(lab, ids, P.EXTRACTORS, 1.0) for lab, ids in sites)
    portfolio_sites = P.sites_for(specs, data, rates, sockets, tables, scenario)
    backend = LpBackend(power_statistic=PowerStatistic.MEAN)
    common = dict(sites=portfolio_sites, bill=bill, allowed_recipes=held.allowed_recipes,
                  weights=site_card.GOALS[P.GOAL],
                  power=PowerBalance(generators=(), grid_mw=P.POWER_OUTSIDE_MW, spare_mw=0.0))
    free = backend.solve_portfolio(PortfolioRequest(**common), data)
    binding = sorted({(b.item_id) for s in free.sites for b in s.binding})
    caps_total: dict[str, float] = {}
    for ps in portfolio_sites:
        for c in ps.resource_caps:
            if c.rate_per_min is not None and c.rate_per_min != float("inf"):
                caps_total[c.item_id] = caps_total.get(c.item_id, 0.0) + c.rate_per_min
    print(f"max scale {free.scale:.4f} per min of each P4 part")
    print("binding raws:", [data.items[i].display_name for i in binding])
    doc = {"schema": "link-sheet-run/0 (research)", "phase": P.PHASE, "tier": P.TIER, "goal": P.GOAL,
           "source_sites": str(a.sites), "resolution": resolution, "max_scale": free.scale,
           "binding": binding, "caps_total": caps_total,
           "bill": [{"item_id": i, "name": data.items[i].display_name, "per_min": u} for i, u in bill]}
    try:
        r = backend.solve_portfolio(PortfolioRequest(**common, target_scale=1.0), data)
        doc["target_scale"] = 1.0
    except Infeasible as e:
        print("1/min refused:", e)
        r = free
        doc["target_scale"] = None
        doc["note"] = f"1/min not reachable; transfers are the max-scale plan at {free.scale:.4f}/min"
    by_id = {s.socket_id: s for s in sockets}
    doc["sites"] = []
    for (lab, ids), ps in zip(sites, portfolio_sites):
        pts = [by_id[i] for i in ids if i in by_id]
        seed = by_id.get("BP_" + lab[3:]) or pts[0]
        doc["sites"].append({"label": lab, "item_id": None, "east_m": seed.east_m, "north_m": seed.north_m,
                             "elevation_m": seed.elevation_m, "socket_ids": list(ids),
                             "capacity_per_min": None, "draw_world_per_min": None})
    doc["site_draw_per_min"] = {s.label: P.raw_draw(s.plan) for s in r.sites}
    doc["transfers"] = [{"source": t.source, "destination": t.destination, "item_id": t.item_id,
                         "name": data.items[t.item_id].display_name, "form": data.items[t.item_id].form,
                         "rate_per_min": t.rate_per_min} for t in r.transfers]
    doc["transfer_volume_per_min"] = r.transfer_volume_per_min
    doc["scale"] = r.scale
    a.out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")
    for x in resolution:
        print("  ", x)
    print(f"plan scale {r.scale:.4f}; transfers {len(r.transfers)}; volume {r.transfer_volume_per_min:.1f}/min")
    print("caps:", {data.items[k].display_name: round(v) for k, v in caps_total.items() if v > 0})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
