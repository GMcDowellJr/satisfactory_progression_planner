from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .io import WorldData, surface_label


@dataclass(frozen=True)
class GridMesh:
    points: np.ndarray
    faces: np.ndarray
    scalars: np.ndarray | None = None


def _factor(spacing_m: float, requested_m: float) -> int:
    raw = requested_m / spacing_m
    f = int(round(raw))
    if f < 1 or not np.isclose(raw, f):
        raise ValueError("mesh spacing must be an integer multiple of source raster spacing")
    return f


def sampled_grid(world: WorldData, spacing_m: float, vertical_exaggeration: float = 1.0, source: str = "terrain") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    f = _factor(world.spacing_m, spacing_m)
    zsrc = world.height_m if source == "terrain" else world.water_m
    z = zsrc[::f, ::f].astype(np.float64, copy=True)
    rows = np.arange(z.shape[0], dtype=np.float64)
    cols = np.arange(z.shape[1], dtype=np.float64)
    east = world.east0_m + cols * spacing_m
    north = world.north0_m - rows * spacing_m
    xx, yy = np.meshgrid(east, north)
    zz = z * float(vertical_exaggeration)
    return xx, yy, zz


def regular_surface_mesh(world: WorldData, spacing_m: float = 24.0, vertical_exaggeration: float = 1.0, source: str = "terrain") -> GridMesh:
    xx, yy, zz = sampled_grid(world, spacing_m, vertical_exaggeration, source)
    valid = np.isfinite(zz)
    nr, nc = zz.shape
    idx = np.arange(nr * nc, dtype=np.int64).reshape(nr, nc)
    points = np.column_stack([xx.ravel(), yy.ravel(), np.nan_to_num(zz, nan=0.0).ravel()])

    a = idx[:-1, :-1].ravel(); b = idx[:-1, 1:].ravel()
    c = idx[1:, 1:].ravel(); d = idx[1:, :-1].ravel()
    ok2 = valid[:-1, :-1] & valid[:-1, 1:] & valid[1:, 1:] & valid[1:, :-1]
    if source == "water":
        # Neighboring water bodies can sit at very different elevations. Do not
        # bridge them with vertical walls in the preview mesh.
        stack = np.stack([zz[:-1, :-1], zz[:-1, 1:], zz[1:, 1:], zz[1:, :-1]], axis=0)
        import warnings
        with np.errstate(all="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            span = np.nanmax(stack, axis=0) - np.nanmin(stack, axis=0)
        ok2 &= span <= 2.0 * float(vertical_exaggeration)
    ok = ok2.ravel()
    quads = np.column_stack([a[ok], b[ok], c[ok], d[ok]])
    faces = np.vstack([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]]) if len(quads) else np.empty((0, 3), dtype=np.int64)
    scalars = np.repeat(np.nan_to_num(zz[:-1, :-1], nan=np.nan).ravel()[ok], 2) if len(quads) else np.empty(0)
    return GridMesh(points=points, faces=faces, scalars=scalars)


def representative_height(world: WorldData, resolution_m: float) -> np.ndarray:
    f = _factor(world.spacing_m, resolution_m)
    h = (world.height_m.shape[0] // f) * f
    w = (world.height_m.shape[1] // f) * f
    view = world.height_m[:h, :w].reshape(h // f, f, w // f, f)
    import warnings
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        return np.nanmedian(view, axis=(1, 3)).astype(np.float32)


def surface_overlay_cells(world: WorldData, labels: np.ndarray, surfaces, resolution_m: float, size_filter: set[str] | None = None,
                          z_offset_m: float = 2.0, platform_elevation_m: float | None = None,
                          region_span_m: float | None = None, local_relief_tolerance_m: float | None = None, clearance_tolerance_m: float | None = None):
    """Return one quad per classified membership cell and cell metadata arrays.

    Elevation-sweep (v3) surfaces are rendered as true horizontal platform
    planes at ``platform_elevation_m``. Legacy v1/v2 outputs remain draped on
    representative terrain for backward compatibility.
    """
    df = surfaces[surfaces["analysis_resolution_m"].astype(float) == float(resolution_m)].copy()
    if clearance_tolerance_m is not None and "clearance_tolerance_m" in df.columns:
        df = df[np.isclose(df["clearance_tolerance_m"].astype(float), float(clearance_tolerance_m))]
    elif platform_elevation_m is not None and "platform_elevation_m" in df.columns:
        df = df[np.isclose(df["platform_elevation_m"].astype(float), float(platform_elevation_m))]
    elif local_relief_tolerance_m is not None and "local_relief_tolerance_m" in df.columns:
        df = df[np.isclose(df["local_relief_tolerance_m"].astype(float), float(local_relief_tolerance_m))]
    elif region_span_m is not None and "region_vertical_span_m" in df.columns:
        df = df[df["region_vertical_span_m"].astype(float) == float(region_span_m)]
    if size_filter:
        df = df[df["size_class"].isin(size_filter)]
    if df.empty:
        return np.empty((0, 3)), np.empty((0, 4), dtype=np.int64), np.empty(0, dtype=np.int32), np.empty(0, dtype=np.int32), []

    label_to_row = {surface_label(row.surface_id): i for i, row in enumerate(df.itertuples(index=False))}
    wanted = np.array(sorted(label_to_row), dtype=np.int32)
    mask = np.isin(labels, wanted)
    rr, cc = np.where(mask)
    if rr.size == 0:
        return np.empty((0, 3)), np.empty((0, 4), dtype=np.int64), np.empty(0, dtype=np.int32), np.empty(0, dtype=np.int32), []

    lab = labels[rr, cc]
    if platform_elevation_m is None:
        z = representative_height(world, resolution_m)
        inside = (rr < z.shape[0]) & (cc < z.shape[1])
        rr, cc = rr[inside], cc[inside]
        lab = labels[rr, cc]
        valid = np.isfinite(z[rr, cc])
        rr, cc, lab = rr[valid], cc[valid], lab[valid]
        elev = z[rr, cc] + z_offset_m
    else:
        elev = np.full(len(rr), float(platform_elevation_m) + float(z_offset_m), dtype=np.float64)

    n = len(rr)
    half = resolution_m / 2.0
    east = world.east0_m + cc * resolution_m
    north = world.north0_m - rr * resolution_m
    pts = np.empty((n * 4, 3), dtype=np.float64)
    pts[0::4] = np.column_stack([east-half, north-half, elev])
    pts[1::4] = np.column_stack([east+half, north-half, elev])
    pts[2::4] = np.column_stack([east+half, north+half, elev])
    pts[3::4] = np.column_stack([east-half, north+half, elev])
    q = np.arange(n * 4, dtype=np.int64).reshape(n, 4)

    size_rank_map = {"small": 1, "medium": 2, "large": 3, "very_large": 4}
    row_index = np.array([label_to_row[int(x)] for x in lab], dtype=np.int32)
    rows = list(df.itertuples(index=False))
    size_rank = np.array([size_rank_map.get(rows[i].size_class, 0) for i in row_index], dtype=np.int32)
    return pts, q, row_index, size_rank, rows
