from __future__ import annotations

import argparse
import csv
import heapq
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "satisfactory_route_tool" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from satisfactory_route_tool.heightfield import load_working_field
from satisfactory_route_tool.package import PlannerPackage
from satisfactory_route_tool.surface_graph import SurfaceGraphData


DEFAULT_ANCHORS = {
    "A": (-2650.293636, 370.014545),
    "B": (-2734.9425, 1543.4125),
    "C": (-1373.568333, 412.741667),
    "D": (-2547.757036, -741.081591),
    "E": (-2482.765125, 1553.894485),
    "F": (-1816.646667, -187.393333),
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Diagnose district routing against an already-built terrain topology. "
            "No world topology rebuild is performed."
        )
    )
    p.add_argument("--planner", default="planning_data")
    p.add_argument("--build", default="502094")
    p.add_argument("--surface-graph", required=True)
    p.add_argument("--component-maps", required=True)
    p.add_argument("--topology-nodes", required=True)
    p.add_argument("--topology-edges", required=True)
    p.add_argument(
        "--topology-components",
        help="optional topology_components.json from v4; otherwise components are derived",
    )
    p.add_argument(
        "--route-dir",
        help=(
            "optional existing district route output (v10/v11) containing "
            "district_route_summary.csv and pairs/*/route_summary.json"
        ),
    )
    p.add_argument(
        "--corridor-pad-m",
        type=float,
        default=800.0,
        help="current detailed-solver rectangular corridor padding to test (default 800 m)",
    )
    p.add_argument(
        "--anchor-search-m",
        type=float,
        default=300.0,
        help="radius for anchor component candidates (default 300 m)",
    )
    p.add_argument(
        "--primary-search-m",
        type=float,
        default=300.0,
        help="maximum snap distance to primary component (default 300 m)",
    )
    p.add_argument(
        "--anchor",
        action="append",
        default=[],
        metavar="NAME,EAST_M,NORTH_M",
        help="override/add anchor; repeatable",
    )
    p.add_argument(
        "--out",
        default="planning_data/analysis/derived/route_topology_diagnostics",
    )
    return p.parse_args()


def parse_anchor_specs(specs: list[str]) -> dict[str, tuple[float, float]]:
    anchors = dict(DEFAULT_ANCHORS)
    for spec in specs:
        parts = [p.strip() for p in str(spec).split(",")]
        if len(parts) != 3:
            raise ValueError(
                f"--anchor must be NAME,EAST_M,NORTH_M; got {spec!r}"
            )
        anchors[parts[0]] = (float(parts[1]), float(parts[2]))
    return anchors


def load_nodes(path: Path) -> dict[int, dict]:
    rows: dict[int, dict] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for rec in csv.DictReader(f):
            node_id = int(rec["node_id"])
            rows[node_id] = {
                "node_id": node_id,
                "east_m": float(rec["east_m"]),
                "north_m": float(rec["north_m"]),
                "z_m": float(rec["z_m"]),
                "state_count": int(rec["state_count"]),
                "degree": int(rec.get("degree") or 0),
                "global_component_id": (
                    int(rec["global_component_id"])
                    if rec.get("global_component_id") not in (None, "")
                    else None
                ),
                "global_component_rank": (
                    int(rec["global_component_rank"])
                    if rec.get("global_component_rank") not in (None, "")
                    else None
                ),
            }
    return rows


def load_edges(path: Path, nodes: dict[int, dict]) -> tuple[list[dict], dict[int, list[tuple[int, float]]]]:
    edges: list[dict] = []
    adj: dict[int, list[tuple[int, float]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        for rec in csv.DictReader(f):
            u = int(rec["u"])
            v = int(rec["v"])
            if u not in nodes or v not in nodes:
                continue
            # Topology edges represent a connection between large local components.
            # Centroid distance gives a useful coarse travel preference; clamp to the
            # recorded detailed crossing distance so adjacent near-identical centroids
            # still carry positive weight.
            du = nodes[u]["east_m"] - nodes[v]["east_m"]
            dn = nodes[u]["north_m"] - nodes[v]["north_m"]
            centroid_m = math.hypot(du, dn)
            crossing_m = float(rec.get("min_distance_m") or 0.0)
            weight = max(1.0, centroid_m, crossing_m)
            e = {
                "u": u,
                "v": v,
                "weight_m": weight,
                "crossing_count": int(rec.get("crossing_count") or 0),
            }
            edges.append(e)
            adj[u].append((v, weight))
            adj[v].append((u, weight))
    return edges, adj


def derive_component_membership(
    nodes: dict[int, dict],
    edges: list[dict],
) -> tuple[np.ndarray, list[dict]]:
    n = max(nodes) + 1 if nodes else 0
    parent = np.arange(n, dtype=np.int32)
    rank = np.zeros(n, dtype=np.uint8)

    def find(x: int) -> int:
        p = int(parent[x])
        while p != x:
            gp = int(parent[p])
            parent[x] = gp
            x = p
            p = gp
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1

    for e in edges:
        union(int(e["u"]), int(e["v"]))

    groups: dict[int, list[int]] = defaultdict(list)
    for node_id in nodes:
        groups[find(node_id)].append(node_id)

    ranked = []
    for root, members in groups.items():
        states = sum(nodes[n]["state_count"] for n in members)
        ranked.append((states, len(members), root, members))
    ranked.sort(key=lambda x: (-x[0], -x[1], x[2]))

    membership = np.full(n, -1, dtype=np.int32)
    comps: list[dict] = []
    for cid, (states, count, root, members) in enumerate(ranked):
        for node_id in members:
            membership[node_id] = cid
        comps.append(
            {
                "component_id": cid,
                "rank": cid + 1,
                "detailed_state_count": int(states),
                "topology_node_count": int(count),
            }
        )
    return membership, comps


def load_component_maps(path: Path) -> tuple[np.ndarray, np.ndarray | None]:
    with np.load(path) as d:
        base = np.asarray(d["base_component_id"], dtype=np.int32)
        topology_component = (
            np.asarray(d["topology_component_id"], dtype=np.int32)
            if "topology_component_id" in d
            else None
        )
    return base, topology_component


def candidate_topology_nodes(
    *,
    east_m: float,
    north_m: float,
    field,
    base_component_map: np.ndarray,
    search_m: float,
) -> dict[int, float]:
    r0, c0 = field.world_to_rc(east_m, north_m)
    radius_cells = max(0, int(math.ceil(search_m / field.step_m)))
    out: dict[int, float] = {}
    h, w = field.shape
    for rr in range(max(0, r0 - radius_cells), min(h, r0 + radius_cells + 1)):
        yn = field.north0_m - rr * field.step_m
        dy = yn - north_m
        if abs(dy) > search_m:
            continue
        for cc in range(max(0, c0 - radius_cells), min(w, c0 + radius_cells + 1)):
            topo = int(base_component_map[rr, cc])
            if topo < 0:
                continue
            xe = field.east0_m + cc * field.step_m
            dx = xe - east_m
            d2 = dx * dx + dy * dy
            if d2 > search_m * search_m:
                continue
            dist = math.sqrt(d2)
            old = out.get(topo)
            if old is None or dist < old:
                out[topo] = dist
    return out


def resolve_anchor(
    name: str,
    east_m: float,
    north_m: float,
    *,
    field,
    base_component_map: np.ndarray,
    topology_membership: np.ndarray,
    nodes: dict[int, dict],
    search_m: float,
    primary_search_m: float,
) -> dict:
    candidates = candidate_topology_nodes(
        east_m=east_m,
        north_m=north_m,
        field=field,
        base_component_map=base_component_map,
        search_m=search_m,
    )
    if not candidates:
        return {
            "name": name,
            "east_m": east_m,
            "north_m": north_m,
            "status": "NO_CANDIDATE",
        }

    ordered = sorted(candidates.items(), key=lambda kv: (kv[1], kv[0]))
    nearest_node, nearest_dist = ordered[0]
    nearest_component = int(topology_membership[nearest_node])

    primary = [
        (dist, node_id)
        for node_id, dist in candidates.items()
        if int(topology_membership[node_id]) == 0 and dist <= primary_search_m + 1e-9
    ]
    primary.sort()
    if primary:
        primary_dist, primary_node = primary[0]
        routing_node = int(primary_node)
        routing_dist = float(primary_dist)
        routing_component = 0
        policy = "PRIMARY_COMPONENT"
    else:
        routing_node = int(nearest_node)
        routing_dist = float(nearest_dist)
        routing_component = int(nearest_component)
        policy = "NEAREST_AVAILABLE"

    component_candidates: dict[int, dict] = {}
    for node_id, dist in ordered:
        cid = int(topology_membership[node_id])
        rec = component_candidates.get(cid)
        if rec is None:
            component_candidates[cid] = {
                "component_id": cid,
                "nearest_distance_m": float(dist),
                "candidate_topology_nodes": 1,
            }
        else:
            rec["candidate_topology_nodes"] += 1

    return {
        "name": name,
        "east_m": east_m,
        "north_m": north_m,
        "status": "RESOLVED",
        "literal_nearest_topology_node": int(nearest_node),
        "literal_nearest_distance_m": round(float(nearest_dist), 3),
        "literal_nearest_component_id": int(nearest_component),
        "routing_topology_node": routing_node,
        "routing_snap_distance_m": round(routing_dist, 3),
        "routing_component_id": routing_component,
        "routing_policy": policy,
        "component_candidates": sorted(
            component_candidates.values(),
            key=lambda r: (r["nearest_distance_m"], r["component_id"]),
        ),
    }


def dijkstra(
    source: int,
    adj: dict[int, list[tuple[int, float]]],
    allowed_component: int,
    membership: np.ndarray,
) -> tuple[dict[int, float], dict[int, int]]:
    dist = {source: 0.0}
    prev: dict[int, int] = {}
    pq = [(0.0, source)]
    while pq:
        cost, u = heapq.heappop(pq)
        if cost != dist.get(u):
            continue
        for v, weight in adj.get(u, ()):
            if int(membership[v]) != allowed_component:
                continue
            nc = cost + weight
            if nc < dist.get(v, math.inf):
                dist[v] = nc
                prev[v] = u
                heapq.heappush(pq, (nc, v))
    return dist, prev


def reconstruct(prev: dict[int, int], source: int, target: int) -> list[int]:
    if source == target:
        return [source]
    if target not in prev:
        return []
    path = [target]
    cur = target
    while cur != source:
        cur = prev[cur]
        path.append(cur)
    path.reverse()
    return path


def required_corridor_pad(
    path: list[int],
    nodes: dict[int, dict],
    a_xy: tuple[float, float],
    b_xy: tuple[float, float],
) -> dict:
    if not path:
        return {
            "required_pad_m": None,
            "west_m": None,
            "east_m": None,
            "south_m": None,
            "north_m": None,
            "path_bbox_m": None,
        }

    xs = np.array([nodes[n]["east_m"] for n in path], dtype=np.float64)
    ys = np.array([nodes[n]["north_m"] for n in path], dtype=np.float64)
    xmin, xmax = min(a_xy[0], b_xy[0]), max(a_xy[0], b_xy[0])
    ymin, ymax = min(a_xy[1], b_xy[1]), max(a_xy[1], b_xy[1])

    west = max(0.0, xmin - float(xs.min()))
    east = max(0.0, float(xs.max()) - xmax)
    south = max(0.0, ymin - float(ys.min()))
    north = max(0.0, float(ys.max()) - ymax)
    return {
        "required_pad_m": max(west, east, south, north),
        "west_m": west,
        "east_m": east,
        "south_m": south,
        "north_m": north,
        "path_bbox_m": [
            float(xs.min()),
            float(ys.min()),
            float(xs.max()),
            float(ys.max()),
        ],
    }


def load_existing_route_status(route_dir: Path | None) -> dict[tuple[str, str], dict]:
    if route_dir is None or not route_dir.exists():
        return {}
    out: dict[tuple[str, str], dict] = {}
    pairs = route_dir / "pairs"
    if not pairs.is_dir():
        return out
    for d in pairs.iterdir():
        if not d.is_dir() or "_to_" not in d.name:
            continue
        a, b = d.name.split("_to_", 1)
        summary = d / "route_summary.json"
        if not summary.exists():
            continue
        rec = json.loads(summary.read_text(encoding="utf-8"))
        out[(a, b)] = {
            "existing_route_status": rec.get("route_status"),
            "existing_destination_reached": rec.get("destination_reached"),
            "existing_route_length_m": rec.get("route_length_m"),
            "existing_remaining_plan_gap_m": rec.get("remaining_plan_gap_m"),
            "existing_reachable_search_states": rec.get("reachable_search_states"),
            "existing_endpoint_access_radius_m": rec.get("endpoint_access_radius_m"),
        }
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    preferred = [
        "origin",
        "destination",
        "same_component",
        "component_id",
        "topology_path_found",
        "topology_hops",
        "topology_coarse_cost_m",
        "required_corridor_pad_m",
        "current_corridor_pad_m",
        "corridor_contains_topology_path",
        "recommended_corridor_pad_m",
        "existing_route_status",
        "existing_destination_reached",
        "existing_route_length_m",
        "existing_remaining_plan_gap_m",
    ]
    extras = sorted(
        {k for row in rows for k in row}
        - set(preferred)
        - {"path_node_ids", "path_bbox_m"}
    )
    fields = preferred + extras
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in fields})


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    graph = SurfaceGraphData(args.surface_graph, None)
    pkg = PlannerPackage(args.planner)
    field = load_working_field(pkg, args.build, graph.step_m)

    nodes = load_nodes(Path(args.topology_nodes))
    edges, adj = load_edges(Path(args.topology_edges), nodes)
    base_map, stored_membership = load_component_maps(Path(args.component_maps))

    if base_map.shape != field.shape:
        raise ValueError(
            f"component base map {base_map.shape} != WorkingField {field.shape}"
        )

    if stored_membership is None:
        membership, components = derive_component_membership(nodes, edges)
    else:
        membership = stored_membership
        # Minimal component statistics for reporting.
        counts = defaultdict(lambda: {"nodes": 0, "states": 0})
        for node_id, rec in nodes.items():
            cid = int(membership[node_id])
            counts[cid]["nodes"] += 1
            counts[cid]["states"] += int(rec["state_count"])
        components = [
            {
                "component_id": cid,
                "rank": cid + 1,
                "topology_node_count": counts[cid]["nodes"],
                "detailed_state_count": counts[cid]["states"],
            }
            for cid in sorted(counts)
        ]

    anchors = parse_anchor_specs(args.anchor)
    resolved: dict[str, dict] = {}
    for name, (east, north) in sorted(anchors.items()):
        resolved[name] = resolve_anchor(
            name,
            east,
            north,
            field=field,
            base_component_map=base_map,
            topology_membership=membership,
            nodes=nodes,
            search_m=float(args.anchor_search_m),
            primary_search_m=float(args.primary_search_m),
        )

    route_status = load_existing_route_status(
        None if args.route_dir is None else Path(args.route_dir)
    )

    # Reuse one shortest-path tree per unique origin/routing node.
    trees: dict[tuple[int, int], tuple[dict[int, float], dict[int, int]]] = {}
    names = sorted(resolved)
    pair_rows: list[dict] = []
    path_payload: dict[str, dict] = {}

    for i, a in enumerate(names):
        ar = resolved[a]
        if ar.get("status") != "RESOLVED":
            continue
        for b in names[i + 1 :]:
            br = resolved[b]
            if br.get("status") != "RESOLVED":
                continue
            an = int(ar["routing_topology_node"])
            bn = int(br["routing_topology_node"])
            ac = int(ar["routing_component_id"])
            bc = int(br["routing_component_id"])
            same = ac == bc

            row = {
                "origin": a,
                "destination": b,
                "same_component": same,
                "component_id": ac if same else None,
                "current_corridor_pad_m": float(args.corridor_pad_m),
                **route_status.get((a, b), route_status.get((b, a), {})),
            }

            if not same:
                row.update(
                    {
                        "topology_path_found": False,
                        "topology_hops": None,
                        "topology_coarse_cost_m": None,
                        "required_corridor_pad_m": None,
                        "corridor_contains_topology_path": False,
                        "recommended_corridor_pad_m": None,
                    }
                )
                pair_rows.append(row)
                continue

            key = (an, ac)
            if key not in trees:
                trees[key] = dijkstra(an, adj, ac, membership)
            dist, prev = trees[key]
            path = reconstruct(prev, an, bn)
            pad = required_corridor_pad(
                path,
                nodes,
                anchors[a],
                anchors[b],
            )

            required = pad["required_pad_m"]
            contains = (
                required is not None
                and required <= float(args.corridor_pad_m) + 1e-6
            )
            # Add one sector of margin so the detailed search is not squeezed
            # directly against the coarse path envelope.
            recommended = (
                None
                if required is None
                else math.ceil((required + 128.0) / 50.0) * 50.0
            )
            row.update(
                {
                    "topology_path_found": bool(path),
                    "topology_hops": max(0, len(path) - 1) if path else None,
                    "topology_coarse_cost_m": (
                        round(float(dist[bn]), 3) if bn in dist else None
                    ),
                    "required_corridor_pad_m": (
                        round(float(required), 3) if required is not None else None
                    ),
                    "corridor_contains_topology_path": contains,
                    "recommended_corridor_pad_m": recommended,
                    "west_excursion_m": (
                        round(float(pad["west_m"]), 3)
                        if pad["west_m"] is not None else None
                    ),
                    "east_excursion_m": (
                        round(float(pad["east_m"]), 3)
                        if pad["east_m"] is not None else None
                    ),
                    "south_excursion_m": (
                        round(float(pad["south_m"]), 3)
                        if pad["south_m"] is not None else None
                    ),
                    "north_excursion_m": (
                        round(float(pad["north_m"]), 3)
                        if pad["north_m"] is not None else None
                    ),
                    "path_bbox_m": pad["path_bbox_m"],
                    "path_node_ids": path,
                }
            )
            pair_rows.append(row)
            path_payload[f"{a}_to_{b}"] = {
                "origin": a,
                "destination": b,
                "topology_node_ids": path,
                "path_bbox_m": pad["path_bbox_m"],
                "required_corridor_pad_m": required,
            }

    (out_dir / "anchor_diagnostics.json").write_text(
        json.dumps(resolved, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "pair_diagnostics.json").write_text(
        json.dumps(pair_rows, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "topology_paths.json").write_text(
        json.dumps(path_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    write_csv(out_dir / "pair_diagnostics.csv", pair_rows)

    summary = {
        "schema_version": 1,
        "purpose": (
            "Post-process an existing terrain topology to test whether district "
            "pairs are globally connected and whether the detailed solver's "
            "rectangular corridor contains a coarse topology path."
        ),
        "world_topology_rebuilt": False,
        "topology_nodes": len(nodes),
        "topology_edges": len(edges),
        "global_components": len(components),
        "current_corridor_pad_m": float(args.corridor_pad_m),
        "anchors": resolved,
        "pairs": {
            "total": len(pair_rows),
            "same_component": sum(bool(r["same_component"]) for r in pair_rows),
            "topology_path_found": sum(bool(r["topology_path_found"]) for r in pair_rows),
            "outside_current_corridor": sum(
                bool(r["topology_path_found"])
                and not bool(r["corridor_contains_topology_path"])
                for r in pair_rows
            ),
        },
    }
    (out_dir / "diagnostic_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"wrote {out_dir}")
    for row in pair_rows:
        status = row.get("existing_route_status", "")
        pad = row.get("required_corridor_pad_m")
        print(
            f"  {row['origin']}↔{row['destination']} "
            f"topology={'PASS' if row['topology_path_found'] else 'NO'} "
            f"required_pad={pad} m "
            f"existing={status}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
