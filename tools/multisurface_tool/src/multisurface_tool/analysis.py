from __future__ import annotations
import numpy as np
from .raster import MultiSurfaceGrid


def derive_clearance(grid: MultiSurfaceGrid, min_gap_m: float=0.75):
    """For each layer, return clearance to the next distinct surface above it."""
    s=grid.surfaces_m
    clearance=np.full_like(s,np.nan,dtype=np.float32)
    for k in range(s.shape[2]-1):
        a=s[:,:,k]; b=s[:,:,k+1]
        gap=b-a
        ok=np.isfinite(a)&np.isfinite(b)&(gap>=min_gap_m)
        clearance[:,:,k][ok]=gap[ok]
    return clearance


def layer_count(grid: MultiSurfaceGrid):
    return np.isfinite(grid.surfaces_m).sum(axis=2).astype(np.uint8)
