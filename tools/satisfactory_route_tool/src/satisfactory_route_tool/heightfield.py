from __future__ import annotations

from dataclasses import dataclass
import json
import zlib
import numpy as np

from .package import PlannerPackage

NODATA = -32768
PROV_CLIFF_VALUES = (4, 5)
WATER_DRY = 0
WATER_MEASURED = 1
WATER_LEVEL_ONLY = 2


def decode_i16(blob: bytes, height: int, width: int) -> np.ndarray:
    delta = np.frombuffer(zlib.decompress(blob), dtype="<i2")
    if delta.size != height * width:
        raise ValueError("raster size does not match meta.json")
    running = np.cumsum(delta.reshape(height, width).astype(np.int32), axis=1)
    return running.astype(np.int16)


def decode_u8(blob: bytes, height: int, width: int) -> np.ndarray:
    flat = np.frombuffer(zlib.decompress(blob), dtype=np.uint8)
    if flat.size != height * width:
        raise ValueError("raster size does not match meta.json")
    return flat.reshape(height, width)


@dataclass
class WorkingField:
    step_m: float
    east0_m: float
    north0_m: float
    z_m: np.ndarray
    prov: np.ndarray
    water_q: np.ndarray
    water_depth_m: np.ndarray

    @property
    def shape(self):
        return self.z_m.shape

    def world_to_rc(self, east_m: float, north_m: float):
        c = int(round((east_m - self.east0_m) / self.step_m))
        r = int(round((self.north0_m - north_m) / self.step_m))
        return r, c

    def rc_to_world(self, r: int, c: int):
        return self.east0_m + c*self.step_m, self.north0_m - r*self.step_m


def load_working_field(pkg: PlannerPackage, build="502094", step_m=5.0) -> WorkingField:
    base = f"world/spatial/heightmap_build_{build}"
    meta = json.loads(pkg.read_text(f"{base}/meta.json"))
    h = int(meta["grid"]["height"])
    w = int(meta["grid"]["width"])
    native_step = float(meta["grid"]["spacing_cm"]) / 100.0
    if step_m < native_step:
        raise ValueError("working step cannot be finer than source field")
    stride = max(1, int(round(step_m/native_step)))
    actual_step = native_step * stride

    height = decode_i16(pkg.read_bytes(f"{base}/height.i16.z"), h, w)[::stride, ::stride]
    prov = decode_u8(pkg.read_bytes(f"{base}/prov.u8.z"), h, w)[::stride, ::stride]
    water = decode_i16(pkg.read_bytes(f"{base}/water.i16.z"), h, w)[::stride, ::stride]
    waterq = decode_u8(pkg.read_bytes(f"{base}/waterq.u8.z"), h, w)[::stride, ::stride]

    z = height.astype(np.float32) / 10.0
    z[height == NODATA] = np.nan
    wz = water.astype(np.float32) / 10.0
    wz[water == NODATA] = np.nan
    depth = np.full(z.shape, np.nan, dtype=np.float32)
    measured = waterq == WATER_MEASURED
    depth[measured] = np.maximum(wz[measured] - z[measured], 0)

    east0 = float(meta["grid"]["x0_cm"]) / 100.0
    # Grid Y grows south. Planner coordinates use north=-gameY.
    north0 = -float(meta["grid"]["y0_cm"]) / 100.0

    return WorkingField(
        step_m=actual_step,
        east0_m=east0,
        north0_m=north0,
        z_m=z,
        prov=prov,
        water_q=waterq,
        water_depth_m=depth,
    )
