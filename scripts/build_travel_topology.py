from __future__ import annotations

import argparse
import os
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import csv
import gc
import json
import math
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "satisfactory_route_tool" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from satisfactory_route_tool.heightfield import load_working_field
from satisfactory_route_tool.package import PlannerPackage
from satisfactory_route_tool.profiles import load_profile
from satisfactory_route_tool.surface_graph import SurfaceGraphData


MODE_CLEARANCE_M = {
    "foot": 2.0,
    "tractor": 4.5,
    "truck": 5.5,
    "rail": 8.0,
}
UNKNOWN_REGION_ID = 255


@dataclass
class RegionSampler:
    labels: np.ndarray
    names: dict[int, str]
    east_min_m: float
    north_max_m: float
    metres_per_texel: float

    def sample_grid(
        self,
        east0_m: float,
        north0_m: float,
        step_m: float,
        height: int,
        width: int,
    ) -> np.ndarray:
        east = east0_m + np.arange(width, dtype=np.float64) * step_m
        north = north0_m - np.arange(height, dtype=np.float64) * step_m
        cc = np.floor((east - self.east_min_m) / self.metres_per_texel).astype(np.int64)
        rr = np.floor((self.north_max_m - north) / self.metres_per_texel).astype(np.int64)
        cc = np.clip(cc, 0, self.labels.shape[1] - 1)
        rr = np.clip(rr, 0, self.labels.shape[0] - 1)
        return self.labels[rr[:, None], cc[None, :]]


class UnionFind:
    def __init__(self, n: int):
        self.parent = np.arange(n, dtype=np.int32)
        self.rank = np.zeros(n, dtype=np.uint8)

    def find(self, x: int) -> int:
        x = int(x)
        p = int(self.parent[x])
        while p != x:
            gp = int(self.parent[p])
            self.parent[x] = gp
            x = p
            p = gp
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Build a terrain-driven hierarchical travel topology from the fixed "
            "2 m hybrid surface graph. Named regions are optional annotations only."
        )
    )
    p.add_argument("--planner", default="planning_data")
    p.add_argument("--build", default="502094")
    p.add_argument("--surface-graph", required=True)
    p.add_argument("--intervals")
    p.add_argument("--profiles")
    p.add_argument("--mode", choices=["foot", "tractor", "truck", "rail"], default="tractor")
    p.add_argument("--bridge-policy", choices=["forbid", "allow"], default="forbid")
    p.add_argument("--minimum-clearance-m", type=float)
    p.add_argument(
        "--workers",
        type=int,
        default=min(4, os.cpu_count() or 1),
        help=(
            "process workers for independent sector contraction "
            "(default min(4, CPU count)); use 1 for serial debugging"
        ),
    )
    p.add_argument(
        "--sector-m",
        type=float,
        default=128.0,
        help=(
            "hierarchy sector size in metres. The value is rounded to an integer "
            "number of surface-graph cells; default 128 m = 64 cells on a 2 m graph."
        ),
    )
    p.add_argument("--region-raster", help="optional exact region_labels.npz")
    p.add_argument("--region-meta", help="optional region_raster_meta.json")
    p.add_argument(
        "--io-threads",
        type=int,
        default=4,
        help=(
            "threads for independent output serialization/writes "
            "(default 4; set 1 for serial output)"
        ),
    )
    p.add_argument(
        "--anchor",
        action="append",
        default=[],
        metavar="NAME,EAST_M,NORTH_M",
        help=(
            "optional routing anchor to map onto the contracted topology; "
            "repeatable, e.g. --anchor A,-2650.29,370.01"
        ),
    )
    p.add_argument(
        "--anchor-search-m",
        type=float,
        default=300.0,
        help=(
            "maximum plan-distance search for nearest routable base cell when "
            "an anchor lands on an unroutable cell (default 300 m)"
        ),
    )
    p.add_argument(
        "--write-component-maps",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "persist detailed-state -> topology-node maps for later hierarchical routing "
            "(default true)"
        ),
    )
    p.add_argument(
        "--out",
        default="planning_data/analysis/derived/world_travel_topology",
    )
    return p.parse_args()


def load_region_sampler(
    raster_path: str | None,
    meta_path: str | None,
) -> RegionSampler | None:
    if not raster_path and not meta_path:
        return None
    if not raster_path or not meta_path:
        raise ValueError("--region-raster and --region-meta must be supplied together")
    meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
    with np.load(raster_path) as d:
        labels = np.asarray(d["region_labels"], dtype=np.uint8)
    frame = meta["frame"]
    names = {
        int(k): str(v["display_name"])
        for k, v in meta["region_ids"].items()
    }
    return RegionSampler(
        labels=labels,
        names=names,
        east_min_m=float(frame["east_min_m"]),
        north_max_m=float(frame["north_max_m"]),
        metres_per_texel=float(frame["metres_per_texel"]),
    )


def deep_water_mask(field, profile: dict) -> np.ndarray:
    wet = field.water_q != 0
    depth = field.water_depth_m
    threshold = float(profile["deep_water_depth_m"])
    return wet & (~np.isfinite(depth) | (depth >= threshold))


def explicit_node_deep_water(graph, field, node_ids: np.ndarray, profile: dict) -> np.ndarray:
    node_ids = np.asarray(node_ids, dtype=np.int64)
    if len(node_ids) == 0:
        return np.zeros(0, dtype=bool)
    cells = graph._node_cell(node_ids)
    flat_q = field.water_q.reshape(-1)
    flat_depth = field.water_depth_m.reshape(-1)
    flat_z = field.z_m.reshape(-1)

    wet = flat_q[cells] != 0
    base_depth = flat_depth[cells]
    base_z = flat_z[cells]
    floor_z = np.asarray(graph.floor_z[node_ids], dtype=np.float32)

    state_depth = np.full(len(node_ids), np.nan, dtype=np.float32)
    known = wet & np.isfinite(base_depth) & np.isfinite(base_z)
    if np.any(known):
        water_level = base_z[known] + base_depth[known]
        state_depth[known] = np.maximum(water_level - floor_z[known], 0.0)

    threshold = float(profile["deep_water_depth_m"])
    return wet & (~np.isfinite(state_depth) | (state_depth >= threshold))


def _direction_slices(rows: int, cols: int, dr: int, dc: int):
    if dr >= 0:
        ra = slice(0, rows - dr)
        rb = slice(dr, rows)
    else:
        ra = slice(-dr, rows)
        rb = slice(0, rows + dr)
    if dc >= 0:
        ca = slice(0, cols - dc)
        cb = slice(dc, cols)
    else:
        ca = slice(-dc, cols)
        cb = slice(0, cols + dc)
    return (ra, ca), (rb, cb)


def _base_edge_ok(
    za: float,
    zb: float,
    horiz_m: float,
    hard_grade: float,
) -> bool:
    if not math.isfinite(za) or not math.isfinite(zb):
        return False
    return abs(zb - za) / horiz_m <= hard_grade + 1e-9


# Worker-local read-only state. Each spawned Windows process initializes this once.
_W_GRAPH = None
_W_FIELD = None
_W_PROFILE = None
_W_DEEP = None
_W_REGION_GRID = None
_W_MIN_CLEARANCE = None
_W_BRIDGE_POLICY = None


def process_sector_local(
    *,
    graph,
    field,
    profile: dict,
    deep_water: np.ndarray,
    region_grid: np.ndarray | None,
    rmin: int,
    rmax: int,
    cmin: int,
    cmax: int,
    sector_r: int,
    sector_c: int,
    min_clearance: float,
    bridge_policy: str,
) -> dict:
    """Reduce one sector and return only local component assignments.

    The worker never writes global component maps. That keeps multiprocessing
    deterministic and avoids writable shared memmaps/file locks on Windows.
    """
    rows = rmax - rmin
    cols = cmax - cmin
    overlay = graph.corridor(rmin, rmax, cmin, cmax)

    z = field.z_m[rmin:rmax, cmin:cmax]
    valid_base = np.isfinite(z)
    if bridge_policy == "forbid":
        valid_base &= ~deep_water[rmin:rmax, cmin:cmax]

    base_index = np.full((rows, cols), -1, dtype=np.int32)
    base_positions = np.argwhere(valid_base)
    if len(base_positions):
        base_index[base_positions[:, 0], base_positions[:, 1]] = np.arange(
            len(base_positions), dtype=np.int32
        )

    explicit_nodes = np.array(sorted(overlay.node_floor_z), dtype=np.int64)
    if len(explicit_nodes):
        clr = np.array(
            [overlay.node_clearance[int(n)] for n in explicit_nodes],
            dtype=np.float32,
        )
        feasible_explicit = ~np.isfinite(clr) | (clr + 1e-6 >= min_clearance)
        if bridge_policy == "forbid":
            feasible_explicit &= ~explicit_node_deep_water(
                graph, field, explicit_nodes, profile
            )
        explicit_nodes = explicit_nodes[feasible_explicit]

    nbase = len(base_positions)
    node_local = {
        int(node): nbase + i for i, node in enumerate(explicit_nodes.tolist())
    }
    uf = UnionFind(nbase + len(explicit_nodes))
    hard_grade = float(profile["grade_hard_block"])

    # Eight-way base connectivity, represented once with four undirected directions.
    for dr, dc, factor in (
        (0, 1, 1.0),
        (1, 0, 1.0),
        (1, 1, math.sqrt(2.0)),
        (1, -1, math.sqrt(2.0)),
    ):
        (sa_r, sa_c), (sb_r, sb_c) = _direction_slices(rows, cols, dr, dc)
        ia = base_index[sa_r, sa_c]
        ib = base_index[sb_r, sb_c]
        mask = (ia >= 0) & (ib >= 0)
        if not np.any(mask):
            continue
        za = z[sa_r, sa_c]
        zb = z[sb_r, sb_c]
        grade = np.abs(zb - za) / (field.step_m * factor)
        mask &= np.isfinite(grade) & (grade <= hard_grade + 1e-9)
        aa = ia[mask]
        bb = ib[mask]
        for va, vb in zip(aa.tolist(), bb.tolist()):
            uf.union(int(va), int(vb))

    # Explicit layered-surface edges internal to the sector.
    for u, links in overlay.explicit_adj.items():
        lu = node_local.get(int(u))
        if lu is None:
            continue
        for v, _dist, grade, clr, _relation in links:
            if int(u) >= int(v):
                continue
            lv = node_local.get(int(v))
            if lv is None:
                continue
            if grade > hard_grade + 1e-9:
                continue
            if math.isfinite(clr) and clr + 1e-6 < min_clearance:
                continue
            uf.union(lu, lv)

    # Base <-> explicit portals internal to the sector.
    for cell, links in overlay.base_to_node.items():
        gr, gc = divmod(int(cell), graph.width)
        rr, cc = gr - rmin, gc - cmin
        if not (0 <= rr < rows and 0 <= cc < cols):
            continue
        lb = int(base_index[rr, cc])
        if lb < 0:
            continue
        for node, _dist, grade, _relation in links:
            ln = node_local.get(int(node))
            if ln is None or grade > hard_grade + 1e-9:
                continue
            uf.union(lb, ln)

    groups: dict[int, list[int]] = defaultdict(list)
    for local_state in range(nbase + len(explicit_nodes)):
        groups[uf.find(local_state)].append(local_state)

    roots = sorted(groups)
    root_to_component = {root: i for i, root in enumerate(roots)}

    # Compact sector-sized local map; parent adds the deterministic global offset.
    base_local = np.full((rows, cols), -1, dtype=np.int32)
    for m, (rr, cc) in enumerate(base_positions):
        base_local[int(rr), int(cc)] = root_to_component[uf.find(m)]

    explicit_local = np.empty(len(explicit_nodes), dtype=np.int32)
    for i in range(len(explicit_nodes)):
        explicit_local[i] = root_to_component[uf.find(nbase + i)]

    explicit_cells = (
        graph._node_cell(explicit_nodes)
        if len(explicit_nodes)
        else np.empty(0, dtype=np.int64)
    )

    records: list[dict] = []
    for local_component_id, root in enumerate(roots):
        members = groups[root]
        base_members = [m for m in members if m < nbase]
        explicit_members = [m for m in members if m >= nbase]

        east_values: list[float] = []
        north_values: list[float] = []
        z_values: list[float] = []
        region_counts: Counter[int] = Counter()

        for m in base_members:
            rr, cc = base_positions[m]
            gr = rmin + int(rr)
            gc = cmin + int(cc)
            east_values.append(field.east0_m + gc * field.step_m)
            north_values.append(field.north0_m - gr * field.step_m)
            z_values.append(float(field.z_m[gr, gc]))
            if region_grid is not None:
                region_counts[int(region_grid[gr, gc])] += 1

        for m in explicit_members:
            ei = m - nbase
            node = int(explicit_nodes[ei])
            cell = int(explicit_cells[ei])
            gr, gc = divmod(cell, graph.width)
            east_values.append(field.east0_m + gc * field.step_m)
            north_values.append(field.north0_m - gr * field.step_m)
            z_values.append(float(graph.floor_z[node]))
            if region_grid is not None:
                region_counts[int(region_grid[gr, gc])] += 1

        region_id = (
            int(region_counts.most_common(1)[0][0])
            if region_counts
            else UNKNOWN_REGION_ID
        )
        records.append(
            {
                "node_id": local_component_id,  # parent converts to global id
                "sector_r": sector_r,
                "sector_c": sector_c,
                "state_count": len(members),
                "base_state_count": len(base_members),
                "explicit_state_count": len(explicit_members),
                "east_m": float(np.mean(east_values)),
                "north_m": float(np.mean(north_values)),
                "z_m": float(np.median(z_values)),
                "bbox_m": [
                    float(min(east_values)),
                    float(min(north_values)),
                    float(max(east_values)),
                    float(max(north_values)),
                ],
                "z_min_m": float(min(z_values)),
                "z_max_m": float(max(z_values)),
                "region_id": region_id,
                "region_counts": dict(
                    sorted((str(k), int(v)) for k, v in region_counts.items())
                ),
            }
        )

    return {
        "sector_r": sector_r,
        "sector_c": sector_c,
        "rmin": rmin,
        "rmax": rmax,
        "cmin": cmin,
        "cmax": cmax,
        "records": records,
        "base_local": base_local,
        "explicit_nodes": explicit_nodes,
        "explicit_local": explicit_local,
    }


def merge_sector_result(
    result: dict,
    *,
    global_component_start: int,
    base_component_map: np.ndarray,
    explicit_component_map: np.ndarray,
) -> tuple[list[dict], int]:
    """Assign deterministic global IDs and write one sector into parent-owned maps."""
    offset = int(global_component_start)
    records = result["records"]

    local = result["base_local"]
    target = base_component_map[
        result["rmin"]:result["rmax"],
        result["cmin"]:result["cmax"],
    ]
    valid = local >= 0
    target[valid] = local[valid] + offset

    nodes = result["explicit_nodes"]
    if len(nodes):
        explicit_component_map[nodes] = result["explicit_local"] + offset

    global_records: list[dict] = []
    for rec in records:
        out = dict(rec)
        out["node_id"] = int(rec["node_id"]) + offset
        global_records.append(out)
    return global_records, offset + len(records)


def _topology_worker_init(
    surface_graph: str,
    intervals: str | None,
    planner: str,
    build: str,
    mode: str,
    profiles: str | None,
    min_clearance: float,
    bridge_policy: str,
    region_raster: str | None,
    region_meta: str | None,
) -> None:
    """Initialize one spawned worker once; task payloads are only sector bounds."""
    global _W_GRAPH, _W_FIELD, _W_PROFILE, _W_DEEP
    global _W_REGION_GRID, _W_MIN_CLEARANCE, _W_BRIDGE_POLICY

    _W_GRAPH = SurfaceGraphData(surface_graph, intervals)
    pkg = PlannerPackage(planner)
    _W_FIELD = load_working_field(pkg, build, _W_GRAPH.step_m)
    if _W_FIELD.shape != (_W_GRAPH.height, _W_GRAPH.width):
        raise ValueError(
            f"worker WorkingField shape {_W_FIELD.shape} != surface graph "
            f"{(_W_GRAPH.height, _W_GRAPH.width)}"
        )
    _W_PROFILE = dict(load_profile(mode, profiles))
    _W_DEEP = deep_water_mask(_W_FIELD, _W_PROFILE)

    sampler = load_region_sampler(region_raster, region_meta)
    _W_REGION_GRID = (
        None
        if sampler is None
        else sampler.sample_grid(
            _W_GRAPH.east0_m,
            _W_GRAPH.north0_m,
            _W_GRAPH.step_m,
            _W_GRAPH.height,
            _W_GRAPH.width,
        )
    )
    _W_MIN_CLEARANCE = float(min_clearance)
    _W_BRIDGE_POLICY = bridge_policy


def _topology_worker_sector(task: tuple[int, int, int, int, int, int]) -> dict:
    sr, sc, rmin, rmax, cmin, cmax = task
    return process_sector_local(
        graph=_W_GRAPH,
        field=_W_FIELD,
        profile=_W_PROFILE,
        deep_water=_W_DEEP,
        region_grid=_W_REGION_GRID,
        rmin=rmin,
        rmax=rmax,
        cmin=cmin,
        cmax=cmax,
        sector_r=sr,
        sector_c=sc,
        min_clearance=_W_MIN_CLEARANCE,
        bridge_policy=_W_BRIDGE_POLICY,
    )



def _aggregate_link(
    links: dict[tuple[int, int], dict],
    a: int,
    b: int,
    *,
    source: str,
    distance_m: float,
    grade: float,
    clearance_m: float | None = None,
    relation: int | None = None,
) -> None:
    if a < 0 or b < 0 or a == b:
        return
    if a > b:
        a, b = b, a
    key = (a, b)
    rec = links.setdefault(
        key,
        {
            "u": a,
            "v": b,
            "crossing_count": 0,
            "base_count": 0,
            "explicit_count": 0,
            "portal_count": 0,
            "min_distance_m": math.inf,
            "min_grade": math.inf,
            "max_grade": 0.0,
            "min_known_clearance_m": math.inf,
            "component_relation_counts": Counter(),
        },
    )
    rec["crossing_count"] += 1
    rec[f"{source}_count"] += 1
    rec["min_distance_m"] = min(rec["min_distance_m"], float(distance_m))
    rec["min_grade"] = min(rec["min_grade"], float(grade))
    rec["max_grade"] = max(rec["max_grade"], float(grade))
    if clearance_m is not None and math.isfinite(clearance_m):
        rec["min_known_clearance_m"] = min(
            rec["min_known_clearance_m"], float(clearance_m)
        )
    if relation is not None:
        rec["component_relation_counts"][int(relation)] += 1


GATEWAY_FIELDS = [
    "gateway_id", "topology_u", "topology_v", "source",
    "u_state_type", "u_state_id", "u_east_m", "u_north_m", "u_z_m",
    "v_state_type", "v_state_id", "v_east_m", "v_north_m", "v_z_m",
    "distance_m", "delta_z_m", "grade", "known_clearance_m",
    "component_relation",
]


def _gateway_row(
    *,
    gateway_id: int,
    topo_a: int,
    topo_b: int,
    source: str,
    a_state_type: str,
    a_state_id: int,
    a_xyz: tuple[float, float, float],
    b_state_type: str,
    b_state_id: int,
    b_xyz: tuple[float, float, float],
    distance_m: float,
    grade: float,
    clearance_m: float | None = None,
    relation: int | None = None,
) -> dict:
    """Return one raw inter-component crossing in topology-id orientation.

    No player capability or preference is applied here.  The row records the
    detailed states and physical crossing facts so runtime profiles can derive
    their own costs later.
    """
    if topo_a <= topo_b:
        u_topo, v_topo = int(topo_a), int(topo_b)
        u_type, u_id, u_xyz = a_state_type, int(a_state_id), a_xyz
        v_type, v_id, v_xyz = b_state_type, int(b_state_id), b_xyz
    else:
        u_topo, v_topo = int(topo_b), int(topo_a)
        u_type, u_id, u_xyz = b_state_type, int(b_state_id), b_xyz
        v_type, v_id, v_xyz = a_state_type, int(a_state_id), a_xyz

    return {
        "gateway_id": int(gateway_id),
        "topology_u": u_topo,
        "topology_v": v_topo,
        "source": source,
        "u_state_type": u_type,
        "u_state_id": u_id,
        "u_east_m": float(u_xyz[0]),
        "u_north_m": float(u_xyz[1]),
        "u_z_m": float(u_xyz[2]),
        "v_state_type": v_type,
        "v_state_id": v_id,
        "v_east_m": float(v_xyz[0]),
        "v_north_m": float(v_xyz[1]),
        "v_z_m": float(v_xyz[2]),
        "distance_m": float(distance_m),
        "delta_z_m": float(v_xyz[2] - u_xyz[2]),
        "grade": float(grade),
        "known_clearance_m": (
            None if clearance_m is None or not math.isfinite(clearance_m)
            else float(clearance_m)
        ),
        "component_relation": None if relation is None else int(relation),
    }


def _write_gateway(writer: csv.DictWriter | None, row: dict) -> None:
    if writer is not None:
        writer.writerow({k: row.get(k) for k in GATEWAY_FIELDS})


def collect_cross_sector_links(
    *,
    graph,
    field,
    profile: dict,
    deep_water: np.ndarray,
    min_clearance: float,
    bridge_policy: str,
    base_component_map: np.ndarray,
    explicit_component_map: np.ndarray,
    gateway_csv_path: Path | None = None,
) -> tuple[list[dict], int]:
    """Collect cross-component topology links and lossless gateway facts.

    ``topology_edges`` remains a compact structural aggregate.  Every detailed
    crossing can additionally be streamed to ``gateway_csv_path`` so runtime
    weighting does not depend on min/max summaries baked at build time.
    """
    links: dict[tuple[int, int], dict] = {}
    gateway_count = 0
    gateway_file = None
    gateway_writer = None
    if gateway_csv_path is not None:
        gateway_csv_path.parent.mkdir(parents=True, exist_ok=True)
        gateway_file = gateway_csv_path.open("w", newline="", encoding="utf-8")
        gateway_writer = csv.DictWriter(gateway_file, fieldnames=GATEWAY_FIELDS)
        gateway_writer.writeheader()
    hard_grade = float(profile["grade_hard_block"])
    h, w = field.shape

    # Base 8-neighbor edges, globally vectorized by direction.
    for dr, dc, factor in (
        (0, 1, 1.0),
        (1, 0, 1.0),
        (1, 1, math.sqrt(2.0)),
        (1, -1, math.sqrt(2.0)),
    ):
        (sa_r, sa_c), (sb_r, sb_c) = _direction_slices(h, w, dr, dc)
        ca = base_component_map[sa_r, sa_c]
        cb = base_component_map[sb_r, sb_c]
        mask = (ca >= 0) & (cb >= 0) & (ca != cb)
        if not np.any(mask):
            continue
        za = field.z_m[sa_r, sa_c]
        zb = field.z_m[sb_r, sb_c]
        grade = np.abs(zb - za) / (field.step_m * factor)
        mask &= np.isfinite(grade) & (grade <= hard_grade + 1e-9)
        if bridge_policy == "forbid":
            mask &= ~deep_water[sa_r, sa_c] & ~deep_water[sb_r, sb_c]
        aa = ca[mask]
        bb = cb[mask]
        gg = grade[mask]
        dist = field.step_m * factor
        rr_local, cc_local = np.nonzero(mask)
        ra = rr_local + (sa_r.start or 0)
        ca_idx = cc_local + (sa_c.start or 0)
        rb = rr_local + (sb_r.start or 0)
        cb_idx = cc_local + (sb_c.start or 0)
        for a, b, g, r_a, c_a, r_b, c_b in zip(
            aa.tolist(), bb.tolist(), gg.tolist(),
            ra.tolist(), ca_idx.tolist(), rb.tolist(), cb_idx.tolist(),
        ):
            _aggregate_link(
                links, int(a), int(b),
                source="base", distance_m=dist, grade=float(g)
            )
            cell_a = int(r_a) * w + int(c_a)
            cell_b = int(r_b) * w + int(c_b)
            row = _gateway_row(
                gateway_id=gateway_count, topo_a=int(a), topo_b=int(b),
                source="base",
                a_state_type="base", a_state_id=cell_a,
                a_xyz=(
                    field.east0_m + int(c_a) * field.step_m,
                    field.north0_m - int(r_a) * field.step_m,
                    float(field.z_m[int(r_a), int(c_a)]),
                ),
                b_state_type="base", b_state_id=cell_b,
                b_xyz=(
                    field.east0_m + int(c_b) * field.step_m,
                    field.north0_m - int(r_b) * field.step_m,
                    float(field.z_m[int(r_b), int(c_b)]),
                ),
                distance_m=dist, grade=float(g),
            )
            _write_gateway(gateway_writer, row)
            gateway_count += 1

    # Explicit graph edges.
    for rec in graph.meta.get("directions", []):
        for shard in rec.get("edge_shards", []):
            with np.load(graph.graph_dir / shard["file"]) as d:
                u = np.asarray(d["u"], dtype=np.int64)
                v = np.asarray(d["v"], dtype=np.int64)
                dist = np.asarray(d["distance_m"], dtype=np.float32)
                grade = np.asarray(d["grade"], dtype=np.float32)
                clr = np.asarray(d["min_known_clearance_m"], dtype=np.float32)
                relation = (
                    np.asarray(d["component_relation"], dtype=np.uint8)
                    if "component_relation" in d
                    else np.full(len(u), 3, dtype=np.uint8)
                )

            cu = explicit_component_map[u]
            cv = explicit_component_map[v]
            mask = (cu >= 0) & (cv >= 0) & (cu != cv)
            mask &= grade <= hard_grade + 1e-9
            mask &= ~np.isfinite(clr) | (clr + 1e-6 >= min_clearance)
            if bridge_policy == "forbid" and np.any(mask):
                idx = np.flatnonzero(mask)
                du = explicit_node_deep_water(graph, field, u[idx], profile)
                dv = explicit_node_deep_water(graph, field, v[idx], profile)
                keep = ~(du | dv)
                newmask = np.zeros_like(mask)
                newmask[idx[keep]] = True
                mask = newmask

            um = u[mask]
            vm = v[mask]
            cells_u = graph._node_cell(um)
            cells_v = graph._node_cell(vm)
            for a, b, uu, vv, cell_u, cell_v, dd, gg, cc, rr in zip(
                cu[mask], cv[mask], um, vm, cells_u, cells_v,
                dist[mask], grade[mask], clr[mask], relation[mask]
            ):
                _aggregate_link(
                    links, int(a), int(b),
                    source="explicit", distance_m=float(dd), grade=float(gg),
                    clearance_m=float(cc), relation=int(rr)
                )
                cell_u = int(cell_u)
                cell_v = int(cell_v)
                eu, nu = graph.cell_to_world(cell_u)
                ev, nv = graph.cell_to_world(cell_v)
                row = _gateway_row(
                    gateway_id=gateway_count, topo_a=int(a), topo_b=int(b),
                    source="explicit",
                    a_state_type="explicit", a_state_id=int(uu),
                    a_xyz=(eu, nu, float(graph.floor_z[int(uu)])),
                    b_state_type="explicit", b_state_id=int(vv),
                    b_xyz=(ev, nv, float(graph.floor_z[int(vv)])),
                    distance_m=float(dd), grade=float(gg),
                    clearance_m=float(cc), relation=int(rr),
                )
                _write_gateway(gateway_writer, row)
                gateway_count += 1

    # Base <-> explicit portals.
    portal_dirs = list(graph.meta.get("portal_directions", []))
    if not portal_dirs:
        portal_dirs = list(graph.meta.get("directions", []))
    flat_base = base_component_map.reshape(-1)
    for rec in portal_dirs:
        for shard in rec.get("portal_shards", []):
            with np.load(graph.graph_dir / shard["file"]) as d:
                node = np.asarray(d["node"], dtype=np.int64)
                cell = np.asarray(d["implicit_cell_index"], dtype=np.int64)
                dist = np.asarray(d["distance_m"], dtype=np.float32)
                grade = np.asarray(d["grade"], dtype=np.float32)
                relation = (
                    np.asarray(d["component_relation"], dtype=np.uint8)
                    if "component_relation" in d
                    else np.full(len(node), 3, dtype=np.uint8)
                )

            cn = explicit_component_map[node]
            cb = flat_base[cell]
            clr = np.asarray(graph.clearance[node], dtype=np.float32)
            mask = (cn >= 0) & (cb >= 0) & (cn != cb)
            mask &= grade <= hard_grade + 1e-9
            mask &= ~np.isfinite(clr) | (clr + 1e-6 >= min_clearance)
            if bridge_policy == "forbid" and np.any(mask):
                idx = np.flatnonzero(mask)
                dn = explicit_node_deep_water(graph, field, node[idx], profile)
                db = deep_water.reshape(-1)[cell[idx]]
                keep = ~(dn | db)
                newmask = np.zeros_like(mask)
                newmask[idx[keep]] = True
                mask = newmask

            nm = node[mask]
            cm = cell[mask]
            node_cells = graph._node_cell(nm)
            for a, b, nn, node_cell, cellid, dd, gg, cc, rr in zip(
                cn[mask], cb[mask], nm, node_cells, cm,
                dist[mask], grade[mask], clr[mask], relation[mask]
            ):
                _aggregate_link(
                    links, int(a), int(b),
                    source="portal", distance_m=float(dd), grade=float(gg),
                    clearance_m=float(cc), relation=int(rr)
                )
                en, nnorth = graph.cell_to_world(int(node_cell))
                eb, bnorth = graph.cell_to_world(int(cellid))
                row = _gateway_row(
                    gateway_id=gateway_count, topo_a=int(a), topo_b=int(b),
                    source="portal",
                    a_state_type="explicit", a_state_id=int(nn),
                    a_xyz=(en, nnorth, float(graph.floor_z[int(nn)])),
                    b_state_type="base", b_state_id=int(cellid),
                    b_xyz=(eb, bnorth, float(field.z_m.reshape(-1)[int(cellid)])),
                    distance_m=float(dd), grade=float(gg),
                    clearance_m=float(cc), relation=int(rr),
                )
                _write_gateway(gateway_writer, row)
                gateway_count += 1

    rows: list[dict] = []
    for key in sorted(links):
        rec = links[key]
        if math.isinf(rec["min_known_clearance_m"]):
            rec["min_known_clearance_m"] = None
        if math.isinf(rec["min_grade"]):
            rec["min_grade"] = None
        rec["component_relation_counts"] = {
            str(k): int(v)
            for k, v in sorted(rec["component_relation_counts"].items())
        }
        rows.append(rec)
    if gateway_file is not None:
        gateway_file.close()
    return rows, gateway_count



def parse_anchor_specs(specs: list[str]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for spec in specs:
        parts = [p.strip() for p in str(spec).split(",")]
        if len(parts) != 3:
            raise ValueError(
                f"--anchor must be NAME,EAST_M,NORTH_M; got {spec!r}"
            )
        name = parts[0]
        if not name:
            raise ValueError(f"--anchor name is blank in {spec!r}")
        if name in seen:
            raise ValueError(f"duplicate --anchor name {name!r}")
        seen.add(name)
        out.append(
            {
                "name": name,
                "east_m": float(parts[1]),
                "north_m": float(parts[2]),
            }
        )
    return out


def derive_global_components(
    nodes: list[dict],
    edges: list[dict],
    *,
    region_names: dict[int, str],
) -> tuple[list[dict], np.ndarray]:
    """Connected components of the contracted topology graph.

    This is intentionally a second-stage structural analysis. It does not alter
    the raw contracted topology or invent links between disconnected pieces.
    """
    n = len(nodes)
    uf = UnionFind(n)
    for e in edges:
        uf.union(int(e["u"]), int(e["v"]))

    root_to_members: dict[int, list[int]] = defaultdict(list)
    for node_id in range(n):
        root_to_members[uf.find(node_id)].append(node_id)

    # Rank by detailed-state coverage, not merely topology-node count.
    raw: list[dict] = []
    for root, members in root_to_members.items():
        state_count = int(sum(int(nodes[i]["state_count"]) for i in members))
        base_count = int(sum(int(nodes[i]["base_state_count"]) for i in members))
        explicit_count = int(
            sum(int(nodes[i]["explicit_state_count"]) for i in members)
        )
        east_min = min(float(nodes[i]["bbox_m"][0]) for i in members)
        north_min = min(float(nodes[i]["bbox_m"][1]) for i in members)
        east_max = max(float(nodes[i]["bbox_m"][2]) for i in members)
        north_max = max(float(nodes[i]["bbox_m"][3]) for i in members)

        region_counts: Counter[int] = Counter()
        degree_sum = 0
        isolated_nodes = 0
        for i in members:
            degree_sum += int(nodes[i].get("degree", 0))
            if int(nodes[i].get("degree", 0)) == 0:
                isolated_nodes += 1
            for rid, count in nodes[i].get("region_counts", {}).items():
                region_counts[int(rid)] += int(count)

        raw.append(
            {
                "root": int(root),
                "topology_node_count": len(members),
                "detailed_state_count": state_count,
                "base_state_count": base_count,
                "explicit_state_count": explicit_count,
                "edge_count": degree_sum // 2,
                "isolated_topology_nodes": isolated_nodes,
                "bbox_m": [east_min, north_min, east_max, north_max],
                "region_counts": dict(
                    sorted((str(k), int(v)) for k, v in region_counts.items())
                ),
                "member_node_ids": members,
            }
        )

    raw.sort(
        key=lambda c: (
            -int(c["detailed_state_count"]),
            -int(c["topology_node_count"]),
            int(c["root"]),
        )
    )

    membership = np.full(n, -1, dtype=np.int32)
    components: list[dict] = []
    for rank, rec in enumerate(raw, start=1):
        component_id = rank - 1
        members = rec.pop("member_node_ids")
        for node_id in members:
            membership[node_id] = component_id

        region_counts = {
            int(k): int(v) for k, v in rec["region_counts"].items()
        }
        dominant_region_id = (
            max(region_counts, key=region_counts.get)
            if region_counts
            else UNKNOWN_REGION_ID
        )

        if rank == 1:
            structural_class = "PRIMARY_WORLD_NETWORK"
        elif int(rec["topology_node_count"]) == 1 and int(rec["edge_count"]) == 0:
            structural_class = "ISOLATED_TOPOLOGY_NODE"
        else:
            structural_class = "CONNECTED_SECONDARY"

        components.append(
            {
                "component_id": component_id,
                "rank_by_detailed_states": rank,
                "structural_class": structural_class,
                "topology_node_count": int(rec["topology_node_count"]),
                "detailed_state_count": int(rec["detailed_state_count"]),
                "base_state_count": int(rec["base_state_count"]),
                "explicit_state_count": int(rec["explicit_state_count"]),
                "edge_count": int(rec["edge_count"]),
                "isolated_topology_nodes": int(rec["isolated_topology_nodes"]),
                "bbox_m": rec["bbox_m"],
                "dominant_region_id": int(dominant_region_id),
                "dominant_region_name": region_names.get(
                    int(dominant_region_id), ""
                ),
                "region_counts": rec["region_counts"],
            }
        )

    return components, membership


def map_anchors_to_topology(
    anchors: list[dict],
    *,
    field,
    base_component_map: np.ndarray,
    topology_component_membership: np.ndarray,
    components: list[dict],
    search_m: float,
) -> list[dict]:
    """Snap each XY anchor to the nearest routable implicit-base cell."""
    if not anchors:
        return []

    h, w = field.shape
    radius_cells = max(0, int(math.ceil(float(search_m) / field.step_m)))
    out: list[dict] = []

    for anchor in anchors:
        east = float(anchor["east_m"])
        north = float(anchor["north_m"])
        c0 = int(round((east - field.east0_m) / field.step_m))
        r0 = int(round((field.north0_m - north) / field.step_m))

        best = None
        rlo = max(0, r0 - radius_cells)
        rhi = min(h - 1, r0 + radius_cells)
        clo = max(0, c0 - radius_cells)
        chi = min(w - 1, c0 + radius_cells)

        for rr in range(rlo, rhi + 1):
            north_r = field.north0_m - rr * field.step_m
            dy = north_r - north
            if abs(dy) > search_m:
                continue
            for cc in range(clo, chi + 1):
                topo_node = int(base_component_map[rr, cc])
                if topo_node < 0:
                    continue
                east_c = field.east0_m + cc * field.step_m
                dx = east_c - east
                d2 = dx * dx + dy * dy
                if d2 > search_m * search_m:
                    continue
                candidate = (d2, rr, cc, topo_node)
                if best is None or candidate < best:
                    best = candidate

        if best is None:
            out.append(
                {
                    **anchor,
                    "status": "NO_ROUTABLE_BASE_WITHIN_SEARCH",
                    "search_m": float(search_m),
                    "snap_distance_m": None,
                    "snapped_east_m": None,
                    "snapped_north_m": None,
                    "topology_node_id": None,
                    "global_component_id": None,
                    "global_component_rank": None,
                    "structural_class": None,
                }
            )
            continue

        d2, rr, cc, topo_node = best
        comp_id = int(topology_component_membership[topo_node])
        comp = components[comp_id]
        out.append(
            {
                **anchor,
                "status": "SNAPPED",
                "search_m": float(search_m),
                "snap_distance_m": round(math.sqrt(float(d2)), 3),
                "snapped_east_m": float(field.east0_m + cc * field.step_m),
                "snapped_north_m": float(field.north0_m - rr * field.step_m),
                "topology_node_id": int(topo_node),
                "global_component_id": comp_id,
                "global_component_rank": int(comp["rank_by_detailed_states"]),
                "structural_class": comp["structural_class"],
            }
        )

    return out


def write_components_csv(path: Path, components: list[dict]) -> None:
    fields = [
        "component_id",
        "rank_by_detailed_states",
        "structural_class",
        "topology_node_count",
        "detailed_state_count",
        "base_state_count",
        "explicit_state_count",
        "edge_count",
        "isolated_topology_nodes",
        "dominant_region_id",
        "dominant_region_name",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for rec in components:
            w.writerow({k: rec.get(k) for k in fields})


def write_anchors_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        "name",
        "east_m",
        "north_m",
        "status",
        "search_m",
        "snap_distance_m",
        "snapped_east_m",
        "snapped_north_m",
        "topology_node_id",
        "global_component_id",
        "global_component_rank",
        "structural_class",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for rec in rows:
            w.writerow({k: rec.get(k) for k in fields})


def _write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def write_nodes_csv(path: Path, nodes: list[dict], region_names: dict[int, str]) -> None:
    fields = [
        "node_id", "sector_r", "sector_c", "state_count",
        "base_state_count", "explicit_state_count",
        "east_m", "north_m", "z_m", "z_min_m", "z_max_m",
        "region_id", "region_name",
        "global_component_id", "global_component_rank",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for n in nodes:
            row = {k: n.get(k) for k in fields}
            rid = int(n["region_id"])
            row["region_name"] = region_names.get(rid, "")
            w.writerow(row)


def write_edges_csv(path: Path, edges: list[dict]) -> None:
    fields = [
        "u", "v", "crossing_count", "base_count", "explicit_count",
        "portal_count", "min_distance_m", "min_grade", "max_grade",
        "min_known_clearance_m",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for e in edges:
            w.writerow({k: e.get(k) for k in fields})


def write_map(path: Path, field, nodes: list[dict], edges: list[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xy = np.array([[n["east_m"], n["north_m"]] for n in nodes], dtype=float)
    by_id = {int(n["node_id"]): n for n in nodes}

    fig, ax = plt.subplots(figsize=(12, 12))
    # Draw only topology edges; detailed terrain stays out of the picture so the
    # amount of contraction is visually obvious.
    for e in edges:
        a = by_id[int(e["u"])]
        b = by_id[int(e["v"])]
        ax.plot(
            [a["east_m"], b["east_m"]],
            [a["north_m"], b["north_m"]],
            linewidth=0.35,
            alpha=0.25,
        )
    if len(xy):
        sizes = np.clip(
            np.sqrt(np.array([n["state_count"] for n in nodes], dtype=float)) * 2.0,
            3.0, 30.0,
        )
        ax.scatter(xy[:, 0], xy[:, 1], s=sizes)
    ax.set_title("Terrain-driven travel topology")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    graph = SurfaceGraphData(args.surface_graph, args.intervals)
    pkg = PlannerPackage(args.planner)
    field = load_working_field(pkg, args.build, graph.step_m)
    if field.shape != (graph.height, graph.width):
        raise ValueError(
            f"WorkingField shape {field.shape} != surface graph "
            f"{(graph.height, graph.width)}"
        )

    profile = dict(load_profile(args.mode, args.profiles))
    min_clearance = (
        float(args.minimum_clearance_m)
        if args.minimum_clearance_m is not None
        else MODE_CLEARANCE_M[args.mode]
    )
    deep = deep_water_mask(field, profile)

    region_sampler = load_region_sampler(args.region_raster, args.region_meta)
    region_grid = (
        None
        if region_sampler is None
        else region_sampler.sample_grid(
            graph.east0_m, graph.north0_m, graph.step_m,
            graph.height, graph.width
        )
    )
    region_names = {} if region_sampler is None else region_sampler.names

    sector_cells = max(1, int(round(float(args.sector_m) / graph.step_m)))
    sector_m = sector_cells * graph.step_m
    sector_rows = math.ceil(graph.height / sector_cells)
    sector_cols = math.ceil(graph.width / sector_cells)

    print(
        f"grid {graph.width}x{graph.height} @ {graph.step_m:g} m; "
        f"sectors {sector_cols}x{sector_rows} @ {sector_m:g} m"
    )

    with tempfile.TemporaryDirectory(prefix="travel_topology_") as td:
        td = Path(td)
        base_map = np.memmap(
            td / "base_component_id.i32",
            dtype=np.int32,
            mode="w+",
            shape=field.shape,
        )
        base_map[:] = -1
        explicit_map = np.memmap(
            td / "explicit_component_id.i32",
            dtype=np.int32,
            mode="w+",
            shape=(len(graph.floor_z),),
        )
        explicit_map[:] = -1

        nodes: list[dict] = []
        next_id = 0

        tasks: list[tuple[int, int, int, int, int, int]] = []
        for sr in range(sector_rows):
            rmin = sr * sector_cells
            rmax = min(graph.height, rmin + sector_cells)
            for sc in range(sector_cols):
                cmin = sc * sector_cells
                cmax = min(graph.width, cmin + sector_cells)
                tasks.append((sr, sc, rmin, rmax, cmin, cmax))

        total_sectors = len(tasks)
        workers = max(1, int(args.workers))
        print(
            f"contracting {total_sectors} sectors with {workers} "
            f"{'worker' if workers == 1 else 'workers'}..."
        )

        if workers == 1:
            result_iter = (
                process_sector_local(
                    graph=graph,
                    field=field,
                    profile=profile,
                    deep_water=deep,
                    region_grid=region_grid,
                    rmin=rmin,
                    rmax=rmax,
                    cmin=cmin,
                    cmax=cmax,
                    sector_r=sr,
                    sector_c=sc,
                    min_clearance=min_clearance,
                    bridge_policy=args.bridge_policy,
                )
                for sr, sc, rmin, rmax, cmin, cmax in tasks
            )
            executor = None
        else:
            # Explicit spawn matches Windows behavior even when tested elsewhere.
            # executor.map preserves task order, so global topology IDs remain
            # identical regardless of which worker finishes first.
            ctx = mp.get_context("spawn")
            executor = ProcessPoolExecutor(
                max_workers=workers,
                mp_context=ctx,
                initializer=_topology_worker_init,
                initargs=(
                    str(args.surface_graph),
                    args.intervals,
                    str(args.planner),
                    str(args.build),
                    str(args.mode),
                    args.profiles,
                    float(min_clearance),
                    str(args.bridge_policy),
                    args.region_raster,
                    args.region_meta,
                ),
            )
            result_iter = executor.map(
                _topology_worker_sector,
                tasks,
                chunksize=1,
            )

        try:
            for done, result in enumerate(result_iter, start=1):
                recs, next_id = merge_sector_result(
                    result,
                    global_component_start=next_id,
                    base_component_map=base_map,
                    explicit_component_map=explicit_map,
                )
                nodes.extend(recs)
                if done % 50 == 0 or done == total_sectors:
                    print(
                        f"  sectors {done}/{total_sectors}; "
                        f"topology nodes {next_id:,}"
                    )
        finally:
            if executor is not None:
                executor.shutdown(wait=True, cancel_futures=True)

        base_map.flush()
        explicit_map.flush()

        print("collecting cross-sector topology edges...")
        edges, gateway_count = collect_cross_sector_links(
            graph=graph,
            field=field,
            profile=profile,
            deep_water=deep,
            min_clearance=min_clearance,
            bridge_policy=args.bridge_policy,
            base_component_map=base_map,
            explicit_component_map=explicit_map,
            gateway_csv_path=out_dir / "topology_gateways.csv",
        )

        # Degree is useful for seeing where actual decisions occur.
        degree = np.zeros(len(nodes), dtype=np.int32)
        for e in edges:
            degree[int(e["u"])] += 1
            degree[int(e["v"])] += 1
        for n in nodes:
            n["degree"] = int(degree[int(n["node_id"])])

        print("deriving global connected travel components...")
        components, topology_component_membership = derive_global_components(
            nodes,
            edges,
            region_names=region_names,
        )
        for n in nodes:
            cid = int(topology_component_membership[int(n["node_id"])])
            n["global_component_id"] = cid
            n["global_component_rank"] = int(
                components[cid]["rank_by_detailed_states"]
            )

        anchors = parse_anchor_specs(args.anchor)
        anchor_rows = map_anchors_to_topology(
            anchors,
            field=field,
            base_component_map=base_map,
            topology_component_membership=topology_component_membership,
            components=components,
            search_m=float(args.anchor_search_m),
        )

        # Independent large outputs are serialized/written concurrently. Threads
        # are appropriate here because this stage is file-I/O heavy and shares the
        # already-built in-process objects without duplicating world arrays.
        io_threads = max(1, int(args.io_threads))
        write_jobs = [
            (_write_json, out_dir / "topology_nodes.json", nodes),
            (_write_json, out_dir / "topology_edges.json", edges),
            (_write_json, out_dir / "topology_components.json", components),
            (_write_json, out_dir / "anchor_components.json", anchor_rows),
            (write_nodes_csv, out_dir / "topology_nodes.csv", nodes, region_names),
            (write_edges_csv, out_dir / "topology_edges.csv", edges),
            (write_components_csv, out_dir / "topology_components.csv", components),
            (write_anchors_csv, out_dir / "anchor_components.csv", anchor_rows),
        ]

        if io_threads == 1:
            for job in write_jobs:
                fn, *job_args = job
                fn(*job_args)
        else:
            with ThreadPoolExecutor(max_workers=io_threads) as pool:
                futures = []
                for job in write_jobs:
                    fn, *job_args = job
                    futures.append(pool.submit(fn, *job_args))
                for fut in futures:
                    fut.result()

        write_map(out_dir / "topology_map.png", field, nodes, edges)

        # Preserve detailed-state -> topology-node mappings and add the second-stage
        # topology-node -> global-component mapping.
        if args.write_component_maps:
            np.savez_compressed(
                out_dir / "component_maps.npz",
                base_component_id=np.asarray(base_map),
                explicit_component_id=np.asarray(explicit_map),
                topology_component_id=topology_component_membership,
            )

        # Output files are already written above.

        # Windows will not let TemporaryDirectory remove an mmap-backed file while
        # NumPy still has the mapping open. Flush and explicitly close the mappings
        # before leaving this context.
        base_map.flush()
        explicit_map.flush()

        base_mmap = getattr(base_map, "_mmap", None)
        explicit_mmap = getattr(explicit_map, "_mmap", None)

        del base_map
        del explicit_map
        gc.collect()

        if base_mmap is not None:
            base_mmap.close()
        if explicit_mmap is not None:
            explicit_mmap.close()

        del base_mmap
        del explicit_mmap
        gc.collect()

    region_transition_edges = 0
    same_region_edges = 0
    for e in edges:
        a = nodes[int(e["u"])]["region_id"]
        b = nodes[int(e["v"])]["region_id"]
        if a != UNKNOWN_REGION_ID and b != UNKNOWN_REGION_ID and a != b:
            region_transition_edges += 1
        elif a == b:
            same_region_edges += 1

    degree_values = np.array([n["degree"] for n in nodes], dtype=np.int32)
    state_counts = np.array([n["state_count"] for n in nodes], dtype=np.int64)
    summary = {
        "schema_version": 2,
        "build": args.build,
        "mode": args.mode,
        "bridge_policy": args.bridge_policy,
        "minimum_clearance_m": min_clearance,
        "surface_graph": str(Path(args.surface_graph)),
        "intervals": args.intervals,
        "sector_cells": sector_cells,
        "sector_m": sector_m,
        "workers": max(1, int(args.workers)),
        "sector_parallelism": "spawned process workers; deterministic ordered parent merge",
        "sector_rows": sector_rows,
        "sector_cols": sector_cols,
        "topology_nodes": len(nodes),
        "topology_edges": len(edges),
        "topology_gateways": int(gateway_count),
        "global_connected_components": len(components),
        "primary_component": (
            components[0] if components else None
        ),
        "anchors": anchor_rows,
        "io_threads": max(1, int(args.io_threads)),
        "detailed_states_assigned": int(state_counts.sum()) if len(state_counts) else 0,
        "mean_states_per_topology_node": (
            float(state_counts.mean()) if len(state_counts) else 0.0
        ),
        "median_states_per_topology_node": (
            float(np.median(state_counts)) if len(state_counts) else 0.0
        ),
        "degree": {
            "mean": float(degree_values.mean()) if len(degree_values) else 0.0,
            "median": float(np.median(degree_values)) if len(degree_values) else 0.0,
            "max": int(degree_values.max()) if len(degree_values) else 0,
            "dead_ends": int(np.sum(degree_values == 1)),
            "degree_2": int(np.sum(degree_values == 2)),
            "junctions_ge_3": int(np.sum(degree_values >= 3)),
        },
        "region_annotation": {
            "enabled": region_sampler is not None,
            "same_region_edges": same_region_edges,
            "cross_region_edges": region_transition_edges,
            "note": (
                "Region labels annotate the terrain-derived topology after contraction; "
                "they do not create nodes or edges."
            ),
        },
        "method": {
            "sector_contraction": (
                "Within each fixed spatial sector, all mode-feasible base cells, explicit "
                "surface nodes, explicit edges and base<->explicit portals are unioned into "
                "local connected components. One topology node is emitted per component."
            ),
            "topology_edges": (
                "Any feasible detailed edge whose endpoints contract to different topology "
                "nodes becomes an aggregated structural edge. Aggregate min/max values are "
                "descriptive facts, not runtime travel costs."
            ),
            "topology_gateways": (
                "Every feasible detailed crossing between contracted topology nodes is emitted "
                "losslessly to topology_gateways.csv with endpoint state IDs, XYZ, distance, "
                "delta-Z, grade, clearance and component relation. Runtime profiles derive costs."
            ),
            "why": (
                "This is terrain-driven hierarchical contraction. It makes no assumption "
                "that biome boundaries, roads or hand-identified passes are decision points."
            ),
        },
    }
    if summary["primary_component"] is not None:
        pc = dict(summary["primary_component"])
        pc.pop("region_counts", None)
        summary["primary_component"] = pc

    (out_dir / "topology_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"wrote {out_dir}: {len(nodes):,} topology nodes, "
        f"{len(edges):,} topology edges, {gateway_count:,} raw gateways"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
