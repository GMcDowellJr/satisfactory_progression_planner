from __future__ import annotations

import argparse
import csv
import heapq
import json
import math
import sys
import time
from collections import deque
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


# ---------------------------------------------------------------------------
# TARGETED A -> D EXPERIMENT
# ---------------------------------------------------------------------------
# This is intentionally a broad study box, not an endpoint corridor. It covers
# the western/southern Rocky Desert approach including the known SCIM-road
# overhang area near roughly E=-2040, N=-600.
DEFAULT_A = (-2650.293636, 370.014545)
DEFAULT_D = (-2547.757036, -741.081591)

DEFAULT_WINDOW = {
    "west": -2925.0,
    "east": -1275.0,
    "south": -1305.0,
    "north": 615.0,
}

# Strong road preference from the v13 experiment.
ROAD_WEIGHTS = {
    "straight": 0.42,
    "turn": 0.55,
    "band": 0.68,
    "transition": 0.85,
}


DIR8 = [
    (-1, 0, 0), (-1, 1, 1), (0, 1, 2), (1, 1, 3),
    (1, 0, 4), (1, -1, 5), (0, -1, 6), (-1, -1, 7),
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Targeted A-to-D sparse 3D clearance-voxel experiment. "
            "Searches a broad study window without a route corridor."
        )
    )
    p.add_argument("--planner", default="planning_data")
    p.add_argument("--build", default="502094")
    p.add_argument("--surface-graph", required=True)
    p.add_argument(
        "--intervals",
        help="vertical_intervals.npz; normally auto-resolved from the surface graph",
    )
    p.add_argument(
        "--roads",
        default=(
            "planning_data/analysis/derived/rocky_desert/"
            "scim_roads/scim_prior_10m/scim_road_prior_5m.npz"
        ),
    )
    p.add_argument("--mode", default="tractor")
    p.add_argument("--origin-east", type=float, default=DEFAULT_A[0])
    p.add_argument("--origin-north", type=float, default=DEFAULT_A[1])
    p.add_argument("--target-east", type=float, default=DEFAULT_D[0])
    p.add_argument("--target-north", type=float, default=DEFAULT_D[1])

    p.add_argument("--west", type=float, default=DEFAULT_WINDOW["west"])
    p.add_argument("--east", type=float, default=DEFAULT_WINDOW["east"])
    p.add_argument("--south", type=float, default=DEFAULT_WINDOW["south"])
    p.add_argument("--north", type=float, default=DEFAULT_WINDOW["north"])

    # Vehicle configuration-space approximation.
    p.add_argument(
        "--tractor-height-m",
        type=float,
        default=4.5,
        help="minimum vertical free clearance above a candidate floor",
    )
    p.add_argument(
        "--footprint-radius-m",
        type=float,
        default=2.0,
        help=(
            "support/clearance radius around the tractor center. "
            "At the 2 m graph grid, 2 m checks cardinal neighboring cells."
        ),
    )
    p.add_argument(
        "--z-voxel-m",
        type=float,
        default=1.0,
        help="vertical quantization used for sparse configuration-space voxel IDs",
    )
    p.add_argument(
        "--footprint-z-slack-m",
        type=float,
        default=1.0,
        help="extra vertical support tolerance for footprint samples",
    )

    p.add_argument(
        "--start-search-m",
        type=float,
        default=40.0,
        help="radius used to resolve A onto a passable vehicle state",
    )
    p.add_argument(
        "--exact-target-radius-m",
        type=float,
        default=20.0,
        help="reachable target gap below which the outcome is COMPLETE",
    )
    p.add_argument(
        "--access-road-slack-m",
        type=float,
        default=120.0,
        help=(
            "after finding the minimum reachable gap to D, road/road-band states "
            "within this additional gap may be chosen as the ACCESS_ENDPOINT"
        ),
    )

    p.add_argument(
        "--out",
        default="planning_data/analysis/derived/ad_clearance_voxel",
    )
    return p.parse_args()


def _resolve_path(value: str | None) -> Path | None:
    if not value:
        return None
    p = Path(value)
    return p if p.is_absolute() else (ROOT / p).resolve()


def _resample_road_prior(path: Path | None, field):
    if path is None or not path.exists():
        return np.zeros(field.shape, bool), np.zeros(field.shape, bool)

    with np.load(path) as d:
        road = np.asarray(d["road"], dtype=bool)
        band = np.asarray(d["road_band"], dtype=bool)
        step = float(np.asarray(d["step_m"]).ravel()[0])
        east0 = float(np.asarray(d["east0_m"]).ravel()[0])
        north0 = float(np.asarray(d["north0_m"]).ravel()[0])

    rr = np.arange(field.shape[0])
    cc = np.arange(field.shape[1])
    north = field.north0_m - rr * field.step_m
    east = field.east0_m + cc * field.step_m
    sr = np.rint((north0 - north) / step).astype(int)
    sc = np.rint((east - east0) / step).astype(int)
    sr = np.clip(sr, 0, road.shape[0] - 1)
    sc = np.clip(sc, 0, road.shape[1] - 1)
    return road[sr[:, None], sc[None, :]], band[sr[:, None], sc[None, :]]


def _state_cell(state: int, graph: SurfaceGraphData) -> int:
    if state < 0:
        return -state - 1
    pos = int(np.searchsorted(graph.offsets, np.int64(state), side="right") - 1)
    return int(graph.cells[pos])


def _state_rc(state: int, graph: SurfaceGraphData) -> tuple[int, int]:
    return divmod(_state_cell(state, graph), graph.width)


def _state_z(state: int, graph: SurfaceGraphData, overlay, field) -> float:
    if state < 0:
        r, c = _state_rc(state, graph)
        return float(field.z_m[r, c])
    return float(overlay.node_floor_z[state])


def _state_clearance(state: int, overlay) -> float:
    if state < 0:
        # Ordinary composed-base cells do not carry a separate ceiling record.
        # Lower under-overhang surfaces are represented as explicit interval states
        # and therefore DO receive the measured interval clearance below.
        return math.inf
    value = float(overlay.node_clearance.get(state, math.nan))
    return value if math.isfinite(value) else math.inf


def _water_depth_for_state(state: int, graph, overlay, field) -> float:
    r, c = _state_rc(state, graph)
    q = int(field.water_q[r, c])
    if q == 0:
        return 0.0

    base_depth = (
        float(field.water_depth_m[r, c])
        if np.isfinite(field.water_depth_m[r, c])
        else math.nan
    )
    if state < 0:
        return base_depth

    if math.isfinite(base_depth):
        water_level = float(field.z_m[r, c]) + base_depth
        return max(0.0, water_level - float(overlay.node_floor_z[state]))
    return math.nan


class SparseVehicleLattice:
    """Sparse 3D tractor-center voxel view over the layered surface graph.

    XY is the existing 2 m graph grid. Z is quantized for identity/reporting,
    while exact floor Z is retained for grade and clearance checks.

    This does NOT allocate a dense world XYZ cube. A voxel exists only where
    there is a candidate supporting floor surface.
    """

    def __init__(
        self,
        *,
        graph,
        overlay,
        field,
        profile,
        roads,
        road_band,
        rmin,
        rmax,
        cmin,
        cmax,
        tractor_height_m,
        footprint_radius_m,
        footprint_z_slack_m,
        z_voxel_m,
    ):
        self.graph = graph
        self.overlay = overlay
        self.field = field
        self.profile = profile
        self.roads = roads
        self.road_band = road_band
        self.rmin = rmin
        self.rmax = rmax
        self.cmin = cmin
        self.cmax = cmax
        self.tractor_height_m = float(tractor_height_m)
        self.footprint_radius_m = float(footprint_radius_m)
        self.footprint_z_slack_m = float(footprint_z_slack_m)
        self.z_voxel_m = float(z_voxel_m)

        self.deep_water_m = float(profile["deep_water_depth_m"])
        self.grade_hard = float(profile["grade_hard_block"])
        self.grade_soft = float(profile["grade_soft_start"])
        self.grade_penalty = float(profile["grade_penalty"])

        self._allowed_cache: dict[int, bool] = {}
        self._footprint_cache: dict[int, bool] = {}

        radius_cells = int(math.ceil(self.footprint_radius_m / field.step_m))
        self.footprint_offsets = []
        for dr in range(-radius_cells, radius_cells + 1):
            for dc in range(-radius_cells, radius_cells + 1):
                plan = math.hypot(dr * field.step_m, dc * field.step_m)
                if plan <= self.footprint_radius_m + 1e-9:
                    self.footprint_offsets.append((dr, dc, plan))

    def inside(self, r: int, c: int) -> bool:
        return self.rmin <= r < self.rmax and self.cmin <= c < self.cmax

    def states_for_cell(self, r: int, c: int) -> list[int]:
        if not self.inside(r, c):
            return []
        cell = r * self.graph.width + c
        states = [-cell - 1]
        # Explicit lower/upper/stacked floors in exception columns.
        nodes = self.graph.nodes_for_cell(cell)
        for n in nodes.tolist():
            if int(n) in self.overlay.node_floor_z:
                states.append(int(n))
        return states

    def allowed_basic(self, state: int) -> bool:
        cached = self._allowed_cache.get(state)
        if cached is not None:
            return cached

        r, c = _state_rc(state, self.graph)
        if not self.inside(r, c):
            self._allowed_cache[state] = False
            return False

        z = _state_z(state, self.graph, self.overlay, self.field)
        if not math.isfinite(z):
            self._allowed_cache[state] = False
            return False

        clearance = _state_clearance(state, self.overlay)
        if clearance + 1e-6 < self.tractor_height_m:
            self._allowed_cache[state] = False
            return False

        depth = _water_depth_for_state(
            state, self.graph, self.overlay, self.field
        )
        if not math.isfinite(depth) and int(self.field.water_q[r, c]) != 0:
            self._allowed_cache[state] = False
            return False
        if math.isfinite(depth) and depth >= self.deep_water_m:
            self._allowed_cache[state] = False
            return False

        self._allowed_cache[state] = True
        return True

    def footprint_passable(self, state: int) -> bool:
        cached = self._footprint_cache.get(state)
        if cached is not None:
            return cached
        if not self.allowed_basic(state):
            self._footprint_cache[state] = False
            return False

        if self.footprint_radius_m <= 0:
            self._footprint_cache[state] = True
            return True

        r, c = _state_rc(state, self.graph)
        z = _state_z(state, self.graph, self.overlay, self.field)

        for dr, dc, plan in self.footprint_offsets:
            rr, cc = r + dr, c + dc
            if not self.inside(rr, cc):
                self._footprint_cache[state] = False
                return False

            # A footprint sample is supported if some passable surface at that XY
            # lies close enough vertically to the tractor floor plane. This is the
            # sparse configuration-space equivalent of eroding free volume by the
            # tractor footprint.
            max_dz = (
                max(self.footprint_z_slack_m, plan * self.grade_hard)
                + self.footprint_z_slack_m
            )
            supported = False
            for other in self.states_for_cell(rr, cc):
                if not self.allowed_basic(other):
                    continue
                oz = _state_z(other, self.graph, self.overlay, self.field)
                if abs(oz - z) <= max_dz + 1e-6:
                    supported = True
                    break
            if not supported:
                self._footprint_cache[state] = False
                return False

        self._footprint_cache[state] = True
        return True

    def voxel_id(self, state: int) -> tuple[int, int, int]:
        r, c = _state_rc(state, self.graph)
        floor_z = _state_z(state, self.graph, self.overlay, self.field)
        center_z = floor_z + self.tractor_height_m * 0.5
        zq = int(round(center_z / self.z_voxel_m))
        return r, c, zq

    def neighbors(self, state: int):
        """Yield (neighbor_state, distance_m, grade, direction_index)."""
        r, c = _state_rc(state, self.graph)
        z = _state_z(state, self.graph, self.overlay, self.field)

        # Base/explicit adjacency is rebuilt as a local sparse 3D lattice rather
        # than restricting movement to a preselected route corridor.
        for dr, dc, direction in DIR8:
            rr, cc = r + dr, c + dc
            if not self.inside(rr, cc):
                continue
            plan = math.hypot(dr * self.field.step_m, dc * self.field.step_m)
            for other in self.states_for_cell(rr, cc):
                if other == state or not self.footprint_passable(other):
                    continue
                oz = _state_z(other, self.graph, self.overlay, self.field)
                dz = abs(oz - z)
                grade = dz / max(plan, 1e-6)
                if grade > self.grade_hard + 1e-9:
                    continue
                yield other, plan, grade, direction

        # Vertical-layer/base portals from the precomputed graph remain useful:
        # they encode where stacked surfaces actually connect locally.
        if state >= 0:
            for cell, dist, grade, _rel in self.overlay.node_to_base.get(state, ()):
                rr, cc = divmod(int(cell), self.graph.width)
                other = -int(cell) - 1
                if (
                    self.inside(rr, cc)
                    and self.footprint_passable(other)
                    and float(grade) <= self.grade_hard + 1e-9
                ):
                    yield other, float(dist), float(grade), None
        else:
            cell = -state - 1
            for node, dist, grade, _rel in self.overlay.base_to_node.get(cell, ()):
                other = int(node)
                if (
                    self.footprint_passable(other)
                    and float(grade) <= self.grade_hard + 1e-9
                ):
                    yield other, float(dist), float(grade), None

    def road_flags(self, state: int) -> tuple[bool, bool]:
        r, c = _state_rc(state, self.graph)
        return bool(self.roads[r, c]), bool(self.road_band[r, c])

    def edge_cost(
        self,
        state: int,
        other: int,
        dist_m: float,
        grade: float,
        incoming_dir: int | None,
        outgoing_dir: int | None,
    ) -> float:
        factor = 1.0

        if grade > self.grade_soft:
            factor *= 1.0 + self.grade_penalty * (grade - self.grade_soft) ** 2

        sroad, sband = self.road_flags(state)
        oroad, oband = self.road_flags(other)

        if sroad and oroad:
            if incoming_dir is None or outgoing_dir is None:
                factor *= ROAD_WEIGHTS["straight"]
            else:
                delta = abs(outgoing_dir - incoming_dir)
                delta = min(delta, 8 - delta)
                factor *= (
                    ROAD_WEIGHTS["straight"]
                    if delta <= 1
                    else ROAD_WEIGHTS["turn"]
                )
        elif sband and oband:
            factor *= ROAD_WEIGHTS["band"]
        elif sroad or oroad or sband or oband:
            factor *= ROAD_WEIGHTS["transition"]

        return float(dist_m) * factor


def _world_window_to_rc(field, west, east, south, north):
    r_n, c_w = field.world_to_rc(west, north)
    r_s, c_e = field.world_to_rc(east, south)
    rmin = max(0, min(r_n, r_s))
    rmax = min(field.shape[0], max(r_n, r_s) + 1)
    cmin = max(0, min(c_w, c_e))
    cmax = min(field.shape[1], max(c_w, c_e) + 1)
    return rmin, rmax, cmin, cmax


def _nearest_start_state(lattice, east, north, radius_m):
    r0, c0 = lattice.field.world_to_rc(east, north)
    radius_cells = int(math.ceil(radius_m / lattice.field.step_m))
    best = None
    for r in range(max(lattice.rmin, r0 - radius_cells),
                   min(lattice.rmax, r0 + radius_cells + 1)):
        for c in range(max(lattice.cmin, c0 - radius_cells),
                       min(lattice.cmax, c0 + radius_cells + 1)):
            x, y = lattice.field.rc_to_world(r, c)
            gap = math.hypot(x - east, y - north)
            if gap > radius_m:
                continue
            for state in lattice.states_for_cell(r, c):
                if not lattice.footprint_passable(state):
                    continue
                candidate = (gap, abs(_state_z(
                    state, lattice.graph, lattice.overlay, lattice.field
                ) - float(lattice.field.z_m[r, c])), state)
                if best is None or candidate < best:
                    best = candidate
    if best is None:
        raise RuntimeError(
            f"no passable start state within {radius_m:.1f} m of ({east},{north})"
        )
    return int(best[2]), float(best[0])


def discover_reachable_component(
    lattice: SparseVehicleLattice,
    start_state: int,
    target_xy: tuple[float, float],
):
    """Flood the actual local vehicle connectivity before choosing an endpoint.

    This is the key difference from v13: ACCESS_ENDPOINT is discovered from the
    reachable component, not scored/accepted during the route search.
    """
    q = deque([start_state])
    seen = {start_state}
    best_gap = math.inf
    nearest_states = []

    while q:
        state = q.popleft()
        r, c = _state_rc(state, lattice.graph)
        east, north = lattice.field.rc_to_world(r, c)
        gap = math.hypot(east - target_xy[0], north - target_xy[1])

        if gap < best_gap - 1e-6:
            best_gap = gap
            nearest_states = [state]
        elif abs(gap - best_gap) <= 1e-6:
            nearest_states.append(state)

        for other, _dist, _grade, _direction in lattice.neighbors(state):
            if other in seen:
                continue
            seen.add(other)
            q.append(other)

    return seen, float(best_gap), nearest_states


def choose_access_endpoint(
    lattice,
    reachable,
    target_xy,
    min_gap_m,
    road_slack_m,
):
    """Choose among states near the reachable frontier, preferring authored road."""
    candidates = []
    limit = float(min_gap_m) + float(road_slack_m)
    for state in reachable:
        r, c = _state_rc(state, lattice.graph)
        east, north = lattice.field.rc_to_world(r, c)
        gap = math.hypot(east - target_xy[0], north - target_xy[1])
        if gap > limit + 1e-6:
            continue
        on_road, in_band = lattice.road_flags(state)
        # Endpoint priority is connectivity-first:
        # 1) road, 2) road band, 3) smallest remaining gap.
        category = 0 if on_road else (1 if in_band else 2)
        # Do not let a road state consume the entire slack unless it is actually
        # reasonably close to the reachable frontier.
        score = (
            category,
            gap,
            abs(_state_z(state, lattice.graph, lattice.overlay, lattice.field)),
            state,
        )
        candidates.append((score, state, gap, on_road, in_band))

    if not candidates:
        raise RuntimeError("reachable component unexpectedly has no endpoint candidate")

    candidates.sort(key=lambda x: x[0])
    _score, state, gap, on_road, in_band = candidates[0]
    return int(state), float(gap), bool(on_road), bool(in_band)


def weighted_route(
    lattice,
    start_state,
    goal_state,
    target_xy,
):
    """Road-aware A* on the already-discovered vehicle component."""
    start_key = (start_state, None)
    g = {start_key: 0.0}
    prev = {}
    pq = []

    def heuristic(state):
        r, c = _state_rc(state, lattice.graph)
        east, north = lattice.field.rc_to_world(r, c)
        # Minimum edge factor may be road_straight=0.42.
        return (
            math.hypot(east - target_xy[0], north - target_xy[1])
            * min(ROAD_WEIGHTS.values())
        )

    heapq.heappush(pq, (heuristic(start_state), 0.0, start_state, -1))
    reached = None

    while pq:
        _f, gcost, state, idir_raw = heapq.heappop(pq)
        idir = None if idir_raw < 0 else idir_raw
        key = (state, idir)
        if gcost != g.get(key):
            continue
        if state == goal_state:
            reached = key
            break

        for other, dist_m, grade, odir in lattice.neighbors(state):
            next_dir = idir if odir is None else odir
            cost = lattice.edge_cost(
                state, other, dist_m, grade, idir, odir
            )
            ng = gcost + cost
            nkey = (other, next_dir)
            if ng + 1e-9 < g.get(nkey, math.inf):
                g[nkey] = ng
                prev[nkey] = key
                h = heuristic(other)
                heapq.heappush(
                    pq,
                    (ng + h, ng, other, -1 if next_dir is None else next_dir),
                )

    if reached is None:
        raise RuntimeError(
            "goal endpoint was discovered reachable but weighted A* could not reconstruct it"
        )

    keys = [reached]
    while keys[-1] != start_key:
        keys.append(prev[keys[-1]])
    keys.reverse()
    states = [k[0] for k in keys]
    return states, float(g[reached]), len(g)


def write_route_csv(path: Path, states, lattice):
    fields = [
        "point_order",
        "state_id",
        "voxel_r",
        "voxel_c",
        "voxel_z",
        "east_m",
        "north_m",
        "floor_z_m",
        "center_z_m",
        "clearance_m",
        "on_road",
        "in_road_band",
        "state_type",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for i, state in enumerate(states):
            r, c, zq = lattice.voxel_id(state)
            east, north = lattice.field.rc_to_world(r, c)
            floor_z = _state_z(
                state, lattice.graph, lattice.overlay, lattice.field
            )
            clearance = _state_clearance(state, lattice.overlay)
            on_road, in_band = lattice.road_flags(state)
            w.writerow(
                {
                    "point_order": i,
                    "state_id": state,
                    "voxel_r": r,
                    "voxel_c": c,
                    "voxel_z": zq,
                    "east_m": east,
                    "north_m": north,
                    "floor_z_m": floor_z,
                    "center_z_m": floor_z + lattice.tractor_height_m * 0.5,
                    "clearance_m": clearance if math.isfinite(clearance) else "",
                    "on_road": on_road,
                    "in_road_band": in_band,
                    "state_type": "explicit_interval" if state >= 0 else "implicit_base",
                }
            )


def write_map(path: Path, states, lattice, origin_xy, target_xy, endpoint_xy):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 10))

    # Show the road prior as a sparse raster background for the study window.
    road_crop = lattice.road_band[
        lattice.rmin:lattice.rmax, lattice.cmin:lattice.cmax
    ]
    west = lattice.field.east0_m + lattice.cmin * lattice.field.step_m
    east = lattice.field.east0_m + (lattice.cmax - 1) * lattice.field.step_m
    north = lattice.field.north0_m - lattice.rmin * lattice.field.step_m
    south = lattice.field.north0_m - (lattice.rmax - 1) * lattice.field.step_m
    ax.imshow(
        road_crop.astype(float),
        extent=[west, east, south, north],
        origin="upper",
        alpha=0.35,
    )

    xs, ys = [], []
    for state in states:
        r, c = _state_rc(state, lattice.graph)
        x, y = lattice.field.rc_to_world(r, c)
        xs.append(x)
        ys.append(y)
    ax.plot(xs, ys, linewidth=1.5, label="clearance-voxel route")
    ax.scatter([origin_xy[0], target_xy[0], endpoint_xy[0]],
               [origin_xy[1], target_xy[1], endpoint_xy[1]])
    ax.text(origin_xy[0], origin_xy[1], " A")
    ax.text(target_xy[0], target_xy[1], " D")
    ax.text(endpoint_xy[0], endpoint_xy[1], " access")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.set_title("Targeted A→D sparse 3D clearance-voxel route")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main() -> int:
    args = parse_args()
    started = time.time()

    out_dir = _resolve_path(args.out)
    assert out_dir is not None
    out_dir.mkdir(parents=True, exist_ok=True)

    graph = SurfaceGraphData(
        _resolve_path(args.surface_graph),
        _resolve_path(args.intervals),
    )
    pkg = PlannerPackage(_resolve_path(args.planner))
    field = load_working_field(pkg, args.build, graph.step_m)
    profile = load_profile(args.mode)

    road_path = _resolve_path(args.roads)
    roads, road_band = _resample_road_prior(road_path, field)

    rmin, rmax, cmin, cmax = _world_window_to_rc(
        field,
        args.west,
        args.east,
        args.south,
        args.north,
    )
    overlay = graph.corridor(rmin, rmax, cmin, cmax)

    lattice = SparseVehicleLattice(
        graph=graph,
        overlay=overlay,
        field=field,
        profile=profile,
        roads=roads,
        road_band=road_band,
        rmin=rmin,
        rmax=rmax,
        cmin=cmin,
        cmax=cmax,
        tractor_height_m=args.tractor_height_m,
        footprint_radius_m=args.footprint_radius_m,
        footprint_z_slack_m=args.footprint_z_slack_m,
        z_voxel_m=args.z_voxel_m,
    )

    origin_xy = (args.origin_east, args.origin_north)
    target_xy = (args.target_east, args.target_north)

    print(
        f"study window: rows {rmin}:{rmax}, cols {cmin}:{cmax} "
        f"({(rmax-rmin)*(cmax-cmin):,} XY cells)"
    )
    print(
        f"sparse tractor voxels: floor states only; "
        f"height={args.tractor_height_m:.1f} m, footprint radius={args.footprint_radius_m:.1f} m"
    )

    start_state, start_gap = _nearest_start_state(
        lattice,
        args.origin_east,
        args.origin_north,
        args.start_search_m,
    )
    print(f"A resolved {start_gap:.2f} m from anchor; flooding vehicle connectivity...")

    reachable, minimum_gap, nearest = discover_reachable_component(
        lattice, start_state, target_xy
    )
    print(
        f"reachable sparse voxels: {len(reachable):,}; "
        f"closest reachable plan gap to D: {minimum_gap:.1f} m"
    )

    endpoint_state, endpoint_gap, endpoint_on_road, endpoint_in_band = (
        choose_access_endpoint(
            lattice,
            reachable,
            target_xy,
            minimum_gap,
            args.access_road_slack_m,
        )
    )
    er, ec = _state_rc(endpoint_state, graph)
    endpoint_xy = field.rc_to_world(er, ec)

    route_status = (
        "COMPLETE"
        if endpoint_gap <= args.exact_target_radius_m
        else "ACCESS_ENDPOINT"
    )

    print(
        f"endpoint: {route_status}, gap={endpoint_gap:.1f} m, "
        f"road={endpoint_on_road}, band={endpoint_in_band}; routing..."
    )

    route_states, route_cost, search_states = weighted_route(
        lattice,
        start_state,
        endpoint_state,
        endpoint_xy,
    )

    route_length = 0.0
    road_points = 0
    explicit_points = 0
    for i, state in enumerate(route_states):
        on_road, _band = lattice.road_flags(state)
        road_points += int(on_road)
        explicit_points += int(state >= 0)
        if i:
            r0, c0 = _state_rc(route_states[i - 1], graph)
            r1, c1 = _state_rc(state, graph)
            route_length += math.hypot(
                (r1 - r0) * field.step_m,
                (c1 - c0) * field.step_m,
            )

    route_csv = out_dir / "ad_clearance_voxel_route.csv"
    write_route_csv(route_csv, route_states, lattice)

    summary = {
        "schema_version": 1,
        "experiment": "targeted_A_to_D_sparse_3d_clearance_voxel",
        "route_status": route_status,
        "mode": args.mode,
        "origin": {"east_m": origin_xy[0], "north_m": origin_xy[1]},
        "target": {"east_m": target_xy[0], "north_m": target_xy[1]},
        "study_window_m": {
            "west": args.west,
            "east": args.east,
            "south": args.south,
            "north": args.north,
        },
        "uses_route_corridor": False,
        "representation": {
            "kind": "sparse_surface_relative_configuration_space_voxels",
            "xy_step_m": graph.step_m,
            "z_voxel_m": args.z_voxel_m,
            "tractor_height_m": args.tractor_height_m,
            "footprint_radius_m": args.footprint_radius_m,
            "note": (
                "A voxel exists only at a candidate supporting floor. Explicit "
                "vertical-interval floors carry measured overhead clearance; "
                "ordinary composed base is implicit. This intentionally tests the "
                "3D layered/clearance concept without allocating a dense XYZ cube."
            ),
        },
        "reachable_sparse_voxels": len(reachable),
        "minimum_reachable_gap_to_target_m": minimum_gap,
        "endpoint": {
            "east_m": endpoint_xy[0],
            "north_m": endpoint_xy[1],
            "floor_z_m": _state_z(endpoint_state, graph, overlay, field),
            "remaining_plan_gap_m": endpoint_gap,
            "on_road": endpoint_on_road,
            "in_road_band": endpoint_in_band,
            "state_type": (
                "explicit_interval" if endpoint_state >= 0 else "implicit_base"
            ),
        },
        "route": {
            "points": len(route_states),
            "plan_length_m": route_length,
            "weighted_cost": route_cost,
            "road_point_fraction": (
                road_points / len(route_states) if route_states else 0.0
            ),
            "explicit_interval_point_fraction": (
                explicit_points / len(route_states) if route_states else 0.0
            ),
            "weighted_search_states": search_states,
        },
        "road_weights": ROAD_WEIGHTS,
        "surface_graph": str(graph.graph_dir),
        "roads": None if road_path is None else str(road_path),
        "elapsed_s": time.time() - started,
    }
    (out_dir / "ad_clearance_voxel_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )

    try:
        write_map(
            out_dir / "ad_clearance_voxel_route.png",
            route_states,
            lattice,
            origin_xy,
            target_xy,
            endpoint_xy,
        )
    except Exception as exc:
        print(f"map write skipped: {type(exc).__name__}: {exc}")

    print(f"wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
