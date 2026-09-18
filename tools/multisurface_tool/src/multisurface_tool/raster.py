from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import numpy as np


@dataclass(frozen=True)
class MultiSurfaceGrid:
    east0_m: float
    north0_m: float
    step_m: float
    surfaces_m: np.ndarray  # [rows, cols, layers], ascending Z, NaN padded
    source_count: np.ndarray  # [rows, cols], number of accepted triangle samples before clustering

    @property
    def shape(self):
        return self.surfaces_m.shape[:2]


def _triangle_plane_z(tri: np.ndarray, x: np.ndarray, y: np.ndarray):
    p0, p1, p2 = tri
    u = p1 - p0
    v = p2 - p0
    n = np.cross(u, v)
    if abs(float(n[2])) < 1e-9:
        return None
    return p0[2] - (n[0] * (x - p0[0]) + n[1] * (y - p0[1])) / n[2]


def _inside_xy(tri: np.ndarray, x: np.ndarray, y: np.ndarray, eps=1e-9):
    x0,y0 = tri[0,:2]; x1,y1 = tri[1,:2]; x2,y2 = tri[2,:2]
    den = (y1-y2)*(x0-x2) + (x2-x1)*(y0-y2)
    if abs(float(den)) < eps:
        return np.zeros_like(x, dtype=bool)
    a = ((y1-y2)*(x-x2) + (x2-x1)*(y-y2)) / den
    b = ((y2-y0)*(x-x2) + (x0-x2)*(y-y2)) / den
    c = 1.0-a-b
    return (a >= -eps) & (b >= -eps) & (c >= -eps)


def _cluster(vals, tol_m: float, max_layers: int):
    if not vals:
        return []
    vals = sorted(float(v) for v in vals if math.isfinite(float(v)))
    if not vals:
        return []
    groups=[[vals[0]]]
    for z in vals[1:]:
        if z - groups[-1][-1] <= tol_m:
            groups[-1].append(z)
        else:
            groups.append([z])
    # Median is robust to duplicate coplanar triangles and tiny shell noise.
    out=[float(np.median(g)) for g in groups]
    if len(out) > max_layers:
        # Keep the vertical envelope plus the most separated interior layers.
        keep=[out[0], out[-1]]
        remaining=out[1:-1]
        while remaining and len(keep)<max_layers:
            candidate=max(remaining, key=lambda z:min(abs(z-k) for k in keep))
            keep.append(candidate); remaining.remove(candidate)
        out=sorted(keep)
    return out


def rasterize_triangles(
    triangles_xyz: np.ndarray,
    bounds,
    step_m: float,
    *,
    base_surface=None,
    cluster_tolerance_m: float=0.75,
    max_layers: int=6,
    min_abs_normal_z: float=0.08,
):
    """Rasterise multiple Z intersections instead of folding geometry to max-Z.

    `triangles_xyz` is world-space [T,3,3].  Near-vertical triangles are ignored because
    their XY projection does not define a stable horizontal surface.  `base_surface`, when
    supplied, is [rows,cols] and is inserted as another surface sample rather than replacing
    mesh geometry.
    """
    xmin,ymin,xmax,ymax = map(float,bounds)
    cols = int(math.floor((xmax-xmin)/step_m))+1
    rows = int(math.floor((ymax-ymin)/step_m))+1
    east0=xmin; north0=ymax
    buckets=[[[] for _ in range(cols)] for _ in range(rows)]
    counts=np.zeros((rows,cols),dtype=np.uint16)

    if base_surface is not None:
        if base_surface.shape != (rows,cols):
            raise ValueError(f"base_surface shape {base_surface.shape} != {(rows,cols)}")
        for r in range(rows):
            for c in range(cols):
                z=float(base_surface[r,c])
                if math.isfinite(z): buckets[r][c].append(z)

    tris=np.asarray(triangles_xyz,dtype=np.float64)
    if tris.ndim != 3 or tris.shape[1:] != (3,3):
        raise ValueError("triangles_xyz must have shape [T,3,3]")

    for tri in tris:
        n=np.cross(tri[1]-tri[0],tri[2]-tri[0])
        norm=float(np.linalg.norm(n))
        if norm <= 1e-12 or abs(float(n[2]))/norm < min_abs_normal_z:
            continue
        tx0=max(xmin,float(np.min(tri[:,0]))); tx1=min(xmax,float(np.max(tri[:,0])))
        ty0=max(ymin,float(np.min(tri[:,1]))); ty1=min(ymax,float(np.max(tri[:,1])))
        if tx0>tx1 or ty0>ty1: continue
        c0=max(0,int(math.floor((tx0-xmin)/step_m))); c1=min(cols-1,int(math.ceil((tx1-xmin)/step_m)))
        r0=max(0,int(math.floor((ymax-ty1)/step_m))); r1=min(rows-1,int(math.ceil((ymax-ty0)/step_m)))
        if c0>c1 or r0>r1: continue
        cs=np.arange(c0,c1+1); rs=np.arange(r0,r1+1)
        xx=xmin+cs*step_m; yy=ymax-rs*step_m
        X,Y=np.meshgrid(xx,yy)
        inside=_inside_xy(tri,X,Y)
        if not inside.any(): continue
        Z=_triangle_plane_z(tri,X,Y)
        if Z is None: continue
        ir,ic=np.where(inside)
        for lr,lc in zip(ir.tolist(),ic.tolist()):
            r=r0+lr; c=c0+lc; z=float(Z[lr,lc])
            if math.isfinite(z):
                buckets[r][c].append(z)
                counts[r,c]=min(65535,int(counts[r,c])+1)

    surf=np.full((rows,cols,max_layers),np.nan,dtype=np.float32)
    for r in range(rows):
        for c in range(cols):
            layers=_cluster(buckets[r][c],cluster_tolerance_m,max_layers)
            if layers:
                surf[r,c,:len(layers)]=layers
    return MultiSurfaceGrid(east0,north0,step_m,surf,counts)


def save_npz(grid: MultiSurfaceGrid, path):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(path,
        surfaces_m=grid.surfaces_m,
        source_count=grid.source_count,
        east0_m=np.array([grid.east0_m],dtype=np.float64),
        north0_m=np.array([grid.north0_m],dtype=np.float64),
        step_m=np.array([grid.step_m],dtype=np.float32),
    )
