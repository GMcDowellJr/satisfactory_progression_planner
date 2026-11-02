#!/usr/bin/env python3
"""The link sheet: for each site pair a run moves items between, the corridor
distance and what each transport mode would need to carry it. Reports only.

Research driver, not tool code (site planner A13; Greg, 2026-11-01 22:25:
option A, the corridor tool for distance, all modes, 1/min). Reads a
`p4_run.py` output; nothing here changes the plan or picks a mode.

    distance  corridor_tool.query.shortest_corridor between the two sites'
              neighborhood seeds over the generated corridors_v1 graph
              (scripts/generate_corridors.py; gitignored output): snap from
              each seed to its nearest graph node + graph path length.
              Physical terrain connectivity only, not a belt, road or rail
              route (the tool's own scope). Drones use the straight line
    belt      items/min over each belt mark open at the tier
              (logistics_capabilities.csv): the share of one belt
    pipe      m3/min over each pipeline mark open at the tier (fluids)
    vehicle   per DIRECTED pair, every item's stacks/min summed
              (rate / stack size, items.csv). A vehicle with S slots keeps up
              alone if its round trip takes at most S / (stacks/min) minutes;
              the average speed that round trip needs over the corridor (or
              the straight line, for drones) is 2 * distance / that time.
              Slots from the game docs snapshot (FGVehicleDescriptor
              mInventorySize): Truck 48, Tractor 25, Explorer 12, Freight
              Car 32 (per car), Drone 9, Cyber Wagon 1. Vehicle speeds are
              not in the repo's sources, so no verdict is made: the needed
              speed is reported for the player to judge
    fluids    fluid vehicles (Fluid Truck, fluid Freight Car) carry a fluid
              inventory whose size is not resolved from the snapshot here:
              reported as unresolved, by name

    uv run --with pandas --with scikit-image python -I research/link_sheet/link_sheet.py \\
        research/link_sheet/p4_run.json --out research/link_sheet/p4_links.json
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
for _src in ("production_adapter", "corridor_tool"):
    _p = str(REPO / "tools" / _src / "src")
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402

from production_adapter import Scenario, load  # noqa: E402
from production_adapter.gamedata import load_logistics  # noqa: E402
from corridor_tool.field import load_field  # noqa: E402
from corridor_tool.query import shortest_corridor  # noqa: E402

CORRIDORS = "planning_data/analysis/derived/corridors/build_502094/corridors_v1"
MANIFEST = "planning_data/world/manifests/world_502094.json"
POLICY = "planning_data/analysis/policies/corridors_v1.json"
#: game docs snapshot docs_a81d250e96aa, FGVehicleDescriptor mInventorySize
#: (read 2026-11-01). Ground and rail vehicles follow the corridor; drones fly
VEHICLES = (
    ("Truck", 48, "corridor"),
    ("Tractor", 25, "corridor"),
    ("Explorer", 12, "corridor"),
    ("Freight Car", 32, "corridor"),
    ("Drone", 9, "straight"),
    ("Cyber Wagon", 1, "corridor"),
)
FLUID_VEHICLES_UNRESOLVED = ("Fluid Truck", "Freight Car (fluid)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    a = ap.parse_args(argv)
    run = json.loads(a.run.read_text(encoding="utf-8"))
    data = load(REPO, Scenario())
    caps, _ = load_logistics(REPO)
    tier = int(run["tier"])
    belts = [c for c in caps if c.capability_type == "belt" and c.unlock_tier is not None
             and c.unlock_tier <= tier]
    pipes = [c for c in caps if c.capability_type == "pipeline" and c.unlock_tier is not None
             and c.unlock_tier <= tier]

    policy = json.loads((REPO / POLICY).read_text(encoding="utf-8"))
    field, _ = load_field(REPO, REPO / MANIFEST, float(policy["analysis_step_m"]))
    cdir = REPO / CORRIDORS
    if not (cdir / "corridor_edges.csv").exists():
        raise SystemExit(f"no corridor graph at {cdir}: run scripts/generate_corridors.py first")
    nodes = pd.read_csv(cdir / "corridor_nodes.csv")
    edges = pd.read_csv(cdir / "corridor_edges.csv")
    site = {s["label"]: s for s in run["sites"]}

    routes: dict[frozenset, dict] = {}

    def route(x: str, y: str) -> dict:
        key = frozenset((x, y))
        if key not in routes:
            o, d = site[x], site[y]
            straight = math.hypot(o["east_m"] - d["east_m"], o["north_m"] - d["north_m"])
            try:
                cp = shortest_corridor(nodes, edges, (o["east_m"], o["north_m"]), (d["east_m"], d["north_m"]),
                                       field.east0_m, field.north0_m, field.step_m)
                s = cp.summary
                routes[key] = {
                    "straight_m": straight,
                    "corridor_m": s["origin_snap_distance_m"] + s["graph_path_length_m"]
                    + s["destination_snap_distance_m"],
                    "snap_m": [s["origin_snap_distance_m"], s["destination_snap_distance_m"]],
                    "chokepoint_edges": s["chokepoint_edge_count"],
                    "max_edge_grade": s["max_graph_edge_grade"],
                    "elevation_delta_m": d["elevation_m"] - o["elevation_m"],
                    "unresolved": None,
                }
            except RuntimeError as e:   # snapped nodes in different components
                routes[key] = {"straight_m": straight, "corridor_m": None, "unresolved": str(e),
                               "elevation_delta_m": d["elevation_m"] - o["elevation_m"]}
        return routes[key]

    pairs: dict[tuple[str, str], dict] = {}
    for t in run["transfers"]:
        item = data.items[t["item_id"]]
        p = pairs.setdefault((t["source"], t["destination"]), {
            "source": t["source"], "destination": t["destination"], "items": [],
            "solid_items_per_min": 0.0, "stacks_per_min": 0.0, "fluid_m3_per_min": 0.0,
        })
        row = {"name": t["name"], "form": item.form, "rate_per_min": t["rate_per_min"]}
        if item.form == "solid":
            row["stack_size"] = item.stack_size
            row["stacks_per_min"] = t["rate_per_min"] / item.stack_size
            p["solid_items_per_min"] += t["rate_per_min"]
            p["stacks_per_min"] += row["stacks_per_min"]
        else:
            p["fluid_m3_per_min"] += t["rate_per_min"]
        p["items"].append(row)

    for (x, y), p in pairs.items():
        r = route(x, y)
        p["route"] = r
        p["belt_share"] = {c.mark: p["solid_items_per_min"] / c.capacity_per_min for c in belts}
        p["pipe_share"] = {c.mark: p["fluid_m3_per_min"] / c.capacity_per_min for c in pipes}
        v = []
        for name, slots, path in VEHICLES:
            dist = r["corridor_m"] if path == "corridor" else r["straight_m"]
            budget = slots / p["stacks_per_min"] if p["stacks_per_min"] > 0 else None
            v.append({
                "vehicle": name, "slots": slots, "path": path,
                "round_trip_budget_min": budget,
                "needed_avg_kmh": (2 * dist / 1000.0) / (budget / 60.0)
                if (budget and dist is not None) else None,
            })
        p["vehicles"] = v
        p["fluid_vehicles_unresolved"] = list(FLUID_VEHICLES_UNRESOLVED) if p["fluid_m3_per_min"] else []

    doc = {"schema": "link-sheet/0 (research)", "run": str(a.run), "tier": tier,
           "corridor_policy": policy["policy_id"], "pairs": list(pairs.values())}
    a.out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8", newline="\n")

    print(f"{'from':<15}{'to':<15}{'items/min':>10}{'stacks/min':>11}{'straight km':>12}"
          f"{'corridor km':>12}{'Mk.1 belts':>11}{'truck budget min':>17}{'truck km/h':>11}{'drone km/h':>11}")
    for p in pairs.values():
        r = p["route"]
        tr = next(x for x in p["vehicles"] if x["vehicle"] == "Truck")
        dr = next(x for x in p["vehicles"] if x["vehicle"] == "Drone")
        cm = "n/a" if r["corridor_m"] is None else f"{r['corridor_m'] / 1000:.2f}"
        print(f"{p['source']:<15}{p['destination']:<15}{p['solid_items_per_min']:>10.1f}"
              f"{p['stacks_per_min']:>11.3f}{r['straight_m'] / 1000:>12.2f}{cm:>12}"
              f"{p['belt_share'].get('Mk.1', float('nan')):>11.2f}"
              f"{tr['round_trip_budget_min'] or float('nan'):>17.1f}"
              f"{tr['needed_avg_kmh'] if tr['needed_avg_kmh'] is not None else float('nan'):>11.2f}"
              f"{dr['needed_avg_kmh'] if dr['needed_avg_kmh'] is not None else float('nan'):>11.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
