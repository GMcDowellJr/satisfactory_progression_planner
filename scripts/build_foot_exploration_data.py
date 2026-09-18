"""Build raw foot-exploration topology products from existing world data.

This is a DATA-LAYER tool.  It intentionally does not assign player-specific
travel costs, safety labels, ramp counts, hazard penalties, or POI-to-POI
shortest-path distances.

Inputs are the existing detailed surface graph, vertical intervals, contracted
foot topology, canonical exploration POIs, and raw POI hazard context.

Outputs:
  * poi_topology_snap.csv/json              - nearest geometric surface association
  * poi_topology_snap_candidates.csv        - top-N raw geometric alternatives per POI
  * poi_topology_node_index.npz             - compact POI/topology indexing only
  * poi_snap_validation_candidates.csv      - diagnostic outliers, not canonical policy
  * manifest.json                           - provenance and counts

Runtime profiles are expected to interpret grade, clearance, hazards, vertical
mismatch, ramps, jetpacks, etc. separately.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "satisfactory_route_tool" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from satisfactory_route_tool.heightfield import load_working_field
from satisfactory_route_tool.package import PlannerPackage
from satisfactory_route_tool.surface_graph import SurfaceGraphData


@dataclass(frozen=True)
class SnapCandidate:
    topology_node_id: int
    state_type: str
    state_id: int
    east_m: float
    north_m: float
    z_m: float
    plan_distance_m: float
    dz_m: float
    spatial_distance_m: float
    known_clearance_m: float | None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--planner", default="planning_data")
    p.add_argument("--build", default="502094")
    p.add_argument("--surface-graph", default="data/local/spatial/surface_graph")
    p.add_argument("--intervals", default="data/local/spatial/multisurface/vertical_intervals.npz")
    p.add_argument("--topology-dir", default="planning_data/analysis/derived/world_foot_topology")
    p.add_argument("--pois", default="planning_data/world/canonical/exploration_pois.csv")
    p.add_argument("--hazards", default="planning_data/game/reference/exploration_poi_hazards.csv")
    p.add_argument("--out", default="planning_data/analysis/derived/foot_exploration_data")
    p.add_argument("--build-topology", action="store_true")
    p.add_argument("--topology-workers", type=int, default=1)
    p.add_argument("--sector-m", type=float, default=128.0)
    p.add_argument("--snap-search-m", type=float, default=160.0)
    p.add_argument("--snap-candidates", type=int, default=8)
    p.add_argument("--validate-only", action="store_true")
    return p.parse_args()


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (ROOT / p).resolve()


def require(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _cm_to_m(v):
    if v in (None, ""):
        return None
    try:
        return float(v) / 100.0
    except (TypeError, ValueError):
        return None


def hazard_facts(h: dict) -> dict:
    """Unit-normalized hazard facts only; no safe/unsafe classification."""
    hostiles = h.get("hostiles_nearby") or {}
    spawns = h.get("spawns_here") or []
    return {
        "nearest_hostile_m": _cm_to_m(h.get("nearest_hostile_cm")),
        "nearest_gas_m": _cm_to_m(h.get("nearest_gas_cm")),
        "nearest_gas_class": h.get("nearest_gas_class"),
        "nearest_uranium_m": _cm_to_m(h.get("nearest_uranium_cm")),
        "nearest_nuclear_hog_spawner_m": _cm_to_m(h.get("nearest_nuclear_hog_spawner_cm")),
        "inside_spore_flower_damage_sphere": bool(h.get("inside_spore_flower_damage_sphere", False)),
        "hostiles_nearby_json": json.dumps(hostiles, separators=(",", ":"), sort_keys=True),
        "spawns_here_json": json.dumps(spawns, separators=(",", ":"), sort_keys=True),
        "hazard_json": json.dumps(h, separators=(",", ":"), sort_keys=True),
    }


def load_hazards(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    for row in load_csv(path):
        raw = (row.get("hazard_json") or "").strip()
        out[row["poi_id"]] = json.loads(raw) if raw else {}
    return out


def maybe_build_topology(args, surface_graph: Path, intervals: Path, topology: Path) -> None:
    required = [
        topology / "topology_nodes.csv",
        topology / "topology_edges.csv",
        topology / "topology_gateways.csv",
        topology / "component_maps.npz",
    ]
    if all(p.exists() for p in required):
        return
    if not args.build_topology:
        missing = ", ".join(str(p) for p in required if not p.exists())
        raise FileNotFoundError(
            "raw foot topology outputs are missing. Run build_travel_topology.py "
            f"or pass --build-topology. Missing: {missing}"
        )
    topology.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "build_travel_topology.py"),
        "--planner", str(resolve(args.planner)),
        "--build", str(args.build),
        "--surface-graph", str(surface_graph),
        "--intervals", str(intervals),
        "--mode", "foot",
        "--sector-m", str(args.sector_m),
        "--workers", str(max(1, args.topology_workers)),
        "--write-component-maps",
        "--out", str(topology),
    ]
    print("building structural foot topology:")
    print(" ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def _candidate_key(c: SnapCandidate) -> tuple:
    # This is only a deterministic geometric association rule, not travel cost.
    return (c.spatial_distance_m, c.plan_distance_m, abs(c.dz_m), c.state_type, c.state_id)


def snap_candidates(
    *, east: float, north: float, z: float,
    graph: SurfaceGraphData, field,
    base_map: np.ndarray, explicit_map: np.ndarray,
    search_m: float, keep_n: int,
) -> list[SnapCandidate]:
    r0, c0 = graph.world_to_rc(east, north)
    radius_cells = int(math.ceil(search_m / graph.step_m))
    rlo = max(0, r0 - radius_cells)
    rhi = min(graph.height - 1, r0 + radius_cells)
    clo = max(0, c0 - radius_cells)
    chi = min(graph.width - 1, c0 + radius_cells)

    best_by_state: dict[tuple[str, int], SnapCandidate] = {}
    for rr in range(rlo, rhi + 1):
        north_c = graph.north0_m - rr * graph.step_m
        dy = north_c - north
        if abs(dy) > search_m:
            continue
        for cc in range(clo, chi + 1):
            east_c = graph.east0_m + cc * graph.step_m
            dx = east_c - east
            plan_m = math.hypot(dx, dy)
            if plan_m > search_m:
                continue

            topo = int(base_map[rr, cc])
            base_z = float(field.z_m[rr, cc])
            if topo >= 0 and math.isfinite(base_z):
                dz = z - base_z
                state_id = rr * graph.width + cc
                c = SnapCandidate(
                    topology_node_id=topo, state_type="base", state_id=state_id,
                    east_m=east_c, north_m=north_c, z_m=base_z,
                    plan_distance_m=plan_m, dz_m=dz,
                    spatial_distance_m=math.hypot(plan_m, dz),
                    known_clearance_m=None,
                )
                best_by_state[(c.state_type, c.state_id)] = c

            cell = rr * graph.width + cc
            for node in graph.nodes_for_cell(cell).tolist():
                if not (0 <= node < len(explicit_map)):
                    continue
                topo = int(explicit_map[node])
                if topo < 0:
                    continue
                floor_z = float(graph.floor_z[node])
                dz = z - floor_z
                clr = float(graph.clearance[node])
                c = SnapCandidate(
                    topology_node_id=topo, state_type="explicit", state_id=int(node),
                    east_m=east_c, north_m=north_c, z_m=floor_z,
                    plan_distance_m=plan_m, dz_m=dz,
                    spatial_distance_m=math.hypot(plan_m, dz),
                    known_clearance_m=clr if math.isfinite(clr) else None,
                )
                best_by_state[(c.state_type, c.state_id)] = c

    return sorted(best_by_state.values(), key=_candidate_key)[:max(1, int(keep_n))]


SNAP_FIELDS = [
    "poi_id", "poi_type", "east_m", "north_m", "elevation_m",
    "snap_status", "selection_method", "topology_node_id",
    "snap_state_type", "snap_state_id", "snapped_east_m", "snapped_north_m",
    "snapped_z_m", "snap_plan_distance_m", "snap_dz_m", "snap_spatial_distance_m",
    "known_clearance_m", "global_component_id", "global_component_rank",
    "nearest_hostile_m", "nearest_gas_m", "nearest_gas_class", "nearest_uranium_m",
    "nearest_nuclear_hog_spawner_m", "inside_spore_flower_damage_sphere",
    "hostiles_nearby_json", "spawns_here_json", "hazard_json",
]

CANDIDATE_FIELDS = [
    "poi_id", "poi_type", "candidate_rank_by_3d",
    "topology_node_id", "snap_state_type", "snap_state_id",
    "snapped_east_m", "snapped_north_m", "snapped_z_m",
    "snap_plan_distance_m", "snap_dz_m", "snap_spatial_distance_m",
    "known_clearance_m", "global_component_id", "global_component_rank",
]


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    args = parse_args()
    planner = resolve(args.planner)
    surface_graph = resolve(args.surface_graph)
    intervals = resolve(args.intervals)
    topology = resolve(args.topology_dir)
    pois_path = resolve(args.pois)
    hazards_path = resolve(args.hazards)
    out_dir = resolve(args.out)

    require(surface_graph / "meta.json", "surface graph")
    require(intervals, "vertical intervals")
    require(pois_path, "canonical POIs")
    require(hazards_path, "POI hazards")
    maybe_build_topology(args, surface_graph, intervals, topology)
    for p, label in [
        (topology / "topology_nodes.csv", "topology nodes"),
        (topology / "topology_edges.csv", "topology edges"),
        (topology / "topology_gateways.csv", "raw topology gateways"),
        (topology / "component_maps.npz", "component maps"),
    ]:
        require(p, label)

    if args.validate_only:
        print("all required raw-data inputs are present")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    graph = SurfaceGraphData(surface_graph, intervals)
    field = load_working_field(PlannerPackage(planner), args.build, graph.step_m)
    with np.load(topology / "component_maps.npz") as d:
        base_map = np.asarray(d["base_component_id"], dtype=np.int32)
        explicit_map = np.asarray(d["explicit_component_id"], dtype=np.int32)
        topology_component_id = np.asarray(d["topology_component_id"], dtype=np.int32)

    topo_nodes = load_csv(topology / "topology_nodes.csv")
    topo_meta = {int(r["node_id"]): r for r in topo_nodes}
    hazards = load_hazards(hazards_path)
    pois = load_csv(pois_path)

    snap_rows: list[dict] = []
    candidate_rows: list[dict] = []
    poi_to_node: list[int] = []
    poi_ids: list[str] = []

    for i, poi in enumerate(pois, 1):
        east, north, z = float(poi["east_m"]), float(poi["north_m"]), float(poi["elevation_m"])
        cands = snap_candidates(
            east=east, north=north, z=z,
            graph=graph, field=field, base_map=base_map, explicit_map=explicit_map,
            search_m=float(args.snap_search_m), keep_n=int(args.snap_candidates),
        )
        hf = hazard_facts(hazards.get(poi["poi_id"], {}))
        base = {
            "poi_id": poi["poi_id"], "poi_type": poi["poi_type"],
            "east_m": east, "north_m": north, "elevation_m": z, **hf,
        }
        if not cands:
            snap_rows.append({**base, "snap_status": "NO_TOPOLOGY_WITHIN_SEARCH", "selection_method": "nearest_3d"})
            poi_to_node.append(-1)
        else:
            for rank, c in enumerate(cands, 1):
                meta = topo_meta.get(c.topology_node_id, {})
                comp = int(topology_component_id[c.topology_node_id]) if c.topology_node_id < len(topology_component_id) else -1
                candidate_rows.append({
                    "poi_id": poi["poi_id"], "poi_type": poi["poi_type"],
                    "candidate_rank_by_3d": rank,
                    "topology_node_id": c.topology_node_id,
                    "snap_state_type": c.state_type, "snap_state_id": c.state_id,
                    "snapped_east_m": c.east_m, "snapped_north_m": c.north_m, "snapped_z_m": c.z_m,
                    "snap_plan_distance_m": c.plan_distance_m, "snap_dz_m": c.dz_m,
                    "snap_spatial_distance_m": c.spatial_distance_m,
                    "known_clearance_m": c.known_clearance_m,
                    "global_component_id": comp,
                    "global_component_rank": meta.get("global_component_rank"),
                })
            c = cands[0]
            meta = topo_meta.get(c.topology_node_id, {})
            comp = int(topology_component_id[c.topology_node_id]) if c.topology_node_id < len(topology_component_id) else -1
            snap_rows.append({
                **base, "snap_status": "SNAPPED", "selection_method": "nearest_3d",
                "topology_node_id": c.topology_node_id,
                "snap_state_type": c.state_type, "snap_state_id": c.state_id,
                "snapped_east_m": c.east_m, "snapped_north_m": c.north_m, "snapped_z_m": c.z_m,
                "snap_plan_distance_m": c.plan_distance_m, "snap_dz_m": c.dz_m,
                "snap_spatial_distance_m": c.spatial_distance_m,
                "known_clearance_m": c.known_clearance_m,
                "global_component_id": comp,
                "global_component_rank": meta.get("global_component_rank"),
            })
            poi_to_node.append(c.topology_node_id)
        poi_ids.append(poi["poi_id"])
        if i % 200 == 0 or i == len(pois):
            print(f"snapped POIs: {i:,}/{len(pois):,}")

    write_csv(out_dir / "poi_topology_snap.csv", SNAP_FIELDS, snap_rows)
    write_csv(out_dir / "poi_topology_snap_candidates.csv", CANDIDATE_FIELDS, candidate_rows)
    (out_dir / "poi_topology_snap.json").write_text(json.dumps(snap_rows, indent=2) + "\n", encoding="utf-8")

    suspicious = sorted(
        [r for r in snap_rows if r.get("snap_status") == "SNAPPED"],
        key=lambda r: (abs(float(r.get("snap_dz_m") or 0.0)), float(r.get("snap_plan_distance_m") or 0.0)),
        reverse=True,
    )[:100]
    write_csv(out_dir / "poi_snap_validation_candidates.csv", SNAP_FIELDS, suspicious)

    unique_nodes = np.array(sorted({x for x in poi_to_node if x >= 0}), dtype=np.int64)
    np.savez_compressed(
        out_dir / "poi_topology_node_index.npz",
        poi_ids=np.asarray(poi_ids, dtype="U64"),
        topology_node_id=np.asarray(poi_to_node, dtype=np.int64),
        unique_topology_node_ids=unique_nodes,
    )

    manifest = {
        "schema_version": 2,
        "layer": "raw_spatial_facts",
        "poi_count": len(snap_rows),
        "snapped_count": sum(r.get("snap_status") == "SNAPPED" for r in snap_rows),
        "unsnapped_count": sum(r.get("snap_status") != "SNAPPED" for r in snap_rows),
        "unique_poi_topology_nodes": int(len(unique_nodes)),
        "snap_search_m": float(args.snap_search_m),
        "snap_candidates_per_poi": int(args.snap_candidates),
        "primary_snap_selection": "nearest_3d geometric distance only",
        "distance_cache_written": False,
        "runtime_weights_embedded": False,
        "runtime_hazard_policy_embedded": False,
        "runtime_capability_policy_embedded": False,
        "surface_graph": str(surface_graph),
        "intervals": str(intervals),
        "topology_dir": str(topology),
        "pois": str(pois_path),
        "hazards": str(hazards_path),
        "notes": [
            "The contracted topology is still a structural FOOT topology and therefore reflects its build-time hard feasibility profile.",
            "topology_gateways.csv contains raw detailed crossings for runtime cost interpretation.",
            "No ramp count, connector cost, safe/unsafe label, or POI-pair shortest-path matrix is canonicalized here.",
        ],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
