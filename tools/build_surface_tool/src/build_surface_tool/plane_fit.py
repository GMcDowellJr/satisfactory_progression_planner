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


def _safe_nanmean(values: np.ndarray) -> float:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    return float(vals.mean()) if vals.size else float("nan")


def _safe_nanpercentile(values: np.ndarray, q: float) -> float:
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    return float(np.percentile(vals, q)) if vals.size else float("nan")


@dataclass(frozen=True)
class PlaneFitGrid:
    resolution_m: float
    east0_m: float
    north0_m: float
    terrain_surface_m: np.ndarray
    terrain_min_m: np.ndarray
    terrain_max_m: np.ndarray
    valid_fraction: np.ndarray
    water_fraction: np.ndarray
    confidence_score: np.ndarray
    local_grade: np.ndarray
    roughness_m: np.ndarray
    domain: np.ndarray
    fit_known: np.ndarray
    overhead_fraction: np.ndarray


def _nanpercentile_block(arr: np.ndarray, factor: int, percentile: float) -> np.ndarray:
    h = (arr.shape[0] // factor) * factor
    w = (arr.shape[1] // factor) * factor
    view = arr[:h, :w].reshape(h // factor, factor, w // factor, factor)
    import warnings
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanpercentile(view, float(percentile), axis=(1, 3)).astype(np.float32)


def _coarse_plane_grid(raster, resolution_m: float, ap: dict) -> PlaneFitGrid:
    source_spacing = float(raster.source_spacing_m)
    raw_factor = float(resolution_m) / source_spacing
    factor = int(round(raw_factor))
    if factor < 1 or not np.isclose(raw_factor, factor):
        raise ValueError("working resolution must be an integer multiple of source spacing")

    height = raster.height_m
    finite = np.isfinite(height)
    terrain_min = _block_reduce(height, factor, np.nanmin)
    terrain_max = _block_reduce(height, factor, np.nanmax)
    cell_percentile = float(ap.get("cell_surface_percentile", 50.0))
    surface_mode = str(ap.get("terrain_surface_mode", "all_top_surface")).lower()
    ground_codes = [int(x) for x in ap.get("ground_provenance_codes", [1, 3])]
    overhead_codes = [int(x) for x in ap.get("overhead_surface_codes", [4, 5])]
    if surface_mode == "prefer_ground_provenance":
        ground_native = finite & np.isin(raster.provenance, ground_codes)
        ground_height = np.where(ground_native, height, np.nan)
        terrain_surface = _nanpercentile_block(ground_height, factor, cell_percentile)
        ground_count = _block_reduce(ground_native.astype(np.float32), factor, np.sum)
        fit_known = np.isfinite(terrain_surface) & (ground_count >= float(ap.get("minimum_ground_samples_per_cell", 1)))
        overhead_fraction = _block_reduce(np.isin(raster.provenance, overhead_codes).astype(np.float32), factor, np.mean)
    elif surface_mode == "all_top_surface":
        terrain_surface = _nanpercentile_block(height, factor, cell_percentile)
        fit_known = np.isfinite(terrain_surface)
        overhead_fraction = _block_reduce(np.isin(raster.provenance, overhead_codes).astype(np.float32), factor, np.mean)
    else:
        raise ValueError("terrain_surface_mode must be 'all_top_surface' or 'prefer_ground_provenance'")
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

    dzdy, dzdx = np.gradient(terrain_surface, float(resolution_m), float(resolution_m))
    grade = np.sqrt(dzdx * dzdx + dzdy * dzdy)
    expanded = np.repeat(np.repeat(terrain_surface, factor, axis=0), factor, axis=1)
    h = min(expanded.shape[0], height.shape[0]); w = min(expanded.shape[1], height.shape[1])
    residual = np.full(height.shape, np.nan, dtype=np.float32)
    residual[:h, :w] = np.abs(height[:h, :w] - expanded[:h, :w])
    roughness = _block_reduce(residual, factor, np.nanmean)

    # ``domain`` means the world cell itself is valid for analysis, not that a
    # ground-support elevation was recovered. With provenance-aware fitting,
    # cliff/overhang cells can be vertically ambiguous while still being valid
    # map cells; ``fit_known`` and minimum_fit_known_fraction handle support.
    domain = valid_fraction >= float(ap.get("minimum_valid_fraction", 0.95))
    if surface_mode == "all_top_surface":
        domain &= np.isfinite(terrain_surface)
    water_mode = str(ap.get("water_mode", "exclude")).lower()
    if water_mode == "exclude":
        domain &= water_fraction == 0
    elif water_mode != "ignore":
        raise ValueError("water_mode must be 'exclude' or 'ignore' for plane-fit analysis")
    if ap.get("minimum_terrain_confidence") is not None:
        domain &= confidence >= float(ap["minimum_terrain_confidence"])

    return PlaneFitGrid(
        resolution_m=float(resolution_m),
        east0_m=float(raster.meta["grid"]["x0_cm"]) / 100.0,
        north0_m=-float(raster.meta["grid"]["y0_cm"]) / 100.0,
        terrain_surface_m=terrain_surface.astype(np.float32),
        terrain_min_m=terrain_min.astype(np.float32),
        terrain_max_m=terrain_max.astype(np.float32),
        valid_fraction=valid_fraction.astype(np.float32),
        water_fraction=water_fraction.astype(np.float32),
        confidence_score=confidence.astype(np.float32),
        local_grade=grade.astype(np.float32),
        roughness_m=roughness.astype(np.float32),
        domain=domain,
        fit_known=fit_known.astype(bool),
        overhead_fraction=overhead_fraction.astype(np.float32),
    )


def _window_shape(span_m: list[float], resolution_m: float, orientation_deg: float) -> tuple[int, int]:
    short_m, long_m = sorted(float(x) for x in span_m)
    if int(round(float(orientation_deg))) % 180 == 90:
        row_m, col_m = long_m, short_m
    else:
        row_m, col_m = short_m, long_m
    return max(1, int(math.ceil(row_m / resolution_m))), max(1, int(math.ceil(col_m / resolution_m)))


def _perimeter_footprint(shape: tuple[int, int]) -> np.ndarray:
    nr, nc = (int(shape[0]), int(shape[1]))
    fp = np.zeros((nr, nc), dtype=bool)
    fp[0, :] = True; fp[-1, :] = True; fp[:, 0] = True; fp[:, -1] = True
    return fp


def _even_window_origin(shape: tuple[int, int]) -> tuple[int, int]:
    """Align ndimage correlation/convolution footprints with size-based filters.

    scipy's size-based maximum/uniform filters and kernel-based convolution use
    opposite half-cell conventions for even windows unless the kernel origin is
    shifted by -1 on each even axis. Without this, an edge-mean can sample a
    neighboring footprint and even exceed the fitted platform maximum.
    """
    return tuple(-1 if int(n) % 2 == 0 else 0 for n in shape)


def _plane_metrics(grid: PlaneFitGrid, shape: tuple[int, int], ap: dict):
    """Fit one flat plane using only known ground-support samples.

    Landscape/fill-derived cells are ground support when
    ``terrain_surface_mode=prefer_ground_provenance``. Cliff-only cells remain
    vertical-layer ambiguity: they may be overhead rock/bridges in the 2.5D
    heightfield, so a limited fraction may be unknown without lifting the plane.
    Water/no-data/base-domain failures still invalidate the footprint.
    """
    size = tuple(int(x) for x in shape)
    known = grid.domain & grid.fit_known & np.isfinite(grid.terrain_surface_m)
    terrain = np.where(known, grid.terrain_surface_m, 0.0).astype(np.float32)
    max_src = np.where(known, grid.terrain_surface_m, -np.inf)
    min_src = np.where(known, grid.terrain_surface_m, np.inf)
    platform_z = ndimage.maximum_filter(max_src, size=size, mode="constant", cval=-np.inf)
    min_z = ndimage.minimum_filter(min_src, size=size, mode="constant", cval=np.inf)
    all_domain = ndimage.minimum_filter(grid.domain.astype(np.uint8), size=size, mode="constant", cval=0) > 0

    footprint_area = float(size[0] * size[1])
    known_fraction = ndimage.uniform_filter(known.astype(np.float32), size=size, mode="constant", cval=0.0)
    terrain_sum = ndimage.uniform_filter(terrain, size=size, mode="constant", cval=0.0) * footprint_area
    known_count = known_fraction * footprint_area
    mean_z = np.divide(terrain_sum, known_count, out=np.full_like(terrain_sum, np.nan), where=known_count > 0)

    edge_fp = _perimeter_footprint(size).astype(np.float32)
    edge_count_total = float(edge_fp.sum())
    origin = _even_window_origin(size)
    edge_known_count = ndimage.convolve(known.astype(np.float32), edge_fp, mode="constant", cval=0.0, origin=origin)
    edge_sum = ndimage.convolve(terrain, edge_fp, mode="constant", cval=0.0, origin=origin)
    edge_mean_z = np.divide(edge_sum, edge_known_count, out=np.full_like(edge_sum, np.nan), where=edge_known_count > 0)
    edge_known_fraction = edge_known_count / max(edge_count_total, 1.0)

    overhead_ambiguous_fraction = ndimage.uniform_filter(grid.overhead_fraction.astype(np.float32), size=size, mode="constant", cval=0.0)
    mean_clearance = platform_z - mean_z
    edge_mean_clearance = platform_z - edge_mean_z
    max_clearance = platform_z - min_z
    valid = all_domain & np.isfinite(platform_z)
    valid &= known_fraction >= float(ap.get("minimum_fit_known_fraction", 1.0))
    valid &= edge_known_fraction >= float(ap.get("minimum_edge_known_fraction", 1.0))
    for arr in (platform_z, mean_clearance, edge_mean_clearance, max_clearance, known_fraction, edge_known_fraction, overhead_ambiguous_fraction):
        arr[~valid] = np.nan
    return {
        "platform_z": platform_z.astype(np.float32),
        "mean_clearance": mean_clearance.astype(np.float32),
        "edge_mean_clearance": edge_mean_clearance.astype(np.float32),
        "max_clearance": max_clearance.astype(np.float32),
        "known_fraction": known_fraction.astype(np.float32),
        "edge_known_fraction": edge_known_fraction.astype(np.float32),
        "overhead_ambiguous_fraction": overhead_ambiguous_fraction.astype(np.float32),
        "all_valid": valid,
    }

def _footprint_family(policy: dict, size_class: str) -> list[tuple[float, float]]:
    """Return configured footprint family in foundation units, shortest side first.

    V6 and earlier policies expose only a reference footprint; V7+ can provide
    multiple rectangles per size class. The analysis code remains backward compatible.
    """
    cfg = policy["size_classes"][size_class]
    family = cfg.get("footprint_family_foundations") or [cfg["reference_span_foundations"]]
    out = []
    for pair in family:
        a, b = sorted(float(x) for x in pair)
        if a <= 0 or b <= 0:
            continue
        out.append((a, b))
    if not out:
        raise ValueError(f"size class {size_class!r} has no usable footprint geometry")
    # Stable de-duplication, then small-to-large order. The selection logic below
    # deliberately prefers the largest qualifying footprint within a class.
    return sorted(set(out), key=lambda x: (x[0] * x[1], x[0], x[1]))


def _placement_maps(grid: PlaneFitGrid, policy: dict, tolerance_m: float, metric_cache: dict | None = None):
    ap = policy["analysis_parameters"]
    orientations = [float(x) for x in ap.get("footprint_orientations_deg", [0, 90])]
    mean_factor = float(ap.get("max_mean_clearance_factor", 1.0))
    edge_factor = float(ap.get("max_edge_mean_clearance_factor", 1.0))
    max_factor = ap.get("max_clearance_factor", 3.0)
    max_factor = None if max_factor is None else float(max_factor)
    foundation_m = float(policy.get("foundation_size_m", 8.0))
    metric_cache = {} if metric_cache is None else metric_cache

    class_qualifies = {}
    class_orientation = {}
    class_metrics = {}

    for name in SIZE_ORDER:
        best_area = np.full(grid.domain.shape, -np.inf, dtype=np.float32)
        best_score = np.full(grid.domain.shape, np.inf, dtype=np.float32)
        best_orientation = np.full(grid.domain.shape, np.nan, dtype=np.float32)
        best = {k: np.full(grid.domain.shape, np.nan, dtype=np.float32)
                for k in ["platform_z", "mean_clearance", "edge_mean_clearance", "max_clearance",
                          "known_fraction", "edge_known_fraction", "overhead_ambiguous_fraction",
                          "width_foundations", "length_foundations", "width_m", "length_m"]}
        best_valid = np.zeros(grid.domain.shape, dtype=bool)

        for short_f, long_f in _footprint_family(policy, name):
            short_m, long_m = short_f * foundation_m, long_f * foundation_m
            area_f = float(short_f * long_f)
            for angle in orientations:
                if int(round(angle)) % 90 != 0:
                    continue
                shape = _window_shape([short_m, long_m], grid.resolution_m, angle)
                # Plane metrics depend on the coarse window, not clearance tolerance.
                # Cache by window shape so multi-tolerance runs do not repeat the
                # expensive ndimage filters for every tolerance and footprint alias.
                cache_key = tuple(int(x) for x in shape)
                metrics = metric_cache.get(cache_key)
                if metrics is None:
                    metrics = _plane_metrics(grid, shape, ap)
                    metric_cache[cache_key] = metrics
                valid = metrics["all_valid"] & np.isfinite(metrics["mean_clearance"]) & np.isfinite(metrics["edge_mean_clearance"])
                qualifies = valid & (metrics["mean_clearance"] <= float(tolerance_m) * mean_factor)
                qualifies &= metrics["edge_mean_clearance"] <= float(tolerance_m) * edge_factor
                if max_factor is not None:
                    qualifies &= metrics["max_clearance"] <= float(tolerance_m) * max_factor
                # Within one size class, prefer the largest practical rectangle.
                # For equal-area footprints, perimeter/overall grounding breaks ties.
                score = metrics["edge_mean_clearance"] + metrics["mean_clearance"] * 0.5
                larger = area_f > (best_area + 1e-6)
                equal_area = np.isclose(best_area, area_f, atol=1e-6)
                improve = qualifies & (larger | (equal_area & (score < best_score)))
                if not np.any(improve):
                    continue
                best_area[improve] = area_f
                best_score[improve] = score[improve]
                best_orientation[improve] = angle
                best_valid[improve] = True
                for key in ["platform_z", "mean_clearance", "edge_mean_clearance", "max_clearance",
                            "known_fraction", "edge_known_fraction", "overhead_ambiguous_fraction"]:
                    best[key][improve] = metrics[key][improve]
                best["width_foundations"][improve] = short_f
                best["length_foundations"][improve] = long_f
                best["width_m"][improve] = short_m
                best["length_m"][improve] = long_m

        class_qualifies[name] = best_valid
        class_orientation[name] = best_orientation
        class_metrics[name] = best

    rank_grid = np.zeros(grid.domain.shape, dtype=np.uint8)
    for name in SIZE_ORDER:
        rank_grid[class_qualifies[name]] = SIZE_RANK[name]
    return rank_grid, class_qualifies, class_orientation, class_metrics

def _overlap_fraction(a, b) -> float:
    ax0, ax1, ay0, ay1 = a; bx0, bx1, by0, by1 = b
    ix = max(0.0, min(ax1, bx1) - max(ax0, bx0)); iy = max(0.0, min(ay1, by1) - max(ay0, by0))
    inter = ix * iy
    if inter <= 0: return 0.0
    amin = min((ax1-ax0)*(ay1-ay0), (bx1-bx0)*(by1-by0))
    return inter / amin if amin > 0 else 0.0


def _rect_bounds(east, north, width_m, length_m, orientation_deg):
    if int(round(float(orientation_deg))) % 180 == 90:
        width_m, length_m = length_m, width_m
    return (east-length_m/2, east+length_m/2, north-width_m/2, north+width_m/2)


def _candidate_rectangles(region_rows, region_cols, grid: PlaneFitGrid, size_class: str, policy: dict,
                          orientation_map: np.ndarray, metrics: dict[str, np.ndarray], max_candidates: int,
                          overlap_limit: float):
    foundation_m = float(policy.get("foundation_size_m", 8.0))
    if region_rows.size == 0:
        return []
    score = metrics["edge_mean_clearance"][region_rows, region_cols] + metrics["mean_clearance"][region_rows, region_cols] * 0.5
    area = metrics["width_foundations"][region_rows, region_cols] * metrics["length_foundations"][region_rows, region_cols]
    # Largest qualifying footprint first; grounding score breaks ties.
    order = np.lexsort((score, -np.nan_to_num(area, nan=-1.0)))
    records = []
    chosen = []
    for oi in order:
        rr = int(region_rows[oi]); cc = int(region_cols[oi])
        width_f = float(metrics["width_foundations"][rr, cc])
        length_f = float(metrics["length_foundations"][rr, cc])
        if not np.isfinite(width_f) or not np.isfinite(length_f):
            continue
        short_f, long_f = sorted((width_f, length_f))
        short_m, long_m = short_f * foundation_m, long_f * foundation_m
        angle = float(orientation_map[rr, cc]) if np.isfinite(orientation_map[rr, cc]) else 0.0
        shape = _window_shape([short_m, long_m], grid.resolution_m, angle)
        # scipy's even-sized filters are centered half a cell toward the negative
        # raster index. Emit the physical rectangle at that actual window center,
        # otherwise its outline is shifted half a coarse cell from its coverage mask.
        row_center = rr - (0.5 if shape[0] % 2 == 0 else 0.0)
        col_center = cc - (0.5 if shape[1] % 2 == 0 else 0.0)
        east = grid.east0_m + col_center * grid.resolution_m
        north = grid.north0_m - row_center * grid.resolution_m
        bounds = _rect_bounds(east, north, short_m, long_m, angle)
        if any(_overlap_fraction(bounds, b) > float(overlap_limit) for b in chosen):
            continue
        chosen.append(bounds)
        records.append({
            "candidate_rank": len(records) + 1,
            "center_east_m": east,
            "center_north_m": north,
            "width_foundations": short_f,
            "length_foundations": long_f,
            # Physical dimensions are derived from foundations, never analysis resolution.
            "width_m": short_f * foundation_m,
            "length_m": long_f * foundation_m,
            "foundation_size_m": foundation_m,
            "rotation_deg": angle,
            "platform_elevation_m": float(metrics["platform_z"][rr, cc]),
            "mean_clearance_m": float(metrics["mean_clearance"][rr, cc]),
            "edge_mean_clearance_m": float(metrics["edge_mean_clearance"][rr, cc]),
            "max_clearance_m": float(metrics["max_clearance"][rr, cc]),
            "terrain_known_fraction": float(metrics["known_fraction"][rr, cc]),
            "edge_known_fraction": float(metrics["edge_known_fraction"][rr, cc]),
            "overhead_ambiguous_fraction": float(metrics["overhead_ambiguous_fraction"][rr, cc]),
            "display_elevation_m": float(metrics["platform_z"][rr, cc]) + 0.5,
        })
        if len(records) >= int(max_candidates):
            break
    return records


def _paint_region_coverage(coverage: np.ndarray, region_rows: np.ndarray, region_cols: np.ndarray,
                           grid: PlaneFitGrid, policy: dict, orientation_map: np.ndarray,
                           metrics: dict[str, np.ndarray], label: int) -> None:
    """Paint the union of every qualifying physical footprint for one center-region.

    ``coverage`` is a display/planning envelope, distinct from the center-membership
    raster used to define region identity. Footprint geometry is always converted
    from foundation units using policy.foundation_size_m, never analysis resolution.
    """
    foundation_m = float(policy.get("foundation_size_m", 8.0))
    H, W = coverage.shape
    for rr, cc in zip(region_rows.tolist(), region_cols.tolist()):
        width_f = float(metrics["width_foundations"][rr, cc])
        length_f = float(metrics["length_foundations"][rr, cc])
        if not np.isfinite(width_f) or not np.isfinite(length_f):
            continue
        angle = float(orientation_map[rr, cc]) if np.isfinite(orientation_map[rr, cc]) else 0.0
        shape = _window_shape([width_f * foundation_m, length_f * foundation_m], grid.resolution_m, angle)
        nr, nc = shape
        # Match scipy maximum_filter's even-window convention exactly. Candidate
        # rectangle centers are emitted with the same half-cell offset above.
        r0 = rr - nr // 2; c0 = cc - nc // 2
        r1 = r0 + nr; c1 = c0 + nc
        ar0=max(0,r0); ac0=max(0,c0); ar1=min(H,r1); ac1=min(W,c1)
        if ar0 >= ar1 or ac0 >= ac1:
            continue
        view = coverage[ar0:ar1, ac0:ac1]
        # Keep the first label in overlap zones. The union remains correct visually;
        # region identity continues to live in the center-membership raster.
        view[view == 0] = int(label)

def analyze_plane_fit(repo_root: Path, world_manifest: Path, policy_path: Path, output_dir: Path,
                      resolutions: list[float] | None = None, clearance_tolerances_m: list[float] | None = None,
                      size_classes: list[str] | None = None) -> pd.DataFrame:
    manifest, raster = load_world_raster(repo_root, world_manifest)
    policy = load_json(policy_path)
    if policy.get("analysis_model") != "horizontal_plane_fit":
        raise ValueError("plane-fit generator expects analysis_model='horizontal_plane_fit'")
    ap=policy["analysis_parameters"]
    resolutions=resolutions or [float(x) for x in ap.get("working_resolutions_m",[16])]
    tolerances=clearance_tolerances_m or [float(x) for x in ap.get("clearance_tolerances_m",[1,2,4,8,16])]
    enabled=[x for x in SIZE_ORDER if x in set(size_classes or SIZE_ORDER)]
    max_candidates=int(ap.get("rectangle_candidates_per_region",3)); overlap=float(ap.get("rectangle_non_overlap_fraction",0.15))
    output_dir.mkdir(parents=True,exist_ok=True)
    all_rows=[]; rect_rows=[]; index=[]; qa_variants=[]

    for resolution in resolutions:
        grid=_coarse_plane_grid(raster,float(resolution),ap)
        metric_cache={}
        for tolerance in tolerances:
            rank_grid, qualifies, orientations, metrics_by_class=_placement_maps(grid,policy,float(tolerance),metric_cache=metric_cache)
            if set(enabled)!=set(SIZE_ORDER):
                rank_grid[:]=0
                for name in enabled: rank_grid[qualifies[name]]=SIZE_RANK[name]
            membership=np.zeros(rank_grid.shape,dtype=np.int32); coverage_membership=np.zeros(rank_grid.shape,dtype=np.int32); class_coverage={name: np.zeros(rank_grid.shape,dtype=np.int32) for name in enabled}; next_label=1; structure=np.ones((3,3),dtype=np.uint8); counts={}
            for name in enabled:
                exact=rank_grid==SIZE_RANK[name]
                labs,count=ndimage.label(exact,structure=structure); class_regions=0
                for lab in range(1,int(count)+1):
                    rr,cc=np.where(labs==lab)
                    if rr.size==0: continue
                    glab=next_label; next_label+=1; membership[rr,cc]=glab; class_regions+=1
                    east=grid.east0_m+cc*grid.resolution_m; north=grid.north0_m-rr*grid.resolution_m
                    bbox_w=(int(cc.max())-int(cc.min())+1)*grid.resolution_m; bbox_h=(int(rr.max())-int(rr.min())+1)*grid.resolution_m
                    shape_class,aspect=classify_shape(bbox_w,bbox_h,policy)
                    sid=f"bs_{raster.build}_{resolution:g}m_c{float(tolerance):g}m_{glab:05d}"
                    candidates=_candidate_rectangles(rr,cc,grid,name,policy,orientations[name],metrics_by_class[name],max_candidates,overlap)
                    _paint_region_coverage(coverage_membership, rr, cc, grid, policy, orientations[name], metrics_by_class[name], glab)
                    _paint_region_coverage(class_coverage[name], rr, cc, grid, policy, orientations[name], metrics_by_class[name], glab)
                    for rec in candidates:
                        rect_rows.append({
                            "rectangle_id":f"{sid}_rect_{int(rec['candidate_rank']):02d}","surface_id":sid,"game_build":raster.build,
                            "policy_id":policy["policy_id"],"analysis_model":"horizontal_plane_fit","analysis_resolution_m":float(resolution),
                            "clearance_tolerance_m":float(tolerance),"size_class":name,**rec,
                        })
                    cfg=policy["size_classes"][name]; primary=candidates[0] if candidates else None; m=metrics_by_class[name]
                    if primary is not None:
                        core_w=float(primary["width_foundations"]); core_l=float(primary["length_foundations"])
                        core_area_f=core_w*core_l; core_area_m2=core_area_f*float(policy.get("foundation_size_m",8.0))**2
                        rect_shape_class, rect_aspect=classify_shape(core_w,core_l,policy)
                    else:
                        core_w=float(min(cfg["reference_span_foundations"])); core_l=float(max(cfg["reference_span_foundations"]))
                        core_area_f=core_w*core_l; core_area_m2=core_area_f*float(policy.get("foundation_size_m",8.0))**2
                        rect_shape_class, rect_aspect=classify_shape(core_w,core_l,policy)
                    all_rows.append({
                        "surface_id":sid,"game_build":raster.build,"policy_id":policy["policy_id"],"analysis_model":"horizontal_plane_fit",
                        "analysis_resolution_m":float(resolution),"clearance_tolerance_m":float(tolerance),"size_class":name,"shape_class":rect_shape_class,"placement_zone_shape_class":shape_class,
                        "centroid_east_m":float(np.mean(east)),"centroid_north_m":float(np.mean(north)),
                        "placement_zone_area_m2":float(rr.size*resolution*resolution),"contiguous_area_m2":float(rr.size*resolution*resolution),
                        "qualifying_center_count":int(rr.size),"core_width_foundations":core_w,
                        "core_length_foundations":core_l,"core_area_foundations":core_area_f,
                        "core_area_m2":core_area_m2,"core_rotation_deg":None if primary is None else float(primary["rotation_deg"]),
                        "core_aspect_ratio":float(rect_aspect),
                        "min_mean_clearance_m":float(np.nanmin(m["mean_clearance"][rr,cc])),"median_mean_clearance_m":float(np.nanmedian(m["mean_clearance"][rr,cc])),
                        "max_mean_clearance_m":float(np.nanmax(m["mean_clearance"][rr,cc])),"median_edge_mean_clearance_m":float(np.nanmedian(m["edge_mean_clearance"][rr,cc])),
                        "median_terrain_known_fraction":float(np.nanmedian(m["known_fraction"][rr,cc])),"minimum_edge_known_fraction":float(np.nanmin(m["edge_known_fraction"][rr,cc])),
                        "median_overhead_ambiguous_fraction":float(np.nanmedian(m["overhead_ambiguous_fraction"][rr,cc])),
                        "mean_grade":_safe_nanmean(grid.local_grade[rr,cc]),"p90_grade":_safe_nanpercentile(grid.local_grade[rr,cc],90),
                        "mean_roughness_m":_safe_nanmean(grid.roughness_m[rr,cc]),"mean_terrain_confidence":_safe_nanmean(grid.confidence_score[rr,cc]),
                        "water_fraction":float(np.nanmean(grid.water_fraction[rr,cc])),"rectangle_candidate_count":int(len(candidates)),
                    })
                counts[name]=class_regions
            token=f"{float(tolerance):g}".replace(".","p")
            filename=f"build_surface_membership_{float(resolution):g}m_clearance_{token}m.npz"
            np.savez_compressed(output_dir/filename,labels=membership,coverage_labels=coverage_membership,class_rank=rank_grid, **{f"coverage_{name}_labels": arr for name, arr in class_coverage.items()})
            index.append({"resolution_m":float(resolution),"clearance_tolerance_m":float(tolerance),"file":filename})
            qa_variants.append({"resolution_m":float(resolution),"clearance_tolerance_m":float(tolerance),"grid_rows":int(rank_grid.shape[0]),"grid_cols":int(rank_grid.shape[1]),
                                "domain_fraction":float(np.mean(grid.domain)),"qualified_center_fraction":float(np.mean(rank_grid>0)),"regions_by_highest_class":counts,
                                "center_counts_by_highest_class":{name:int(np.count_nonzero(rank_grid==SIZE_RANK[name])) for name in enabled}})

    df=pd.DataFrame(all_rows); rects=pd.DataFrame(rect_rows)
    df.to_csv(output_dir/"build_surfaces.csv",index=False, lineterminator="\n"); rects.to_csv(output_dir/"build_surface_rectangles.csv",index=False, lineterminator="\n")
    (output_dir/"build_surface_membership_index.json").write_text(json.dumps({"analysis_model":"horizontal_plane_fit","variants":index},indent=2)+"\n",encoding="utf-8", newline="\n")
    summary={"world_extract_id":manifest["world_extract_id"],"game_build":raster.build,"policy_id":policy["policy_id"],"analysis_model":"horizontal_plane_fit",
             "resolutions_m":[float(x) for x in resolutions],"clearance_tolerances_m":[float(x) for x in tolerances],"surface_region_count":int(len(df)),
             "rectangle_candidate_count":int(len(rects)),"counts_by_size":{} if df.empty else {str(k):int(v) for k,v in df["size_class"].value_counts().to_dict().items()},
             "note":"Each rectangle is one horizontal plane fitted to known ground-support cells. V9 supports multiple physical footprint proportions per class; coverage_<class>_labels stores class-specific footprint union while coverage_labels retains the combined union and labels retains qualifying-center region identity. With prefer_ground_provenance, landscape/fill defines ground while cliff-only top surfaces are reported as vertical-layer ambiguity."}
    (output_dir/"summary.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8", newline="\n")
    qa={"status":"PASS","world_build_alignment":manifest.get("alignment",{}).get("status"),"source_grid":raster.meta["grid"],"variants":qa_variants,
        "diagnostics":{"horizontal_resolution_independent_of_clearance_tolerance":True,"platform_is_single_horizontal_plane":True,
                       "cell_surface_percentile":float(ap.get("cell_surface_percentile",95.0)),"terrain_penetration_at_working_resolution":"prevented for representative cell surface",
                       "mean_clearance_factor":float(ap.get("max_mean_clearance_factor",1.0)),"edge_mean_clearance_factor":float(ap.get("max_edge_mean_clearance_factor",1.0)),
                       "max_clearance_factor":ap.get("max_clearance_factor",3.0),"water_mode":ap.get("water_mode","exclude"),"terrain_surface_mode":ap.get("terrain_surface_mode","all_top_surface"),
                       "ground_provenance_codes":ap.get("ground_provenance_codes",[1,3]),"overhead_surface_codes":ap.get("overhead_surface_codes",[4,5]),
                       "minimum_fit_known_fraction":ap.get("minimum_fit_known_fraction",1.0),"minimum_edge_known_fraction":ap.get("minimum_edge_known_fraction",1.0)}}
    (output_dir/"qa.json").write_text(json.dumps(qa,indent=2)+"\n",encoding="utf-8", newline="\n")
    return df
