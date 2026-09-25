from __future__ import annotations

import io, math
from pathlib import Path
import numpy as np
import pandas as pd

from .package import PlannerPackage


def _read_csv(pkg: PlannerPackage, rel: str):
    return pd.read_csv(io.BytesIO(pkg.read_bytes(rel)))


def score_pois(pkg: PlannerPackage, route_csv: str, out_dir: str, trip_type="first_trip", max_offset_m=350.0):
    route=pd.read_csv(route_csv)
    pois=_read_csv(pkg,"world/canonical/exploration_pois.csv")
    req=_read_csv(pkg,"game/reference/crash_site_requirements.csv")
    pois=pois.merge(req,on="poi_id",how="left")

    rxy=route[["east_m","north_m"]].to_numpy()
    rz=route["elevation_m"].to_numpy() if "elevation_m" in route else np.full(len(route),np.nan)

    rows=[]
    for _,p in pois.iterrows():
        d=np.hypot(rxy[:,0]-p.east_m,rxy[:,1]-p.north_m)
        k=int(np.argmin(d)); off=float(d[k])
        if off>max_offset_m: continue
        dz=abs(float(p.elevation_m-rz[k])) if np.isfinite(rz[k]) else 0.0
        effort=2*off+1.5*dz
        if effort<=100: cls="near_free"
        elif effort<=250: cls="strong_detour"
        elif p.poi_type=="crash_site" and effort<=500: cls="purposeful_detour"
        elif effort<=400: cls="optional_detour"
        else: cls="defer"
        rows.append({
            "poi_id":p.poi_id,"poi_type":p.poi_type,
            "east_m":p.east_m,"north_m":p.north_m,"elevation_m":p.elevation_m,
            "nearest_route_point":k,"horizontal_offset_m":off,"vertical_delta_m":dz,
            "foot_equivalent_outback_m":effort,"recommendation_class":cls,
            "cost_type":p.get("cost_type"),"item":p.get("item"),"amount":p.get("amount"),
            "trip_type":trip_type,
        })
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    df=pd.DataFrame(rows).sort_values(["recommendation_class","foot_equivalent_outback_m"])
    df.to_csv(out/"nearby_pois.csv",index=False, lineterminator="\n")
    return df
