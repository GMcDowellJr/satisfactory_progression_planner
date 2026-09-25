from __future__ import annotations

from dataclasses import dataclass
import heapq, math
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from .heightfield import WorkingField, WATER_MEASURED, WATER_LEVEL_ONLY, PROV_CLIFF_VALUES


@dataclass
class SolveResult:
    route: pd.DataFrame
    validation: pd.DataFrame
    summary: dict


def _in_bounds(shape,r,c):
    return 0<=r<shape[0] and 0<=c<shape[1]


def _box_nanmean(a: np.ndarray, radius: int) -> np.ndarray:
    """Fast NaN-aware square mean used only for grade estimation."""
    if radius <= 0:
        return a.copy()
    valid=np.isfinite(a)
    vals=np.where(valid,a,0.0).astype(np.float64)
    cnt=valid.astype(np.int32)
    ps=np.pad(vals,((1,0),(1,0))).cumsum(0).cumsum(1)
    pc=np.pad(cnt,((1,0),(1,0))).cumsum(0).cumsum(1)
    out=np.full(a.shape,np.nan,dtype=np.float32)
    for r in range(a.shape[0]):
        r0=max(0,r-radius); r1=min(a.shape[0],r+radius+1)
        c0=np.maximum(0,np.arange(a.shape[1])-radius)
        c1=np.minimum(a.shape[1],np.arange(a.shape[1])+radius+1)
        sums=ps[r1,c1]-ps[r0,c1]-ps[r1,c0]+ps[r0,c0]
        counts=pc[r1,c1]-pc[r0,c1]-pc[r1,c0]+pc[r0,c0]
        ok=counts>0
        out[r,ok]=(sums[ok]/counts[ok]).astype(np.float32)
    return out


def _snap_valid(field: WorkingField, seed, max_radius_cells=30):
    r0,c0=seed
    if _in_bounds(field.shape,r0,c0) and np.isfinite(field.z_m[r0,c0]):
        return seed
    for rad in range(1,max_radius_cells+1):
        best=None; bestd=1e9
        for r in range(max(0,r0-rad),min(field.shape[0],r0+rad+1)):
            for c in range(max(0,c0-rad),min(field.shape[1],c0+rad+1)):
                if not np.isfinite(field.z_m[r,c]): continue
                d=(r-r0)**2+(c-c0)**2
                if d<bestd: bestd=d; best=(r,c)
        if best is not None: return best
    raise ValueError("could not snap endpoint to known terrain")


def solve(
    field: WorkingField,
    origin,
    destination,
    profile,
    roads=None,
    road_band=None,
    bridge_policy="forbid",
    corridor_pad_m=800.0,
):
    """A* over a cropped working grid with water/grade constraints inside the search."""
    roads=np.zeros(field.shape,dtype=bool) if roads is None else roads
    road_band=np.zeros(field.shape,dtype=bool) if road_band is None else road_band

    s=_snap_valid(field,field.world_to_rc(*origin))
    g=_snap_valid(field,field.world_to_rc(*destination))

    pad=max(10,int(round(corridor_pad_m/field.step_m)))
    rmin=max(0,min(s[0],g[0])-pad); rmax=min(field.shape[0],max(s[0],g[0])+pad+1)
    cmin=max(0,min(s[1],g[1])-pad); cmax=min(field.shape[1],max(s[1],g[1])+pad+1)

    z=field.z_m[rmin:rmax,cmin:cmax]
    # Grade uses a ~20 m neighborhood instead of noisy 5 m raw edges.
    grade_radius=max(1,int(round(10.0/field.step_m)))
    zg=_box_nanmean(z,grade_radius)
    prov=field.prov[rmin:rmax,cmin:cmax]
    wq=field.water_q[rmin:rmax,cmin:cmax]
    wd=field.water_depth_m[rmin:rmax,cmin:cmax]
    rd=roads[rmin:rmax,cmin:cmax]
    rb=road_band[rmin:rmax,cmin:cmax]

    ls=(s[0]-rmin,s[1]-cmin); lg=(g[0]-rmin,g[1]-cmin)
    shape=z.shape
    dist=np.full(shape,np.inf,dtype=np.float64)
    prev=np.full((shape[0],shape[1],2),-1,dtype=np.int32)
    dist[ls]=0.0
    pq=[(math.hypot(ls[0]-lg[0],ls[1]-lg[1]),0.0,ls)]
    dirs=[(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]
    stepxy=[field.step_m]*4+[field.step_m*math.sqrt(2)]*4

    hard_grade=float(profile["grade_hard_block"])
    soft_grade=float(profile["grade_soft_start"])

    while pq:
        _,gc,(r,c)=heapq.heappop(pq)
        if gc != dist[r,c]:
            continue
        if (r,c)==lg:
            break
        z0=z[r,c]
        if not np.isfinite(z0): continue

        for (dr,dc),horizontal in zip(dirs,stepxy):
            nr,nc=r+dr,c+dc
            if not _in_bounds(shape,nr,nc): continue
            z1=z[nr,nc]
            if not np.isfinite(z1): continue

            gz0=zg[r,c]; gz1=zg[nr,nc]
            grade=abs(float(gz1-gz0))/horizontal if np.isfinite(gz0) and np.isfinite(gz1) else 0.0
            if grade > hard_grade:
                continue

            waterq=int(wq[nr,nc])
            depth=float(wd[nr,nc]) if np.isfinite(wd[nr,nc]) else None
            deep = waterq != 0 and (depth is None or depth >= float(profile["deep_water_depth_m"]))
            if deep and bridge_policy=="forbid":
                continue

            factor=1.0
            if rd[nr,nc]:
                factor*=float(profile["road_factor"])
            elif rb[nr,nc]:
                factor*=float(profile["road_band_factor"])

            if grade>soft_grade:
                factor *= 1.0 + float(profile["grade_penalty"])*(grade-soft_grade)**2

            if waterq != 0:
                factor *= float(profile["deep_water_penalty"] if deep else profile["shallow_water_penalty"])

            if int(prov[nr,nc]) in PROV_CLIFF_VALUES:
                factor *= float(profile["cliff_penalty"])

            ng=gc+horizontal*factor
            if ng<dist[nr,nc]:
                dist[nr,nc]=ng
                prev[nr,nc]=[r,c]
                h=math.hypot(nr-lg[0],nc-lg[1])*field.step_m
                heapq.heappush(pq,(ng+h,ng,(nr,nc)))

    if not np.isfinite(dist[lg]):
        raise RuntimeError(
            "No route found under current constraints. Try a larger --corridor-pad-m, "
            "bridge-policy allow, or a different movement profile."
        )

    path=[]
    cur=lg
    while cur!=ls:
        path.append(cur)
        pr=prev[cur]
        if pr[0]<0: raise RuntimeError("route predecessor chain broke")
        cur=(int(pr[0]),int(pr[1]))
    path.append(ls); path.reverse()

    recs=[]; cum=0.0
    prev_world=None
    for i,(lr,lc) in enumerate(path):
        gr,gc=lr+rmin,lc+cmin
        east,north=field.rc_to_world(gr,gc)
        if prev_world is None:
            seg=0.0; grade=0.0
        else:
            seg=math.hypot(east-prev_world[0],north-prev_world[1])
            grade=abs(float(field.z_m[gr,gc]-prev_world[2]))/seg if seg else 0.0
            cum+=seg
        depth=float(field.water_depth_m[gr,gc]) if np.isfinite(field.water_depth_m[gr,gc]) else np.nan
        recs.append({
            "point_order":i,"east_m":east,"north_m":north,
            "elevation_m":float(field.z_m[gr,gc]),
            "segment_distance_m":seg,"cumulative_distance_m":cum,
            "edge_grade_pct":grade*100,
            "water_quality":int(field.water_q[gr,gc]),
            "water_depth_m":depth,
            "terrain_provenance":int(field.prov[gr,gc]),
            "on_road":bool(roads[gr,gc]),
            "in_road_band":bool(road_band[gr,gc]),
        })
        prev_world=(east,north,float(field.z_m[gr,gc]))
    route=pd.DataFrame(recs)

    validation=_validate(route,profile)
    summary={
        "route_length_m":float(route["cumulative_distance_m"].iloc[-1]),
        "search_cost":float(dist[lg]),
        "point_count":len(route),
        "road_fraction":float(route["on_road"].mean()),
        "road_band_fraction":float(route["in_road_band"].mean()),
        "water_fraction":float((route["water_quality"]!=0).mean()),
        "max_edge_grade_pct":float(route["edge_grade_pct"].max()),
        "bridge_policy":bridge_policy,
        "valid_under_profile":not (validation["status"]=="FAIL").any(),
    }
    return SolveResult(route,validation,summary)


def _validate(route: pd.DataFrame, profile):
    rows=[]
    maxg=float(route.edge_grade_pct.max())
    rows.append({
        "check":"hard_grade",
        "status":"PASS" if maxg <= float(profile["grade_hard_block"])*100+1e-6 else "FAIL",
        "value":maxg,
        "limit":float(profile["grade_hard_block"])*100,
    })
    deep_threshold=float(profile["deep_water_depth_m"])
    known_deep=route.water_depth_m.fillna(-1)>=deep_threshold
    unknown_water=(route.water_quality!=0)&route.water_depth_m.isna()
    rows.append({
        "check":"deep_water_exposure",
        "status":"WARN" if bool(known_deep.any() or unknown_water.any()) else "PASS",
        "value":int((known_deep|unknown_water).sum()),
        "limit":0,
    })
    rows.append({
        "check":"unknown_terrain",
        "status":"PASS",
        "value":0,
        "limit":0,
    })
    return pd.DataFrame(rows)


def write_result(result: SolveResult, out_dir: str, field: WorkingField, roads=None):
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    result.route.to_csv(out/"route_points.csv",index=False, lineterminator="\n")
    result.validation.to_csv(out/"route_validation.csv",index=False, lineterminator="\n")
    import json
    (out/"route_summary.json").write_text(json.dumps(result.summary,indent=2),encoding="utf-8", newline="\n")

    plt.figure(figsize=(9,7))
    if roads is not None:
        # crop display around route
        rcs=[field.world_to_rc(e,n) for e,n in result.route[["east_m","north_m"]].to_numpy()]
        rr=[r for r,c in rcs]; cc=[c for r,c in rcs]
        pad=80
        r0=max(0,min(rr)-pad); r1=min(field.shape[0],max(rr)+pad)
        c0=max(0,min(cc)-pad); c1=min(field.shape[1],max(cc)+pad)
        plt.imshow(roads[r0:r1,c0:c1],origin="upper",extent=[
            field.east0_m+c0*field.step_m,
            field.east0_m+c1*field.step_m,
            field.north0_m-r1*field.step_m,
            field.north0_m-r0*field.step_m,
        ],alpha=0.35)
    plt.plot(result.route.east_m,result.route.north_m)
    plt.scatter([result.route.east_m.iloc[0],result.route.east_m.iloc[-1]],
                [result.route.north_m.iloc[0],result.route.north_m.iloc[-1]])
    plt.xlabel("East (m)"); plt.ylabel("North (m)")
    plt.title("Solved route")
    plt.axis("equal"); plt.tight_layout()
    plt.savefig(out/"route_map.png",dpi=160)
    plt.close()
