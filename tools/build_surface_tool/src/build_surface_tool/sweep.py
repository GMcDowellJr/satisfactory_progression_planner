from __future__ import annotations

from pathlib import Path
import json
import math
import numpy as np
import pandas as pd

from .classify import classify_shape, classify_size
from .io import load_json, load_world_raster
from .rectangles import best_rotated_rectangle
from .regions import label_regions_at_plane
from .terrain import make_sweep_grid


def _rotation_angles(policy: dict) -> list[float]:
    vals = policy["analysis_parameters"].get("core_rotation_angles_deg", [0, 15, 30, 45, 60, 75])
    return [float(v) for v in vals]


def _plane_token(z: float) -> str:
    sign = "neg" if z < 0 else "pos"
    mag = f"{abs(float(z)):g}".replace(".", "p")
    return f"{sign}{mag}"


def _plane_sequence(obstruction_m: np.ndarray, step_m: float, minimum, maximum, origin) -> list[float]:
    finite = obstruction_m[np.isfinite(obstruction_m)]
    if finite.size == 0:
        return []
    step = float(step_m)
    if step <= 0:
        raise ValueError("vertical step must be > 0")

    zmin = float(np.nanmin(finite)) if minimum in (None, "auto") else float(minimum)
    zmax = float(np.nanmax(finite)) if maximum in (None, "auto") else float(maximum)
    if zmax < zmin:
        raise ValueError("plane maximum must be >= plane minimum")

    if origin in (None, "auto_aligned"):
        base = math.floor(zmin / step) * step
    else:
        base = float(origin)
        while base > zmin:
            base -= step
        if base + step <= zmin:
            base += math.floor((zmin - base) / step) * step

    first = base
    while first < zmin - 1e-9:
        first += step
    last = math.ceil((zmax - first) / step - 1e-12)
    return [round(first + i * step, 6) for i in range(max(0, last) + 1)]


def analyze(repo_root: Path, world_manifest: Path, policy_path: Path, output_dir: Path,
            resolutions: list[float] | None = None, vertical_step_m: float | None = None,
            plane_min_m: float | None = None, plane_max_m: float | None = None) -> pd.DataFrame:
    manifest, raster = load_world_raster(repo_root, world_manifest)
    policy = load_json(policy_path)
    ap = policy["analysis_parameters"]
    if policy.get("analysis_model") != "elevation_sweep":
        raise ValueError("this generator expects a policy with analysis_model='elevation_sweep'; use build_surfaces_v3.json")

    resolutions = resolutions or [float(x) for x in ap.get("working_resolutions_m", [16])]
    step = float(vertical_step_m if vertical_step_m is not None else ap.get("vertical_step_m", 16.0))
    foundation_m = float(policy["foundation_size_m"])
    min_small_m = float(policy["size_classes"]["small"]["minimum_short_span_m"])
    rotation_angles = _rotation_angles(policy)

    output_dir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    membership_entries: list[dict] = []
    per_plane_qa: list[dict] = []

    for resolution in resolutions:
        grid = make_sweep_grid(
            raster.height_m, raster.water_m, raster.provenance, raster.water_q, raster.meta,
            raster.source_spacing_m, resolution,
            minimum_valid_fraction=float(ap.get("minimum_valid_fraction", 0.5)),
            minimum_terrain_confidence=ap.get("minimum_terrain_confidence"),
            max_local_grade=ap.get("max_local_grade"),
            roughness_threshold_m=ap.get("roughness_threshold_m"),
            water_obstruction_mode=ap.get("water_obstruction_mode", "surface"),
        )
        planes = _plane_sequence(
            grid.obstruction_m,
            step,
            plane_min_m if plane_min_m is not None else ap.get("plane_min_m", "auto"),
            plane_max_m if plane_max_m is not None else ap.get("plane_max_m", "auto"),
            ap.get("plane_origin_m", "auto_aligned"),
        )
        min_cells = max(1, int(math.floor((min_small_m / resolution) ** 2 / 4)))
        prior_usable_fraction = -1.0

        for platform_z in planes:
            labels, regions = label_regions_at_plane(grid.domain, grid.obstruction_m, platform_z, min_cells=min_cells)
            usable_mask = labels > 0
            usable_fraction = float(np.mean(grid.domain & (grid.obstruction_m <= platform_z)))
            monotonic = usable_fraction + 1e-12 >= prior_usable_fraction
            prior_usable_fraction = usable_fraction

            token = _plane_token(platform_z)
            membership_name = f"build_surface_membership_{resolution:g}m_plane_{token}m.npz"
            np.savez_compressed(output_dir / membership_name, labels=labels)
            membership_entries.append({
                "resolution_m": float(resolution),
                "platform_elevation_m": float(platform_z),
                "vertical_step_m": float(step),
                "file": membership_name,
            })

            kept = 0
            for region in regions:
                crop = labels[region.row0:region.row1, region.col0:region.col1] == region.label
                rect = best_rotated_rectangle(crop, rotation_angles)
                width_m = rect.width_cells * resolution
                height_m = rect.height_cells * resolution
                short_f = min(width_m, height_m) / foundation_m
                long_f = max(width_m, height_m) / foundation_m
                core_area_m2 = rect.area_cells * resolution * resolution
                size_class = classify_size(short_f, core_area_m2, policy)
                if size_class == "below_small":
                    continue
                shape_class, aspect = classify_shape(short_f, long_f, policy)

                rr, cc = np.where(crop)
                gr = rr + region.row0
                gc = cc + region.col0
                terrain_med = grid.terrain_median_m[gr, gc]
                terrain_max = grid.terrain_max_m[gr, gc]
                obstruction = grid.obstruction_m[gr, gc]
                clearance = float(platform_z) - terrain_med
                east = grid.east0_m + gc * resolution
                north = grid.north0_m - gr * resolution
                kept += 1
                all_rows.append({
                    "surface_id": f"bs_{raster.build}_{resolution:g}m_p{token}m_{region.label:05d}",
                    "game_build": raster.build,
                    "policy_id": policy["policy_id"],
                    "analysis_model": "elevation_sweep",
                    "analysis_resolution_m": float(resolution),
                    "vertical_step_m": float(step),
                    "platform_elevation_m": float(platform_z),
                    "size_class": size_class,
                    "shape_class": shape_class,
                    "centroid_east_m": float(np.mean(east)),
                    "centroid_north_m": float(np.mean(north)),
                    "contiguous_area_m2": float(region.cells * resolution * resolution),
                    "core_width_foundations": float(min(short_f, long_f)),
                    "core_length_foundations": float(max(short_f, long_f)),
                    "core_area_foundations": float(rect.area_cells * (resolution / foundation_m) ** 2),
                    "core_area_m2": float(core_area_m2),
                    "core_rotation_deg": float(rect.rotation_deg),
                    "core_aspect_ratio": float(aspect),
                    "min_terrain_elevation_m": float(np.nanmin(terrain_med)),
                    "max_terrain_elevation_m": float(np.nanmax(terrain_max)),
                    "max_obstruction_elevation_m": float(np.nanmax(obstruction)),
                    "median_platform_clearance_m": float(np.nanmedian(clearance)),
                    "p90_platform_clearance_m": float(np.nanpercentile(clearance, 90)),
                    "max_platform_clearance_m": float(np.nanmax(clearance)),
                    "mean_grade": float(np.nanmean(grid.local_grade[gr, gc])),
                    "p90_grade": float(np.nanpercentile(grid.local_grade[gr, gc], 90)),
                    "mean_roughness_m": float(np.nanmean(grid.roughness_m[gr, gc])),
                    "mean_terrain_confidence": float(np.nanmean(grid.confidence_score[gr, gc])),
                    "water_fraction": float(np.nanmean(grid.water_fraction[gr, gc])),
                    "region_cells": int(region.cells),
                })

            per_plane_qa.append({
                "resolution_m": float(resolution),
                "platform_elevation_m": float(platform_z),
                "vertical_step_m": float(step),
                "grid_rows": int(grid.domain.shape[0]),
                "grid_cols": int(grid.domain.shape[1]),
                "domain_fraction": float(np.mean(grid.domain)),
                "usable_fraction": usable_fraction,
                "monotonic_from_previous_plane": bool(monotonic),
                "candidate_regions": len(regions),
                "classified_surfaces": kept,
            })

    df = pd.DataFrame(all_rows)
    if not df.empty:
        rank = {"small": 1, "medium": 2, "large": 3, "very_large": 4}
        df["_size_rank"] = df["size_class"].map(rank).fillna(0)
        df = df.sort_values(
            ["analysis_resolution_m", "platform_elevation_m", "_size_rank", "core_area_m2", "contiguous_area_m2"],
            ascending=[True, True, False, False, False],
        ).drop(columns="_size_rank")
    df.to_csv(output_dir / "build_surfaces.csv", index=False, lineterminator="\n")
    (output_dir / "build_surface_membership_index.json").write_text(
        json.dumps({"analysis_model": "elevation_sweep", "variants": membership_entries}, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )

    summary = {
        "world_extract_id": manifest["world_extract_id"],
        "game_build": raster.build,
        "policy_id": policy["policy_id"],
        "analysis_model": "elevation_sweep",
        "resolutions_m": [float(x) for x in resolutions],
        "vertical_step_m": float(step),
        "surface_count": int(len(df)),
        "counts_by_size": {} if df.empty else {str(k): int(v) for k, v in df["size_class"].value_counts().to_dict().items()},
        "note": "Rows are per horizontal resolution and sampled platform elevation. Horizontal resolution controls edge detail; vertical step controls which platform elevations are sampled. At a fixed elevation, changing step does not change geometry.",
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")

    all_monotonic = all(x["monotonic_from_previous_plane"] for x in per_plane_qa)
    qa = {
        "status": "PASS" if all_monotonic else "FAIL",
        "world_build_alignment": manifest.get("alignment", {}).get("status"),
        "source_grid": raster.meta["grid"],
        "per_plane": per_plane_qa,
        "diagnostics": {
            "horizontal_resolution_is_edge_detail": True,
            "vertical_step_is_sampling_cadence": True,
            "platform_mask_is_monotonic_with_elevation": all_monotonic,
            "coarse_cell_obstruction_reducer": "maximum terrain elevation",
            "water_obstruction_mode": ap.get("water_obstruction_mode", "surface"),
            "grade_is_gate": ap.get("max_local_grade") is not None,
            "roughness_is_gate": ap.get("roughness_threshold_m") is not None,
            "confidence_is_gate": ap.get("minimum_terrain_confidence") is not None,
        },
    }
    (output_dir / "qa.json").write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8", newline="\n")
    if not all_monotonic:
        raise RuntimeError("elevation sweep violated monotonic usable-area invariant")
    return df
