from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np
import pandas as pd
from scipy import ndimage as ndi
from skimage.morphology import skeletonize
from .field import TerrainField, PROV_CLIFF_VALUES

@dataclass
class CorridorResult:
    passable: np.ndarray
    clearance_m: np.ndarray
    skeleton: np.ndarray
    nodes: pd.DataFrame
    edges: pd.DataFrame
    summary: dict


def _smooth_nan(z: np.ndarray, radius: int) -> np.ndarray:
    if radius<=0: return z.copy()
    size=2*radius+1
    valid=np.isfinite(z)
    vals=np.where(valid,z,0.)
    s=ndi.uniform_filter(vals.astype(np.float64),size=size,mode="nearest")
    c=ndi.uniform_filter(valid.astype(np.float64),size=size,mode="nearest")
    out=np.full(z.shape,np.nan,np.float32)
    ok=c>1e-9
    out[ok]=(s[ok]/c[ok]).astype(np.float32)
    return out


def build_passability(field: TerrainField, policy: dict):
    t=policy["terrain"]; w=policy["water"]
    radius=max(1,int(round(float(t["grade_neighborhood_m"])/(2*field.step_m))))
    zs=_smooth_nan(field.z_m,radius)
    gy,gx=np.gradient(zs,field.step_m,field.step_m)
    grade=np.sqrt(gx*gx+gy*gy)
    passable=np.isfinite(field.z_m)
    if bool(t.get("unknown_terrain_block",True)):
        passable &= np.isfinite(zs)
    passable &= np.nan_to_num(grade,np.inf) <= float(t["grade_hard_block"])
    if bool(t.get("cliff_provenance_block",False)):
        passable &= ~np.isin(field.prov,PROV_CLIFF_VALUES)
    if bool(w.get("block_any_water",False)):
        passable &= field.water_q==0
    elif bool(w.get("block_deep_or_unknown_depth",True)):
        inwater=field.water_q!=0
        known_deep=np.isfinite(field.water_depth_m)&(field.water_depth_m>=float(w["deep_water_depth_m"]))
        unknown=inwater&~np.isfinite(field.water_depth_m)
        passable &= ~(known_deep|unknown)
    return passable, grade


def _neighbors8(shape,r,c):
    for dr in (-1,0,1):
        for dc in (-1,0,1):
            if dr==0 and dc==0: continue
            rr=r+dr; cc=c+dc
            if 0<=rr<shape[0] and 0<=cc<shape[1]: yield rr,cc


def _trace_graph(skel: np.ndarray, field: TerrainField, clearance: np.ndarray, grade: np.ndarray):
    coords=np.argwhere(skel)
    degree=np.zeros(skel.shape,np.uint8)
    for r,c in coords:
        degree[r,c]=sum(1 for rr,cc in _neighbors8(skel.shape,int(r),int(c)) if skel[rr,cc])
    node_mask=skel & (degree!=2)
    node_coords=[tuple(map(int,x)) for x in np.argwhere(node_mask)]
    # Closed loops have no natural degree!=2 node. Seed one node per such remaining component later.
    node_set=set(node_coords)
    visited=set(); edges=[]
    def edgekey(a,b): return (a,b) if a<=b else (b,a)
    def trace_from(start,nxt):
        path=[start,nxt]; prev=start; cur=nxt
        while cur not in node_set:
            opts=[x for x in _neighbors8(skel.shape,*cur) if skel[x] and x!=prev]
            if not opts: break
            # degree 2 should leave exactly one continuation.
            nn=opts[0]; path.append(nn); prev,cur=cur,nn
        return path
    for start in list(node_coords):
        for nb in _neighbors8(skel.shape,*start):
            if not skel[nb] or edgekey(start,nb) in visited: continue
            path=trace_from(start,nb)
            for a,b in zip(path[:-1],path[1:]): visited.add(edgekey(a,b))
            end=path[-1]
            if end not in node_set:
                node_set.add(end); node_coords.append(end)
            edges.append(path)
    # Recover pure-loop components omitted above.
    remaining=skel.copy()
    for a,b in visited:
        remaining[a]=False; remaining[b]=False
    lab,n=ndi.label(remaining,np.ones((3,3),int))
    for k in range(1,n+1):
        pts=np.argwhere(lab==k)
        if len(pts)<3: continue
        seed=tuple(map(int,pts[0])); node_set.add(seed); node_coords.append(seed)
    # Stable node ids by world position.
    node_coords=sorted(set(node_coords))
    nid={rc:f"CN{idx+1:05d}" for idx,rc in enumerate(node_coords)}
    node_rows=[]
    for rc in node_coords:
        r,c=rc; east,north=field.rc_to_world(r,c)
        d=int(degree[r,c])
        kind="endpoint" if d<=1 else ("junction" if d>=3 else "loop_anchor")
        node_rows.append({"node_id":nid[rc],"kind":kind,"row":r,"col":c,"east_m":east,"north_m":north,"elevation_m":float(field.z_m[r,c]),"degree":d,"clearance_m":float(clearance[r,c])})
    edge_rows=[]
    for i,path in enumerate(edges,1):
        a=path[0]; b=path[-1]
        if a not in nid or b not in nid: continue
        length=0.; maxg=0.; cls=[]
        for p,q in zip(path[:-1],path[1:]):
            dr=q[0]-p[0]; dc=q[1]-p[1]
            length+=field.step_m*math.hypot(dr,dc)
        for r,c in path:
            if np.isfinite(grade[r,c]): maxg=max(maxg,float(grade[r,c]))
            if np.isfinite(clearance[r,c]): cls.append(float(clearance[r,c]))
        mincl=min(cls) if cls else float("nan"); medcl=float(np.median(cls)) if cls else float("nan")
        edge_rows.append({"edge_id":f"CE{i:05d}","from_node":nid[a],"to_node":nid[b],"length_m":length,"point_count":len(path),"min_clearance_m":mincl,"p10_clearance_m":float(np.percentile(cls,10)) if cls else float("nan"),"median_clearance_m":medcl,"max_grade":maxg,"path_rc":";".join(f"{r}:{c}" for r,c in path)})
    return pd.DataFrame(node_rows),pd.DataFrame(edge_rows)


def derive(field: TerrainField, policy: dict) -> CorridorResult:
    passable,grade=build_passability(field,policy)
    # Distance to nearest physical blocker. Border acts as outside-world blocker.
    clearance=ndi.distance_transform_edt(passable)*field.step_m
    skel=skeletonize(passable)
    nodes,edges=_trace_graph(skel,field,clearance,grade)
    cpol=policy["corridor"]
    if not edges.empty:
        edges["corridor_class"]=np.where(edges.p10_clearance_m<=float(cpol["chokepoint_half_width_m"]),"chokepoint",np.where(edges.median_clearance_m<=float(cpol["maximum_constrained_half_width_m"]),"constrained","open"))
        edges=edges[edges.length_m>=float(cpol["minimum_branch_length_m"])].reset_index(drop=True)
        referenced=set(edges.from_node).union(edges.to_node)
        nodes=nodes[nodes.node_id.isin(referenced)].copy().reset_index(drop=True)
        if not nodes.empty:
            deg=pd.concat([edges.from_node,edges.to_node]).value_counts()
            nodes["graph_degree"]=nodes.node_id.map(deg).fillna(0).astype(int)
    labels,ncomp=ndi.label(passable,np.ones((3,3),int))
    summary={
        "analysis_step_m":field.step_m,
        "grid_height":int(passable.shape[0]),"grid_width":int(passable.shape[1]),
        "passable_fraction":float(passable.mean()),"passable_components":int(ncomp),
        "skeleton_cells":int(skel.sum()),"graph_nodes":int(len(nodes)),"graph_edges":int(len(edges)),
        "edge_classes":({str(k):int(v) for k,v in edges.corridor_class.value_counts().items()} if not edges.empty else {}),
    }
    return CorridorResult(passable,clearance.astype(np.float32),skel,nodes,edges,summary)
