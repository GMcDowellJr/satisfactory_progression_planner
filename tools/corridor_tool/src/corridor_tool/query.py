from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
from pathlib import Path
import pandas as pd


@dataclass
class CorridorPath:
    points: pd.DataFrame
    edges: pd.DataFrame
    summary: dict


def _nearest_node(nodes: pd.DataFrame, point: tuple[float,float]):
    dx=nodes["east_m"]-float(point[0]); dy=nodes["north_m"]-float(point[1])
    d=(dx*dx+dy*dy)**0.5
    idx=d.idxmin()
    return str(nodes.loc[idx,"node_id"]), float(d.loc[idx])


def _edge_cost(e, grade_soft_start=0.35, chokepoint_penalty=0.10):
    # Physical-corridor ranking only: mostly length, with modest penalties for
    # sustained grade and narrow topology. Mode-specific costs remain downstream.
    grade=max(0.0,float(e.max_grade)-float(grade_soft_start))
    narrow=1.0 + (float(chokepoint_penalty) if str(e.corridor_class)=="chokepoint" else 0.0)
    return float(e.length_m) * narrow * (1.0 + 2.0*grade*grade)


def shortest_corridor(nodes: pd.DataFrame, edges: pd.DataFrame,
                      origin: tuple[float,float], destination: tuple[float,float],
                      east0_m: float, north0_m: float, step_m: float) -> CorridorPath:
    s,snap_s=_nearest_node(nodes,origin); g,snap_g=_nearest_node(nodes,destination)
    adj={}
    for idx,e in edges.iterrows():
        cost=_edge_cost(e)
        adj.setdefault(str(e.from_node),[]).append((str(e.to_node),cost,idx))
        adj.setdefault(str(e.to_node),[]).append((str(e.from_node),cost,idx))
    dist={s:0.0}; prev={}; pq=[(0.0,s)]
    while pq:
        du,u=heapq.heappop(pq)
        if du!=dist.get(u): continue
        if u==g: break
        for v,w,idx in adj.get(u,[]):
            nd=du+w
            if nd<dist.get(v,math.inf):
                dist[v]=nd; prev[v]=(u,idx); heapq.heappush(pq,(nd,v))
    if g not in dist:
        raise RuntimeError(f"corridor graph has no connected path between snapped nodes {s} and {g}")
    chain=[]; u=g
    while u!=s:
        pu,idx=prev[u]; chain.append((pu,u,idx)); u=pu
    chain.reverse()
    edge_rows=[]; point_rows=[]; cumulative=0.0; last=None
    for order,(u,v,idx) in enumerate(chain):
        e=edges.loc[idx]
        rcs=[tuple(map(int,t.split(":"))) for t in str(e.path_rc).split(";")]
        if str(e.from_node)!=u: rcs.reverse()
        edge_rows.append(e.to_dict())
        for r,c in (rcs if order==0 else rcs[1:]):
            east=float(east0_m+c*step_m); north=float(north0_m-r*step_m)
            if last is not None: cumulative += math.hypot(east-last[0],north-last[1])
            point_rows.append({"point_order":len(point_rows),"row":r,"col":c,"east_m":east,"north_m":north,"cumulative_distance_m":cumulative})
            last=(east,north)
    ep=pd.DataFrame(edge_rows)
    pp=pd.DataFrame(point_rows)
    summary={
        "origin_snap_node":s,"destination_snap_node":g,
        "origin_snap_distance_m":snap_s,"destination_snap_distance_m":snap_g,
        "graph_path_length_m":float(ep.length_m.sum()) if not ep.empty else 0.0,
        "graph_search_cost":float(dist[g]),"edge_count":int(len(ep)),"point_count":int(len(pp)),
        "chokepoint_edge_count":int((ep.corridor_class=="chokepoint").sum()) if not ep.empty else 0,
        "max_graph_edge_grade":float(ep.max_grade.max()) if not ep.empty else 0.0,
        "minimum_p10_clearance_m":float(ep.p10_clearance_m.min()) if not ep.empty else math.nan,
    }
    return CorridorPath(pp,ep,summary)


def corridor_alternatives(nodes: pd.DataFrame, edges: pd.DataFrame,
                          origin: tuple[float,float], destination: tuple[float,float],
                          east0_m: float, north0_m: float, step_m: float,
                          count: int = 3, separation_m: float = 128.0,
                          avoidance_penalty: float = 3.0) -> list[CorridorPath]:
    """Return materially different corridor candidates by progressively penalizing
    graph edges close to already-selected routes.

    This is intentionally not a mode-specific k-shortest-path solver.  It is a
    physical-corridor sampler: candidate 1 is the normal terrain-preferred path;
    later candidates are encouraged into different terrain bands so downstream
    movement profiles can evaluate genuinely different options.
    """
    if count <= 0:
        return []
    s,snap_s=_nearest_node(nodes,origin); g,snap_g=_nearest_node(nodes,destination)

    # Predecode edge geometry and midpoint once.
    edge_geom={}
    edge_mid={}
    for idx,e in edges.iterrows():
        rcs=[tuple(map(int,t.split(":"))) for t in str(e.path_rc).split(";")]
        pts=[(float(east0_m+c*step_m), float(north0_m-r*step_m)) for r,c in rcs]
        edge_geom[idx]=pts
        edge_mid[idx]=pts[len(pts)//2]

    adj={}
    for idx,e in edges.iterrows():
        cost=_edge_cost(e)
        adj.setdefault(str(e.from_node),[]).append((str(e.to_node),cost,idx))
        adj.setdefault(str(e.to_node),[]).append((str(e.from_node),cost,idx))

    def _run(mult):
        dist={s:0.0}; prev={}; pq=[(0.0,s)]
        while pq:
            du,u=heapq.heappop(pq)
            if du!=dist.get(u): continue
            if u==g: break
            for v,w,idx in adj.get(u,[]):
                nd=du+w*mult.get(idx,1.0)
                if nd<dist.get(v,math.inf):
                    dist[v]=nd; prev[v]=(u,idx); heapq.heappush(pq,(nd,v))
        if g not in dist:
            return None
        chain=[]; u=g
        while u!=s:
            pu,idx=prev[u]; chain.append((pu,u,idx)); u=pu
        chain.reverse()
        edge_rows=[]; point_rows=[]; cumulative=0.0; last=None
        for order,(u,v,idx) in enumerate(chain):
            e=edges.loc[idx]
            pts=list(edge_geom[idx])
            if str(e.from_node)!=u: pts.reverse()
            edge_rows.append(e.to_dict())
            for east,north in (pts if order==0 else pts[1:]):
                if last is not None: cumulative += math.hypot(east-last[0],north-last[1])
                r=int(round((north0_m-north)/step_m)); c=int(round((east-east0_m)/step_m))
                point_rows.append({"point_order":len(point_rows),"row":r,"col":c,
                                   "east_m":east,"north_m":north,
                                   "cumulative_distance_m":cumulative})
                last=(east,north)
        ep=pd.DataFrame(edge_rows); pp=pd.DataFrame(point_rows)
        summary={
            "origin_snap_node":s,"destination_snap_node":g,
            "origin_snap_distance_m":snap_s,"destination_snap_distance_m":snap_g,
            "graph_path_length_m":float(ep.length_m.sum()) if not ep.empty else 0.0,
            "graph_search_cost":float(dist[g]),"edge_count":int(len(ep)),"point_count":int(len(pp)),
            "chokepoint_edge_count":int((ep.corridor_class=="chokepoint").sum()) if not ep.empty else 0,
            "max_graph_edge_grade":float(ep.max_grade.max()) if not ep.empty else 0.0,
            "minimum_p10_clearance_m":float(ep.p10_clearance_m.min()) if not ep.empty else math.nan,
        }
        return CorridorPath(pp,ep,summary)

    selected=[]
    prior_points=[]
    for k in range(count):
        mult={}
        if prior_points:
            # Keep computation bounded; corridor routes are already sampled at graph resolution.
            samples=[]
            for pts in prior_points:
                stride=max(1,len(pts)//500)
                samples.extend(pts[::stride])
            sep2=float(separation_m)**2
            for idx,(mx,my) in edge_mid.items():
                d2=min((mx-x)**2+(my-y)**2 for x,y in samples)
                if d2 < sep2:
                    d=math.sqrt(d2)
                    mult[idx]=1.0 + float(avoidance_penalty)*(1.0-d/float(separation_m))**2
        result=_run(mult)
        if result is None: break
        # Stop rather than emit an exact duplicate when the graph has no further material option.
        edge_ids=tuple(result.edges.get("edge_id",pd.Series(dtype=str)).astype(str))
        prior_ids={tuple(x.edges.get("edge_id",pd.Series(dtype=str)).astype(str)) for x in selected}
        if edge_ids in prior_ids: break
        result.summary["alternative_index"]=k+1
        selected.append(result)
        prior_points.append(list(result.points[["east_m","north_m"]].itertuples(index=False,name=None)))
    return selected
