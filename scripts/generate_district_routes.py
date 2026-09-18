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
ROUTE_SRC = ROOT / "tools" / "satisfactory_route_tool" / "src"
if str(ROUTE_SRC) not in sys.path:
    sys.path.insert(0, str(ROUTE_SRC))

from satisfactory_route_tool.package import PlannerPackage
from satisfactory_route_tool.heightfield import load_working_field
from satisfactory_route_tool.profiles import load_profile
from satisfactory_route_tool.roads import load_road_prior
from satisfactory_route_tool.solver import LayeredRouteError, solve, write_result


DEFAULT_ANCHORS = "planning_data/analysis/derived/rocky_desert/district_anchors.csv"
DEFAULT_ROADS = (
    "planning_data/analysis/derived/rocky_desert/routes/"
    "scim_prior_10m/scim_road_prior_5m.npz"
)
DEFAULT_MULTISURFACE = "data/local/spatial/multisurface/multisurface.npz"
DEFAULT_SCIM = "planning_data/analysis/derived/rocky_desert/scim_roads/scim_map_crop.png"
DEFAULT_REGISTRATION = (
    "planning_data/analysis/derived/rocky_desert/scim_roads/scim_image_registration.csv"
)
DEFAULT_OUT = "data/local/routes/district_network_layered"


# Worker-local read-only routing state. Each process loads it once, then reuses it for
# several route searches. This is much faster than re-reading the multi-surface NPZ for
# every pair and avoids trying to pickle very large NumPy arrays between processes.
_W_FIELD = None
_W_ROADS = None
_W_ROAD_BAND = None
_W_PROFILE = None
_W_CFG = None


def parse_args():
    p = argparse.ArgumentParser(
        description=(
            "Generate the complete A-F Rocky Desert layered district route network. "
            "Each unique physical pair is solved once; outputs are then presented from "
            "each district as an origin to all other districts."
        )
    )
    p.add_argument("--planner", default="planning_data")
    p.add_argument("--anchors", default=DEFAULT_ANCHORS)
    p.add_argument("--roads", default=DEFAULT_ROADS)
    p.add_argument("--multisurface", default=DEFAULT_MULTISURFACE)
    p.add_argument("--scim-image", default=DEFAULT_SCIM)
    p.add_argument("--registration", default=DEFAULT_REGISTRATION)
    p.add_argument("--out", default=DEFAULT_OUT)
    p.add_argument("--build", default="502094")
    p.add_argument("--mode", default="tractor", choices=["foot", "tractor", "truck", "rail"])
    p.add_argument("--step-m", type=float, default=10.0)
    p.add_argument("--corridor-pad-m", type=float, default=1600.0)
    p.add_argument("--endpoint-access-radius-m", type=float, default=200.0)
    p.add_argument("--minimum-clearance-m", type=float)
    p.add_argument("--bridge-policy", choices=["forbid", "allow"], default="forbid")
    p.add_argument(
        "--workers",
        type=int,
        default=0,
        help=(
            "parallel route worker processes. 0=auto (up to 4, roughly half CPU count); "
            "1=serial/debug. Each worker holds its own copy of the routing arrays."
        ),
    )
    p.add_argument(
        "--districts",
        default="ABCDEF",
        help="district letters to include; default ABCDEF",
    )
    p.add_argument(
        "--scim-content-crop",
        nargs=4,
        type=int,
        default=[49, 68, 1752, 1769],
        metavar=("X0", "Y0", "X1", "Y1"),
        help=(
            "registered content crop inside scim_map_crop.png. The current Rocky Desert "
            "artifact uses 49 68 1752 1769."
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

    # Route search is CPU-bound Python, so use processes, not threads. Keep auto modest
    # because each worker owns a copy of the whole-world multi-surface arrays.
    cpu = os.cpu_count() or 2
    auto = max(1, min(4, max(1, cpu // 2)))
    return min(auto, pair_count)


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


def portal_for_direction(summary: dict, origin: str, a: str, b: str):
    if origin == a:
        return summary["origin_portal"], summary["destination_portal"]
    return summary["destination_portal"], summary["origin_portal"]


def anchor_for_direction(summary: dict, origin: str, a: str, b: str):
    if origin == a:
        return summary["origin_anchor"], summary["destination_anchor"]
    return summary["destination_anchor"], summary["origin_anchor"]


def summary_row(a: str, b: str, origin: str, dest: str, summary: dict, pair_dir: Path):
    op, dp = portal_for_direction(summary, origin, a, b)
    oa, da = anchor_for_direction(summary, origin, a, b)
    return {
        "origin": origin,
        "destination": dest,
        "status": "PASS",
        "regional_route_length_m": summary.get("regional_route_length_m", summary["route_length_m"]),
        "origin_connector_m": op.get("connector_m"),
        "destination_connector_m": dp.get("connector_m"),
        "anchor_to_anchor_accounted_length_m": summary.get("anchor_to_anchor_accounted_length_m"),
        "road_fraction": summary.get("road_fraction"),
        "road_band_fraction": summary.get("road_band_fraction"),
        "water_fraction": summary.get("water_fraction"),
        "max_routing_grade_pct": summary.get("max_routing_grade_pct"),
        "multisurface_fraction": summary.get("multisurface_fraction"),
        "multi_layer_fraction": summary.get("multi_layer_fraction"),
        "surface_component_switches": summary.get("surface_component_switches"),
        "minimum_clearance_m": summary.get("minimum_clearance_m"),
        "origin_anchor_east_m": oa.get("east_m"),
        "origin_anchor_north_m": oa.get("north_m"),
        "origin_anchor_z_m": oa.get("z_m"),
        "origin_portal_east_m": op.get("east_m"),
        "origin_portal_north_m": op.get("north_m"),
        "origin_portal_z_m": op.get("z_m"),
        "origin_portal_direct_grade_pct": op.get("direct_grade_pct"),
        "destination_anchor_east_m": da.get("east_m"),
        "destination_anchor_north_m": da.get("north_m"),
        "destination_anchor_z_m": da.get("z_m"),
        "destination_portal_east_m": dp.get("east_m"),
        "destination_portal_north_m": dp.get("north_m"),
        "destination_portal_z_m": dp.get("z_m"),
        "destination_portal_direct_grade_pct": dp.get("direct_grade_pct"),
        "pair_output": str(pair_dir),
    }


def reverse_route(df: pd.DataFrame):
    out = df.iloc[::-1].copy().reset_index(drop=True)
    if "point_order" in out:
        out["point_order"] = range(len(out))
    if "segment_distance_m" in out:
        # Distances belong to edges, so reconstruct after reversal from XY rather than
        # merely reversing the old edge labels.
        de = out["east_m"].diff()
        dn = out["north_m"].diff()
        out["segment_distance_m"] = (de.pow(2) + dn.pow(2)).pow(0.5).fillna(0.0)
    if "cumulative_distance_m" in out and "segment_distance_m" in out:
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


def _worker_init(cfg: dict):
    global _W_FIELD, _W_ROADS, _W_ROAD_BAND, _W_PROFILE, _W_CFG

    _W_CFG = cfg
    pkg = PlannerPackage(Path(cfg["planner_path"]))
    _W_FIELD = load_working_field(pkg, cfg["build"], cfg["step_m"])
    _W_ROADS, _W_ROAD_BAND = load_road_prior(cfg["roads_path"], _W_FIELD.shape)
    _W_PROFILE = dict(load_profile(cfg["mode"], None))
    _W_PROFILE["_mode"] = cfg["mode"]

    # Warm the worker-local multi-surface cache once. solver.load_multisurface is cached,
    # so all later pair solves in this worker reuse the same arrays.
    from satisfactory_route_tool.solver import load_multisurface
    load_multisurface(cfg["multisurface_path"])


def _solve_pair_worker(job: dict) -> dict:
    a = job["a"]
    b = job["b"]
    pair_dir = Path(job["pair_dir"])
    pair_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    try:
        result = solve(
            _W_FIELD,
            tuple(job["origin_xy"]),
            tuple(job["destination_xy"]),
            _W_PROFILE,
            roads=_W_ROADS,
            road_band=_W_ROAD_BAND,
            bridge_policy=_W_CFG["bridge_policy"],
            corridor_pad_m=_W_CFG["corridor_pad_m"],
            cliff_ambiguity_mode="layered",
            multisurface_path=_W_CFG["multisurface_path"],
            minimum_clearance_m=_W_CFG["minimum_clearance_m"],
            endpoint_access_radius_m=_W_CFG["endpoint_access_radius_m"],
        )
        write_result(result, pair_dir, _W_FIELD, _W_ROADS)
        return {
            "a": a,
            "b": b,
            "status": "PASS",
            "summary": result.summary,
            "pair_dir": str(pair_dir),
            "elapsed_s": time.perf_counter() - started,
        }
    except LayeredRouteError as exc:
        exc.diagnostic.to_csv(pair_dir / "layered_failure_frontier.csv", index=False)
        (pair_dir / "layered_failure_summary.json").write_text(
            json.dumps(exc.summary, indent=2), encoding="utf-8"
        )
        return {
            "a": a,
            "b": b,
            "status": "FAIL",
            "error": str(exc),
            "failure_summary": exc.summary,
            "pair_dir": str(pair_dir),
            "elapsed_s": time.perf_counter() - started,
        }
    except Exception as exc:
        (pair_dir / "error.txt").write_text(repr(exc), encoding="utf-8")
        return {
            "a": a,
            "b": b,
            "status": "ERROR",
            "error": repr(exc),
            "pair_dir": str(pair_dir),
            "elapsed_s": time.perf_counter() - started,
        }


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
        if not item or item["status"] != "PASS":
            continue

        route_path = Path(item["pair_dir"]) / "route_points.csv"
        route = pd.read_csv(route_path)
        if origin != a:
            route = reverse_route(route)

        summary = item["summary"]
        op, dp = portal_for_direction(summary, origin, a, b)
        oa, da = anchor_for_direction(summary, origin, a, b)

        ax.plot(
            route["east_m"],
            route["north_m"],
            linewidth=2.0,
            label=f"{origin}→{dest}  {summary['regional_route_length_m']/1000:.2f} km",
        )
        ax.plot(
            [oa["east_m"], op["east_m"]],
            [oa["north_m"], op["north_m"]],
            linestyle="--",
            linewidth=1.0,
            alpha=0.8,
        )
        ax.plot(
            [dp["east_m"], da["east_m"]],
            [dp["north_m"], da["north_m"]],
            linestyle="--",
            linewidth=1.0,
            alpha=0.8,
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
        f"Rocky Desert layered routes from {origin} "
        f"({mode}; dashed = local access connector)"
    )
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def main():
    args = parse_args()
    letters = sorted(set(c.upper() for c in args.districts if c.strip()))
    if len(letters) < 2:
        raise SystemExit("need at least two districts")

    planner_path = (ROOT / args.planner).resolve()
    anchors_path = (ROOT / args.anchors).resolve()
    roads_path = (ROOT / args.roads).resolve()
    multisurface_path = (ROOT / args.multisurface).resolve()
    scim_path = (ROOT / args.scim_image).resolve()
    registration_path = (ROOT / args.registration).resolve()
    out_root = (ROOT / args.out).resolve()
    pairs_root = out_root / "pairs"
    images_root = out_root / "by_origin"
    pairs_root.mkdir(parents=True, exist_ok=True)
    images_root.mkdir(parents=True, exist_ok=True)

    for required in (planner_path, anchors_path, roads_path, multisurface_path):
        if not required.exists():
            raise SystemExit(f"required input not found: {required}")

    anchors = load_anchors(anchors_path, letters)
    anchor_xy = {
        row["letter"]: (float(row["anchor_east_m"]), float(row["anchor_north_m"]))
        for _, row in anchors.iterrows()
    }

    pairs = list(combinations(letters, 2))
    workers = resolve_workers(args.workers, len(pairs))
    cfg = {
        "planner_path": str(planner_path),
        "roads_path": str(roads_path),
        "multisurface_path": str(multisurface_path),
        "build": args.build,
        "mode": args.mode,
        "step_m": args.step_m,
        "bridge_policy": args.bridge_policy,
        "corridor_pad_m": args.corridor_pad_m,
        "endpoint_access_radius_m": args.endpoint_access_radius_m,
        "minimum_clearance_m": args.minimum_clearance_m,
    }

    jobs = []
    for a, b in pairs:
        jobs.append({
            "a": a,
            "b": b,
            "origin_xy": anchor_xy[a],
            "destination_xy": anchor_xy[b],
            "pair_dir": str(pairs_root / f"{a}_to_{b}"),
        })

    print(
        f"Solving {len(letters)} districts / {len(pairs)} unique physical pairs "
        f"with {workers} worker{'s' if workers != 1 else ''}..."
    )
    started_all = time.perf_counter()
    raw_results = []

    if workers == 1:
        _worker_init(cfg)
        for job in jobs:
            print(f"  {job['a']} ↔ {job['b']} ...", flush=True)
            item = _solve_pair_worker(job)
            raw_results.append(item)
            if item["status"] == "PASS":
                print(
                    f"    PASS regional={item['summary']['regional_route_length_m']/1000:.2f} km "
                    f"({item['elapsed_s']:.1f}s)"
                )
            else:
                print(f"    {item['status']} ({item['elapsed_s']:.1f}s) {item.get('error','')}")
    else:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_worker_init,
            initargs=(cfg,),
        ) as pool:
            futures = {pool.submit(_solve_pair_worker, job): job for job in jobs}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    item = future.result()
                except Exception as exc:
                    item = {
                        "a": job["a"],
                        "b": job["b"],
                        "status": "ERROR",
                        "error": repr(exc),
                        "pair_dir": job["pair_dir"],
                        "elapsed_s": math.nan,
                    }
                raw_results.append(item)
                if item["status"] == "PASS":
                    print(
                        f"  {item['a']} ↔ {item['b']} PASS "
                        f"{item['summary']['regional_route_length_m']/1000:.2f} km "
                        f"({item['elapsed_s']:.1f}s)",
                        flush=True,
                    )
                else:
                    print(
                        f"  {item['a']} ↔ {item['b']} {item['status']} "
                        f"({item.get('elapsed_s', math.nan):.1f}s) {item.get('error','')}",
                        flush=True,
                    )

    elapsed_all = time.perf_counter() - started_all
    raw_results.sort(key=lambda x: (x["a"], x["b"]))
    pair_results = {(x["a"], x["b"]): x for x in raw_results}

    directed_rows = []
    for item in raw_results:
        a, b = item["a"], item["b"]
        pair_dir = Path(item["pair_dir"])
        if item["status"] == "PASS":
            summary = item["summary"]
            directed_rows.append(summary_row(a, b, a, b, summary, pair_dir))
            directed_rows.append(summary_row(a, b, b, a, summary, pair_dir))
        else:
            for origin, dest in ((a, b), (b, a)):
                row = {
                    "origin": origin,
                    "destination": dest,
                    "status": item["status"],
                    "pair_output": str(pair_dir),
                    "error": item.get("error"),
                }
                if item.get("failure_summary"):
                    row["closest_reachable_to_goal_m"] = item["failure_summary"].get(
                        "closest_reachable_to_goal_m"
                    )
                directed_rows.append(row)

    summary_df = pd.DataFrame(directed_rows).sort_values(["origin", "destination"])
    summary_df.to_csv(out_root / "district_route_summary.csv", index=False)

    matrix = pd.DataFrame(index=letters, columns=letters, dtype=float)
    for k in letters:
        matrix.loc[k, k] = 0.0
    for (a, b), item in pair_results.items():
        if item["status"] == "PASS":
            km = float(item["summary"]["regional_route_length_m"]) / 1000.0
            matrix.loc[a, b] = km
            matrix.loc[b, a] = km
    matrix.index.name = "origin"
    matrix.to_csv(out_root / "regional_route_length_matrix_km.csv")

    if scim_path.exists() and registration_path.exists():
        scim_image, scim_extent = registered_scim(
            scim_path, args.scim_content_crop, registration_path
        )
        for origin in letters:
            render_origin(
                origin,
                letters,
                anchor_xy,
                pair_results,
                scim_image,
                scim_extent,
                images_root / f"routes_from_{origin}.png",
                args.mode,
            )
    else:
        print("SCIM image or registration missing; skipping origin overlay images.")

    manifest = {
        "districts": letters,
        "unique_pairs_attempted": len(pairs),
        "unique_pairs_passed": sum(
            1 for item in pair_results.values() if item["status"] == "PASS"
        ),
        "mode": args.mode,
        "step_m": args.step_m,
        "bridge_policy": args.bridge_policy,
        "cliff_ambiguity_mode": "layered",
        "multisurface": str(multisurface_path),
        "corridor_pad_m": args.corridor_pad_m,
        "endpoint_access_radius_m": args.endpoint_access_radius_m,
        "minimum_clearance_m": args.minimum_clearance_m,
        "workers": workers,
        "elapsed_s": elapsed_all,
        "pair_elapsed_s": {
            f"{x['a']}-{x['b']}": x.get("elapsed_s") for x in raw_results
        },
        "parallelism": (
            "Independent A-F pair searches use worker processes because the Python A* "
            "search is CPU-bound. Each worker loads routing terrain/road/multisurface "
            "state once and reuses it for multiple pairs."
        ),
        "note": (
            "Each unique physical pair is solved once because the current terrain, road, "
            "water, grade and endpoint-connector costs are symmetric. Directed A→B and "
            "B→A records/images reuse the same validated physical route in reverse."
        ),
    }
    (out_root / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print()
    print(
        f"Completed: {manifest['unique_pairs_passed']}/{manifest['unique_pairs_attempted']} "
        f"unique pairs passed in {elapsed_all:.1f}s with {workers} worker(s)."
    )
    print(f"Summary: {out_root / 'district_route_summary.csv'}")
    print(f"Matrix:  {out_root / 'regional_route_length_matrix_km.csv'}")
    print(f"Images:  {images_root}")
    return 0 if manifest["unique_pairs_passed"] == manifest["unique_pairs_attempted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
