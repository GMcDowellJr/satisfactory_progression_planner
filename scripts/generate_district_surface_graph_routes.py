from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import combinations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "satisfactory_route_tool" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from satisfactory_route_tool.package import PlannerPackage
from satisfactory_route_tool.heightfield import load_working_field
from satisfactory_route_tool.profiles import load_profile
from satisfactory_route_tool.graph_solver import solve_surface_graph, write_result
from satisfactory_route_tool.vehicle_passability import (
    apply_vehicle_patch,
    load_vehicle_patch,
)

DEFAULT_ANCHORS = "planning_data/analysis/derived/rocky_desert/district_anchors.csv"
DEFAULT_ROADS = (
    "planning_data/analysis/derived/rocky_desert/routes/"
    "scim_prior_10m/scim_road_prior_5m.npz"
)
DEFAULT_OUT = "data/local/routes/district_surface_graph_v14"

# Easy-to-tune route behavior defaults.
ROAD_WEIGHT_DEFAULTS = {
    "road_straight_factor": 0.42,
    "road_turn_factor": 0.55,
    "band_continuation_factor": 0.68,
    "road_transition_factor": 0.85,
}
ACCESS_TARGET_DEFAULTS = "D"
DEFAULT_SCIM = "planning_data/analysis/derived/rocky_desert/scim_roads/scim_map_crop.png"
DEFAULT_REGISTRATION = (
    "planning_data/analysis/derived/rocky_desert/scim_roads/scim_image_registration.csv"
)

_W_FIELD = None
_W_PROFILE = None
_W_CFG = None
_W_PATCH_STATS = []


def parse_args():
    p = argparse.ArgumentParser(
        description="Solve all selected district pairs with the layered surface graph."
    )
    p.add_argument("--planner", default="planning_data")
    p.add_argument("--anchors", default=DEFAULT_ANCHORS)
    p.add_argument("--surface-graph", required=True)
    p.add_argument("--intervals")
    p.add_argument(
        "--vehicle-patch",
        action="append",
        default=[],
        help=(
            "portable vehicle-passability patch NPZ. Repeat to apply multiple "
            "raw-geometry validated patches before routing."
        ),
    )
    p.add_argument("--roads", default=DEFAULT_ROADS)
    p.add_argument("--out", default=DEFAULT_OUT)
    p.add_argument("--scim-image", default=DEFAULT_SCIM)
    p.add_argument("--registration", default=DEFAULT_REGISTRATION)
    p.add_argument(
        "--scim-content-crop",
        nargs=4,
        type=int,
        default=[49, 68, 1752, 1769],
        metavar=("X0", "Y0", "X1", "Y1"),
    )
    p.add_argument("--districts", default="ABCDEF")
    p.add_argument(
        "--pairs",
        help=(
            "optional comma-separated unordered pair filter, e.g. A-D,B-D. "
            "When omitted, solve all combinations of --districts."
        ),
    )
    p.add_argument("--mode", choices=["foot", "tractor", "truck", "rail"], default="tractor")
    p.add_argument("--profiles")
    p.add_argument("--build", default="502094")
    p.add_argument("--bridge-policy", choices=["forbid", "allow"], default="forbid")
    p.add_argument("--corridor-pad-m", type=float, default=800.0)
    p.add_argument(
        "--regional-domain-bounds",
        type=float,
        nargs=4,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help=(
            "optional broad routing domain applied to selected pairs. When set, "
            "it overrides topology-path/fixed endpoint corridors and gives A* "
            "the whole rectangular region."
        ),
    )
    p.add_argument(
        "--topology-paths",
        help=(
            "optional topology_paths.json from diagnose_topology_routes.py; "
            "when supplied, each pair uses that coarse path bbox instead of a "
            "fixed anchor-bbox corridor"
        ),
    )
    p.add_argument(
        "--topology-margin-m",
        type=float,
        default=150.0,
        help="margin added around each coarse topology path bbox (default 150 m)",
    )
    p.add_argument("--endpoint-access-radius-m", type=float, default=200.0)
    p.add_argument(
        "--access-targets",
        default=ACCESS_TARGET_DEFAULTS,
        help=(
            "district letters that should terminate at a useful road/land access "
            "endpoint instead of requiring the vehicle to reach the anchor "
            "(default D; use empty string to disable)"
        ),
    )
    p.add_argument(
        "--access-endpoint-radius-m",
        type=float,
        default=1200.0,
        help="maximum anchor gap considered for ACCESS_ENDPOINT mode (default 1200 m)",
    )
    p.add_argument("--minimum-clearance-m", type=float)
    p.add_argument(
        "--base-component-seam-penalty-m",
        type=float,
        default=0.50,
        help="base penalty before route-aware seam confidence scaling",
    )
    p.add_argument(
        "--cross-component-seam-penalty-m",
        type=float,
        default=2.0,
        help="base penalty before route-aware seam confidence scaling",
    )
    p.add_argument(
        "--ambiguous-component-seam-penalty-m",
        type=float,
        default=4.0,
        help="base penalty before route-aware seam confidence scaling",
    )
    p.add_argument(
        "--road-straight-factor", type=float, default=ROAD_WEIGHT_DEFAULTS["road_straight_factor"],
        help="cost factor for road→road edges continuing within 45 degrees",
    )
    p.add_argument(
        "--road-turn-factor", type=float, default=ROAD_WEIGHT_DEFAULTS["road_turn_factor"],
        help="cost factor for road→road edges making a 90+ degree turn",
    )
    p.add_argument(
        "--band-continuation-factor", type=float, default=ROAD_WEIGHT_DEFAULTS["band_continuation_factor"],
        help="cost factor when both edge endpoints remain in the road band",
    )
    p.add_argument(
        "--road-transition-factor", type=float, default=ROAD_WEIGHT_DEFAULTS["road_transition_factor"],
        help="cost factor for entering/leaving the road or road band",
    )
    p.add_argument(
        "--max-complete-stretch", type=float, default=2.25,
        help=(
            "diagnostic threshold for complete-route stretch relative to anchor "
            "straight-line distance; no longer hard-rejects valid complete routes"
        ),
    )
    p.add_argument(
        "--workers",
        type=int,
        default=0,
        help=(
            "parallel route worker processes. 0=auto (up to 4); 1=serial/debug. "
            "Each worker loads the field once and caches graph/interval state."
        ),
    )
    return p.parse_args()


def resolve_workers(requested: int, pair_count: int) -> int:
    if requested < 0:
        raise SystemExit("--workers must be >= 0")
    if requested == 1:
        return 1
    if requested > 1:
        return min(requested, pair_count)
    cpu = os.cpu_count() or 2
    return min(pair_count, max(1, min(4, cpu // 2 if cpu > 1 else 1)))



def parse_pair_filter(value: str | None, letters: list[str]) -> set[tuple[str, str]] | None:
    if not value:
        return None
    allowed = set(letters)
    out: set[tuple[str, str]] = set()
    for raw in str(value).split(","):
        token = raw.strip().upper().replace("→", "-").replace("_TO_", "-")
        if not token:
            continue
        parts = [p.strip() for p in token.split("-") if p.strip()]
        if len(parts) != 2 or len(parts[0]) != 1 or len(parts[1]) != 1:
            raise SystemExit(f"invalid --pairs token {raw!r}; use forms like A-D,B-D")
        a, b = parts
        if a == b:
            raise SystemExit(f"invalid self-pair {raw!r}")
        if a not in allowed or b not in allowed:
            raise SystemExit(
                f"pair {raw!r} references district outside --districts={''.join(letters)}"
            )
        out.add(tuple(sorted((a, b))))
    if not out:
        raise SystemExit("--pairs did not contain any usable pairs")
    return out

def load_anchors(path: Path, letters: list[str]):
    df = pd.read_csv(path)
    df["letter"] = (
        df["district_id"]
        .str.extract(r"rocky_desert_([a-z])", expand=False)
        .str.upper()
    )
    df = df[df["letter"].isin(letters)].copy()
    missing = sorted(set(letters) - set(df["letter"]))
    if missing:
        raise SystemExit(f"missing district anchors for: {', '.join(missing)}")
    return df.sort_values("letter").reset_index(drop=True)



def load_topology_pair_bounds(path: Path | None, margin_m: float) -> dict[tuple[str,str], list[float]]:
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    margin = float(margin_m)
    for key, rec in data.items():
        if "_to_" not in key:
            continue
        a, b = key.split("_to_", 1)
        bbox = rec.get("path_bbox_m")
        if not bbox or len(bbox) != 4:
            continue
        west, south, east, north = (float(v) for v in bbox)
        out[(a.upper(), b.upper())] = [
            west-margin,
            south-margin,
            east+margin,
            north+margin,
        ]
    return out


def _worker_init(cfg: dict):
    global _W_FIELD, _W_PROFILE, _W_CFG, _W_PATCH_STATS
    _W_CFG = cfg
    pkg = PlannerPackage(cfg["planner"])
    field = load_working_field(pkg, cfg["build"], cfg["step_m"])

    _W_PATCH_STATS = []
    for patch_path in cfg.get("vehicle_patches", []):
        patch = load_vehicle_patch(patch_path)
        field, stats = apply_vehicle_patch(field, patch)
        _W_PATCH_STATS.append(stats)

    _W_FIELD = field
    _W_PROFILE = dict(load_profile(cfg["mode"], cfg["profiles"]))
    _W_PROFILE["_mode"] = cfg["mode"]


def _solve_pair(job: dict) -> dict:
    started = time.perf_counter()
    pair_dir = Path(job["pair_dir"])
    pair_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = solve_surface_graph(
            _W_FIELD,
            tuple(job["origin_xy"]),
            tuple(job["destination_xy"]),
            _W_PROFILE,
            surface_graph_dir=_W_CFG["surface_graph"],
            intervals_path=_W_CFG["intervals"],
            road_prior_path=_W_CFG["roads"],
            bridge_policy=_W_CFG["bridge_policy"],
            corridor_pad_m=_W_CFG["corridor_pad_m"],
            minimum_clearance_m=_W_CFG["minimum_clearance_m"],
            endpoint_access_radius_m=_W_CFG["endpoint_access_radius_m"],
            base_component_seam_penalty_m=_W_CFG["base_component_seam_penalty_m"],
            cross_component_seam_penalty_m=_W_CFG["cross_component_seam_penalty_m"],
            ambiguous_component_seam_penalty_m=_W_CFG["ambiguous_component_seam_penalty_m"],
            road_straight_factor=_W_CFG["road_straight_factor"],
            road_turn_factor=_W_CFG["road_turn_factor"],
            band_continuation_factor=_W_CFG["band_continuation_factor"],
            road_transition_factor=_W_CFG["road_transition_factor"],
            max_complete_stretch=_W_CFG["max_complete_stretch"],
            corridor_bounds_m=job.get("corridor_bounds_m"),
            destination_mode=job.get("destination_mode","exact"),
            access_endpoint_radius_m=_W_CFG["access_endpoint_radius_m"],
        )
        if _W_PATCH_STATS:
            result.summary["vehicle_passability_patches"] = _W_PATCH_STATS
        result.summary["routing_domain_model"] = (
            "regional_domain"
            if job.get("regional_domain_used")
            else (
                "topology_path_bbox"
                if job.get("corridor_bounds_m") is not None
                else "fixed_anchor_bbox_corridor"
            )
        )
        write_result(result, pair_dir)
        route_status = str(result.summary.get("route_status", "COMPLETE")).upper()
        status = (
            "PARTIAL" if route_status == "PARTIAL"
            else ("ACCESS_ENDPOINT" if route_status == "ACCESS_ENDPOINT" else "PASS")
        )
        return {
            "a": job["a"],
            "b": job["b"],
            "solved_origin": job.get("solved_origin", job["a"]),
            "solved_destination": job.get("solved_destination", job["b"]),
            "status": status,
            "summary": result.summary,
            "pair_dir": str(pair_dir),
            "elapsed_s": time.perf_counter() - started,
        }
    except Exception as exc:
        (pair_dir / "error.txt").write_text(repr(exc), encoding="utf-8", newline="\n")
        return {
            "a": job["a"],
            "b": job["b"],
            "status": "ERROR",
            "error": repr(exc),
            "pair_dir": str(pair_dir),
            "elapsed_s": time.perf_counter() - started,
        }


def directed_row(item: dict, origin: str, destination: str, *, solved_direction: bool = True):
    if item["status"] not in ("PASS", "PARTIAL", "ACCESS_ENDPOINT"):
        return {
            "origin": origin,
            "destination": destination,
            "status": item["status"],
            "pair_output": item["pair_dir"],
            "error": item.get("error"),
        }

    if item["status"] in ("PARTIAL","ACCESS_ENDPOINT") and not solved_direction:
        return {
            "origin": origin,
            "destination": destination,
            "status": "REVERSE_NOT_SOLVED",
            "destination_reached": None,
            "remaining_plan_gap_m": None,
            "remaining_anchor_gap_m": None,
            "pair_output": item["pair_dir"],
            "error": "Partial/access routes are directional; reverse search was not run.",
        }

    s = item["summary"]
    # Current search/cost model is symmetric; one physical solve is reused in both directions.
    return {
        "origin": origin,
        "destination": destination,
        "status": item["status"],
        "destination_reached": s.get("destination_reached"),
        "remaining_plan_gap_m": s.get("remaining_plan_gap_m"),
        "remaining_anchor_gap_m": s.get("remaining_anchor_gap_m"),
        "access_endpoint_reached": s.get("access_endpoint_reached"),
        "destination_mode": s.get("destination_mode"),
        "access_endpoint_on_road": s.get("access_endpoint_on_road"),
        "access_endpoint_in_road_band": s.get("access_endpoint_in_road_band"),
        "regional_route_length_m": s.get("regional_route_length_m", s.get("route_length_m")),
        "anchor_to_anchor_accounted_length_m": s.get("anchor_to_anchor_accounted_length_m"),
        "road_fraction": s.get("road_fraction"),
        "road_band_fraction": s.get("road_band_fraction"),
        "water_fraction": s.get("water_fraction"),
        "max_routing_grade_pct": s.get("max_routing_grade_pct"),
        "surface_graph_fraction": s.get("surface_graph_fraction"),
        "surface_graph_edge_count": s.get("surface_graph_edge_count"),
        "surface_graph_portal_transitions": s.get("surface_graph_portal_transitions"),
        "surface_component_switches": s.get("surface_component_switches"),
        "same_component_edges": (s.get("component_relation_counts") or {}).get("same_component"),
        "base_component_seams": (s.get("component_relation_counts") or {}).get("base_component_seam"),
        "cross_component_seams": (s.get("component_relation_counts") or {}).get("cross_component_seam"),
        "ambiguous_component_seams": (s.get("component_relation_counts") or {}).get("ambiguous_component_seam"),
        "component_seam_penalty_cost_m": s.get("component_seam_penalty_cost_m"),
        "turn_penalty_cost_m": s.get("turn_penalty_cost_m"),
        "accounted_stretch_ratio": s.get("accounted_stretch_ratio"),
        "stretch_guardrail_rejected_complete": s.get("stretch_guardrail_rejected_complete"),
        "minimum_clearance_m": s.get("minimum_clearance_m"),
        "valid_under_profile": s.get("valid_under_profile"),
        "pair_output": item["pair_dir"],
    }



def reverse_route(df: pd.DataFrame) -> pd.DataFrame:
    out = df.iloc[::-1].copy().reset_index(drop=True)
    if "point_order" in out.columns:
        out["point_order"] = range(len(out))
    if {"east_m", "north_m"}.issubset(out.columns):
        de = out["east_m"].diff()
        dn = out["north_m"].diff()
        out["segment_distance_m"] = (de.pow(2) + dn.pow(2)).pow(0.5).fillna(0.0)
        out["cumulative_distance_m"] = out["segment_distance_m"].cumsum()
    return out


def registered_scim(image_path: Path, crop, registration_path: Path):
    image = Image.open(image_path).convert("RGB").crop(tuple(crop))
    reg = pd.read_csv(registration_path).iloc[0]
    extent = [
        float(reg["east_min_m"]),
        float(reg["east_max_m"]),
        float(reg["north_min_m"]),
        float(reg["north_max_m"]),
    ]
    return image, extent


def _connector_points(summary: dict, origin: str, a: str):
    """Return anchor/portal pairs if graph solver summary exposes them."""
    if origin == a:
        oa = summary.get("origin_anchor")
        op = summary.get("origin_portal")
        da = summary.get("destination_anchor")
        dp = summary.get("destination_portal")
    else:
        oa = summary.get("destination_anchor")
        op = summary.get("destination_portal")
        da = summary.get("origin_anchor")
        dp = summary.get("origin_portal")
    return oa, op, da, dp


def render_origin(
    origin: str,
    letters: list[str],
    anchor_xy: dict[str, tuple[float, float]],
    pair_results: dict,
    scim_image,
    scim_extent,
    out_path: Path,
    mode: str,
):
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.imshow(scim_image, extent=scim_extent, origin="upper")

    xs = [anchor_xy[k][0] for k in letters]
    ys = [anchor_xy[k][1] for k in letters]
    all_x = list(xs)
    all_y = list(ys)

    for dest in letters:
        if dest == origin:
            continue

        a, b = sorted((origin, dest))
        item = pair_results.get((a, b))
        if not item or item["status"] not in ("PASS", "PARTIAL", "ACCESS_ENDPOINT"):
            continue

        route_path = Path(item["pair_dir"]) / "route_points.csv"
        if not route_path.exists():
            continue
        route = pd.read_csv(route_path)
        if origin != a:
            if item["status"] in ("PARTIAL", "ACCESS_ENDPOINT"):
                # Partial/access searches are directional; do not fabricate reverse geometry.
                continue
            route = reverse_route(route)

        summary = item["summary"]
        length_m = summary.get("regional_route_length_m", summary.get("route_length_m"))
        if length_m is None and "cumulative_distance_m" in route.columns and len(route):
            length_m = float(route["cumulative_distance_m"].iloc[-1])
        label = f"{origin}→{dest}"
        if item["status"] == "PARTIAL":
            gap = summary.get("remaining_plan_gap_m")
            label += " partial"
            if gap is not None:
                label += f" (gap {float(gap):.0f} m)"
        if length_m is not None:
            label += f"  {float(length_m)/1000:.2f} km"

        ax.plot(
            route["east_m"],
            route["north_m"],
            linewidth=2.0,
            label=label,
        )

        oa, op, da, dp = _connector_points(summary, origin, a)
        if oa and op:
            ax.plot(
                [oa["east_m"], op["east_m"]],
                [oa["north_m"], op["north_m"]],
                linestyle="--",
                linewidth=1.0,
                alpha=0.8,
            )
        if da and dp:
            ax.plot(
                [dp["east_m"], da["east_m"]],
                [dp["north_m"], da["north_m"]],
                linestyle="--",
                linewidth=1.0 if item["status"] != "PARTIAL" else 1.5,
                alpha=0.8,
            )
            if item["status"] == "PARTIAL":
                ax.scatter(
                    [dp["east_m"]], [dp["north_m"]],
                    marker="x", s=45, zorder=7,
                )

        all_x.extend(route["east_m"].tolist())
        all_y.extend(route["north_m"].tolist())

    ax.scatter(xs, ys, s=35, zorder=5)
    for k in letters:
        x, y = anchor_xy[k]
        ax.text(
            x + 25,
            y - 25,
            k,
            fontsize=11,
            fontweight="bold" if k == origin else "normal",
            zorder=6,
        )

    pad = 250.0
    ax.set_xlim(min(all_x) - pad, max(all_x) + pad)
    ax.set_ylim(min(all_y) - pad, max(all_y) + pad)
    ax.set_aspect("equal")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.set_title(
        f"Rocky Desert surface-graph routes from {origin} "
        f"({mode}; dashed = access connector / unresolved partial gap)"
    )
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(handles, labels, loc="best", fontsize=8)
    else:
        ax.text(
            0.5, 0.03,
            f"No successful routes from {origin}",
            transform=ax.transAxes,
            ha="center",
            va="bottom",
            fontsize=9,
        )
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)



def main():
    args = parse_args()

    planner = (ROOT / args.planner).resolve()
    anchors_path = (ROOT / args.anchors).resolve()
    roads = (ROOT / args.roads).resolve() if args.roads else None
    graph_dir = Path(args.surface_graph).resolve()
    intervals = Path(args.intervals).resolve() if args.intervals else None
    vehicle_patches = [
        (Path(p).resolve() if Path(p).is_absolute() else (ROOT / p).resolve())
        for p in args.vehicle_patch
    ]
    missing_patches = [str(p) for p in vehicle_patches if not p.exists()]
    if missing_patches:
        raise SystemExit(
            "vehicle passability patch not found: " + ", ".join(missing_patches)
        )
    out_root = (ROOT / args.out).resolve()
    pairs_root = out_root / "pairs"
    images_root = out_root / "by_origin"
    pairs_root.mkdir(parents=True, exist_ok=True)
    images_root.mkdir(parents=True, exist_ok=True)

    scim_path = (ROOT / args.scim_image).resolve()
    registration_path = (ROOT / args.registration).resolve()

    meta = json.loads((graph_dir / "meta.json").read_text(encoding="utf-8"))
    step_m = float(meta["grid"]["step_m"])

    letters = sorted(set(c.upper() for c in args.districts if c.strip()))
    anchors = load_anchors(anchors_path, letters)
    xy = {
        row["letter"]: (float(row["anchor_east_m"]), float(row["anchor_north_m"]))
        for _, row in anchors.iterrows()
    }

    pair_filter = parse_pair_filter(args.pairs, letters)
    pairs = list(combinations(letters, 2))
    if pair_filter is not None:
        pairs = [pair for pair in pairs if tuple(sorted(pair)) in pair_filter]
    if not pairs:
        raise SystemExit("no district pairs selected")
    workers = resolve_workers(args.workers, len(pairs))

    cfg = {
        "planner": str(planner),
        "surface_graph": str(graph_dir),
        "intervals": None if intervals is None else str(intervals),
        "vehicle_passability_patches": [str(p) for p in vehicle_patches],
        "pair_filter": None if pair_filter is None else [
            f"{a}-{b}" for a, b in sorted(pair_filter)
        ],
        "regional_domain_bounds_m": (
            None
            if args.regional_domain_bounds is None
            else {
                "west": float(args.regional_domain_bounds[0]),
                "south": float(args.regional_domain_bounds[1]),
                "east": float(args.regional_domain_bounds[2]),
                "north": float(args.regional_domain_bounds[3]),
            }
        ),
        "roads": None if roads is None else str(roads),
        "build": args.build,
        "step_m": step_m,
        "mode": args.mode,
        "profiles": args.profiles,
        "bridge_policy": args.bridge_policy,
        "corridor_pad_m": args.corridor_pad_m,
        "minimum_clearance_m": args.minimum_clearance_m,
        "endpoint_access_radius_m": args.endpoint_access_radius_m,
        "access_endpoint_radius_m": args.access_endpoint_radius_m,
        "base_component_seam_penalty_m": args.base_component_seam_penalty_m,
        "cross_component_seam_penalty_m": args.cross_component_seam_penalty_m,
        "ambiguous_component_seam_penalty_m": args.ambiguous_component_seam_penalty_m,
        "road_straight_factor": args.road_straight_factor,
        "road_turn_factor": args.road_turn_factor,
        "band_continuation_factor": args.band_continuation_factor,
        "road_transition_factor": args.road_transition_factor,
        "max_complete_stretch": args.max_complete_stretch,
        "vehicle_patches": [str(p) for p in vehicle_patches],
    }

    topology_paths_path = (
        (ROOT / args.topology_paths).resolve()
        if args.topology_paths else None
    )
    topology_bounds = load_topology_pair_bounds(
        topology_paths_path,
        args.topology_margin_m,
    )

    access_targets=set(str(args.access_targets).upper())
    jobs = []
    for a,b in pairs:
        if a in access_targets and b not in access_targets:
            solved_origin,solved_destination=b,a
            destination_mode="access"
        elif b in access_targets:
            solved_origin,solved_destination=a,b
            destination_mode="access"
        else:
            solved_origin,solved_destination=a,b
            destination_mode="exact"

        if args.regional_domain_bounds is not None:
            bounds = [float(v) for v in args.regional_domain_bounds]
            regional_domain_used = True
        else:
            bounds = (
                topology_bounds.get((a,b))
                or topology_bounds.get((b,a))
            )
            regional_domain_used = False

        jobs.append({
            "a":a,
            "b":b,
            "solved_origin":solved_origin,
            "solved_destination":solved_destination,
            "origin_xy":xy[solved_origin],
            "destination_xy":xy[solved_destination],
            "pair_dir":str(pairs_root / f"{a}_to_{b}"),
            "corridor_bounds_m":bounds,
            "regional_domain_used":regional_domain_used,
            "destination_mode":destination_mode,
        })

    print(
        f"Solving {len(pairs)} unique district pairs with "
        f"{workers} worker{'s' if workers != 1 else ''}..."
    )
    started = time.perf_counter()
    results = []

    if workers == 1:
        _worker_init(cfg)
        for job in jobs:
            print(f"  {job['a']} ↔ {job['b']} ...", flush=True)
            item = _solve_pair(job)
            results.append(item)
            if item["status"] in ("PASS", "PARTIAL", "ACCESS_ENDPOINT"):
                extra = ""
                if item["status"] == "PARTIAL":
                    extra = f", gap {item['summary'].get('remaining_plan_gap_m', float('nan')):.0f} m"
                print(
                    f"    {item['status']} {item['summary']['regional_route_length_m']/1000:.2f} km"
                    f"{extra} ({item['elapsed_s']:.1f}s)"
                )
            else:
                print(f"    ERROR {item['error']}")
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_worker_init,
            initargs=(cfg,),
        ) as pool:
            futures = {pool.submit(_solve_pair, job): job for job in jobs}
            for fut in as_completed(futures):
                item = fut.result()
                results.append(item)
                if item["status"] in ("PASS", "PARTIAL", "ACCESS_ENDPOINT"):
                    extra = ""
                    if item["status"] == "PARTIAL":
                        extra = f", gap {item['summary'].get('remaining_plan_gap_m', float('nan')):.0f} m"
                    print(
                        f"  {item['a']} ↔ {item['b']} {item['status']} "
                        f"{item['summary']['regional_route_length_m']/1000:.2f} km"
                        f"{extra} ({item['elapsed_s']:.1f}s)",
                        flush=True,
                    )
                else:
                    print(
                        f"  {item['a']} ↔ {item['b']} ERROR "
                        f"({item['elapsed_s']:.1f}s) {item.get('error','')}",
                        flush=True,
                    )

    results.sort(key=lambda x: (x["a"], x["b"]))
    rows = []
    for item in results:
        so=item.get("solved_origin",item["a"])
        sd=item.get("solved_destination",item["b"])
        rows.append(directed_row(item,so,sd,solved_direction=True))
        rows.append(directed_row(item,sd,so,solved_direction=False))

    pd.DataFrame(rows).sort_values(["origin", "destination"]).to_csv(
        out_root / "district_route_summary.csv", index=False, lineterminator="\n"
    )

    pair_results = {(r["a"], r["b"]): r for r in results}
    images_written = []
    if scim_path.exists() and registration_path.exists():
        scim_image, scim_extent = registered_scim(
            scim_path, args.scim_content_crop, registration_path
        )
        for origin in letters:
            image_path = images_root / f"routes_from_{origin}.png"
            render_origin(
                origin,
                letters,
                xy,
                pair_results,
                scim_image,
                scim_extent,
                image_path,
                args.mode,
            )
            images_written.append(str(image_path))
    else:
        print(
            "SCIM image or registration file missing; "
            "skipping by-origin route images."
        )

    manifest = {
        "districts": letters,
        "unique_pairs_attempted": len(pairs),
        "unique_pairs_passed": sum(r["status"] == "PASS" for r in results),
        "unique_pairs_partial": sum(r["status"] == "PARTIAL" for r in results),
        "unique_pairs_access_endpoint": sum(r["status"] == "ACCESS_ENDPOINT" for r in results),
        "workers": workers,
        "mode": args.mode,
        "step_m": step_m,
        "component_seam_penalties_m": {
            "base_component": args.base_component_seam_penalty_m,
            "cross_component": args.cross_component_seam_penalty_m,
            "ambiguous_component": args.ambiguous_component_seam_penalty_m,
        },
        "route_aware_weights": {
            "road_straight_factor": args.road_straight_factor,
            "road_turn_factor": args.road_turn_factor,
            "band_continuation_factor": args.band_continuation_factor,
            "road_transition_factor": args.road_transition_factor,
            "max_complete_stretch": args.max_complete_stretch,
            "stretch_guardrail_mode": "diagnostic_only",
            "topology_paths": (
                None if topology_paths_path is None else str(topology_paths_path)
            ),
            "topology_margin_m": args.topology_margin_m,
            "access_targets": sorted(set(str(args.access_targets).upper())),
            "access_endpoint_radius_m": args.access_endpoint_radius_m,
        },
        "surface_graph": str(graph_dir),
        "intervals": None if intervals is None else str(intervals),
        "elapsed_s": time.perf_counter() - started,
        "pair_elapsed_s": {
            f"{r['a']}-{r['b']}": r["elapsed_s"] for r in results
        },
        "by_origin_images": images_written,
        "parallel_strategy": (
            "independent pair searches use worker processes; each worker loads the "
            "working field once and graph_solver caches SurfaceGraphData process-locally"
        ),
    }
    (out_root / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8", newline="\n"
    )

    print()
    print(
        f"Completed {manifest['unique_pairs_passed']} complete + "
        f"{manifest['unique_pairs_partial']} partial / "
        f"{manifest['unique_pairs_attempted']} pairs in "
        f"{manifest['elapsed_s']:.1f}s."
    )
    print(out_root / "district_route_summary.csv")
    if images_written:
        print(f"Images: {images_root}")
    return 0 if all(r["status"] in ("PASS", "PARTIAL", "ACCESS_ENDPOINT") for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
