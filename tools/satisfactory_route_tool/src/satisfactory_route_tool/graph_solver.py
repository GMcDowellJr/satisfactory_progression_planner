from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import heapq, math
from pathlib import Path
import numpy as np
import pandas as pd

from .heightfield import WorkingField, PROV_CLIFF_VALUES
from .surface_graph import SurfaceGraphData, CorridorOverlay


# ---------------------------------------------------------------------------
# ROUTING TUNING CONFIG
# ---------------------------------------------------------------------------
# Lower road factors make authored SCIM roads more attractive. These are
# intentionally centralized so route behavior can be tuned without touching
# the search implementation.
ROUTING_TUNING = {
    "road_straight_factor": 0.42,
    "road_turn_factor": 0.55,
    "band_continuation_factor": 0.68,
    "road_transition_factor": 0.85,

    # ACCESS_ENDPOINT mode: used for destinations (such as an island district)
    # where a useful vehicle route should terminate at the best land/road
    # approach rather than requiring the vehicle to reach the anchor itself.
    "access_endpoint_radius_m": 1200.0,
    "access_gap_factor": 0.75,
    "access_road_bonus_m": 220.0,
    "access_road_band_bonus_m": 90.0,
}


@dataclass
class SolveResult:
    route: pd.DataFrame
    validation: pd.DataFrame
    summary: dict



@lru_cache(maxsize=8)
def _cached_surface_graph(graph_dir: str, intervals_path: str | None):
    """Process-local cache; useful when a worker solves several district pairs."""
    return SurfaceGraphData(
        Path(graph_dir),
        None if intervals_path is None else Path(intervals_path),
    )


def _mode_default_clearance(profile):
    mode=str(profile.get('_mode','')).lower()
    return {'foot':2.0,'tractor':4.5,'truck':5.5,'rail':8.0}.get(mode,4.5)


def _resample_prior(path,field):
    if path is None:
        return np.zeros(field.shape,bool),np.zeros(field.shape,bool)
    with np.load(path) as d:
        road=np.asarray(d['road']).astype(bool); band=np.asarray(d['road_band']).astype(bool)
        step=float(np.asarray(d['step_m']).ravel()[0]); e0=float(np.asarray(d['east0_m']).ravel()[0]); n0=float(np.asarray(d['north0_m']).ravel()[0])
    rr=np.arange(field.shape[0]); cc=np.arange(field.shape[1])
    north=field.north0_m-rr*field.step_m; east=field.east0_m+cc*field.step_m
    sr=np.rint((n0-north)/step).astype(int); sc=np.rint((east-e0)/step).astype(int)
    sr=np.clip(sr,0,road.shape[0]-1); sc=np.clip(sc,0,road.shape[1]-1)
    return road[sr[:,None],sc[None,:]], band[sr[:,None],sc[None,:]]


def _state_cell(state,graph:SurfaceGraphData):
    if state<0: return -state-1
    pos=int(np.searchsorted(graph.offsets,np.int64(state),side='right')-1)
    return int(graph.cells[pos])


def _state_rc(state, graph):
    return divmod(_state_cell(state, graph), graph.width)


def _state_world(state, graph, field):
    r, c = _state_rc(state, graph)
    return field.rc_to_world(r, c)


def _state_z(state,graph,overlay,field):
    if state>=0: return overlay.node_floor_z[state]
    cell=-state-1; r,c=divmod(cell,graph.width); return float(field.z_m[r,c])


def _state_clearance(state,overlay):
    if state<0: return math.inf
    v=overlay.node_clearance.get(state,math.nan)
    return float(v) if math.isfinite(v) else math.inf


def _water_for_state(state,graph,overlay,field):
    cell=_state_cell(state,graph); r,c=divmod(cell,graph.width)
    q=int(field.water_q[r,c])
    if q==0: return 0,0.0
    base_depth=float(field.water_depth_m[r,c]) if np.isfinite(field.water_depth_m[r,c]) else math.nan
    if state<0: return q,base_depth
    if math.isfinite(base_depth):
        water_level=float(field.z_m[r,c])+base_depth
        d=max(0.0,water_level-overlay.node_floor_z[state])
        return (0,0.0) if d<=1e-6 else (q,d)
    return q,math.nan


def _allowed(state,graph,overlay,field,profile,bridge_policy,min_clearance):
    if state>=0:
        clr=_state_clearance(state,overlay)
        if math.isfinite(clr) and clr+1e-6<min_clearance: return False
    q,depth=_water_for_state(state,graph,overlay,field)
    deep=q!=0 and (not math.isfinite(depth) or depth>=float(profile['deep_water_depth_m']))
    if deep and bridge_policy=='forbid': return False
    return True


def _factor_for_destination(state,cell,grade,graph,overlay,field,roads,band,profile,bridge_policy):
    r,c=divmod(cell,graph.width)
    factor=1.0
    # Road preference is handled by the route-aware edge model in solve_surface_graph().
    soft=float(profile['grade_soft_start'])
    if grade>soft: factor*=1.0+float(profile['grade_penalty'])*(grade-soft)**2
    q,depth=_water_for_state(state,graph,overlay,field)
    if q!=0:
        deep=not math.isfinite(depth) or depth>=float(profile['deep_water_depth_m'])
        factor*=float(profile['deep_water_penalty'] if deep else profile['shallow_water_penalty'])
    if state<0 and int(field.prov[r,c]) in PROV_CLIFF_VALUES:
        factor*=float(profile['cliff_penalty'])
    return factor



_DIR8 = (
    (-1, 0), (-1, 1), (0, 1), (1, 1),
    (1, 0), (1, -1), (0, -1), (-1, -1),
)
_START_DIR = 8


def _direction_bin(cell_a: int, cell_b: int, width: int, incoming_dir: int) -> int:
    ra, ca = divmod(cell_a, width)
    rb, cb = divmod(cell_b, width)
    dr = 0 if rb == ra else (1 if rb > ra else -1)
    dc = 0 if cb == ca else (1 if cb > ca else -1)
    if dr == 0 and dc == 0:
        return incoming_dir
    return _DIR8.index((dr, dc))


def _turn_steps(incoming_dir: int, outgoing_dir: int) -> int:
    if incoming_dir == _START_DIR or outgoing_dir == _START_DIR:
        return 0
    d = abs(int(outgoing_dir) - int(incoming_dir)) % 8
    return min(d, 8 - d)


def _road_edge_class(r0, c0, r1, c1, roads, band) -> str:
    road0, road1 = bool(roads[r0, c0]), bool(roads[r1, c1])
    band0, band1 = bool(band[r0, c0]), bool(band[r1, c1])
    if road0 and road1:
        return "road_continuation"
    if (road0 or band0) and (road1 or band1):
        return "band_continuation"
    if road0 or road1 or band0 or band1:
        return "road_transition"
    return "offroad"



def _base_cell_direction_sensitive(cell: int, graph, overlay, roads, band) -> bool:
    """Return True when arrival heading can affect future cost at a base cell.

    Heading is retained only where route-aware evidence exists:
      * SCIM road / road-band continuation
      * a base<->explicit-surface portal

    Ordinary off-road base terrain collapses to one canonical search state.
    """
    r, c = divmod(cell, graph.width)
    return bool(
        roads[r, c]
        or band[r, c]
        or cell in overlay.base_to_node
    )


def _direction_sensitive(state: int, graph, overlay, roads, band) -> bool:
    # Explicit graph surfaces always keep heading because graph/seam transitions are
    # precisely where continuity evidence matters.
    if state >= 0:
        return True
    return _base_cell_direction_sensitive(
        _state_cell(state, graph), graph, overlay, roads, band
    )


def _canonical_direction(
    state: int,
    proposed_dir: int,
    graph,
    overlay,
    roads,
    band,
) -> int:
    """Collapse ordinary off-road base terrain to the START heading."""
    if _direction_sensitive(state, graph, overlay, roads, band):
        return int(proposed_dir)
    return _START_DIR


def _road_factor_for_edge(
    road_class: str,
    turn_steps: int,
    *,
    road_straight_factor: float,
    road_turn_factor: float,
    band_continuation_factor: float,
    road_transition_factor: float,
) -> float:
    if road_class == "road_continuation":
        # 0/45-degree continuation gets the strongest evidence weight.
        return road_straight_factor if turn_steps <= 1 else road_turn_factor
    if road_class == "band_continuation":
        return band_continuation_factor
    if road_class == "road_transition":
        return road_transition_factor
    return 1.0


def _turn_penalty_m(turn_steps: int) -> float:
    # At 2 m XY, 45-degree stair-stepping is common raster noise.
    return (0.0, 0.05, 0.50, 2.0, 8.0)[max(0, min(4, int(turn_steps)))]


def _dynamic_seam_penalty(
    relation: int,
    *,
    road_class: str,
    grade: float,
    turn_steps: int,
    base_component_seam_penalty_m: float,
    cross_component_seam_penalty_m: float,
    ambiguous_component_seam_penalty_m: float,
) -> float:
    if relation == 1:
        penalty = float(base_component_seam_penalty_m)
    elif relation == 2:
        penalty = float(cross_component_seam_penalty_m)
    elif relation == 3:
        penalty = float(ambiguous_component_seam_penalty_m)
    else:
        return 0.0

    # Independent SCIM road continuity is strong evidence that the seam is real.
    if road_class == "road_continuation":
        penalty *= 0.20
    elif road_class == "band_continuation":
        penalty *= 0.50
    elif road_class == "road_transition":
        penalty *= 0.80

    # Small local dz is stronger continuity evidence.
    if grade <= 0.25:
        penalty *= 0.50
    elif grade > 0.75:
        penalty *= 1.50

    # A seam requiring a sharp turn is less convincing.
    if turn_steps >= 3:
        penalty *= 1.75
    elif turn_steps == 2:
        penalty *= 1.25

    return penalty


def _endpoint_candidates(anchor,graph,overlay,field,profile,bridge_policy,min_clearance,radius_m):
    ar,ac=field.world_to_rc(*anchor); anchor_z=float(field.z_m[ar,ac]) if 0<=ar<field.shape[0] and 0<=ac<field.shape[1] and np.isfinite(field.z_m[ar,ac]) else 0.0
    rad=max(0,int(math.ceil(radius_m/field.step_m)))
    out=[]
    for r in range(max(overlay.rmin,ar-rad),min(overlay.rmin+overlay.rows,ar+rad+1)):
        for c in range(max(overlay.cmin,ac-rad),min(overlay.cmin+overlay.cols,ac+rad+1)):
            east,north=field.rc_to_world(r,c); conn=math.hypot(east-anchor[0],north-anchor[1])
            if conn>radius_m+1e-6: continue
            cell=r*graph.width+c
            states=[]
            if np.isfinite(field.z_m[r,c]):
                states.append(-(cell+1))
            if overlay.is_exception_local(r,c):
                states.extend(graph.nodes_for_cell(cell).tolist())
            for state in states:
                if state>=0 and state not in overlay.node_floor_z: continue
                if not _allowed(state,graph,overlay,field,profile,bridge_policy,min_clearance): continue
                z=_state_z(state,graph,overlay,field); vg=abs(z-anchor_z)/conn if conn>1e-6 else 0.0
                if vg>float(profile['grade_hard_block'])+1e-9: continue
                out.append({'state':int(state),'connector_m':float(conn),'east_m':east,'north_m':north,'z_m':z,'vertical_delta_m':z-anchor_z,'direct_grade_pct':vg*100,'state_type':'surface' if state>=0 else 'base'})
    out.sort(key=lambda x:(x['connector_m'],abs(x['vertical_delta_m'])))
    return out


def solve_surface_graph(
    field:WorkingField, origin, destination, profile, *, surface_graph_dir, intervals_path=None,
    road_prior_path=None, bridge_policy='forbid', corridor_pad_m=800.0,
    minimum_clearance_m=None, endpoint_access_radius_m=200.0,
    base_component_seam_penalty_m=0.50,
    cross_component_seam_penalty_m=2.0,
    ambiguous_component_seam_penalty_m=4.0,
    road_straight_factor=ROUTING_TUNING["road_straight_factor"],
    road_turn_factor=ROUTING_TUNING["road_turn_factor"],
    band_continuation_factor=ROUTING_TUNING["band_continuation_factor"],
    road_transition_factor=ROUTING_TUNING["road_transition_factor"],
    max_complete_stretch=2.25,
    corridor_bounds_m=None,
    destination_mode="exact",
    access_endpoint_radius_m=ROUTING_TUNING["access_endpoint_radius_m"],
):
    graph=_cached_surface_graph(
        str(Path(surface_graph_dir).resolve()),
        None if intervals_path is None else str(Path(intervals_path).resolve()),
    )
    if abs(field.step_m-graph.step_m)>1e-6 or field.shape!=(graph.height,graph.width):
        raise ValueError(
            f'WorkingField must match surface graph grid exactly; '
            f'field step/shape={field.step_m}/{field.shape}, '
            f'graph={graph.step_m}/{(graph.height,graph.width)}'
        )
    if abs(field.east0_m-graph.east0_m)>1e-6 or abs(field.north0_m-graph.north0_m)>1e-6:
        raise ValueError('WorkingField and surface graph origins do not match')

    profile=dict(profile)
    min_clearance=float(
        _mode_default_clearance(profile)
        if minimum_clearance_m is None else minimum_clearance_m
    )
    roads,band=_resample_prior(road_prior_path,field)
    destination_mode=str(destination_mode).lower().strip()
    if destination_mode not in ("exact","access"):
        raise ValueError(
            f"destination_mode must be 'exact' or 'access'; got {destination_mode!r}"
        )
    sr,sc=field.world_to_rc(*origin)
    gr,gc=field.world_to_rc(*destination)

    if corridor_bounds_m is None:
        pad=max(10,int(math.ceil(corridor_pad_m/field.step_m)))
        rmin=max(0,min(sr,gr)-pad)
        rmax=min(field.shape[0],max(sr,gr)+pad+1)
        cmin=max(0,min(sc,gc)-pad)
        cmax=min(field.shape[1],max(sc,gc)+pad+1)
        corridor_source='anchor_bbox_pad'
        corridor_bounds_used_m=None
    else:
        west,south,east,north=(float(v) for v in corridor_bounds_m)
        if east < west or north < south:
            raise ValueError(
                f'invalid corridor_bounds_m={corridor_bounds_m}; '
                'expected [west,south,east,north]'
            )
        # Convert world bounds to inclusive grid bounds. Expand by one cell to
        # avoid numerical clipping at the requested envelope.
        c0=int(math.floor((west-field.east0_m)/field.step_m))-1
        c1=int(math.ceil((east-field.east0_m)/field.step_m))+1
        r0=int(math.floor((field.north0_m-north)/field.step_m))-1
        r1=int(math.ceil((field.north0_m-south)/field.step_m))+1
        rmin=max(0,min(r0,r1))
        rmax=min(field.shape[0],max(r0,r1)+1)
        cmin=max(0,min(c0,c1))
        cmax=min(field.shape[1],max(c0,c1)+1)
        # Always include the exact endpoint cells even if the coarse topology
        # envelope was generated from snapped topology centroids.
        rmin=max(0,min(rmin,sr,gr))
        rmax=min(field.shape[0],max(rmax,sr+1,gr+1))
        cmin=max(0,min(cmin,sc,gc))
        cmax=min(field.shape[1],max(cmax,sc+1,gc+1))
        corridor_source='topology_path_bbox'
        corridor_bounds_used_m=[west,south,east,north]
    overlay=graph.corridor(rmin,rmax,cmin,cmax)

    starts=_endpoint_candidates(
        origin,graph,overlay,field,profile,bridge_policy,min_clearance,
        endpoint_access_radius_m
    )
    goals=_endpoint_candidates(
        destination,graph,overlay,field,profile,bridge_policy,min_clearance,
        endpoint_access_radius_m
    )
    if not starts:
        raise RuntimeError('origin has no usable graph/base portal within endpoint radius')
    if not goals:
        raise RuntimeError('destination has no usable graph/base portal within endpoint radius')

    goalmap={x['state']:x for x in goals}
    startmap={x['state']:x for x in starts}
    hard=float(profile['grade_hard_block'])
    direct_anchor_m=math.hypot(
        float(destination[0])-float(origin[0]),
        float(destination[1])-float(origin[1]),
    )
    stretch_limit_m=max(
        direct_anchor_m,
        direct_anchor_m*float(max_complete_stretch),
    )

    # Hybrid heading state: road/band/portal/explicit states retain 8-way arrival heading; ordinary off-road base cells collapse to START=8.
    dist={}
    physical_len={}
    prev={}
    prev_edge={}
    pq=[]

    # Lowest possible per-meter factor keeps the A* heuristic admissible.
    hfactor=min(
        1.0,
        float(road_straight_factor),
        float(road_turn_factor),
        float(band_continuation_factor),
        float(road_transition_factor),
    )

    for s in starts:
        raw_state=int(s['state'])
        key=(raw_state,_START_DIR)
        gcost=float(s['connector_m'])
        if gcost+1e-9 >= dist.get(key,math.inf):
            continue
        dist[key]=gcost
        physical_len[key]=float(s['connector_m'])
        cell=_state_cell(raw_state,graph)
        r,c=divmod(cell,graph.width)
        h=math.hypot(r-gr,c-gc)*field.step_m*hfactor
        heapq.heappush(pq,(gcost+h,gcost,key))

    reached_key=None
    best=math.inf
    best_access=None
    access_max_bonus=max(
        float(ROUTING_TUNING["access_road_bonus_m"]),
        float(ROUTING_TUNING["access_road_band_bonus_m"]),
    )
    dirs=_DIR8

    while pq:
        f,gcost,key=heapq.heappop(pq)
        if abs(gcost-dist.get(key,math.inf))>1e-9:
            continue
        if f>=best-1e-9:
            break

        state,incoming_dir=key
        cell=_state_cell(state,graph)
        r,c=divmod(cell,graph.width)

        if destination_mode=="exact":
            if state in goalmap:
                total=gcost+float(goalmap[state]['connector_m'])
                if total<best:
                    best=total
                    reached_key=key
                continue
        else:
            east_here,north_here=field.rc_to_world(r,c)
            anchor_gap=math.hypot(
                float(east_here)-float(destination[0]),
                float(north_here)-float(destination[1]),
            )
            if anchor_gap<=float(access_endpoint_radius_m)+1e-9:
                on_road=bool(roads[r,c])
                in_band=bool(band[r,c])
                if on_road or in_band:
                    bonus=(
                        float(ROUTING_TUNING["access_road_bonus_m"])
                        if on_road
                        else float(ROUTING_TUNING["access_road_band_bonus_m"])
                    )
                    access_score=(
                        float(gcost)
                        +float(anchor_gap)*float(ROUTING_TUNING["access_gap_factor"])
                        -bonus
                    )
                    candidate={
                        "key":key,
                        "score":float(access_score),
                        "anchor_gap_m":float(anchor_gap),
                        "on_road":on_road,
                        "in_road_band":in_band,
                        "east_m":float(east_here),
                        "north_m":float(north_here),
                    }
                    if best_access is None or (
                        candidate["score"],
                        candidate["anchor_gap_m"],
                        candidate["key"],
                    ) < (
                        best_access["score"],
                        best_access["anchor_gap_m"],
                        best_access["key"],
                    ):
                        best_access=candidate
                        best=float(candidate["score"]+access_max_bonus)

            # f is an admissible lower bound before the possible road bonus.
            if (
                best_access is not None
                and f-access_max_bonus>best_access["score"]+1e-9
            ):
                reached_key=best_access["key"]
                break

        nbrs=[]

        if state<0:
            z0=float(field.z_m[r,c])
            for dr,dc in dirs:
                nr,nc=r+dr,c+dc
                if nr<rmin or nr>=rmax or nc<cmin or nc>=cmax:
                    continue
                if not np.isfinite(field.z_m[nr,nc]):
                    continue
                ncell=nr*graph.width+nc
                ns=-(ncell+1)
                horiz=field.step_m*(math.sqrt(2) if dr and dc else 1.0)
                grade=abs(float(field.z_m[nr,nc])-z0)/horiz
                nbrs.append((ns,horiz,grade,-1))
            for ns,dd,gg,reln in overlay.base_to_node.get(cell,[]):
                nbrs.append((ns,dd,gg,reln))
        else:
            for ns,dd,gg,_clr,reln in overlay.explicit_adj.get(state,[]):
                nbrs.append((ns,dd,gg,reln))
            for ncell,dd,gg,reln in overlay.node_to_base.get(state,[]):
                nbrs.append((-(ncell+1),dd,gg,reln))

        for ns,horiz,grade,reln in nbrs:
            if grade>hard+1e-9:
                continue
            if not _allowed(
                ns,graph,overlay,field,profile,bridge_policy,min_clearance
            ):
                continue

            ncell=_state_cell(ns,graph)
            nr,nc=divmod(ncell,graph.width)
            geometric_outgoing_dir=_direction_bin(
                cell,ncell,graph.width,incoming_dir
            )
            turn_steps=_turn_steps(incoming_dir,geometric_outgoing_dir)
            road_class=_road_edge_class(r,c,nr,nc,roads,band)
            road_factor=_road_factor_for_edge(
                road_class,turn_steps,
                road_straight_factor=float(road_straight_factor),
                road_turn_factor=float(road_turn_factor),
                band_continuation_factor=float(band_continuation_factor),
                road_transition_factor=float(road_transition_factor),
            )
            terrain_factor=_factor_for_destination(
                ns,ncell,grade,graph,overlay,field,roads,band,profile,bridge_policy
            )
            turn_penalty=_turn_penalty_m(turn_steps)
            seam_penalty=_dynamic_seam_penalty(
                int(reln),
                road_class=road_class,
                grade=float(grade),
                turn_steps=turn_steps,
                base_component_seam_penalty_m=base_component_seam_penalty_m,
                cross_component_seam_penalty_m=cross_component_seam_penalty_m,
                ambiguous_component_seam_penalty_m=ambiguous_component_seam_penalty_m,
            )

            edge_cost=(
                float(horiz)*road_factor*terrain_factor
                +turn_penalty
                +seam_penalty
            )
            ng=gcost+edge_cost

            next_heading=_canonical_direction(
                int(ns),
                int(geometric_outgoing_dir),
                graph,overlay,roads,band,
            )
            nkey=(int(ns),int(next_heading))

            if ng+1e-9<dist.get(nkey,math.inf):
                dist[nkey]=ng
                physical_len[nkey]=physical_len[key]+float(horiz)
                prev[nkey]=key
                prev_edge[nkey]={
                    'relation':int(reln),
                    'incoming_dir':int(incoming_dir),
                    'outgoing_dir':int(geometric_outgoing_dir),
                    'turn_steps':int(turn_steps),
                    'road_class':road_class,
                    'road_factor':float(road_factor),
                    'terrain_factor':float(terrain_factor),
                    'turn_penalty_m':float(turn_penalty),
                    'seam_penalty_m':float(seam_penalty),
                    'edge_cost':float(edge_cost),
                }
                h=math.hypot(nr-gr,nc-gc)*field.step_m*hfactor
                heapq.heappush(pq,(ng+h,ng,nkey))

    if destination_mode=="access" and reached_key is None and best_access is not None:
        reached_key=best_access["key"]

    # The stretch guardrail is diagnostic only. Hard-rejecting complete routes
    # proved incorrect for legitimate terrain detours around cliffs/canyons.
    selected_complete_physical_m=(
        physical_len.get(reached_key,math.inf)+float(goalmap[reached_key[0]]['connector_m'])
        if (destination_mode=="exact" and reached_key is not None) else math.inf
    )
    stretch_rejected=False
    stretch_exceeded=(
        destination_mode=="exact"
        and reached_key is not None
        and selected_complete_physical_m>stretch_limit_m+1e-6
    )

    partial_route=False
    access_endpoint=(destination_mode=="access" and reached_key is not None)
    remaining_gap_m=0.0
    closest_goal_state=None
    reachable_state_count=len(dist)

    if reached_key is None:
        if not dist:
            raise RuntimeError(
                'No states reachable from origin under current constraints'
            )

        # Prefer the closest reachable state. Stretch is no longer a hard
        # feasibility gate; topology-guided corridor bounds constrain the search.
        candidates=list(dist.items())

        best_key=None
        best_rank=None
        for candidate_key,cost in candidates:
            state=candidate_key[0]
            east,north=_state_world(state,graph,field)
            anchor_gap=math.hypot(
                float(east)-float(destination[0]),
                float(north)-float(destination[1]),
            )
            rank=(anchor_gap,float(cost))
            if best_rank is None or rank<best_rank:
                best_rank=rank
                best_key=candidate_key

        if best_key is None:
            raise RuntimeError('Search produced no usable partial endpoint')

        reached_key=best_key
        partial_route=True
        reached_state=reached_key[0]
        pe,pn=_state_world(reached_state,graph,field)

        nearest_gap=math.inf
        for goal in goals:
            gap=math.hypot(
                float(pe)-float(goal['east_m']),
                float(pn)-float(goal['north_m']),
            )
            if gap<nearest_gap:
                nearest_gap=gap
                closest_goal_state=int(goal['state'])
        remaining_gap_m=float(nearest_gap)

    # Reconstruct heading-aware state path.
    key_path=[]
    cur=reached_key
    while True:
        key_path.append(cur)
        if cur not in prev:
            break
        cur=prev[cur]
    key_path.reverse()
    path=[k[0] for k in key_path]

    origin_portal=startmap[path[0]]

    if partial_route or access_endpoint:
        reached_state=path[-1]
        pr,pc=_state_rc(reached_state,graph)
        pe,pn=field.rc_to_world(pr,pc)
        pz=_state_z(reached_state,graph,overlay,field)
        destination_portal={
            'state':int(reached_state),
            'connector_m':0.0,
            'east_m':float(pe),
            'north_m':float(pn),
            'z_m':float(pz),
            'vertical_delta_m':0.0,
            'direct_grade_pct':0.0,
            'state_type':'surface_graph' if reached_state>=0 else 'base',
        }
        closest_destination_candidate=(
            goalmap.get(closest_goal_state)
            if closest_goal_state is not None else None
        )
    else:
        reached_state=path[-1]
        destination_portal=goalmap[reached_state]
        closest_destination_candidate=destination_portal

    rec=[]
    cum=0.0
    prevxyz=None
    graph_edges=0
    portal_transitions=0
    total_turn_penalty=0.0
    total_seam_penalty=0.0

    for i,(key,state) in enumerate(zip(key_path,path)):
        cell=_state_cell(state,graph)
        r,c=divmod(cell,graph.width)
        e,n=field.rc_to_world(r,c)
        z=_state_z(state,graph,overlay,field)

        if prevxyz is None:
            seg=grade=0.0
            emeta={
                'relation':-1,'incoming_dir':_START_DIR,
                'outgoing_dir':key[1],'turn_steps':0,
                'road_class':'start','road_factor':1.0,
                'terrain_factor':1.0,'turn_penalty_m':0.0,
                'seam_penalty_m':0.0,'edge_cost':0.0,
            }
        else:
            seg=math.hypot(e-prevxyz[0],n-prevxyz[1])
            grade=abs(z-prevxyz[2])/seg if seg else 0.0
            cum+=seg
            emeta=prev_edge[key]
            total_turn_penalty+=float(emeta['turn_penalty_m'])
            total_seam_penalty+=float(emeta['seam_penalty_m'])
            if (state>=0)!=(path[i-1]>=0):
                portal_transitions+=1
            if state>=0 and path[i-1]>=0:
                graph_edges+=1

        q,depth=_water_for_state(state,graph,overlay,field)
        comp=overlay.node_component.get(state,0) if state>=0 else 0

        rec.append({
            'point_order':i,
            'state_type':'surface_graph' if state>=0 else 'base',
            'surface_node_id':state if state>=0 else np.nan,
            'surface_component_id':int(comp),
            'incoming_component_relation':int(emeta['relation']),
            'incoming_direction_bin':int(emeta['incoming_dir']),
            'outgoing_direction_bin':int(emeta['outgoing_dir']),
            'turn_steps_45deg':int(emeta['turn_steps']),
            'heading_sensitive_state':bool(
                _direction_sensitive(state,graph,overlay,roads,band)
            ),
            'edge_road_class':emeta['road_class'],
            'edge_road_factor':float(emeta['road_factor']),
            'edge_terrain_factor':float(emeta['terrain_factor']),
            'edge_turn_penalty_m':float(emeta['turn_penalty_m']),
            'edge_seam_penalty_m':float(emeta['seam_penalty_m']),
            'edge_weighted_cost':float(emeta['edge_cost']),
            'east_m':e,'north_m':n,'elevation_m':z,
            'surface_clearance_m':_state_clearance(state,overlay),
            'segment_distance_m':seg,
            'cumulative_distance_m':cum,
            'routing_grade_pct':grade*100,
            'water_quality':q,
            'water_depth_m':depth if math.isfinite(depth) else np.nan,
            'terrain_provenance':int(field.prov[r,c]),
            'on_road':bool(roads[r,c]),
            'in_road_band':bool(band[r,c]),
        })
        prevxyz=(e,n,z)

    route=pd.DataFrame(rec)
    finite_clear=route.surface_clearance_m.replace(
        [np.inf,-np.inf],np.nan
    ).dropna()
    min_observed=float(finite_clear.min()) if len(finite_clear) else math.inf

    validation=pd.DataFrame([
        {
            'check':'hard_grade',
            'status':'PASS' if route.routing_grade_pct.max()<=hard*100+1e-6 else 'FAIL',
            'value':float(route.routing_grade_pct.max()),
            'limit':hard*100,
        },
        {
            'check':'surface_clearance',
            'status':'PASS' if min_observed+1e-6>=min_clearance else 'FAIL',
            'value':min_observed,
            'limit':min_clearance,
        },
        {
            'check':'complete_route_stretch',
            'status':(
                'N/A' if (partial_route or access_endpoint)
                else ('WARN' if stretch_exceeded else 'PASS')
            ),
            'value':(
                float(
                    route.cumulative_distance_m.iloc[-1]
                    +origin_portal['connector_m']
                    +destination_portal['connector_m']
                )/direct_anchor_m
                if (not partial_route and not access_endpoint and direct_anchor_m>1e-6) else np.nan
            ),
            'limit':float(max_complete_stretch),
        },
    ])

    relation_counts={
        'same_component':int((route.incoming_component_relation==0).sum()),
        'base_component_seam':int((route.incoming_component_relation==1).sum()),
        'cross_component_seam':int((route.incoming_component_relation==2).sum()),
        'ambiguous_component_seam':int((route.incoming_component_relation==3).sum()),
    }

    origin_anchor_z=(
        float(field.z_m[sr,sc]) if np.isfinite(field.z_m[sr,sc]) else math.nan
    )
    destination_anchor_z=(
        float(field.z_m[gr,gc]) if np.isfinite(field.z_m[gr,gc]) else math.nan
    )

    regional_len=float(route.cumulative_distance_m.iloc[-1])
    complete_accounted=(
        regional_len+float(origin_portal['connector_m'])+float(destination_portal['connector_m'])
        if (not partial_route and not access_endpoint) else None
    )
    partial_accounted=(
        regional_len+float(origin_portal['connector_m'])
        if partial_route else None
    )
    access_accounted=(
        regional_len+float(origin_portal['connector_m'])
        if access_endpoint else None
    )

    summary={
        'route_length_m':regional_len,
        'regional_route_length_m':regional_len,
        'search_cost':float(dist[reached_key]+(
            destination_portal.get('connector_m',0.0) if not partial_route else 0.0
        )),
        'point_count':len(route),
        'road_fraction':float(route.on_road.mean()),
        'road_band_fraction':float(route.in_road_band.mean()),
        'water_fraction':float((route.water_quality!=0).mean()),
        'max_routing_grade_pct':float(route.routing_grade_pct.max()),
        'bridge_policy':bridge_policy,
        'surface_graph_dir':str(surface_graph_dir),
        'implicit_base_policy':'composed_heightfield_everywhere',
        'routing_state_model':'hybrid_heading_sensitive_state',
        'route_aware_weights':{
            'road_straight_factor':float(road_straight_factor),
            'road_turn_factor':float(road_turn_factor),
            'band_continuation_factor':float(band_continuation_factor),
            'road_transition_factor':float(road_transition_factor),
            'turn_penalty_m_by_45deg_steps':[0.0,0.05,0.50,2.0,8.0],
            'base_component_seam_penalty_m':float(base_component_seam_penalty_m),
            'cross_component_seam_penalty_m':float(cross_component_seam_penalty_m),
            'ambiguous_component_seam_penalty_m':float(ambiguous_component_seam_penalty_m),
            'max_complete_stretch':float(max_complete_stretch),
        },
        'destination_mode':destination_mode,
        'access_endpoint_radius_m':float(access_endpoint_radius_m),
        'access_endpoint_score':(
            float(best_access["score"]) if best_access is not None else None
        ),
        'access_endpoint_on_road':(
            bool(best_access["on_road"]) if best_access is not None else None
        ),
        'access_endpoint_in_road_band':(
            bool(best_access["in_road_band"]) if best_access is not None else None
        ),
        'turn_penalty_cost_m':float(total_turn_penalty),
        'component_seam_penalty_cost_m':float(total_seam_penalty),
        'surface_graph_fraction':float((route.state_type=='surface_graph').mean()),
        'surface_graph_edge_count':graph_edges,
        'surface_graph_portal_transitions':portal_transitions,
        'component_relation_counts':relation_counts,
        'surface_component_switches':int(
            (
                (route.surface_component_id!=route.surface_component_id.shift(1))
                &(route.state_type=='surface_graph')
                &(route.state_type.shift(1)=='surface_graph')
            ).sum()
        ),
        'minimum_clearance_m':min_clearance,
        'endpoint_access_radius_m':endpoint_access_radius_m,
        'corridor_source':corridor_source,
        'corridor_bounds_used_m':corridor_bounds_used_m,
        'corridor_grid_bounds':{
            'rmin':int(rmin),'rmax':int(rmax),
            'cmin':int(cmin),'cmax':int(cmax),
        },
        'origin_portal_candidates':len(starts),
        'destination_portal_candidates':len(goals),
        'reachable_search_states':int(reachable_state_count),
        'route_heading_sensitive_fraction':float(
            route.heading_sensitive_state.mean()
        ),
        'route_heading_sensitive_points':int(
            route.heading_sensitive_state.sum()
        ),
        'origin_anchor':{
            'east_m':float(origin[0]),'north_m':float(origin[1]),'z_m':origin_anchor_z
        },
        'destination_anchor':{
            'east_m':float(destination[0]),'north_m':float(destination[1]),'z_m':destination_anchor_z
        },
        'origin_portal':{k:v for k,v in origin_portal.items() if k!='state'},
        'destination_portal':{k:v for k,v in destination_portal.items() if k!='state'},
        'closest_destination_candidate':(
            {k:v for k,v in closest_destination_candidate.items() if k!='state'}
            if closest_destination_candidate is not None else None
        ),
        'local_connector_total_m':float(
            origin_portal['connector_m']
            +(destination_portal['connector_m'] if not partial_route else 0.0)
        ),
        'anchor_to_anchor_accounted_length_m':(
            float(complete_accounted) if complete_accounted is not None else None
        ),
        'partial_accounted_length_m':(
            float(partial_accounted) if partial_accounted is not None else None
        ),
        'access_accounted_length_m':(
            float(access_accounted) if access_accounted is not None else None
        ),
        'direct_anchor_distance_m':float(direct_anchor_m),
        'accounted_stretch_ratio':(
            float(complete_accounted/direct_anchor_m)
            if complete_accounted is not None and direct_anchor_m>1e-6 else None
        ),
        'stretch_guardrail_rejected_complete':bool(stretch_rejected),
        'stretch_guardrail_exceeded_complete':bool(stretch_exceeded),
        'stretch_guardrail_mode':'diagnostic_only',
        'valid_under_profile':not (validation.status=='FAIL').any(),
        'route_status':(
            'PARTIAL' if partial_route
            else ('ACCESS_ENDPOINT' if access_endpoint else 'COMPLETE')
        ),
        'destination_reached':(
            False if (partial_route or access_endpoint) else True
        ),
        'access_endpoint_reached':bool(access_endpoint),
        'remaining_plan_gap_m':(
            float(remaining_gap_m) if partial_route
            else (
                float(math.hypot(
                    float(destination[0])-float(destination_portal['east_m']),
                    float(destination[1])-float(destination_portal['north_m']),
                ))
                if access_endpoint else 0.0
            )
        ),
        'remaining_anchor_gap_m':(
            float(math.hypot(
                float(destination[0])-float(destination_portal['east_m']),
                float(destination[1])-float(destination_portal['north_m']),
            ))
            if (partial_route or access_endpoint) else 0.0
        ),
        'closest_destination_candidate_state':(
            int(closest_goal_state) if closest_goal_state is not None else None
        ),
    }
    return SolveResult(route,validation,summary)

def write_result(result:SolveResult,out_dir):
    import json
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    result.route.to_csv(out/'route_points.csv',index=False)
    result.validation.to_csv(out/'route_validation.csv',index=False)
    (out/'route_summary.json').write_text(json.dumps(result.summary,indent=2),encoding='utf-8')
