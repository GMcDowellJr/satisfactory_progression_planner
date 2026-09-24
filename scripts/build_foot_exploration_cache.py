"""Build terrain-aware foot-travel lookup products for exploration POIs.

This script does not compute a detailed route for every POI pair. Instead it:

1. consumes (or optionally builds) the contracted foot travel topology;
2. snaps every canonical exploration POI to the best nearby detailed/base surface,
   then maps that surface to a topology node;
3. records local vertical/access cost (including optional 4 m ramp construction);
4. builds a shortest-path distance matrix only between topology nodes actually used
   by POIs; and
5. writes a compact index that lets the expedition planner evaluate POI A -> B as

       connector(A) + topology_distance(nodeA, nodeB) + connector(B)

The expensive work is static and is intended to be run once per game build.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "satisfactory_route_tool" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from satisfactory_route_tool.heightfield import load_working_field
from satisfactory_route_tool.package import PlannerPackage
from satisfactory_route_tool.surface_graph import SurfaceGraphData


ALPHA_TOKENS = ("Alpha",)


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
    ramp_count: int
    connector_cost_m: float
    score: float


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--planner", default="planning_data")
    p.add_argument("--build", default="502094")
    p.add_argument(
        "--surface-graph",
        default="data/local/spatial/surface_graph",
        help="hybrid surface graph directory produced by build_surface_graph.py",
    )
    p.add_argument(
        "--intervals",
        default="data/local/spatial/multisurface/vertical_intervals.npz",
        help="vertical_intervals.npz used by the surface graph",
    )
    p.add_argument(
        "--topology-dir",
        default="planning_data/analysis/derived/world_foot_topology",
        help="directory containing/receiving build_travel_topology.py outputs",
    )
    p.add_argument(
        "--pois",
        default="planning_data/world/canonical/exploration_pois.csv",
    )
    p.add_argument(
        "--hazards",
        default="planning_data/game/reference/exploration_poi_hazards.csv",
    )
    p.add_argument(
        "--out",
        default="planning_data/analysis/derived/foot_exploration_cache",
    )
    p.add_argument("--build-topology", action="store_true")
    p.add_argument(
        "--bootstrap-base-only",
        action="store_true",
        help=(
            "if the local layered surface artifacts are absent, create a base-terrain-only "
            "surface graph from the checked-in heightmap, then continue. This is sufficient "
            "for the first foot-routing cache and requires no new game-data extraction."
        ),
    )
    p.add_argument(
        "--base-step-m",
        type=float,
        default=8.0,
        help="grid step for --bootstrap-base-only (default 8 m)",
    )
    p.add_argument("--surface-workers", type=int, default=1)
    p.add_argument("--topology-workers", type=int, default=1)
    p.add_argument("--sector-m", type=float, default=128.0)
    p.add_argument("--snap-search-m", type=float, default=160.0)
    p.add_argument(
        "--vertical-weight",
        type=float,
        default=1.0,
        help="connector cost metres added per metre of vertical mismatch",
    )
    p.add_argument(
        "--ramp-height-m",
        type=float,
        default=4.0,
        help="vertical rise represented by one buildable ramp",
    )
    p.add_argument(
        "--ramp-penalty-m",
        type=float,
        default=8.0,
        help="equivalent travel-cost metres per required 4 m ramp",
    )
    p.add_argument(
        "--ramps-available",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    p.add_argument(
        "--max-no-ramp-dz-m",
        type=float,
        default=8.0,
        help="local vertical mismatch allowed when ramps are unavailable",
    )
    p.add_argument("--foot-clearance-m", type=float, default=2.0)
    p.add_argument(
        "--topology-grade-soft-start",
        type=float,
        default=0.75,
    )
    p.add_argument(
        "--topology-grade-penalty",
        type=float,
        default=1.5,
    )
    p.add_argument("--dijkstra-batch", type=int, default=64)
    p.add_argument("--skip-distance-cache", action="store_true")
    p.add_argument(
        "--validate-only",
        action="store_true",
        help="validate required inputs and report what would run",
    )
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


def load_hazards(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    for row in load_csv(path):
        raw = row.get("hazard_json", "").strip()
        try:
            hazard = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid hazard_json for {row.get('poi_id')}: {exc}") from exc
        out[row["poi_id"]] = hazard
    return out


def hazard_flags(h: dict) -> dict:
    hostiles = h.get("hostiles_nearby") or {}
    has_alpha = any(any(tok in str(k) for tok in ALPHA_TOKENS) for k in hostiles)
    return {
        "has_alpha_hostile": bool(has_alpha),
        "inside_spore_flower_damage_sphere": bool(h.get("inside_spore_flower_damage_sphere", False)),
        "nearest_hostile_m": _cm_to_m(h.get("nearest_hostile_cm")),
        "nearest_gas_m": _cm_to_m(h.get("nearest_gas_cm")),
        "nearest_uranium_m": _cm_to_m(h.get("nearest_uranium_cm")),
        "nearest_nuclear_hog_spawner_m": _cm_to_m(h.get("nearest_nuclear_hog_spawner_cm")),
        "hazard_json": json.dumps(h, separators=(",", ":"), sort_keys=True),
    }


def _cm_to_m(v):
    if v is None:
        return None
    try:
        return round(float(v) / 100.0, 3)
    except (TypeError, ValueError):
        return None


def bootstrap_base_only(args: argparse.Namespace, planner: Path, surface_graph: Path, intervals: Path) -> None:
    if (surface_graph / "meta.json").exists() and intervals.exists():
        return
    if not args.bootstrap_base_only:
        return

    spatial_root = intervals.parent.parent
    expected_graph = spatial_root / "surface_graph"
    if surface_graph.resolve() != expected_graph.resolve():
        raise ValueError(
            "--bootstrap-base-only expects --surface-graph to be <spatial-root>/surface_graph "
            f"and --intervals to be <spatial-root>/multisurface/vertical_intervals.npz; got {surface_graph} and {intervals}"
        )

    source_height = planner / f"world/spatial/heightmap_build_{args.build}"
    require(source_height / "meta.json", "checked-in heightmap metadata")
    require(source_height / "height.i16.z", "checked-in heightmap")

    height_dir = spatial_root / "heightmap"
    multi_dir = spatial_root / "multisurface"
    height_dir.mkdir(parents=True, exist_ok=True)
    multi_dir.mkdir(parents=True, exist_ok=True)

    for name in ("meta.json", "height.i16.z", "prov.u8.z", "water.i16.z", "waterq.u8.z"):
        src = source_height / name
        if src.exists():
            shutil.copy2(src, height_dir / name)

    meta = json.loads((source_height / "meta.json").read_text(encoding="utf-8"))
    g = meta["grid"]
    native_step = float(g["spacing_cm"]) / 100.0
    stride = int(round(float(args.base_step_m) / native_step))
    if stride < 1 or abs(stride * native_step - float(args.base_step_m)) > 1e-6:
        raise ValueError(
            f"--base-step-m {args.base_step_m} must be a whole multiple of native {native_step} m"
        )
    width = int(math.ceil(int(g["width"]) / stride))
    height = int(math.ceil(int(g["height"]) / stride))
    east0 = float(g["x0_cm"]) / 100.0
    north0 = -float(g["y0_cm"]) / 100.0

    np.savez_compressed(
        intervals,
        schema_version=np.array([3], dtype=np.int32),
        step_m=np.array([stride * native_step], dtype=np.float32),
        east0_m=np.array([east0], dtype=np.float64),
        north0_m=np.array([north0], dtype=np.float64),
        width=np.array([width], dtype=np.int32),
        height=np.array([height], dtype=np.int32),
        cell_index=np.empty(0, dtype=np.int64),
        interval_offsets=np.array([0], dtype=np.int64),
        floor_z_m=np.empty(0, dtype=np.float32),
        floor_component_id=np.empty(0, dtype=np.int32),
        clearance_m=np.empty(0, dtype=np.float32),
    )

    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "build_surface_graph.py"),
        "--spatial-root", str(spatial_root),
        "--out", str(surface_graph),
        "--workers", str(max(1, args.surface_workers)),
    ]
    if surface_graph.exists():
        cmd.append("--force")
    print("bootstrapping base-only surface graph:")
    print(" ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def maybe_build_topology(args: argparse.Namespace, surface_graph: Path, intervals: Path, topology: Path) -> None:
    required = [topology / "topology_nodes.csv", topology / "topology_edges.csv", topology / "component_maps.npz"]
    if all(p.exists() for p in required):
        return
    if not args.build_topology:
        missing = ", ".join(str(p) for p in required if not p.exists())
        raise FileNotFoundError(
            "foot topology outputs are missing. Either run scripts/build_travel_topology.py "
            f"first or pass --build-topology. Missing: {missing}"
        )
    require(surface_graph / "meta.json", "surface graph")
    require(intervals, "vertical intervals")
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
    print("building foot topology:")
    print(" ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def _ramp_count(abs_dz_m: float, args: argparse.Namespace) -> int:
    if abs_dz_m <= 1e-6:
        return 0
    if not args.ramps_available:
        return 0
    return int(math.ceil(abs_dz_m / max(args.ramp_height_m, 1e-6)))


def _connector_cost(plan_m: float, dz_m: float, args: argparse.Namespace) -> tuple[float, int] | None:
    adz = abs(float(dz_m))
    if (not args.ramps_available) and adz > args.max_no_ramp_dz_m:
        return None
    ramps = _ramp_count(adz, args)
    cost = float(plan_m) + adz * float(args.vertical_weight)
    if args.ramps_available:
        cost += ramps * float(args.ramp_penalty_m)
    return cost, ramps


def snap_poi(
    *,
    east: float,
    north: float,
    z: float,
    graph: SurfaceGraphData,
    field,
    base_map: np.ndarray,
    explicit_map: np.ndarray,
    args: argparse.Namespace,
) -> SnapCandidate | None:
    r0, c0 = graph.world_to_rc(east, north)
    radius_cells = int(math.ceil(args.snap_search_m / graph.step_m))
    rlo = max(0, r0 - radius_cells)
    rhi = min(graph.height - 1, r0 + radius_cells)
    clo = max(0, c0 - radius_cells)
    chi = min(graph.width - 1, c0 + radius_cells)

    best: SnapCandidate | None = None

    for rr in range(rlo, rhi + 1):
        north_c = graph.north0_m - rr * graph.step_m
        dy = north_c - north
        if abs(dy) > args.snap_search_m:
            continue
        for cc in range(clo, chi + 1):
            east_c = graph.east0_m + cc * graph.step_m
            dx = east_c - east
            plan_m = math.hypot(dx, dy)
            if plan_m > args.snap_search_m:
                continue

            # Base terrain state.
            topo = int(base_map[rr, cc])
            base_z = float(field.z_m[rr, cc])
            if topo >= 0 and math.isfinite(base_z):
                dz = z - base_z
                ccost = _connector_cost(plan_m, dz, args)
                if ccost is not None:
                    cost, ramps = ccost
                    cand = SnapCandidate(
                        topology_node_id=topo,
                        state_type="base",
                        state_id=rr * graph.width + cc,
                        east_m=east_c,
                        north_m=north_c,
                        z_m=base_z,
                        plan_distance_m=plan_m,
                        dz_m=dz,
                        ramp_count=ramps,
                        connector_cost_m=cost,
                        score=cost,
                    )
                    if best is None or (cand.score, cand.plan_distance_m, abs(cand.dz_m)) < (
                        best.score, best.plan_distance_m, abs(best.dz_m)
                    ):
                        best = cand

            # Explicit/layered surface states in the same 2 m column.
            cell = rr * graph.width + cc
            nodes = graph.nodes_for_cell(cell)
            for node in nodes.tolist():
                if node < 0 or node >= len(explicit_map):
                    continue
                topo = int(explicit_map[node])
                if topo < 0:
                    continue
                if float(graph.clearance[node]) < args.foot_clearance_m:
                    continue
                floor_z = float(graph.floor_z[node])
                dz = z - floor_z
                ccost = _connector_cost(plan_m, dz, args)
                if ccost is None:
                    continue
                cost, ramps = ccost
                cand = SnapCandidate(
                    topology_node_id=topo,
                    state_type="explicit",
                    state_id=int(node),
                    east_m=east_c,
                    north_m=north_c,
                    z_m=floor_z,
                    plan_distance_m=plan_m,
                    dz_m=dz,
                    ramp_count=ramps,
                    connector_cost_m=cost,
                    score=cost,
                )
                if best is None or (cand.score, cand.plan_distance_m, abs(cand.dz_m)) < (
                    best.score, best.plan_distance_m, abs(best.dz_m)
                ):
                    best = cand

    return best


def write_snap_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "poi_id", "poi_type", "east_m", "north_m", "elevation_m",
        "snap_status", "topology_node_id", "topology_cache_index",
        "snap_state_type", "snap_state_id", "snapped_east_m", "snapped_north_m",
        "snapped_z_m", "snap_plan_distance_m", "snap_dz_m", "estimated_4m_ramps",
        "connector_cost_m", "global_component_id", "global_component_rank",
        "has_alpha_hostile", "inside_spore_flower_damage_sphere",
        "nearest_hostile_m", "nearest_gas_m", "nearest_uranium_m",
        "nearest_nuclear_hog_spawner_m", "hazard_json",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def topology_graph(nodes_path: Path, edges_path: Path, args: argparse.Namespace):
    nodes = load_csv(nodes_path)
    edges = load_csv(edges_path)
    by_id = {int(r["node_id"]): r for r in nodes}
    node_ids = np.array(sorted(by_id), dtype=np.int64)
    id_to_ix = {int(n): i for i, n in enumerate(node_ids.tolist())}

    rr: list[int] = []
    cc: list[int] = []
    ww: list[float] = []
    for e in edges:
        u = int(e["u"])
        v = int(e["v"])
        if u not in id_to_ix or v not in id_to_ix:
            continue
        a = by_id[u]
        b = by_id[v]
        dx = float(a["east_m"]) - float(b["east_m"])
        dy = float(a["north_m"]) - float(b["north_m"])
        dz = float(a["z_m"]) - float(b["z_m"])
        horizontal = math.hypot(dx, dy)
        spatial = math.hypot(horizontal, dz)
        min_cross = float(e.get("min_distance_m") or 0.0)
        base = max(spatial, min_cross, 1e-3)
        grade = abs(dz) / max(horizontal, 1e-3)
        excess = max(0.0, grade - float(args.topology_grade_soft_start))
        cost = base * (1.0 + excess * float(args.topology_grade_penalty))
        ui = id_to_ix[u]
        vi = id_to_ix[v]
        rr.extend((ui, vi))
        cc.extend((vi, ui))
        ww.extend((cost, cost))

    graph = coo_matrix((np.asarray(ww, np.float64), (rr, cc)), shape=(len(node_ids), len(node_ids))).tocsr()
    return node_ids, id_to_ix, graph, by_id


def build_distance_cache(
    *,
    graph_csr,
    node_ids: np.ndarray,
    id_to_ix: dict[int, int],
    used_topology_ids: list[int],
    batch: int,
) -> tuple[np.ndarray, np.ndarray]:
    used = np.array(sorted(set(int(x) for x in used_topology_ids)), dtype=np.int64)
    source_ix = np.array([id_to_ix[int(x)] for x in used], dtype=np.int64)
    k = len(used)
    out = np.full((k, k), np.inf, dtype=np.float32)
    batch = max(1, int(batch))
    for start in range(0, k, batch):
        stop = min(k, start + batch)
        rows = dijkstra(graph_csr, directed=False, indices=source_ix[start:stop], return_predecessors=False)
        out[start:stop, :] = np.asarray(rows[:, source_ix], dtype=np.float32)
        print(f"distance cache: {stop:,}/{k:,} source topology nodes")
    return used, out


def main() -> int:
    args = parse_args()
    planner = resolve(args.planner)
    surface_graph = resolve(args.surface_graph)
    intervals = resolve(args.intervals)
    topology = resolve(args.topology_dir)
    pois_path = resolve(args.pois)
    hazards_path = resolve(args.hazards)
    out_dir = resolve(args.out)

    require(planner / f"world/spatial/heightmap_build_{args.build}/height.i16.z", "planner heightmap")
    require(pois_path, "canonical POIs")
    require(hazards_path, "POI hazards")
    bootstrap_base_only(args, planner, surface_graph, intervals)
    require(surface_graph / "meta.json", "surface graph")
    require(intervals, "vertical intervals")

    maybe_build_topology(args, surface_graph, intervals, topology)
    for p, label in [
        (topology / "topology_nodes.csv", "topology nodes"),
        (topology / "topology_edges.csv", "topology edges"),
        (topology / "component_maps.npz", "topology component maps"),
    ]:
        require(p, label)

    if args.validate_only:
        print("all required inputs are present")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    graph = SurfaceGraphData(surface_graph, intervals)
    pkg = PlannerPackage(planner)
    field = load_working_field(pkg, args.build, graph.step_m)
    if field.shape != (graph.height, graph.width):
        raise ValueError(f"height field {field.shape} != surface graph {(graph.height, graph.width)}")

    with np.load(topology / "component_maps.npz") as d:
        base_map = np.asarray(d["base_component_id"], dtype=np.int32)
        explicit_map = np.asarray(d["explicit_component_id"], dtype=np.int32)
        topology_component_id = np.asarray(d["topology_component_id"], dtype=np.int32)
    if base_map.shape != field.shape:
        raise ValueError(f"base component map {base_map.shape} != field {field.shape}")
    if len(explicit_map) != len(graph.floor_z):
        raise ValueError("explicit component map length does not match surface graph node count")

    topo_nodes = load_csv(topology / "topology_nodes.csv")
    topo_meta = {int(r["node_id"]): r for r in topo_nodes}
    hazards = load_hazards(hazards_path)
    pois = load_csv(pois_path)

    rows: list[dict] = []
    snapped_ids: list[int] = []
    for i, poi in enumerate(pois, 1):
        east = float(poi["east_m"])
        north = float(poi["north_m"])
        z = float(poi["elevation_m"])
        snap = snap_poi(
            east=east,
            north=north,
            z=z,
            graph=graph,
            field=field,
            base_map=base_map,
            explicit_map=explicit_map,
            args=args,
        )
        hf = hazard_flags(hazards.get(poi["poi_id"], {}))
        row = {
            "poi_id": poi["poi_id"],
            "poi_type": poi["poi_type"],
            "east_m": east,
            "north_m": north,
            "elevation_m": z,
            **hf,
            "topology_cache_index": None,
        }
        if snap is None:
            row.update({"snap_status": "NO_TOPOLOGY_WITHIN_SEARCH"})
        else:
            meta = topo_meta.get(snap.topology_node_id, {})
            comp = int(topology_component_id[snap.topology_node_id]) if snap.topology_node_id < len(topology_component_id) else -1
            row.update({
                "snap_status": "SNAPPED",
                "topology_node_id": snap.topology_node_id,
                "snap_state_type": snap.state_type,
                "snap_state_id": snap.state_id,
                "snapped_east_m": round(snap.east_m, 3),
                "snapped_north_m": round(snap.north_m, 3),
                "snapped_z_m": round(snap.z_m, 3),
                "snap_plan_distance_m": round(snap.plan_distance_m, 3),
                "snap_dz_m": round(snap.dz_m, 3),
                "estimated_4m_ramps": snap.ramp_count,
                "connector_cost_m": round(snap.connector_cost_m, 3),
                "global_component_id": comp,
                "global_component_rank": meta.get("global_component_rank"),
            })
            snapped_ids.append(snap.topology_node_id)
        rows.append(row)
        if i % 200 == 0 or i == len(pois):
            print(f"snapped POIs: {i:,}/{len(pois):,}")

    cache_node_ids = np.array(sorted(set(snapped_ids)), dtype=np.int64)
    distance_matrix = None
    if not args.skip_distance_cache and len(cache_node_ids):
        all_node_ids, id_to_ix, graph_csr, _ = topology_graph(
            topology / "topology_nodes.csv", topology / "topology_edges.csv", args
        )
        missing = [int(x) for x in cache_node_ids if int(x) not in id_to_ix]
        if missing:
            raise ValueError(f"snapped topology nodes absent from topology_nodes.csv: {missing[:10]}")
        cache_node_ids, distance_matrix = build_distance_cache(
            graph_csr=graph_csr,
            node_ids=all_node_ids,
            id_to_ix=id_to_ix,
            used_topology_ids=cache_node_ids.tolist(),
            batch=args.dijkstra_batch,
        )
        cache_ix = {int(n): i for i, n in enumerate(cache_node_ids.tolist())}
        for row in rows:
            if row.get("snap_status") == "SNAPPED":
                row["topology_cache_index"] = cache_ix[int(row["topology_node_id"])]
        np.savez_compressed(
            out_dir / "foot_topology_distance_cache.npz",
            topology_node_ids=cache_node_ids,
            distance_m=distance_matrix,
        )

    write_snap_csv(out_dir / "poi_topology_snap.csv", rows)
    (out_dir / "poi_topology_snap.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8", newline="\n")

    suspicious = sorted(
        [r for r in rows if r.get("snap_status") == "SNAPPED"],
        key=lambda r: (int(r.get("estimated_4m_ramps") or 0), abs(float(r.get("snap_dz_m") or 0.0)), float(r.get("snap_plan_distance_m") or 0.0)),
        reverse=True,
    )[:50]
    write_snap_csv(out_dir / "poi_snap_validation_candidates.csv", suspicious)

    counts = {
        "poi_count": len(rows),
        "snapped_count": sum(r.get("snap_status") == "SNAPPED" for r in rows),
        "unsnapped_count": sum(r.get("snap_status") != "SNAPPED" for r in rows),
        "unique_poi_topology_nodes": int(len(cache_node_ids)),
        "distance_cache_written": bool(distance_matrix is not None),
        "ramps_available": bool(args.ramps_available),
        "ramp_height_m": float(args.ramp_height_m),
        "ramp_penalty_m": float(args.ramp_penalty_m),
        "snap_search_m": float(args.snap_search_m),
        "surface_graph": str(surface_graph),
        "intervals": str(intervals),
        "topology_dir": str(topology),
        "pois": str(pois_path),
        "hazards": str(hazards_path),
    }
    (out_dir / "manifest.json").write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(json.dumps(counts, indent=2))
    print(f"wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
