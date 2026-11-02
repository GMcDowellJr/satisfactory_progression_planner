#!/usr/bin/env python3
"""Deposits and the corridor graph, as one JSON document for the site-links page.

Research driver, not tool code (handoff 2026-11-01 23:30 follow-up; Greg,
2026-11-02 12:58): pick forward from the start; select a deposit (e.g. crude
oil in the south-west) and see the other raws' deposits that could support
it, with their corridors, purity and access. Nothing here ranks or chooses;
the page sorts a list by corridor distance as a view, and shows ties.

    deposit   the sockets of ONE raw chained within LINK_M of each other
              (single-link clustering: two sockets are in one deposit when a
              chain of same-raw sockets, each within LINK_M of the next,
              joins them). Fracking satellites group by their core instead
              (the game's own grouping). LINK_M is policy, declared here;
              it differs from a neighborhood's radius in that no seed is
              chosen, so a deposit has no "best" centre
    capacity  per extractor (rates from extraction_rates.csv via
              gamedata.load_logistics), 100 % clock, by purity. Belt limits
              are not applied: a Mk.3 miner on a pure node (480/min) needs a
              Mk.4 belt
    graph     corridors_v1 (tools/corridor_tool; scripts/generate_corridors.py
              writes it, gitignored): nodes, edges with length, the tool's
              own search cost (corridor_tool.query._edge_cost), class, max
              grade, and the geometry thinned to every THIN-th cell. The page
              runs Dijkstra on the same cost the tool's shortest_corridor does
    snap      each deposit's centroid to its nearest graph node, as the tool
              snaps an endpoint; the snap distance is reported
    phases    raws each phase draws at 1/min (research/step_planner/
              selection_threshold_output.txt, S0, standard recipes, plant
              included), for the page's phase filter and coverage check

    uv run --with pandas --with scikit-image python -I research/site_links/build.py --out site_links.json
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
for _src in ("production_adapter", "progression", "realization", "corridor_tool"):
    _p = str(REPO / "tools" / _src / "src")
    if _p not in sys.path:
        sys.path.insert(0, _p)
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

import pandas as pd  # noqa: E402

from production_adapter import load  # noqa: E402
from production_adapter.gamedata import load_logistics  # noqa: E402
from corridor_tool.field import load_field  # noqa: E402
from corridor_tool.query import _edge_cost  # noqa: E402

import site_card  # noqa: E402

WORLD = "default_502094"
LINK_M = 350.0
THIN = 2
CORRIDORS = "planning_data/analysis/derived/corridors/build_502094/corridors_v1"
EXTRACTORS = {
    "miner": ("Build_MinerMk1_C", "Build_MinerMk2_C", "Build_MinerMk3_C"),
    "oil": ("Build_OilPump_C",),
    "well": ("Build_FrackingExtractor_C",),
}
#: research/step_planner/selection_threshold_output.txt, "all1 P<n> | S0", draw per minute
PHASE_DRAW = {
    1: {"Desc_Stone_C": 55, "Desc_OreIron_C": 56, "Desc_OreCopper_C": 11},
    2: {"Desc_Coal_C": 75, "Desc_OreCopper_C": 41, "Desc_OreIron_C": 92, "Desc_Stone_C": 19},
    3: {"Desc_Coal_C": 278, "Desc_OreCopper_C": 169, "Desc_OreIron_C": 359, "Desc_LiquidOil_C": 159,
        "Desc_Stone_C": 82},
    4: {"Desc_OreCopper_C": 1557, "Desc_LiquidOil_C": 965, "Desc_OreGold_C": 412, "Desc_OreBauxite_C": 355,
        "Desc_Coal_C": 400, "Desc_RawQuartz_C": 224, "Desc_NitrogenGas_C": 203, "Desc_OreIron_C": 396,
        "Desc_Stone_C": 161},
    5: {"Desc_LiquidOil_C": 1875, "Desc_OreCopper_C": 1893, "Desc_OreBauxite_C": 461, "Desc_Coal_C": 703,
        "Desc_SAM_C": 162, "Desc_RawQuartz_C": 345, "Desc_NitrogenGas_C": 319, "Desc_OreGold_C": 229,
        "Desc_OreIron_C": 746, "Desc_Stone_C": 108},
}


def kind_of(s) -> str:
    if s.source_kind == "fracking_satellite":
        return "well"
    return "oil" if s.item_id == "Desc_LiquidOil_C" else "miner"


def deposits(sockets):
    pool = [s for s in sockets if s.item_id and s.source_kind in ("resource_node", "fracking_satellite")]
    groups: list[list] = []
    wells: dict[str, list] = {}
    by_item: dict[str, list] = {}
    for s in pool:
        if s.source_kind == "fracking_satellite":
            wells.setdefault(f"{s.core_socket_id}|{s.item_id}", []).append(s)
        else:
            by_item.setdefault(s.item_id, []).append(s)
    for items in by_item.values():
        seen: set[str] = set()
        for s in items:
            if s.socket_id in seen:
                continue
            comp, stack = [], [s]
            seen.add(s.socket_id)
            while stack:
                u = stack.pop()
                comp.append(u)
                for v in items:
                    if v.socket_id not in seen and math.hypot(u.east_m - v.east_m, u.north_m - v.north_m) <= LINK_M:
                        seen.add(v.socket_id)
                        stack.append(v)
            groups.append(comp)
    groups.extend(wells.values())
    return groups


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=pathlib.Path, required=True)
    a = ap.parse_args(argv)
    data = load(REPO)
    _, rates = load_logistics(REPO)
    rate = {(r.extractor_class, r.purity): r.nominal_rate_min for r in rates}
    sockets = site_card.load_sockets(REPO, WORLD)

    policy = json.loads((REPO / "planning_data/analysis/policies/corridors_v1.json").read_text(encoding="utf-8"))
    field, _ = load_field(REPO, REPO / "planning_data/world/manifests/world_502094.json",
                          float(policy["analysis_step_m"]))
    cdir = REPO / CORRIDORS
    nodes = pd.read_csv(cdir / "corridor_nodes.csv")
    edges = pd.read_csv(cdir / "corridor_edges.csv")
    node_ix = {nid: i for i, nid in enumerate(nodes.node_id.astype(str))}
    ne, nn = nodes.east_m.to_numpy(), nodes.north_m.to_numpy()

    out_dep = []
    for k, comp in enumerate(deposits(sockets)):
        item = comp[0].item_id
        kind = kind_of(comp[0])
        e = sum(s.east_m for s in comp) / len(comp)
        n = sum(s.north_m for s in comp) / len(comp)
        d2 = (ne - e) ** 2 + (nn - n) ** 2
        j = int(d2.argmin())
        purity = {p: sum(1 for s in comp if s.purity == p) for p in ("impure", "normal", "pure")}
        cap = {x: sum(rate[(x, s.purity)] for s in comp) for x in EXTRACTORS[kind]}
        out_dep.append({
            "id": k, "item": item, "kind": kind, "e": round(e, 1), "n": round(n, 1),
            "z": [round(min(s.elevation_m for s in comp), 1), round(max(s.elevation_m for s in comp), 1)],
            "nodes": len(comp), "purity": purity, "cap": cap,
            "snap": j, "snap_m": round(math.sqrt(float(d2[j])), 1),
            "sockets": [[round(s.east_m), round(s.north_m), s.purity[0]] for s in comp],
        })

    out_edges = []
    for e in edges.itertuples(index=False):
        rcs = [tuple(map(int, t.split(":"))) for t in str(e.path_rc).split(";")]
        keep = rcs[::THIN] + ([rcs[-1]] if (len(rcs) - 1) % THIN else [])
        pts = [[round(field.east0_m + c * field.step_m), round(field.north0_m - r * field.step_m)] for r, c in keep]
        out_edges.append([node_ix[str(e.from_node)], node_ix[str(e.to_node)], round(float(e.length_m), 1),
                          round(_edge_cost(e), 1), 1 if str(e.corridor_class) == "chokepoint" else 0,
                          round(float(e.max_grade), 3), pts])

    items = sorted({d["item"] for d in out_dep})
    doc = {
        "schema": "site-links/0 (research)", "world": WORLD, "link_m": LINK_M,
        "corridor_policy": policy["policy_id"],
        "items": {i: {"name": data.items[i].display_name, "form": data.items[i].form} for i in items},
        "phase_draw": PHASE_DRAW,
        "nodes": [[round(float(x)), round(float(y))] for x, y in zip(ne, nn)],
        "edges": out_edges,
        "deposits": out_dep,
    }
    a.out.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    print(f"deposits {len(out_dep)}; graph nodes {len(nodes)}, edges {len(edges)}; "
          f"{a.out.stat().st_size / 1e6:.2f} MB")
    by = {}
    for d in out_dep:
        by[d["item"]] = by.get(d["item"], 0) + 1
    print({data.items[i].display_name: c for i, c in by.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
