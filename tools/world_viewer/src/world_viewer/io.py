from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import zlib

import numpy as np
import pandas as pd

NODATA = -32768


@dataclass(frozen=True)
class WorldData:
    manifest: dict
    meta: dict
    height_m: np.ndarray
    water_m: np.ndarray
    water_q: np.ndarray
    provenance: np.ndarray
    east0_m: float
    north0_m: float
    spacing_m: float
    build: int


def load_json(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def _decode_i16(path: Path, height: int, width: int) -> np.ndarray:
    delta = np.frombuffer(zlib.decompress(path.read_bytes()), dtype="<i2")
    if delta.size != height * width:
        raise ValueError(f"raster size mismatch in {path}")
    return np.cumsum(delta.reshape(height, width).astype(np.int32), axis=1).astype(np.int16)


def _decode_u8(path: Path, height: int, width: int) -> np.ndarray:
    flat = np.frombuffer(zlib.decompress(path.read_bytes()), dtype=np.uint8)
    if flat.size != height * width:
        raise ValueError(f"raster size mismatch in {path}")
    return flat.reshape(height, width)


def load_world(repo_root: Path, world_manifest: Path) -> WorldData:
    repo_root = Path(repo_root).resolve()
    manifest = load_json(world_manifest)
    rel = manifest["layers"]["terrain_water"]["path"]
    terrain_dir = repo_root / "planning_data" / rel
    meta = load_json(terrain_dir / "meta.json")
    h = int(meta["grid"]["height"])
    w = int(meta["grid"]["width"])

    raw_h = _decode_i16(terrain_dir / "height.i16.z", h, w)
    height_m = raw_h.astype(np.float32) / 10.0
    height_m[raw_h == NODATA] = np.nan

    water_path = terrain_dir / "water.i16.z"
    if water_path.exists():
        raw_w = _decode_i16(water_path, h, w)
        water_m = raw_w.astype(np.float32) / 10.0
        water_m[raw_w == NODATA] = np.nan
    else:
        water_m = np.full((h, w), np.nan, dtype=np.float32)

    return WorldData(
        manifest=manifest,
        meta=meta,
        height_m=height_m,
        water_m=water_m,
        water_q=_decode_u8(terrain_dir / "waterq.u8.z", h, w),
        provenance=_decode_u8(terrain_dir / "prov.u8.z", h, w),
        east0_m=float(meta["grid"]["x0_cm"]) / 100.0,
        north0_m=-float(meta["grid"]["y0_cm"]) / 100.0,
        spacing_m=float(meta["grid"]["spacing_cm"]) / 100.0,
        build=int(manifest["game"]["build"]),
    )


def load_resources(repo_root: Path, manifest: dict) -> pd.DataFrame:
    base = Path(repo_root) / "planning_data"
    sockets_path = base / manifest["layers"]["resource_nodes"]["canonical_sockets"]
    assignments_path = base / manifest["layers"]["default_world_configuration"]["resource_assignments"]
    sockets = pd.read_csv(sockets_path)
    assignments = pd.read_csv(assignments_path)
    return sockets.merge(assignments[["socket_id", "resource_id", "purity"]], on="socket_id", how="left")


def load_surfaces(surface_dir: Path) -> pd.DataFrame:
    path = Path(surface_dir) / "build_surfaces.csv"
    if not path.exists():
        raise FileNotFoundError(f"build-surface output not found: {path}; run generate_build_surfaces.py first")
    return pd.read_csv(path)


def _plane_token(z: float) -> str:
    sign = "neg" if float(z) < 0 else "pos"
    mag = f"{abs(float(z)):g}".replace(".", "p")
    return f"{sign}{mag}"


def _relief_token(value: float) -> str:
    return f"{float(value):g}".replace(".", "p")


def load_rectangles(surface_dir: Path) -> pd.DataFrame:
    path = Path(surface_dir) / "build_surface_rectangles.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def analysis_model(surface_dir: Path) -> str:
    surface_dir = Path(surface_dir)
    index = surface_dir / "build_surface_membership_index.json"
    if index.exists():
        try:
            return str(load_json(index).get("analysis_model", "legacy"))
        except Exception:
            pass
    csv = surface_dir / "build_surfaces.csv"
    if csv.exists():
        surfaces = pd.read_csv(csv)
        if "analysis_model" in surfaces.columns and not surfaces.empty:
            return str(surfaces.iloc[0]["analysis_model"])
    names = [p.name for p in surface_dir.glob("build_surface_membership_*m*.npz")]
    if any("_clearance_" in n for n in names): return "horizontal_plane_fit"
    if any("_relief_" in n for n in names): return "local_multiscale_relief"
    if any("_plane_" in n for n in names): return "elevation_sweep"
    if any("_z" in n for n in names): return "vertical_band_legacy"
    return "legacy"


def available_surface_variants(surface_dir: Path) -> list[tuple[float, float | None]]:
    """Legacy-compatible variant discovery.

    For elevation sweep, the second value is platform elevation. For local
    multiscale relief, it is local relief tolerance. Consumers should inspect
    ``analysis_model(surface_dir)`` before interpreting it.
    """
    index = Path(surface_dir) / "build_surface_membership_index.json"
    if index.exists():
        try:
            data = load_json(index)
            out=[]
            for v in data.get("variants", []):
                second = v.get("clearance_tolerance_m", v.get("local_relief_tolerance_m", v.get("platform_elevation_m", v.get("region_vertical_span_m"))))
                out.append((float(v["resolution_m"]), None if second is None else float(second)))
            if out:
                return sorted(set(out), key=lambda x:(x[0], float("inf") if x[1] is None else x[1]))
        except Exception:
            pass
    out: list[tuple[float, float | None]] = []
    clearance_pat = re.compile(r"build_surface_membership_([0-9.]+)m_clearance_([0-9p.]+)m\.npz$")
    relief_pat = re.compile(r"build_surface_membership_([0-9.]+)m_relief_([0-9p.]+)m\.npz$")
    plane_pat = re.compile(r"build_surface_membership_([0-9.]+)m_plane_(neg|pos)([0-9p.]+)m\.npz$")
    band_pat = re.compile(r"build_surface_membership_([0-9.]+)m_z([0-9.]+)m\.npz$")
    old_pat = re.compile(r"build_surface_membership_([0-9.]+)m\.npz$")
    for path in Path(surface_dir).glob("build_surface_membership_*m*.npz"):
        m = clearance_pat.match(path.name)
        if m:
            out.append((float(m.group(1)), float(m.group(2).replace("p", ".")))); continue
        m = relief_pat.match(path.name)
        if m:
            out.append((float(m.group(1)), float(m.group(2).replace("p", ".")))); continue
        m = plane_pat.match(path.name)
        if m:
            value=float(m.group(3).replace("p", ".")); value = -value if m.group(2)=="neg" else value
            out.append((float(m.group(1)), value)); continue
        m = band_pat.match(path.name)
        if m:
            out.append((float(m.group(1)), float(m.group(2)))); continue
        m = old_pat.match(path.name)
        if m:
            out.append((float(m.group(1)), None))
    return sorted(set(out), key=lambda x:(x[0], float("inf") if x[1] is None else x[1]))


def available_surface_resolutions(surface_dir: Path) -> list[float]:
    return sorted(set(v[0] for v in available_surface_variants(surface_dir)))


def available_clearance_tolerances(surface_dir: Path, resolution_m: float) -> list[float]:
    if analysis_model(surface_dir) != "horizontal_plane_fit":
        return []
    return sorted(v[1] for v in available_surface_variants(surface_dir) if v[0] == float(resolution_m) and v[1] is not None)


def available_local_relief_tolerances(surface_dir: Path, resolution_m: float) -> list[float]:
    if analysis_model(surface_dir) != "local_multiscale_relief":
        return []
    return sorted(v[1] for v in available_surface_variants(surface_dir) if v[0] == float(resolution_m) and v[1] is not None)


def available_platform_elevations(surface_dir: Path, resolution_m: float) -> list[float]:
    if analysis_model(surface_dir) != "elevation_sweep":
        return []
    return sorted(v[1] for v in available_surface_variants(surface_dir) if v[0] == float(resolution_m) and v[1] is not None)


def available_region_spans(surface_dir: Path, resolution_m: float) -> list[float]:
    return sorted(v[1] for v in available_surface_variants(surface_dir) if v[0] == float(resolution_m) and v[1] is not None)


def load_membership(surface_dir: Path, resolution_m: float, platform_elevation_m: float | None = None,
                    local_relief_tolerance_m: float | None = None, clearance_tolerance_m: float | None = None,
                    layer: str = "labels") -> np.ndarray:
    surface_dir = Path(surface_dir)
    index = surface_dir / "build_surface_membership_index.json"
    if index.exists():
        try:
            data = load_json(index)
            for v in data.get("variants", []):
                if float(v.get("resolution_m")) != float(resolution_m):
                    continue
                if clearance_tolerance_m is not None and "clearance_tolerance_m" in v and np.isclose(float(v["clearance_tolerance_m"]), float(clearance_tolerance_m)):
                    with np.load(surface_dir / v["file"]) as z: return z[layer if layer in z.files else "labels"].astype(np.int32, copy=False)
                if local_relief_tolerance_m is not None and "local_relief_tolerance_m" in v and np.isclose(float(v["local_relief_tolerance_m"]), float(local_relief_tolerance_m)):
                    with np.load(surface_dir / v["file"]) as z: return z[layer if layer in z.files else "labels"].astype(np.int32, copy=False)
                if platform_elevation_m is not None and "platform_elevation_m" in v and np.isclose(float(v["platform_elevation_m"]), float(platform_elevation_m)):
                    with np.load(surface_dir / v["file"]) as z: return z[layer if layer in z.files else "labels"].astype(np.int32, copy=False)
        except Exception:
            pass
    if clearance_tolerance_m is not None:
        path=surface_dir / f"build_surface_membership_{resolution_m:g}m_clearance_{_relief_token(clearance_tolerance_m)}m.npz"
    elif local_relief_tolerance_m is not None:
        path=surface_dir / f"build_surface_membership_{resolution_m:g}m_relief_{_relief_token(local_relief_tolerance_m)}m.npz"
    elif platform_elevation_m is not None:
        plane=surface_dir / f"build_surface_membership_{resolution_m:g}m_plane_{_plane_token(platform_elevation_m)}m.npz"
        band=surface_dir / f"build_surface_membership_{resolution_m:g}m_z{platform_elevation_m:g}m.npz"
        path=plane if plane.exists() else band
    else:
        legacy=surface_dir / f"build_surface_membership_{resolution_m:g}m.npz"
        if legacy.exists(): path=legacy
        else:
            vals=available_surface_variants(surface_dir)
            vals=[v[1] for v in vals if v[0]==float(resolution_m) and v[1] is not None]
            if not vals: raise FileNotFoundError(f"no membership raster for {resolution_m:g} m in {surface_dir}")
            if analysis_model(surface_dir)=="horizontal_plane_fit":
                return load_membership(surface_dir,resolution_m,clearance_tolerance_m=max(vals),layer=layer)
            if analysis_model(surface_dir)=="local_multiscale_relief":
                return load_membership(surface_dir,resolution_m,local_relief_tolerance_m=max(vals),layer=layer)
            return load_membership(surface_dir,resolution_m,platform_elevation_m=max(vals),layer=layer)
    if not path.exists(): raise FileNotFoundError(path)
    with np.load(path) as z: return z[layer if layer in z.files else "labels"].astype(np.int32, copy=False)


def surface_label(surface_id: str) -> int:
    m = re.search(r"_(\d+)$", str(surface_id))
    if not m:
        raise ValueError(f"cannot recover membership label from surface_id {surface_id!r}")
    return int(m.group(1))
