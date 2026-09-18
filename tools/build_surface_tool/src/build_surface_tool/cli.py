from __future__ import annotations

import argparse
from pathlib import Path

from .analyze import analyze
from .io import load_json

ALL_SIZES = ["small", "medium", "large", "very_large"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate terrain-derived build-surface suitability from a versioned world extract.")
    p.add_argument("--repo-root", type=Path, default=Path.cwd(), help="repository root (default: current directory)")
    p.add_argument("--world-manifest", type=Path, default=None, help="world manifest JSON; defaults to planning_data/world/manifests/world_502094.json")
    p.add_argument("--policy", type=Path, default=None, help="policy JSON; defaults to build_surfaces_v9 class-specific-coverage horizontal-plane-support policy")
    p.add_argument("--output-dir", type=Path, default=None, help="output directory")
    p.add_argument("--resolutions", type=float, nargs="+", default=None, help="horizontal analysis resolution(s) in metres")
    p.add_argument("--clearance-tolerances", type=float, nargs="+", default=None, help="allowed p90/edge clearance values for fitted horizontal planes, in metres")
    p.add_argument("--relief-tolerances", type=float, nargs="+", default=None, help="v4 local-relief policy only")
    p.add_argument("--sizes", nargs="+", choices=ALL_SIZES, default=None, help="optional subset of footprint classes")
    # Retained for running the alternate v3 elevation-sweep policy.
    p.add_argument("--vertical-step", type=float, default=None, help="v3 elevation-sweep only")
    p.add_argument("--plane-min", type=float, default=None, help="v3 elevation-sweep only")
    p.add_argument("--plane-max", type=float, default=None, help="v3 elevation-sweep only")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo_root.resolve()
    world = args.world_manifest or repo / "planning_data/world/manifests/world_502094.json"
    policy = args.policy or repo / "planning_data/analysis/policies/build_surfaces_v9.json"
    manifest = load_json(world)
    policy_data = load_json(policy)
    if args.output_dir is not None:
        output = args.output_dir
    elif policy_data.get("policy_id") == manifest.get("layers", {}).get("buildable_areas", {}).get("policy_id"):
        output = repo / "planning_data" / manifest["layers"]["buildable_areas"]["outputs"]
    else:
        output = repo / "planning_data/analysis/derived/build_surfaces" / f"build_{manifest['game']['build']}" / policy_data["policy_id"]
    df = analyze(repo, world, policy, output,
                 resolutions=args.resolutions,
                 relief_tolerances_m=args.relief_tolerances,
                 size_classes=args.sizes,
                 vertical_step_m=args.vertical_step,
                 plane_min_m=args.plane_min,
                 plane_max_m=args.plane_max,
                 clearance_tolerances_m=args.clearance_tolerances)
    print(f"wrote {len(df)} classified surface-region rows to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
