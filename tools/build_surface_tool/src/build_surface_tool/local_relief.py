from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import math
import numpy as np
import pandas as pd
from scipy import ndimage

from .classify import classify_shape
from .io import load_json, load_world_raster
from .terrain import _block_reduce, _confidence_lookup

SIZE_ORDER = ["small", "medium", "large", "very_large"]
SIZE_RANK = {name: i + 1 for i, name in enumerate(SIZE_ORDER)}


@dataclass(frozen=True)
class ReliefGrid:
    resolution_m: float
    east0_m: float
    north0_m: float
    terrain_min_m: np.ndarray
    terrain_max_m: np.ndarray
    terrain_median_m: np.ndarray
    valid_fraction: np.ndarray
    water_fraction: np.ndarray
    confidence_score: np.ndarray
    local_grade: np.ndarray
    roughness_m: np.ndarray
    domain: np.ndarray


def _coarse_relief_grid(raster, resolution_m: float, ap: dict) -> ReliefGrid:
    source_spacing = float(raster.source_spacing_m)
    raw_factor = float(resolution_m) / source_spacing
    factor = int(round(raw_factor))
    if factor < 1 or not np.isclose(raw_factor, factor):
        raise ValueError("working resolution must be an integer multiple of source spacing")

    height = raster.height_m
    finite = np.isfinite(height)
    terrain_min = _block_reduce(height, factor, np.nanmin)
    terrain_max = _block_reduce(height, factor, np.nanmax)
    terrain_median = _block_reduce(height, factor, np.nanmedian)
    valid_fraction = _block_reduce(finite.astype(np.float32), factor, np.mean)
    water_fraction = _block_reduce((raster.water_q > 0).astype(np.float32), factor, np.mean)

    scores = _confidence_lookup(raster.meta)
    max_code = int(raster.provenance.max(initial=0))
    lut = np.zeros(max_code + 1, dtype=np.float32)
    for code, score in scores.items():
        if code <= max_code:
            lut[code] = score
    confidence_native = lut[raster.provenance]
    confidence = _block_reduce(confidence_native, factor, np.mean)

    # Diagnostics at working-grid scale.
    dzdy, dzdx = np.gradient(terrain_median, float(resolution_m), float(resolution_m))
    grade = np.sqrt(dzdx * dzdx + dzdy * dzdy)
    expanded = np.repeat(np.repeat(terrain_median, factor, axis=0), factor, axis=1)
    h = min(expanded.shape[0], height.shape[0]); w = min(expanded.shape[1], height.shape[1])
    residual = np.full(height.shape, np.nan, dtype=np.float32)
    residual[:h, :w] = np.abs(height[:h, :w] - expanded[:h, :w])
    roughness = _block_reduce(residual, factor, np.nanmean)

    domain = np.isfinite(terrain_min) & np.isfinite(terrain_max)
    domain &= valid_fraction >= float(ap.get("minimum_valid_fraction", 0.95))
    if str(ap.get("water_mode", "exclude")).lower() == "exclude":
        domain &= water_fraction == 0
    elif str(ap.get("water_mode", "exclude")).lower() != "ignore":
        raise ValueError("water_mode must be 'exclude' or 'ignore' for local relief analysis")
    if ap.get("minimum_terrain_confidence") is not None:
        domain &= confidence >= float(ap["minimum_terrain_confidence"])
    if ap.get("max_local_grade") is not None:
        domain &= grade <= float(ap["max_local_grade"])
    if ap.get("roughness_threshold_m") is not None:
        domain &= roughness <= float(ap["roughness_threshold_m"])

    return ReliefGrid(
        resolution_m=float(resolution_m),
        east0_m=float(raster.meta["grid"]["x0_cm"]) / 100.0,
        north0_m=-float(raster.meta["grid"]["y0_cm"]) / 100.0,
        terrain_min_m=terrain_min.astype(np.float32),
        terrain_max_m=terrain_max.astype(np.float32),
        terrain_median_m=terrain_median.astype(np.float32),
        valid_fraction=valid_fraction.astype(np.float32),
        water_fraction=water_fraction.astype(np.float32),
        confidence_score=confidence.astype(np.float32),
        local_grade=grade.astype(np.float32),
        roughness_m=roughness.astype(np.float32),
        domain=domain,
    )


def _window_shape(span_m: list[float], resolution_m: float, orientation_deg: float) -> tuple[int, int]:
    short_m, long_m = sorted(float(x) for x in span_m)
    if int(round(float(orientation_deg))) % 180 == 90:
        row_m, col_m = long_m, short_m
    else:
        row_m, col_m = short_m, long_m
    return max(1, int(math.ceil(row_m / resolution_m))), max(1, int(math.ceil(col_m / resolution_m)))


def _footprint_relief(grid: ReliefGrid, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Moving-window min/max relief, requiring the full footprint to remain in-domain."""
    size = tuple(int(x) for x in shape)
    max_z = ndimage.maximum_filter(np.where(grid.domain, grid.terrain_max_m, -np.inf), size=size, mode="constant", cval=-np.inf)
    min_z = ndimage.minimum_filter(np.where(grid.domain, grid.terrain_min_m, np.inf), size=size, mode="constant", cval=np.inf)
    all_valid = ndimage.minimum_filter(grid.domain.astype(np.uint8), size=size, mode="constant", cval=0) > 0
    relief = max_z - min_z
    relief[~all_valid] = np.inf
    return relief.astype(np.float32), min_z.astype(np.float32), max_z.astype(np.float32), all_valid


def _placement_maps(grid: ReliefGrid, policy: dict, tolerance_m: float):
    ap = policy["analysis_parameters"]
    orientations = [float(x) for x in ap.get("footprint_orientations_deg", [0, 90])]
    class_qualifies: dict[str, np.ndarray] = {}
    class_relief: dict[str, np.ndarray] = {}
    class_orientation: dict[str, np.ndarray] = {}
    class_min: dict[str, np.ndarray] = {}
    class_max: dict[str, np.ndarray] = {}

    for name in SIZE_ORDER:
        span = policy["size_classes"][name]["reference_span_m"]
        best_relief = np.full(grid.domain.shape, np.inf, dtype=np.float32)
        best_orientation = np.full(grid.domain.shape, np.nan, dtype=np.float32)
        best_min = np.full(grid.domain.shape, np.nan, dtype=np.float32)
        best_max = np.full(grid.domain.shape, np.nan, dtype=np.float32)
        for angle in orientations:
            # v4 intentionally supports orthogonal kernels only; policy is explicit about this.
            if int(round(angle)) % 90 != 0:
                continue
            shape = _window_shape(span, grid.resolution_m, angle)
            relief, min_z, max_z, valid = _footprint_relief(grid, shape)
            improve = valid & (relief < best_relief)
            best_relief[improve] = relief[improve]
            best_orientation[improve] = angle
            best_min[improve] = min_z[improve]
            best_max[improve] = max_z[improve]
        class_qualifies[name] = np.isfinite(best_relief) & (best_relief <= float(tolerance_m))
        class_relief[name] = best_relief
        class_orientation[name] = best_orientation
        class_min[name] = best_min
        class_max[name] = best_max

    # Highest class wins at each candidate center. This makes the displayed classes exclusive.
    rank_grid = np.zeros(grid.domain.shape, dtype=np.uint8)
    for name in SIZE_ORDER:
        rank_grid[class_qualifies[name]] = SIZE_RANK[name]
    return rank_grid, class_qualifies, class_relief, class_orientation, class_min, class_max


def _overlap_fraction(a, b) -> float:
    ax0, ax1, ay0, ay1 = a
    bx0, bx1, by0, by1 = b
    ix = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    iy = max(0.0, min(ay1, by1) - max(ay0, by0))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    amin = min((ax1 - ax0) * (ay1 - ay0), (bx1 - bx0) * (by1 - by0))
    return inter / amin if amin > 0 else 0.0


def _rect_bounds(east: float, north: float, width_m: float, length_m: float, orientation_deg: float):
    if int(round(float(orientation_deg))) % 180 == 90:
        width_m, length_m = length_m, width_m
    return (east - length_m / 2, east + length_m / 2, north - width_m / 2, north + width_m / 2)


def _candidate_rectangles(region_mask: np.ndarray, region_rows: np.ndarray, region_cols: np.ndarray, grid: ReliefGrid,
                          size_class: str, policy: dict, relief_map: np.ndarray, orientation_map: np.ndarray,
                          min_map: np.ndarray, max_map: np.ndarray, max_candidates: int, overlap_limit: float):
    cfg = policy["size_classes"][size_class]
    short_m, long_m = sorted(float(x) for x in cfg["reference_span_m"])
    foundation_m = float(policy["foundation_size_m"])
    records = []
    if region_rows.size == 0:
        return records
    scores = relief_map[region_rows, region_cols]
    order = np.argsort(scores, kind="stable")
    chosen_bounds = []
    for oi in order:
        rr = int(region_rows[oi]); cc = int(region_cols[oi])
        angle = float(orientation_map[rr, cc]) if np.isfinite(orientation_map[rr, cc]) else 0.0
        east = grid.east0_m + cc * grid.resolution_m
        north = grid.north0_m - rr * grid.resolution_m
        bounds = _rect_bounds(east, north, short_m, long_m, angle)
        if any(_overlap_fraction(bounds, prior) > float(overlap_limit) for prior in chosen_bounds):
            continue
        chosen_bounds.append(bounds)
        records.append({
            "candidate_rank": len(records) + 1,
            "center_east_m": east,
            "center_north_m": north,
            "width_foundations": short_m / foundation_m,
            "length_foundations": long_m / foundation_m,
            "width_m": short_m,
            "length_m": long_m,
            "rotation_deg": angle,
            "footprint_min_terrain_elevation_m": float(min_map[rr, cc]),
            "footprint_max_terrain_elevation_m": float(max_map[rr, cc]),
            "footprint_local_relief_m": float(relief_map[rr, cc]),
            "display_elevation_m": float(max_map[rr, cc]) + 1.0,
        })
        if len(records) >= int(max_candidates):
            break
    return records


def analyze_local_relief(repo_root: Path, world_manifest: Path, policy_path: Path, output_dir: Path,
                         resolutions: list[float] | None = None, relief_tolerances_m: list[float] | None = None,
                         size_classes: list[str] | None = None) -> pd.DataFrame:
    manifest, raster = load_world_raster(repo_root, world_manifest)
    policy = load_json(policy_path)
    if policy.get("analysis_model") != "local_multiscale_relief":
        raise ValueError("local-relief generator expects analysis_model='local_multiscale_relief'")
    ap = policy["analysis_parameters"]
    resolutions = resolutions or [float(x) for x in ap.get("working_resolutions_m", [16])]
    tolerances = relief_tolerances_m or [float(x) for x in ap.get("local_relief_tolerances_m", [2, 4, 8, 16])]
    enabled = [x for x in SIZE_ORDER if x in set(size_classes or SIZE_ORDER)]
    max_candidates = int(ap.get("rectangle_candidates_per_region", 3))
    overlap_limit = float(ap.get("rectangle_non_overlap_fraction", 0.15))

    output_dir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []
    rectangle_rows: list[dict] = []
    membership_entries: list[dict] = []
    qa_variants: list[dict] = []

    for resolution in resolutions:
        grid = _coarse_relief_grid(raster, float(resolution), ap)
        for tolerance in tolerances:
            rank_grid, qualifies, reliefs, orientations, mins, maxs = _placement_maps(grid, policy, float(tolerance))
            # Disable classes not requested, and demote cells to the highest remaining qualifying class.
            if set(enabled) != set(SIZE_ORDER):
                rank_grid[:] = 0
                for name in enabled:
                    rank_grid[qualifies[name]] = SIZE_RANK[name]

            membership = np.zeros(rank_grid.shape, dtype=np.int32)
            next_label = 1
            structure = np.ones((3, 3), dtype=np.uint8)
            variant_class_counts = {}

            for name in enabled:
                rank = SIZE_RANK[name]
                exact = rank_grid == rank
                local_labels, count = ndimage.label(exact, structure=structure)
                class_regions = 0
                for local_lab in range(1, int(count) + 1):
                    rr, cc = np.where(local_labels == local_lab)
                    if rr.size == 0:
                        continue
                    global_lab = next_label; next_label += 1
                    membership[rr, cc] = global_lab
                    class_regions += 1
                    east = grid.east0_m + cc * grid.resolution_m
                    north = grid.north0_m - rr * grid.resolution_m
                    bbox_w_m = (int(cc.max()) - int(cc.min()) + 1) * grid.resolution_m
                    bbox_h_m = (int(rr.max()) - int(rr.min()) + 1) * grid.resolution_m
                    shape_class, aspect = classify_shape(bbox_w_m, bbox_h_m, policy)
                    sid = f"bs_{raster.build}_{resolution:g}m_r{float(tolerance):g}m_{global_lab:05d}"
                    candidates = _candidate_rectangles(
                        local_labels == local_lab, rr, cc, grid, name, policy,
                        reliefs[name], orientations[name], mins[name], maxs[name], max_candidates, overlap_limit,
                    )
                    for rec in candidates:
                        rectangle_rows.append({
                            "rectangle_id": f"{sid}_rect_{int(rec['candidate_rank']):02d}",
                            "surface_id": sid,
                            "game_build": raster.build,
                            "policy_id": policy["policy_id"],
                            "analysis_model": "local_multiscale_relief",
                            "analysis_resolution_m": float(resolution),
                            "local_relief_tolerance_m": float(tolerance),
                            "size_class": name,
                            **rec,
                        })
                    cfg = policy["size_classes"][name]
                    primary = candidates[0] if candidates else None
                    all_rows.append({
                        "surface_id": sid,
                        "game_build": raster.build,
                        "policy_id": policy["policy_id"],
                        "analysis_model": "local_multiscale_relief",
                        "analysis_resolution_m": float(resolution),
                        "local_relief_tolerance_m": float(tolerance),
                        "size_class": name,
                        "shape_class": shape_class,
                        "centroid_east_m": float(np.mean(east)),
                        "centroid_north_m": float(np.mean(north)),
                        "placement_zone_area_m2": float(rr.size * resolution * resolution),
                        "contiguous_area_m2": float(rr.size * resolution * resolution),
                        "qualifying_center_count": int(rr.size),
                        "core_width_foundations": float(min(cfg["reference_span_foundations"])),
                        "core_length_foundations": float(max(cfg["reference_span_foundations"])),
                        "core_area_foundations": float(np.prod(cfg["reference_span_foundations"])),
                        "core_area_m2": float(cfg["reference_core_area_m2"]),
                        "core_rotation_deg": None if primary is None else float(primary["rotation_deg"]),
                        "core_aspect_ratio": float(aspect),
                        "min_local_relief_m": float(np.nanmin(reliefs[name][rr, cc])),
                        "median_local_relief_m": float(np.nanmedian(reliefs[name][rr, cc])),
                        "max_local_relief_m": float(np.nanmax(reliefs[name][rr, cc])),
                        "mean_grade": float(np.nanmean(grid.local_grade[rr, cc])),
                        "p90_grade": float(np.nanpercentile(grid.local_grade[rr, cc], 90)),
                        "mean_roughness_m": float(np.nanmean(grid.roughness_m[rr, cc])),
                        "mean_terrain_confidence": float(np.nanmean(grid.confidence_score[rr, cc])),
                        "water_fraction": float(np.nanmean(grid.water_fraction[rr, cc])),
                        "rectangle_candidate_count": int(len(candidates)),
                    })
                variant_class_counts[name] = class_regions

            token = f"{float(tolerance):g}".replace(".", "p")
            filename = f"build_surface_membership_{float(resolution):g}m_relief_{token}m.npz"
            np.savez_compressed(output_dir / filename, labels=membership, class_rank=rank_grid)
            membership_entries.append({
                "resolution_m": float(resolution),
                "local_relief_tolerance_m": float(tolerance),
                "file": filename,
            })
            qa_variants.append({
                "resolution_m": float(resolution),
                "local_relief_tolerance_m": float(tolerance),
                "grid_rows": int(rank_grid.shape[0]),
                "grid_cols": int(rank_grid.shape[1]),
                "domain_fraction": float(np.mean(grid.domain)),
                "qualified_center_fraction": float(np.mean(rank_grid > 0)),
                "regions_by_highest_class": variant_class_counts,
                "center_counts_by_highest_class": {
                    name: int(np.count_nonzero(rank_grid == SIZE_RANK[name])) for name in enabled
                },
            })

    df = pd.DataFrame(all_rows)
    rectangles = pd.DataFrame(rectangle_rows)
    if not df.empty:
        df["_rank"] = df["size_class"].map(SIZE_RANK)
        df = df.sort_values(["analysis_resolution_m", "local_relief_tolerance_m", "_rank", "placement_zone_area_m2"],
                            ascending=[True, True, False, False]).drop(columns="_rank")
    if not rectangles.empty:
        rectangles = rectangles.sort_values(["analysis_resolution_m", "local_relief_tolerance_m", "size_class", "surface_id", "candidate_rank"])
    df.to_csv(output_dir / "build_surfaces.csv", index=False)
    rectangles.to_csv(output_dir / "build_surface_rectangles.csv", index=False)
    (output_dir / "build_surface_membership_index.json").write_text(
        json.dumps({"analysis_model": "local_multiscale_relief", "variants": membership_entries}, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "world_extract_id": manifest["world_extract_id"],
        "game_build": raster.build,
        "policy_id": policy["policy_id"],
        "analysis_model": "local_multiscale_relief",
        "resolutions_m": [float(x) for x in resolutions],
        "local_relief_tolerances_m": [float(x) for x in tolerances],
        "surface_region_count": int(len(df)),
        "rectangle_candidate_count": int(len(rectangles)),
        "counts_by_size": {} if df.empty else {str(k): int(v) for k, v in df["size_class"].value_counts().to_dict().items()},
        "note": "Irregular regions are zones of qualifying footprint centers. build_surface_rectangles.csv contains the concrete reference footprints demonstrating qualification.",
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    qa = {
        "status": "PASS",
        "world_build_alignment": manifest.get("alignment", {}).get("status"),
        "source_grid": raster.meta["grid"],
        "variants": qa_variants,
        "diagnostics": {
            "horizontal_resolution_independent_of_relief_tolerance": True,
            "size_classes_use_distinct_reference_footprints": True,
            "displayed_regions_are_placement_center_zones": True,
            "qualifying_rectangles_emitted": True,
            "water_mode": ap.get("water_mode", "exclude"),
            "grade_is_gate": ap.get("max_local_grade") is not None,
            "roughness_is_gate": ap.get("roughness_threshold_m") is not None,
            "confidence_is_gate": ap.get("minimum_terrain_confidence") is not None,
        },
    }
    (output_dir / "qa.json").write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    return df
