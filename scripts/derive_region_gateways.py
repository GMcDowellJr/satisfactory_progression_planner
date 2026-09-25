from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "satisfactory_route_tool" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from satisfactory_route_tool.heightfield import (
    PROV_CLIFF_VALUES,
    load_working_field,
)
from satisfactory_route_tool.package import PlannerPackage
from satisfactory_route_tool.profiles import load_profile
from satisfactory_route_tool.surface_graph import SurfaceGraphData


DEFAULT_OUT = "planning_data/analysis/derived/world_topology"
UNKNOWN_REGION_ID = 255
NO_MANS_LAND = "No Man's Land"

# Four undirected raster-neighbor directions are enough to represent all 8-way
# connectivity once. The matching reverse edges are implicit.
BASE_DIRECTIONS = (
    (0, 1, 1.0, "E"),
    (1, 0, 1.0, "S"),
    (1, 1, math.sqrt(2.0), "SE"),
    (1, -1, math.sqrt(2.0), "SW"),
)

MODE_CLEARANCE_M = {
    "foot": 2.0,
    "tractor": 4.5,
    "truck": 5.5,
    "rail": 8.0,
}


@dataclass
class RegionRaster:
    palette: np.ndarray
    region: np.ndarray
    meta: dict
    region_names: dict[int, str]
    palette_meta: dict[int, dict]

    @property
    def height(self) -> int:
        return int(self.region.shape[0])

    @property
    def width(self) -> int:
        return int(self.region.shape[1])

    @property
    def frame(self) -> dict:
        return self.meta["frame"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Derive exact region/sub-area adjacency and traversable inter-region "
            "gateways from the game region raster plus the layered surface graph."
        )
    )
    p.add_argument("--planner", default="planning_data")
    p.add_argument("--build", default="502094")
    p.add_argument("--region-raster", required=True, help="region_labels.npz")
    p.add_argument("--region-meta", required=True, help="region_raster_meta.json")
    p.add_argument("--surface-graph", required=True)
    p.add_argument("--intervals")
    p.add_argument("--roads", help="optional road prior NPZ with road and road_band arrays")
    p.add_argument("--profiles")
    p.add_argument("--mode", choices=["foot", "tractor", "truck", "rail"], default="tractor")
    p.add_argument("--bridge-policy", choices=["forbid", "allow"], default="forbid")
    p.add_argument("--minimum-clearance-m", type=float)
    p.add_argument(
        "--cluster-gap-m",
        type=float,
        default=24.0,
        help=(
            "maximum gap between neighboring crossing samples in one gateway cluster. "
            "Continuous 2 m boundary crossings chain into one broad gateway."
        ),
    )
    p.add_argument(
        "--min-candidates",
        type=int,
        default=3,
        help="minimum crossing samples required to publish a gateway",
    )
    p.add_argument(
        "--include-no-mans-land",
        action="store_true",
        help="include named-region <-> No Man's Land crossings as gateways",
    )
    p.add_argument(
        "--include-unknown",
        action="store_true",
        help="include region id 255 in exact adjacency products",
    )
    p.add_argument("--out", default=DEFAULT_OUT)
    return p.parse_args()


def load_region_raster(npz_path: Path, meta_path: Path) -> RegionRaster:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    with np.load(npz_path) as d:
        palette = np.asarray(d["palette_labels"], dtype=np.uint8)
        region = np.asarray(d["region_labels"], dtype=np.uint8)

    if palette.shape != region.shape:
        raise ValueError(
            f"palette_labels {palette.shape} != region_labels {region.shape}"
        )
    expected = tuple(meta["arrays"]["region_labels"]["shape"])
    if tuple(region.shape) != expected:
        raise ValueError(
            f"region raster shape {region.shape} != metadata shape {expected}"
        )

    region_names = {
        int(k): str(v["display_name"])
        for k, v in meta["region_ids"].items()
    }
    palette_meta = {
        int(rec["palette_index"]): rec
        for rec in meta["palette_entries"]
    }
    return RegionRaster(
        palette=palette,
        region=region,
        meta=meta,
        region_names=region_names,
        palette_meta=palette_meta,
    )


def native_adjacency(
    labels: np.ndarray,
    *,
    pixel_m: float,
    include_unknown: bool,
) -> dict[tuple[int, int], dict]:
    """Count exact native-raster boundaries between label pairs.

    E/W and N/S boundaries are scanned once each. Boundary length is therefore a
    physical line length in metres, not a count of 8-neighbor contacts.
    """
    out: dict[tuple[int, int], dict] = {}

    def accumulate(a: np.ndarray, b: np.ndarray, orientation: str) -> None:
        mask = a != b
        if not include_unknown:
            mask &= (a != UNKNOWN_REGION_ID) & (b != UNKNOWN_REGION_ID)
        if not np.any(mask):
            return

        lo = np.minimum(a[mask], b[mask]).astype(np.uint16)
        hi = np.maximum(a[mask], b[mask]).astype(np.uint16)
        packed = (lo << 8) | hi
        keys, counts = np.unique(packed, return_counts=True)
        for packed_key, count in zip(keys.tolist(), counts.tolist()):
            x = int(packed_key)
            pair = ((x >> 8) & 255, x & 255)
            rec = out.setdefault(
                pair,
                {
                    "boundary_edges": 0,
                    "boundary_length_m": 0.0,
                    "vertical_edges": 0,
                    "horizontal_edges": 0,
                },
            )
            rec["boundary_edges"] += int(count)
            rec["boundary_length_m"] += float(count) * pixel_m
            if orientation == "vertical":
                rec["vertical_edges"] += int(count)
            else:
                rec["horizontal_edges"] += int(count)

    # Adjacent columns share a vertical boundary segment.
    accumulate(labels[:, :-1], labels[:, 1:], "vertical")
    # Adjacent rows share a horizontal boundary segment.
    accumulate(labels[:-1, :], labels[1:, :], "horizontal")
    return out


def sample_region_grid(
    raster: RegionRaster,
    *,
    east0_m: float,
    north0_m: float,
    step_m: float,
    height: int,
    width: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Nearest-texel sample of exact region/palette labels onto the graph grid."""
    f = raster.frame
    px = float(f["metres_per_texel"])
    east_min = float(f["east_min_m"])
    north_max = float(f["north_max_m"])

    east = east0_m + np.arange(width, dtype=np.float64) * step_m
    north = north0_m - np.arange(height, dtype=np.float64) * step_m

    cc = np.floor((east - east_min) / px).astype(np.int64)
    rr = np.floor((north_max - north) / px).astype(np.int64)
    cc = np.clip(cc, 0, raster.width - 1)
    rr = np.clip(rr, 0, raster.height - 1)

    return (
        raster.region[rr[:, None], cc[None, :]],
        raster.palette[rr[:, None], cc[None, :]],
    )


def resample_road_prior(path: Path | None, field) -> tuple[np.ndarray, np.ndarray]:
    if path is None:
        return np.zeros(field.shape, bool), np.zeros(field.shape, bool)

    with np.load(path) as d:
        road = np.asarray(d["road"]).astype(bool)
        band = np.asarray(d["road_band"]).astype(bool)
        step = float(np.asarray(d["step_m"]).ravel()[0])
        e0 = float(np.asarray(d["east0_m"]).ravel()[0])
        n0 = float(np.asarray(d["north0_m"]).ravel()[0])

    rr = np.arange(field.shape[0])
    cc = np.arange(field.shape[1])
    north = field.north0_m - rr * field.step_m
    east = field.east0_m + cc * field.step_m
    sr = np.rint((n0 - north) / step).astype(int)
    sc = np.rint((east - e0) / step).astype(int)
    sr = np.clip(sr, 0, road.shape[0] - 1)
    sc = np.clip(sc, 0, road.shape[1] - 1)
    return road[sr[:, None], sc[None, :]], band[sr[:, None], sc[None, :]]


def deep_water_mask(field, profile: dict) -> np.ndarray:
    wet = field.water_q != 0
    depth = field.water_depth_m
    threshold = float(profile["deep_water_depth_m"])
    return wet & (~np.isfinite(depth) | (depth >= threshold))


def _slice_pair(shape: tuple[int, int], dr: int, dc: int):
    h, w = shape
    if dr >= 0:
        ra = slice(0, h - dr)
        rb = slice(dr, h)
    else:
        ra = slice(-dr, h)
        rb = slice(0, h + dr)

    if dc >= 0:
        ca = slice(0, w - dc)
        cb = slice(dc, w)
    else:
        ca = slice(-dc, w)
        cb = slice(0, w + dc)
    return (ra, ca), (rb, cb)


def _road_flags(
    roads_a: np.ndarray,
    roads_b: np.ndarray,
    band_a: np.ndarray,
    band_b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    road = roads_a & roads_b
    band = (roads_a | band_a) & (roads_b | band_b)
    return road, band


def base_crossing_candidates(
    field,
    region_grid: np.ndarray,
    palette_grid: np.ndarray,
    roads: np.ndarray,
    road_band: np.ndarray,
    profile: dict,
    *,
    bridge_policy: str,
    include_no_mans_land: bool,
    no_mans_land_id: int | None,
) -> list[dict]:
    """Vectorized scan of traversable implicit-base edges crossing region boundaries."""
    out: list[dict] = []
    z = field.z_m
    hard_grade = float(profile["grade_hard_block"])
    deep = deep_water_mask(field, profile)

    for dr, dc, dist_factor, direction in BASE_DIRECTIONS:
        (sa_r, sa_c), (sb_r, sb_c) = _slice_pair(field.shape, dr, dc)

        za = z[sa_r, sa_c]
        zb = z[sb_r, sb_c]
        ra = region_grid[sa_r, sa_c]
        rb = region_grid[sb_r, sb_c]
        pa = palette_grid[sa_r, sa_c]
        pb = palette_grid[sb_r, sb_c]

        mask = np.isfinite(za) & np.isfinite(zb)
        mask &= ra != rb
        mask &= (ra != UNKNOWN_REGION_ID) & (rb != UNKNOWN_REGION_ID)

        if not include_no_mans_land and no_mans_land_id is not None:
            mask &= (ra != no_mans_land_id) & (rb != no_mans_land_id)

        horiz = field.step_m * dist_factor
        grade = np.abs(zb - za) / horiz
        mask &= np.isfinite(grade) & (grade <= hard_grade + 1e-9)

        if bridge_policy == "forbid":
            mask &= ~deep[sa_r, sa_c] & ~deep[sb_r, sb_c]

        if not np.any(mask):
            continue

        roads_same, band_same = _road_flags(
            roads[sa_r, sa_c],
            roads[sb_r, sb_c],
            road_band[sa_r, sa_c],
            road_band[sb_r, sb_c],
        )

        rr, cc = np.nonzero(mask)
        # Convert local slice indexes back to global indexes.
        row_a0 = 0 if dr >= 0 else -dr
        row_b0 = dr if dr >= 0 else 0
        col_a0 = 0 if dc >= 0 else -dc
        col_b0 = dc if dc >= 0 else 0

        ga_r = rr + row_a0
        gb_r = rr + row_b0
        ga_c = cc + col_a0
        gb_c = cc + col_b0

        east_a = field.east0_m + ga_c * field.step_m
        east_b = field.east0_m + gb_c * field.step_m
        north_a = field.north0_m - ga_r * field.step_m
        north_b = field.north0_m - gb_r * field.step_m

        sel_grade = grade[mask]
        sel_ra = ra[mask]
        sel_rb = rb[mask]
        sel_pa = pa[mask]
        sel_pb = pb[mask]
        sel_road = roads_same[mask]
        sel_band = band_same[mask]
        sel_za = za[mask]
        sel_zb = zb[mask]

        for i in range(len(sel_grade)):
            out.append(
                {
                    "source": "base",
                    "region_a": int(sel_ra[i]),
                    "region_b": int(sel_rb[i]),
                    "palette_a": int(sel_pa[i]),
                    "palette_b": int(sel_pb[i]),
                    "east_m": float((east_a[i] + east_b[i]) * 0.5),
                    "north_m": float((north_a[i] + north_b[i]) * 0.5),
                    "z_m": float((sel_za[i] + sel_zb[i]) * 0.5),
                    "distance_m": float(horiz),
                    "grade": float(sel_grade[i]),
                    "road": bool(sel_road[i]),
                    "road_band": bool(sel_band[i]),
                    "min_clearance_m": None,
                    "component_relation": None,
                    "direction": direction,
                }
            )
    return out


def node_cells(graph: SurfaceGraphData, node_ids: np.ndarray) -> np.ndarray:
    pos = np.searchsorted(graph.offsets, node_ids, side="right") - 1
    return graph.cells[pos]


def _grid_value(flat: np.ndarray, cell: np.ndarray) -> np.ndarray:
    return flat[cell]



def node_deep_water(
    graph: SurfaceGraphData,
    field,
    node_ids: np.ndarray,
    profile: dict,
) -> np.ndarray:
    """Deep-water test for explicit surface nodes, matching graph_solver semantics."""
    node_ids = np.asarray(node_ids, dtype=np.int64)
    cells = node_cells(graph, node_ids)
    q = field.water_q.reshape(-1)[cells]
    base_depth = field.water_depth_m.reshape(-1)[cells]
    base_z = field.z_m.reshape(-1)[cells]
    floor_z = np.asarray(graph.floor_z[node_ids], dtype=np.float32)

    wet = q != 0
    state_depth = np.full(len(node_ids), np.nan, dtype=np.float32)

    known = wet & np.isfinite(base_depth) & np.isfinite(base_z)
    if np.any(known):
        water_level = base_z[known] + base_depth[known]
        state_depth[known] = np.maximum(water_level - floor_z[known], 0.0)

    threshold = float(profile["deep_water_depth_m"])
    # Unknown water depth remains conservatively deep; a node above a known water
    # surface becomes dry, exactly as in graph_solver._water_for_state().
    return wet & (~np.isfinite(state_depth) | (state_depth >= threshold))


def _candidate_rows_from_graph_arrays(
    *,
    source: str,
    cell_a: np.ndarray,
    cell_b: np.ndarray,
    distance: np.ndarray,
    grade: np.ndarray,
    clearance: np.ndarray | None,
    relation: np.ndarray | None,
    region_flat: np.ndarray,
    palette_flat: np.ndarray,
    roads_flat: np.ndarray,
    band_flat: np.ndarray,
    field,
    graph,
    hard_grade: float,
    min_clearance: float,
    deep_a: np.ndarray,
    deep_b: np.ndarray,
    bridge_policy: str,
    include_no_mans_land: bool,
    no_mans_land_id: int | None,
) -> list[dict]:
    if len(cell_a) == 0:
        return []

    reg_a = _grid_value(region_flat, cell_a)
    reg_b = _grid_value(region_flat, cell_b)
    mask = reg_a != reg_b
    mask &= (reg_a != UNKNOWN_REGION_ID) & (reg_b != UNKNOWN_REGION_ID)
    mask &= np.isfinite(grade) & (grade <= hard_grade + 1e-9)

    if not include_no_mans_land and no_mans_land_id is not None:
        mask &= (reg_a != no_mans_land_id) & (reg_b != no_mans_land_id)

    if clearance is not None:
        known = np.isfinite(clearance)
        mask &= ~known | (clearance + 1e-6 >= min_clearance)

    if bridge_policy == "forbid":
        mask &= ~deep_a & ~deep_b

    idx = np.flatnonzero(mask)
    if len(idx) == 0:
        return []

    ca = cell_a[idx]
    cb = cell_b[idx]
    ra = ca // graph.width
    cola = ca % graph.width
    rb = cb // graph.width
    colb = cb % graph.width

    east = (
        (field.east0_m + cola * field.step_m)
        + (field.east0_m + colb * field.step_m)
    ) * 0.5
    north = (
        (field.north0_m - ra * field.step_m)
        + (field.north0_m - rb * field.step_m)
    ) * 0.5

    road = roads_flat[ca] & roads_flat[cb]
    band = (roads_flat[ca] | band_flat[ca]) & (
        roads_flat[cb] | band_flat[cb]
    )

    za = field.z_m.reshape(-1)[ca]
    zb = field.z_m.reshape(-1)[cb]
    zmid = np.nanmean(np.stack([za, zb], axis=1), axis=1)

    rows: list[dict] = []
    for j, ii in enumerate(idx.tolist()):
        rows.append(
            {
                "source": source,
                "region_a": int(reg_a[ii]),
                "region_b": int(reg_b[ii]),
                "palette_a": int(palette_flat[cell_a[ii]]),
                "palette_b": int(palette_flat[cell_b[ii]]),
                "east_m": float(east[j]),
                "north_m": float(north[j]),
                "z_m": float(zmid[j]) if np.isfinite(zmid[j]) else None,
                "distance_m": float(distance[ii]),
                "grade": float(grade[ii]),
                "road": bool(road[j]),
                "road_band": bool(band[j]),
                "min_clearance_m": (
                    None
                    if clearance is None or not np.isfinite(clearance[ii])
                    else float(clearance[ii])
                ),
                "component_relation": (
                    None if relation is None else int(relation[ii])
                ),
                "direction": None,
            }
        )
    return rows


def graph_crossing_candidates(
    graph: SurfaceGraphData,
    field,
    region_grid: np.ndarray,
    palette_grid: np.ndarray,
    roads: np.ndarray,
    road_band: np.ndarray,
    profile: dict,
    *,
    bridge_policy: str,
    min_clearance: float,
    include_no_mans_land: bool,
    no_mans_land_id: int | None,
) -> list[dict]:
    """Read graph shards directly; avoids materializing a whole-world CorridorOverlay."""
    out: list[dict] = []
    region_flat = region_grid.reshape(-1)
    palette_flat = palette_grid.reshape(-1)
    roads_flat = roads.reshape(-1)
    band_flat = road_band.reshape(-1)
    deep_flat = deep_water_mask(field, profile).reshape(-1)
    hard_grade = float(profile["grade_hard_block"])

    directions = list(graph.meta.get("directions", []))
    portal_dirs = list(graph.meta.get("portal_directions", [])) or directions

    for rec in directions:
        for shard in rec.get("edge_shards", []):
            with np.load(graph.graph_dir / shard["file"]) as d:
                u = np.asarray(d["u"], dtype=np.int64)
                v = np.asarray(d["v"], dtype=np.int64)
                distance = np.asarray(d["distance_m"], dtype=np.float32)
                grade = np.asarray(d["grade"], dtype=np.float32)
                clearance = np.asarray(
                    d["min_known_clearance_m"], dtype=np.float32
                )
                relation = (
                    np.asarray(d["component_relation"], dtype=np.uint8)
                    if "component_relation" in d
                    else np.full(len(u), 3, dtype=np.uint8)
                )
            out.extend(
                _candidate_rows_from_graph_arrays(
                    source="explicit",
                    cell_a=node_cells(graph, u),
                    cell_b=node_cells(graph, v),
                    distance=distance,
                    grade=grade,
                    clearance=clearance,
                    relation=relation,
                    region_flat=region_flat,
                    palette_flat=palette_flat,
                    roads_flat=roads_flat,
                    band_flat=band_flat,
                    field=field,
                    graph=graph,
                    hard_grade=hard_grade,
                    min_clearance=min_clearance,
                    deep_a=node_deep_water(graph, field, u, profile),
                    deep_b=node_deep_water(graph, field, v, profile),
                    bridge_policy=bridge_policy,
                    include_no_mans_land=include_no_mans_land,
                    no_mans_land_id=no_mans_land_id,
                )
            )

    for rec in portal_dirs:
        for shard in rec.get("portal_shards", []):
            with np.load(graph.graph_dir / shard["file"]) as d:
                node = np.asarray(d["node"], dtype=np.int64)
                implicit = np.asarray(
                    d["implicit_cell_index"], dtype=np.int64
                )
                distance = np.asarray(d["distance_m"], dtype=np.float32)
                grade = np.asarray(d["grade"], dtype=np.float32)
                relation = (
                    np.asarray(d["component_relation"], dtype=np.uint8)
                    if "component_relation" in d
                    else np.full(len(node), 3, dtype=np.uint8)
                )
            node_cell = node_cells(graph, node)
            # Portal clearance is the explicit node's floor clearance.
            clearance = np.asarray(graph.clearance[node], dtype=np.float32)
            out.extend(
                _candidate_rows_from_graph_arrays(
                    source="portal",
                    cell_a=node_cell,
                    cell_b=implicit,
                    distance=distance,
                    grade=grade,
                    clearance=clearance,
                    relation=relation,
                    region_flat=region_flat,
                    palette_flat=palette_flat,
                    roads_flat=roads_flat,
                    band_flat=band_flat,
                    field=field,
                    graph=graph,
                    hard_grade=hard_grade,
                    min_clearance=min_clearance,
                    deep_a=node_deep_water(graph, field, node, profile),
                    deep_b=deep_flat[implicit],
                    bridge_policy=bridge_policy,
                    include_no_mans_land=include_no_mans_land,
                    no_mans_land_id=no_mans_land_id,
                )
            )
    return out


class UnionFind:
    def __init__(self, n: int):
        self.parent = np.arange(n, dtype=np.int32)
        self.rank = np.zeros(n, dtype=np.uint8)

    def find(self, x: int) -> int:
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


def canonicalize_candidates(rows: list[dict]) -> None:
    """Sort region/palette endpoints so pair grouping is orientation-independent."""
    for row in rows:
        a, b = int(row["region_a"]), int(row["region_b"])
        if a > b:
            row["region_a"], row["region_b"] = b, a
            row["palette_a"], row["palette_b"] = (
                row["palette_b"],
                row["palette_a"],
            )


def cluster_gateways(
    rows: list[dict],
    *,
    gap_m: float,
    min_candidates: int,
    region_names: dict[int, str],
) -> list[dict]:
    """Spatially cluster crossing samples independently for every region pair.

    Grid-bucket union-find keeps this O(N)ish without a scipy dependency. Chaining
    is intentional: a continuously traversable 600 m boundary should become one
    broad gateway, while an impassable gap longer than ``gap_m`` splits gateways.
    """
    grouped: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        grouped[(int(row["region_a"]), int(row["region_b"]))].append(i)

    gateways: list[dict] = []
    gap2 = gap_m * gap_m

    for pair, indexes in sorted(grouped.items()):
        n = len(indexes)
        if n < min_candidates:
            continue

        pts = np.array(
            [[rows[i]["east_m"], rows[i]["north_m"]] for i in indexes],
            dtype=np.float64,
        )
        uf = UnionFind(n)
        bucket_size = gap_m
        buckets: dict[tuple[int, int], list[int]] = defaultdict(list)

        for local_i, (x, y) in enumerate(pts):
            bx = math.floor(x / bucket_size)
            by = math.floor(y / bucket_size)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for local_j in buckets.get((bx + dx, by + dy), ()):
                        d = pts[local_j] - pts[local_i]
                        if float(d[0] * d[0] + d[1] * d[1]) <= gap2:
                            uf.union(local_i, local_j)
            buckets[(bx, by)].append(local_i)

        comps: dict[int, list[int]] = defaultdict(list)
        for local_i in range(n):
            comps[uf.find(local_i)].append(local_i)

        for members in comps.values():
            if len(members) < min_candidates:
                continue
            global_idx = [indexes[i] for i in members]
            subset = [rows[i] for i in global_idx]
            xy = np.array(
                [[r["east_m"], r["north_m"]] for r in subset],
                dtype=np.float64,
            )
            grades = np.array([r["grade"] for r in subset], dtype=np.float64)
            z = np.array(
                [
                    np.nan if r["z_m"] is None else float(r["z_m"])
                    for r in subset
                ],
                dtype=np.float64,
            )

            # PCA span is a better "gateway width" proxy than bbox diagonal for a
            # long boundary segment that is not axis-aligned.
            center = xy.mean(axis=0)
            centered = xy - center
            if len(xy) >= 2 and np.any(np.abs(centered) > 1e-9):
                _, _, vt = np.linalg.svd(centered, full_matrices=False)
                proj = centered @ vt[0]
                span = float(proj.max() - proj.min())
            else:
                span = 0.0

            road_fraction = float(np.mean([r["road"] for r in subset]))
            band_fraction = float(np.mean([r["road_band"] for r in subset]))
            p90_grade = float(np.percentile(grades, 90))
            max_grade = float(np.max(grades))
            sources = Counter(r["source"] for r in subset)
            palette_pairs = sorted(
                {
                    f"{min(r['palette_a'], r['palette_b'])}:"
                    f"{max(r['palette_a'], r['palette_b'])}"
                    for r in subset
                }
            )
            relation_counts = Counter(
                str(r["component_relation"])
                for r in subset
                if r["component_relation"] is not None
            )

            # Ranking only, not pass/fail. Low grade is most important; breadth and
            # road evidence help distinguish obvious natural travel corridors.
            # Normalize grade using a 100% broad vehicle envelope so this score stays
            # interpretable across modes; actual passability was already mode-filtered.
            grade_score = max(0.0, min(1.0, 1.0 - p90_grade / 1.0))
            width_score = max(0.0, min(1.0, span / 80.0))
            road_score = max(road_fraction, 0.5 * band_fraction)
            score = 0.55 * grade_score + 0.25 * width_score + 0.20 * road_score

            gateways.append(
                {
                    "region_a": pair[0],
                    "region_b": pair[1],
                    "region_a_name": region_names.get(pair[0], str(pair[0])),
                    "region_b_name": region_names.get(pair[1], str(pair[1])),
                    "candidate_count": len(subset),
                    "east_m": round(float(center[0]), 3),
                    "north_m": round(float(center[1]), 3),
                    "z_m": (
                        None
                        if not np.any(np.isfinite(z))
                        else round(float(np.nanmedian(z)), 3)
                    ),
                    "gateway_span_m": round(span, 3),
                    "p90_grade": round(p90_grade, 6),
                    "max_grade": round(max_grade, 6),
                    "road_fraction": round(road_fraction, 6),
                    "road_band_fraction": round(band_fraction, 6),
                    "source_counts": dict(sorted(sources.items())),
                    "component_relation_counts": dict(
                        sorted(relation_counts.items())
                    ),
                    "palette_pairs": palette_pairs,
                    "score": round(float(score), 6),
                    "bbox_m": [
                        round(float(xy[:, 0].min()), 3),
                        round(float(xy[:, 1].min()), 3),
                        round(float(xy[:, 0].max()), 3),
                        round(float(xy[:, 1].max()), 3),
                    ],
                }
            )

    # Stable IDs after global ranking by region pair and descending score.
    gateways.sort(
        key=lambda g: (
            g["region_a"],
            g["region_b"],
            -g["score"],
            g["east_m"],
            g["north_m"],
        )
    )
    pair_counts: dict[tuple[int, int], int] = defaultdict(int)
    for g in gateways:
        pair = (g["region_a"], g["region_b"])
        pair_counts[pair] += 1
        g["gateway_id"] = (
            f"r{pair[0]:02d}_r{pair[1]:02d}_g{pair_counts[pair]:02d}"
        )
    return gateways


def named_adjacency_json(
    adj: dict[tuple[int, int], dict],
    names: dict[int, str],
) -> list[dict]:
    rows = []
    for (a, b), rec in sorted(adj.items()):
        rows.append(
            {
                "region_a": a,
                "region_b": b,
                "region_a_name": names.get(a, str(a)),
                "region_b_name": names.get(b, str(b)),
                **rec,
            }
        )
    return rows


def palette_adjacency_json(
    adj: dict[tuple[int, int], dict],
    palette_meta: dict[int, dict],
) -> list[dict]:
    rows = []
    for (a, b), rec in sorted(adj.items()):
        ma = palette_meta.get(a, {})
        mb = palette_meta.get(b, {})
        rows.append(
            {
                "palette_a": a,
                "palette_b": b,
                "area_a": ma.get("area_asset"),
                "area_b": mb.get("area_asset"),
                "region_a": ma.get("region_id"),
                "region_b": mb.get("region_id"),
                "display_name_a": ma.get("display_name"),
                "display_name_b": mb.get("display_name"),
                **rec,
            }
        )
    return rows


def write_candidates_csv(path: Path, rows: list[dict], names: dict[int, str]) -> None:
    fields = [
        "source",
        "region_a",
        "region_b",
        "region_a_name",
        "region_b_name",
        "palette_a",
        "palette_b",
        "east_m",
        "north_m",
        "z_m",
        "distance_m",
        "grade",
        "road",
        "road_band",
        "min_clearance_m",
        "component_relation",
        "direction",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for row in rows:
            rec = dict(row)
            rec["region_a_name"] = names.get(
                int(row["region_a"]), str(row["region_a"])
            )
            rec["region_b_name"] = names.get(
                int(row["region_b"]), str(row["region_b"])
            )
            w.writerow({k: rec.get(k) for k in fields})


def write_gateway_csv(path: Path, gateways: list[dict]) -> None:
    fields = [
        "gateway_id",
        "region_a",
        "region_b",
        "region_a_name",
        "region_b_name",
        "candidate_count",
        "east_m",
        "north_m",
        "z_m",
        "gateway_span_m",
        "p90_grade",
        "max_grade",
        "road_fraction",
        "road_band_fraction",
        "score",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for row in gateways:
            w.writerow({k: row.get(k) for k in fields})


def write_map(
    path: Path,
    raster: RegionRaster,
    gateways: list[dict],
    *,
    title: str,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    f = raster.frame
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.imshow(
        raster.region,
        origin="upper",
        extent=[
            float(f["east_min_m"]),
            float(f["east_max_m"]),
            float(f["north_min_m"]),
            float(f["north_max_m"]),
        ],
        interpolation="nearest",
        alpha=0.55,
    )
    if gateways:
        x = [g["east_m"] for g in gateways]
        y = [g["north_m"] for g in gateways]
        size = [24 + 80 * g["score"] for g in gateways]
        ax.scatter(x, y, s=size, marker="o")
        for g in gateways:
            ax.annotate(
                g["gateway_id"],
                (g["east_m"], g["north_m"]),
                xytext=(3, 3),
                textcoords="offset points",
                fontsize=6,
            )
    ax.set_title(title)
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

    raster = load_region_raster(
        Path(args.region_raster),
        Path(args.region_meta),
    )
    print(
        f"region raster: {raster.width}x{raster.height}, "
        f"{len(raster.region_names)} named regions"
    )

    pixel_m = float(raster.frame["metres_per_texel"])
    region_adj = native_adjacency(
        raster.region,
        pixel_m=pixel_m,
        include_unknown=args.include_unknown,
    )
    palette_adj = native_adjacency(
        raster.palette,
        pixel_m=pixel_m,
        include_unknown=True,
    )
    print(
        f"exact adjacency: {len(region_adj)} named-region pairs, "
        f"{len(palette_adj)} palette/sub-area pairs"
    )

    graph = SurfaceGraphData(args.surface_graph, args.intervals)
    pkg = PlannerPackage(args.planner)
    field = load_working_field(pkg, args.build, graph.step_m)

    if field.shape != (graph.height, graph.width):
        raise ValueError(
            f"WorkingField shape {field.shape} != surface graph "
            f"{(graph.height, graph.width)}"
        )
    if abs(field.east0_m - graph.east0_m) > 1e-6 or abs(
        field.north0_m - graph.north0_m
    ) > 1e-6:
        raise ValueError("WorkingField and surface graph origins do not match")

    profile = dict(load_profile(args.mode, args.profiles))
    profile["_mode"] = args.mode
    min_clearance = (
        float(args.minimum_clearance_m)
        if args.minimum_clearance_m is not None
        else MODE_CLEARANCE_M[args.mode]
    )

    region_grid, palette_grid = sample_region_grid(
        raster,
        east0_m=graph.east0_m,
        north0_m=graph.north0_m,
        step_m=graph.step_m,
        height=graph.height,
        width=graph.width,
    )
    roads, road_band = resample_road_prior(
        None if args.roads is None else Path(args.roads),
        field,
    )

    no_mans_land_id = next(
        (
            rid
            for rid, name in raster.region_names.items()
            if name == NO_MANS_LAND
        ),
        None,
    )

    base = base_crossing_candidates(
        field,
        region_grid,
        palette_grid,
        roads,
        road_band,
        profile,
        bridge_policy=args.bridge_policy,
        include_no_mans_land=args.include_no_mans_land,
        no_mans_land_id=no_mans_land_id,
    )
    print(f"base crossing candidates: {len(base):,}")

    layered = graph_crossing_candidates(
        graph,
        field,
        region_grid,
        palette_grid,
        roads,
        road_band,
        profile,
        bridge_policy=args.bridge_policy,
        min_clearance=min_clearance,
        include_no_mans_land=args.include_no_mans_land,
        no_mans_land_id=no_mans_land_id,
    )
    print(f"explicit/portal crossing candidates: {len(layered):,}")

    candidates = base + layered
    canonicalize_candidates(candidates)

    gateways = cluster_gateways(
        candidates,
        gap_m=float(args.cluster_gap_m),
        min_candidates=int(args.min_candidates),
        region_names=raster.region_names,
    )
    print(f"published gateways: {len(gateways):,}")

    region_adj_rows = named_adjacency_json(region_adj, raster.region_names)
    palette_adj_rows = palette_adjacency_json(
        palette_adj,
        raster.palette_meta,
    )

    # Attach gateway counts to region adjacency rows.
    gateway_counts = Counter(
        (int(g["region_a"]), int(g["region_b"])) for g in gateways
    )
    traversable_pairs = set(gateway_counts)
    for rec in region_adj_rows:
        pair = (int(rec["region_a"]), int(rec["region_b"]))
        rec["gateway_count"] = int(gateway_counts.get(pair, 0))
        rec["traversable_for_mode"] = pair in traversable_pairs

    (out_dir / "region_adjacency.json").write_text(
        json.dumps(region_adj_rows, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    (out_dir / "subarea_adjacency.json").write_text(
        json.dumps(palette_adj_rows, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    (out_dir / "gateways.json").write_text(
        json.dumps(gateways, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    write_candidates_csv(
        out_dir / "gateway_candidates.csv",
        candidates,
        raster.region_names,
    )
    write_gateway_csv(out_dir / "gateways.csv", gateways)
    write_map(
        out_dir / "gateways_map.png",
        raster,
        gateways,
        title=f"Satisfactory region gateways — {args.mode}",
    )

    manifest = {
        "schema_version": 1,
        "build": args.build,
        "mode": args.mode,
        "bridge_policy": args.bridge_policy,
        "minimum_clearance_m": min_clearance,
        "cluster_gap_m": float(args.cluster_gap_m),
        "min_candidates": int(args.min_candidates),
        "include_no_mans_land": bool(args.include_no_mans_land),
        "region_raster": str(Path(args.region_raster)),
        "region_meta": str(Path(args.region_meta)),
        "surface_graph": str(Path(args.surface_graph)),
        "intervals": args.intervals,
        "roads": args.roads,
        "graph_grid": {
            "step_m": graph.step_m,
            "width": graph.width,
            "height": graph.height,
            "east0_m": graph.east0_m,
            "north0_m": graph.north0_m,
        },
        "counts": {
            "region_adjacency_pairs": len(region_adj_rows),
            "subarea_adjacency_pairs": len(palette_adj_rows),
            "base_crossing_candidates": len(base),
            "layered_crossing_candidates": len(layered),
            "crossing_candidates_total": len(candidates),
            "gateways": len(gateways),
        },
        "method": {
            "adjacency": (
                "Exact native 4096x4096 region/palette raster E/S boundaries."
            ),
            "base_crossings": (
                "2 m implicit-base neighbor edges crossing a named-region boundary, "
                "filtered by mode hard grade and bridge/water policy."
            ),
            "layered_crossings": (
                "Explicit graph edges and base<->explicit portals crossing a "
                "named-region boundary, filtered by mode grade, clearance and "
                "bridge/water policy."
            ),
            "clustering": (
                "Per-region-pair spatial union-find using cluster_gap_m. Chaining "
                "is intentional so a continuously traversable boundary becomes one "
                "broad gateway."
            ),
            "score": (
                "Ranking only: 55% low p90 grade, 25% boundary span, 20% road/band "
                "evidence. It does not decide passability."
            ),
        },
    }
    (out_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )

    print(f"wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
