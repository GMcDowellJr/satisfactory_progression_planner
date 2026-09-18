from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "satisfactory_route_tool" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from satisfactory_route_tool.graph_solver import solve_surface_graph, write_result
from satisfactory_route_tool.heightfield import load_working_field
from satisfactory_route_tool.package import PlannerPackage
from satisfactory_route_tool.profiles import load_profile
from satisfactory_route_tool.surface_graph import SurfaceGraphData
from satisfactory_route_tool.vehicle_passability import (
    apply_vehicle_patch,
    load_vehicle_patch,
)


A = (-2650.293636, 370.014545)
D = (-2547.757036, -741.081591)

# This is a regional search domain, NOT an origin-destination corridor.
# It gives A* the western/southern Rocky Desert as a free 2D search area,
# including the eastward road detour and overhang.
DEFAULT_DOMAIN = (-3100.0, -1300.0, -1000.0, 700.0)  # W,S,E,N


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Targeted A->D route using a raw-geometry vehicle-passability patch. "
            "Searches a broad regional domain with no topology-path corridor."
        )
    )
    p.add_argument("--planner", default="planning_data")
    p.add_argument("--build", default="502094")
    p.add_argument("--surface-graph", required=True)
    p.add_argument("--intervals")
    p.add_argument("--vehicle-patch", required=True)
    p.add_argument(
        "--roads",
        default=(
            "planning_data/analysis/derived/rocky_desert/routes/"
            "scim_prior_10m/scim_road_prior_5m.npz"
        ),
    )
    p.add_argument("--mode", default="tractor")

    p.add_argument("--origin-east", type=float, default=A[0])
    p.add_argument("--origin-north", type=float, default=A[1])
    p.add_argument("--target-east", type=float, default=D[0])
    p.add_argument("--target-north", type=float, default=D[1])

    p.add_argument(
        "--domain-bounds",
        type=float,
        nargs=4,
        default=DEFAULT_DOMAIN,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        help=(
            "regional search domain; unlike the old corridor, this does not "
            "follow or pad the origin-destination line"
        ),
    )
    p.add_argument(
        "--domain-boundary-margin-m",
        type=float,
        default=40.0,
        help=(
            "a failed exact route can be classified ACCESS_ENDPOINT only if "
            "its closest reachable endpoint is farther than this from the "
            "regional-domain boundary"
        ),
    )
    p.add_argument("--endpoint-access-radius-m", type=float, default=200.0)
    p.add_argument("--minimum-clearance-m", type=float, default=4.5)
    p.add_argument("--out", default="data/local/routes/ad_vehicle_patch_v14")
    return p.parse_args()


def resolve(path: str | None) -> Path | None:
    if path is None:
        return None
    p = Path(path)
    return p if p.is_absolute() else (ROOT / p).resolve()


def boundary_distance(east: float, north: float, bounds) -> float:
    west, south, east_bound, north_bound = (float(x) for x in bounds)
    return min(
        east - west,
        east_bound - east,
        north - south,
        north_bound - north,
    )


def main() -> int:
    args = parse_args()
    started = time.time()

    graph_dir = resolve(args.surface_graph)
    intervals = resolve(args.intervals)
    patch_path = resolve(args.vehicle_patch)
    roads = resolve(args.roads)
    out_dir = resolve(args.out)

    graph = SurfaceGraphData(graph_dir, intervals)
    pkg = PlannerPackage(resolve(args.planner))
    field = load_working_field(pkg, args.build, graph.step_m)

    patch = load_vehicle_patch(patch_path)
    patched_field, patch_stats = apply_vehicle_patch(field, patch)

    profile = load_profile(args.mode)
    profile = dict(profile)
    profile["_mode"] = args.mode

    origin = (float(args.origin_east), float(args.origin_north))
    destination = (float(args.target_east), float(args.target_north))
    domain = tuple(float(x) for x in args.domain_bounds)

    print(
        "vehicle patch: "
        f"{patch_stats['passable_field_cells']:,} passable / "
        f"{patch_stats['tested_field_cells']:,} tested 2m field cells"
    )
    print(
        "regional search domain: "
        f"W={domain[0]:.0f}, S={domain[1]:.0f}, "
        f"E={domain[2]:.0f}, N={domain[3]:.0f}"
    )
    print("routing A -> D with exact target; no topology-path corridor...")

    result = solve_surface_graph(
        patched_field,
        origin,
        destination,
        profile,
        surface_graph_dir=graph_dir,
        intervals_path=intervals,
        road_prior_path=roads if roads and roads.exists() else None,
        bridge_policy="forbid",
        minimum_clearance_m=float(args.minimum_clearance_m),
        endpoint_access_radius_m=float(args.endpoint_access_radius_m),
        corridor_bounds_m=domain,
        # Exact first. If unreachable, the solver exhausts the reachable
        # component and returns the closest reachable state as PARTIAL.
        destination_mode="exact",
    )

    summary = result.summary
    original_status = str(summary.get("route_status"))
    auto_status = original_status
    access_reason = None
    boundary_gap = None

    if original_status == "PARTIAL":
        portal = summary.get("destination_portal") or {}
        pe = portal.get("east_m")
        pn = portal.get("north_m")
        if pe is not None and pn is not None:
            boundary_gap = boundary_distance(float(pe), float(pn), domain)

            # If exhaustive exact search stopped at an internal connectivity
            # frontier rather than at our artificial regional-domain edge, this
            # is a discovered vehicle access endpoint.
            if boundary_gap > float(args.domain_boundary_margin_m):
                auto_status = "ACCESS_ENDPOINT"
                access_reason = "target_not_vehicle_connected_within_exhausted_regional_component"
                summary["route_status"] = auto_status
                summary["destination_reached"] = False
                summary["access_endpoint_reached"] = True
                summary["access_accounted_length_m"] = summary.get(
                    "partial_accounted_length_m"
                )
                summary["partial_accounted_length_m"] = None

    summary["vehicle_passability_patch"] = patch_stats
    summary["routing_domain_model"] = "regional_domain_no_route_corridor"
    summary["regional_domain_bounds_m"] = {
        "west": domain[0],
        "south": domain[1],
        "east": domain[2],
        "north": domain[3],
    }
    summary["original_solver_status"] = original_status
    summary["automatic_endpoint_classification"] = {
        "status": auto_status,
        "reason": access_reason,
        "endpoint_distance_to_domain_boundary_m": boundary_gap,
        "boundary_margin_required_m": float(args.domain_boundary_margin_m),
    }
    summary["topology_path_corridor_used"] = False
    summary["elapsed_wrapper_s"] = time.time() - started

    out_dir.mkdir(parents=True, exist_ok=True)
    write_result(result, out_dir)

    run = {
        "schema_version": 1,
        "experiment": "A_to_D_vehicle_patch_regional_search",
        "surface_graph": str(graph_dir),
        "vehicle_patch": str(patch_path),
        "roads": str(roads) if roads else None,
        "origin": origin,
        "destination": destination,
        "domain_bounds_wsen": list(domain),
        "result_status": auto_status,
        "remaining_anchor_gap_m": summary.get("remaining_anchor_gap_m"),
        "route_length_m": summary.get("route_length_m"),
        "road_fraction": summary.get("road_fraction"),
        "reachable_search_states": summary.get("reachable_search_states"),
        "elapsed_s": time.time() - started,
    }
    (out_dir / "run_manifest.json").write_text(
        json.dumps(run, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"{auto_status}: route={summary.get('route_length_m', math.nan):.1f} m, "
        f"remaining gap={summary.get('remaining_anchor_gap_m', math.nan):.1f} m, "
        f"road fraction={summary.get('road_fraction', math.nan):.3f}"
    )
    if boundary_gap is not None:
        print(f"endpoint distance from regional boundary: {boundary_gap:.1f} m")
    print(f"wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
