from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import numpy as np

from .codec import decode_i16, decode_u8, NODATA


@dataclass(frozen=True)
class WorldRaster:
    build: int
    height_m: np.ndarray
    water_m: np.ndarray
    provenance: np.ndarray
    water_q: np.ndarray
    east0_m: float
    north0_m: float
    source_spacing_m: float
    meta: dict


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_repo_path(repo_root: Path, planning_relative: str) -> Path:
    """Manifest paths are relative to planning_data/."""
    return repo_root / "planning_data" / planning_relative


def load_world_raster(repo_root: Path, world_manifest_path: Path) -> tuple[dict, WorldRaster]:
    manifest = load_json(world_manifest_path)
    layer = manifest["layers"]["terrain_water"]
    terrain_dir = resolve_repo_path(repo_root, layer["path"])
    meta = load_json(terrain_dir / "meta.json")
    h = int(meta["grid"]["height"])
    w = int(meta["grid"]["width"])

    height_raw = decode_i16((terrain_dir / "height.i16.z").read_bytes(), h, w)
    provenance = decode_u8((terrain_dir / "prov.u8.z").read_bytes(), h, w)
    water_q = decode_u8((terrain_dir / "waterq.u8.z").read_bytes(), h, w)

    height_m = height_raw.astype(np.float32) / 10.0
    height_m[height_raw == NODATA] = np.nan

    water_path = terrain_dir / "water.i16.z"
    if water_path.exists():
        water_raw = decode_i16(water_path.read_bytes(), h, w)
        water_m = water_raw.astype(np.float32) / 10.0
        water_m[water_raw == NODATA] = np.nan
    else:
        water_m = np.full((h, w), np.nan, dtype=np.float32)

    return manifest, WorldRaster(
        build=int(manifest["game"]["build"]),
        height_m=height_m,
        water_m=water_m,
        provenance=provenance,
        water_q=water_q,
        east0_m=float(meta["grid"]["x0_cm"]) / 100.0,
        north0_m=-float(meta["grid"]["y0_cm"]) / 100.0,
        source_spacing_m=float(meta["grid"]["spacing_cm"]) / 100.0,
        meta=meta,
    )
