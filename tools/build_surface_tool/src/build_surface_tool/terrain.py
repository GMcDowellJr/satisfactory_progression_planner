from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import warnings


@dataclass
class WorkingGrid:
    resolution_m: float
    east0_m: float
    north0_m: float
    z_m: np.ndarray
    valid_fraction: np.ndarray
    water_fraction: np.ndarray
    confidence_score: np.ndarray
    local_relief_m: np.ndarray
    local_grade: np.ndarray
    roughness_m: np.ndarray
    usable: np.ndarray


def _block_reduce(arr: np.ndarray, factor: int, reducer, fill=np.nan) -> np.ndarray:
    h = (arr.shape[0] // factor) * factor
    w = (arr.shape[1] // factor) * factor
    if h == 0 or w == 0:
        raise ValueError("working resolution is larger than the raster")
    view = arr[:h, :w].reshape(h // factor, factor, w // factor, factor)
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        out = reducer(view, axis=(1, 3))
    if np.isscalar(out):
        return np.full((h // factor, w // factor), fill)
    return out


def _confidence_lookup(meta: dict) -> dict[int, float]:
    prov = meta.get("provenance", {})
    scored: dict[int, float] = {0: 0.0}
    accuracies = []
    for k, v in prov.items():
        a = v.get("accuracy_m") if isinstance(v, dict) else None
        if a is not None:
            accuracies.append(float(a))
    scale = max(accuracies) if accuracies else 1.0
    for k, v in prov.items():
        key = int(k)
        a = v.get("accuracy_m") if isinstance(v, dict) else None
        if a is None:
            scored[key] = 0.0 if key == 0 else 0.5
        else:
            scored[key] = max(0.0, min(1.0, 1.0 - float(a) / (scale * 1.25)))
    return scored


def make_working_grid(
    height_m: np.ndarray,
    provenance: np.ndarray,
    water_q: np.ndarray,
    meta: dict,
    source_spacing_m: float,
    resolution_m: float,
    cell_relief_tolerance_m: float,
    max_neighbor_step_m: float,
    water_exclusion: bool = True,
    minimum_terrain_confidence: float | None = None,
    max_local_grade: float | None = None,
    roughness_threshold_m: float | None = None,
) -> WorkingGrid:
    factor_f = resolution_m / source_spacing_m
    factor = int(round(factor_f))
    if factor < 1 or not np.isclose(factor, factor_f):
        raise ValueError("working resolution must be an integer multiple of source spacing")

    finite = np.isfinite(height_m)
    z = _block_reduce(height_m, factor, np.nanmedian)
    zmin = _block_reduce(height_m, factor, np.nanmin)
    zmax = _block_reduce(height_m, factor, np.nanmax)
    valid_fraction = _block_reduce(finite.astype(np.float32), factor, np.mean)
    water_fraction = _block_reduce((water_q > 0).astype(np.float32), factor, np.mean)

    scores = _confidence_lookup(meta)
    max_code = int(provenance.max(initial=0))
    lut = np.zeros(max_code + 1, dtype=np.float32)
    for code, score in scores.items():
        if code <= max_code:
            lut[code] = score
    confidence_native = lut[provenance]
    confidence = _block_reduce(confidence_native, factor, np.mean)

    relief = zmax - zmin
    roughness = _block_reduce(np.abs(height_m - _block_expand(z, factor, height_m.shape)), factor, np.nanmean)

    # Grade is a diagnostic on the representative terrain-following surface.
    dzdy, dzdx = np.gradient(z, resolution_m, resolution_m)
    grade = np.sqrt(dzdx * dzdx + dzdy * dzdy)

    usable = np.isfinite(z) & (valid_fraction >= 0.5)
    if cell_relief_tolerance_m is not None:
        usable &= relief <= float(cell_relief_tolerance_m)
    if water_exclusion:
        usable &= water_fraction == 0
    if minimum_terrain_confidence is not None:
        usable &= confidence >= minimum_terrain_confidence
    if max_local_grade is not None:
        usable &= grade <= max_local_grade
    if roughness_threshold_m is not None:
        usable &= roughness <= roughness_threshold_m

    # A terrain-following surface may rise/fall, but abrupt neighbor-to-neighbor
    # steps above the configured neighbor-step tolerance are treated as breaks. A cell touching
    # such a break is removed so ordinary connected-component labeling cannot
    # bridge a cliff that happens to align exactly to a block boundary.
    bad_edge = np.zeros_like(usable, dtype=bool)
    hdiff = np.abs(z[:, 1:] - z[:, :-1])
    bad = np.isfinite(hdiff) & (hdiff > max_neighbor_step_m)
    bad_edge[:, 1:] |= bad
    bad_edge[:, :-1] |= bad
    vdiff = np.abs(z[1:, :] - z[:-1, :])
    bad = np.isfinite(vdiff) & (vdiff > max_neighbor_step_m)
    bad_edge[1:, :] |= bad
    bad_edge[:-1, :] |= bad
    usable &= ~bad_edge

    return WorkingGrid(
        resolution_m=resolution_m,
        east0_m=float(meta["grid"]["x0_cm"]) / 100.0,
        north0_m=-float(meta["grid"]["y0_cm"]) / 100.0,
        z_m=z.astype(np.float32),
        valid_fraction=valid_fraction.astype(np.float32),
        water_fraction=water_fraction.astype(np.float32),
        confidence_score=confidence.astype(np.float32),
        local_relief_m=relief.astype(np.float32),
        local_grade=grade.astype(np.float32),
        roughness_m=roughness.astype(np.float32),
        usable=usable,
    )


def _block_expand(coarse: np.ndarray, factor: int, target_shape: tuple[int, int]) -> np.ndarray:
    expanded = np.repeat(np.repeat(coarse, factor, axis=0), factor, axis=1)
    out = np.full(target_shape, np.nan, dtype=np.float32)
    h = min(target_shape[0], expanded.shape[0])
    w = min(target_shape[1], expanded.shape[1])
    out[:h, :w] = expanded[:h, :w]
    return out


@dataclass
class SweepGrid:
    resolution_m: float
    east0_m: float
    north0_m: float
    terrain_median_m: np.ndarray
    terrain_max_m: np.ndarray
    water_surface_max_m: np.ndarray
    obstruction_m: np.ndarray
    valid_fraction: np.ndarray
    water_fraction: np.ndarray
    confidence_score: np.ndarray
    local_grade: np.ndarray
    roughness_m: np.ndarray
    domain: np.ndarray


def make_sweep_grid(
    height_m: np.ndarray,
    water_m: np.ndarray,
    provenance: np.ndarray,
    water_q: np.ndarray,
    meta: dict,
    source_spacing_m: float,
    resolution_m: float,
    *,
    minimum_valid_fraction: float = 0.5,
    minimum_terrain_confidence: float | None = None,
    max_local_grade: float | None = None,
    roughness_threshold_m: float | None = None,
    water_obstruction_mode: str = "surface",
) -> SweepGrid:
    """Build the coarse obstruction field used by elevation-sweep analysis.

    Horizontal resolution controls edge/detail fidelity.  Each coarse cell keeps
    the maximum terrain elevation so small ridges are not erased by averaging.
    Water is not permanently excluded: with ``water_obstruction_mode='surface'``
    its surface elevation is treated as another obstruction height, so a platform
    becomes available once the sampled plane rises above the water.
    """
    factor_f = resolution_m / source_spacing_m
    factor = int(round(factor_f))
    if factor < 1 or not np.isclose(factor, factor_f):
        raise ValueError("working resolution must be an integer multiple of source spacing")

    finite = np.isfinite(height_m)
    terrain_median = _block_reduce(height_m, factor, np.nanmedian)
    terrain_max = _block_reduce(height_m, factor, np.nanmax)
    valid_fraction = _block_reduce(finite.astype(np.float32), factor, np.mean)
    water_fraction = _block_reduce((water_q > 0).astype(np.float32), factor, np.mean)

    if water_m is None:
        water_max = np.full_like(terrain_max, np.nan, dtype=np.float32)
    else:
        water_max = _block_reduce(water_m, factor, np.nanmax)

    scores = _confidence_lookup(meta)
    max_code = int(provenance.max(initial=0))
    lut = np.zeros(max_code + 1, dtype=np.float32)
    for code, score in scores.items():
        if code <= max_code:
            lut[code] = score
    confidence_native = lut[provenance]
    confidence = _block_reduce(confidence_native, factor, np.mean)

    roughness = _block_reduce(np.abs(height_m - _block_expand(terrain_median, factor, height_m.shape)), factor, np.nanmean)
    dzdy, dzdx = np.gradient(terrain_median, resolution_m, resolution_m)
    grade = np.sqrt(dzdx * dzdx + dzdy * dzdy)

    obstruction = terrain_max.astype(np.float32, copy=True)
    mode = str(water_obstruction_mode).lower()
    if mode == "surface":
        both = np.isfinite(obstruction) & np.isfinite(water_max)
        obstruction[both] = np.maximum(obstruction[both], water_max[both])
        only_water = ~np.isfinite(obstruction) & np.isfinite(water_max)
        obstruction[only_water] = water_max[only_water]
    elif mode == "ignore":
        pass
    elif mode == "exclude":
        obstruction[water_fraction > 0] = np.nan
    else:
        raise ValueError("water_obstruction_mode must be one of: surface, ignore, exclude")

    domain = np.isfinite(obstruction) & (valid_fraction >= float(minimum_valid_fraction))
    if minimum_terrain_confidence is not None:
        domain &= confidence >= float(minimum_terrain_confidence)
    if max_local_grade is not None:
        domain &= grade <= float(max_local_grade)
    if roughness_threshold_m is not None:
        domain &= roughness <= float(roughness_threshold_m)

    return SweepGrid(
        resolution_m=float(resolution_m),
        east0_m=float(meta["grid"]["x0_cm"]) / 100.0,
        north0_m=-float(meta["grid"]["y0_cm"]) / 100.0,
        terrain_median_m=terrain_median.astype(np.float32),
        terrain_max_m=terrain_max.astype(np.float32),
        water_surface_max_m=water_max.astype(np.float32),
        obstruction_m=obstruction.astype(np.float32),
        valid_fraction=valid_fraction.astype(np.float32),
        water_fraction=water_fraction.astype(np.float32),
        confidence_score=confidence.astype(np.float32),
        local_grade=grade.astype(np.float32),
        roughness_m=roughness.astype(np.float32),
        domain=domain,
    )
