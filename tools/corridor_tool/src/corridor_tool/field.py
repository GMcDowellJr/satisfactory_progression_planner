from __future__ import annotations

from dataclasses import dataclass
import json, zlib
from pathlib import Path
import numpy as np

NODATA = -32768
WATER_DRY = 0
WATER_MEASURED = 1
PROV_CLIFF_VALUES = (4, 5)


def decode_i16(path: Path, h: int, w: int) -> np.ndarray:
    delta = np.frombuffer(zlib.decompress(path.read_bytes()), dtype="<i2")
    if delta.size != h*w:
        raise ValueError(f"raster size mismatch for {path}")
    return np.cumsum(delta.reshape(h,w).astype(np.int32), axis=1).astype(np.int16)


def decode_u8(path: Path, h: int, w: int) -> np.ndarray:
    a=np.frombuffer(zlib.decompress(path.read_bytes()), dtype=np.uint8)
    if a.size != h*w:
        raise ValueError(f"raster size mismatch for {path}")
    return a.reshape(h,w)


@dataclass
class TerrainField:
    step_m: float
    east0_m: float
    north0_m: float
    z_m: np.ndarray
    prov: np.ndarray
    water_q: np.ndarray
    water_depth_m: np.ndarray

    def rc_to_world(self,r:int,c:int):
        return self.east0_m+c*self.step_m, self.north0_m-r*self.step_m


def load_field(repo: Path, world_manifest: Path, step_m: float) -> tuple[TerrainField, dict]:
    manifest=json.loads(world_manifest.read_text(encoding="utf-8"))
    rel=manifest["layers"]["terrain_water"]["path"]
    base=repo/"planning_data"/rel
    meta=json.loads((base/"meta.json").read_text(encoding="utf-8"))
    h=int(meta["grid"]["height"]); w=int(meta["grid"]["width"])
    native=float(meta["grid"]["spacing_cm"])/100.0
    stride=max(1,int(round(step_m/native)))
    actual=native*stride
    height=decode_i16(base/"height.i16.z",h,w)[::stride,::stride]
    prov=decode_u8(base/"prov.u8.z",h,w)[::stride,::stride]
    water=decode_i16(base/"water.i16.z",h,w)[::stride,::stride]
    waterq=decode_u8(base/"waterq.u8.z",h,w)[::stride,::stride]
    z=height.astype(np.float32)/10.; z[height==NODATA]=np.nan
    wz=water.astype(np.float32)/10.; wz[water==NODATA]=np.nan
    depth=np.full(z.shape,np.nan,np.float32)
    m=waterq==WATER_MEASURED
    depth[m]=np.maximum(wz[m]-z[m],0)
    east0=float(meta["grid"]["x0_cm"])/100.
    north0=-float(meta["grid"]["y0_cm"])/100.
    return TerrainField(actual,east0,north0,z,prov,waterq,depth), manifest
