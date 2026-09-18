from __future__ import annotations

import argparse
from pathlib import Path

from .io import (
    analysis_model,
    available_clearance_tolerances,
    available_local_relief_tolerances,
    available_platform_elevations,
    available_surface_resolutions,
    available_surface_variants,
    load_resources,
    load_surfaces,
    load_world,
)
from .vtk_view import view

ALL_SIZES = {"small", "medium", "large", "very_large"}


def _common(p):
    p.add_argument("--repo-root", type=Path, default=Path.cwd())
    p.add_argument("--world-manifest", type=Path, default=None)
    p.add_argument("--surface-dir", type=Path, default=None)
    p.add_argument("--resolution", type=float, default=None, help="surface-analysis horizontal resolution; defaults to the coarsest available")
    p.add_argument("--clearance-tolerance", type=float, default=None, help="horizontal-plane-fit analysis: allowed p90/perimeter clearance in metres; defaults to 4m when available")
    p.add_argument("--relief-tolerance", type=float, default=None, help="v4 local-relief analysis only")
    p.add_argument("--platform-elevation", type=float, default=None, help="elevation-sweep analysis only: sampled horizontal platform elevation")
    p.add_argument("--terrain-spacing", type=float, default=24.0, help="3D preview terrain mesh spacing in metres")
    p.add_argument("--sizes", nargs="+", choices=sorted(ALL_SIZES), default=sorted(ALL_SIZES))
    p.add_argument("--vertical-exaggeration", type=float, default=1.0)
    p.add_argument("--motion-factor", type=float, default=8.0, help="initial orbit/pan sensitivity; adjustable live in viewer")
    p.add_argument("--wheel-factor", type=float, default=0.5, help="initial mouse-wheel sensitivity; adjustable live in viewer")
    p.add_argument("--fine-factor", type=float, default=0.25, help="Shift fine-control multiplier; adjustable live in viewer")
    p.add_argument("--no-water", action="store_true")
    p.add_argument("--no-resources", action="store_true")


def parser():
    p = argparse.ArgumentParser(description="3D viewer/exporter for Satisfactory terrain and build-surface analysis")
    sub = p.add_subparsers(dest="command", required=True)
    v = sub.add_parser("view", help="open the interactive VTK desktop viewer"); _common(v)
    s = sub.add_parser("snapshot", help="render an offscreen PNG snapshot"); _common(s); s.add_argument("--output", type=Path, required=True)
    e = sub.add_parser("export", help="export a portable GLB scene"); _common(e); e.add_argument("--output", type=Path, required=True)
    return p


def _resolve(args):
    repo = args.repo_root.resolve()
    world_path = args.world_manifest or repo / "planning_data/world/manifests/world_502094.json"
    world = load_world(repo, world_path)
    surface_dir = args.surface_dir or repo / "planning_data" / world.manifest["layers"]["buildable_areas"]["outputs"]
    surfaces = load_surfaces(surface_dir)
    resources = load_resources(repo, world.manifest)
    available = available_surface_resolutions(surface_dir)
    if not available:
        raise FileNotFoundError(f"no build-surface membership files in {surface_dir}")
    resolution = args.resolution if args.resolution is not None else max(available)
    if resolution not in available:
        raise ValueError(f"resolution {resolution:g} m not present; available: {available}")
    model = analysis_model(surface_dir)
    platform_elevation = None
    relief_tolerance = None
    clearance_tolerance = None
    if model == "horizontal_plane_fit":
        vals = available_clearance_tolerances(surface_dir, resolution)
        if not vals:
            raise ValueError(f"no clearance-tolerance variants found for {resolution:g} m")
        clearance_tolerance = args.clearance_tolerance
        if clearance_tolerance is None:
            clearance_tolerance = 4.0 if 4.0 in vals else vals[len(vals)//2]
        if not any(abs(float(clearance_tolerance)-x) < 1e-6 for x in vals):
            raise ValueError(f"clearance tolerance {clearance_tolerance:g} m not present; available: {vals}")
    elif model == "local_multiscale_relief":
        vals = available_local_relief_tolerances(surface_dir, resolution)
        if not vals:
            raise ValueError(f"no relief-tolerance variants found for {resolution:g} m")
        relief_tolerance = args.relief_tolerance
        if relief_tolerance is None:
            relief_tolerance = 8.0 if 8.0 in vals else vals[len(vals)//2]
        if not any(abs(float(relief_tolerance)-x) < 1e-6 for x in vals):
            raise ValueError(f"relief tolerance {relief_tolerance:g} m not present; available: {vals}")
    elif model == "elevation_sweep":
        planes = available_platform_elevations(surface_dir, resolution)
        platform_elevation = args.platform_elevation if args.platform_elevation is not None else (max(planes) if planes else None)
        if args.platform_elevation is not None and not any(abs(float(args.platform_elevation)-x) < 1e-6 for x in planes):
            raise ValueError(f"platform elevation {args.platform_elevation:g} m not present; available: {planes}")
    return repo, world, Path(surface_dir), surfaces, resources, resolution, platform_elevation, relief_tolerance, clearance_tolerance, model


def main(argv=None):
    args = parser().parse_args(argv)
    _, world, surface_dir, surfaces, resources, resolution, platform_elevation, relief_tolerance, clearance_tolerance, model = _resolve(args)
    common = dict(resolution_m=resolution, platform_elevation_m=platform_elevation,
                  local_relief_tolerance_m=relief_tolerance, clearance_tolerance_m=clearance_tolerance, terrain_spacing_m=args.terrain_spacing,
                  size_filter=set(args.sizes), vertical_exaggeration=args.vertical_exaggeration,
                  motion_factor=args.motion_factor, wheel_factor=args.wheel_factor, fine_factor=args.fine_factor)
    if args.command == "export":
        if model in {"local_multiscale_relief", "horizontal_plane_fit"}:
            raise SystemExit("GLB export for suitability analyses is not implemented yet; use view or snapshot. The analysis CSV/rectangle outputs are portable.")
        try:
            from .export import export_glb
        except ModuleNotFoundError as exc:
            if exc.name == "trimesh":
                raise SystemExit("GLB export requires trimesh. Install export support with: python -m pip install -e \"tools\\world_viewer[export]\"") from None
            raise
        export_common = {k:v for k,v in common.items() if k not in {"motion_factor", "wheel_factor", "fine_factor", "local_relief_tolerance_m", "clearance_tolerance_m"}}
        out = export_glb(world, resources, surfaces, surface_dir, args.output,
                         include_water=not args.no_water, include_resources=not args.no_resources, **export_common)
        print(f"wrote {out}")
    else:
        view(world, resources, surfaces, surface_dir,
             show_water=not args.no_water, show_resources=not args.no_resources,
             screenshot=args.output if args.command == "snapshot" else None,
             offscreen=args.command == "snapshot", available_resolutions=available_surface_resolutions(surface_dir),
             available_variants=available_surface_variants(surface_dir), **common)
        if args.command == "snapshot":
            print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
