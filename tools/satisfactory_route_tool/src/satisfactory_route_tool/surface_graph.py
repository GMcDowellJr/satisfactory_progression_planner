from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from collections import defaultdict
import numpy as np


@dataclass
class CorridorOverlay:
    node_floor_z: dict[int, float]
    node_clearance: dict[int, float]
    node_component: dict[int, int]
    explicit_adj: dict[int, list[tuple[int, float, float, float, int]]]
    node_to_base: dict[int, list[tuple[int, float, float, int]]]
    base_to_node: dict[int, list[tuple[int, float, float, int]]]
    exception_mask: np.ndarray
    rmin: int
    cmin: int
    rows: int
    cols: int
    graph_step_m: float
    graph_width: int

    def is_exception_local(self, r: int, c: int) -> bool:
        rr=r-self.rmin; cc=c-self.cmin
        return 0 <= rr < self.rows and 0 <= cc < self.cols and bool(self.exception_mask[rr,cc])


class SurfaceGraphData:
    """Loader for the hybrid surface graph + vertical interval node table."""

    def __init__(self, graph_dir: str | Path, intervals_path: str | Path | None = None):
        self.graph_dir=Path(graph_dir)
        self.meta=json.loads((self.graph_dir/'meta.json').read_text(encoding='utf-8'))
        g=self.meta['grid']
        self.step_m=float(g['step_m']); self.width=int(g['width']); self.height=int(g['height'])
        self.east0_m=float(g['east0_m']); self.north0_m=float(g['north0_m'])
        if intervals_path is None:
            candidate=self.graph_dir.parent/'multisurface'/'vertical_intervals.npz'
            if candidate.exists(): intervals_path=candidate
            else:
                p=Path(self.meta.get('source_intervals',''))
                intervals_path=p if p.exists() else None
        if intervals_path is None:
            raise FileNotFoundError('vertical_intervals.npz not found; pass intervals_path explicitly')
        self.intervals_path=Path(intervals_path)
        with np.load(self.intervals_path) as d:
            self.cells=np.asarray(d['cell_index'],dtype=np.int64)
            self.offsets=np.asarray(d['interval_offsets'],dtype=np.int64)
            self.floor_z=np.asarray(d['floor_z_m'],dtype=np.float32)
            self.clearance=np.asarray(d['clearance_m'],dtype=np.float32)
            self.floor_component=(
                np.asarray(d['floor_component_id'],dtype=np.int32)
                if 'floor_component_id' in d
                else np.full(len(self.floor_z),-1,np.int32)
            )
        if len(self.offsets)!=len(self.cells)+1:
            raise ValueError('interval_offsets length mismatch')
        if int(self.offsets[-1])!=len(self.floor_z):
            raise ValueError('node count mismatch')

    def world_to_rc(self,east:float,north:float):
        c=int(round((east-self.east0_m)/self.step_m))
        r=int(round((self.north0_m-north)/self.step_m))
        return r,c

    def rc_to_cell(self,r:int,c:int)->int:
        return r*self.width+c

    def cell_to_rc(self,cell:int):
        return divmod(int(cell),self.width)

    def cell_to_world(self,cell:int):
        r,c=self.cell_to_rc(cell)
        return self.east0_m+c*self.step_m, self.north0_m-r*self.step_m

    def column_pos(self,cell:int)->int|None:
        i=int(np.searchsorted(self.cells,np.int64(cell)))
        if i>=len(self.cells) or int(self.cells[i])!=int(cell): return None
        return i

    def nodes_for_cell(self,cell:int)->np.ndarray:
        i=self.column_pos(cell)
        if i is None: return np.empty(0,dtype=np.int64)
        return np.arange(int(self.offsets[i]),int(self.offsets[i+1]),dtype=np.int64)

    @staticmethod
    def _bbox_intersects(bbox, rmin,rmax,cmin,cmax):
        if not bbox: return True
        a,b,c,d=map(int,bbox)
        return not (b < rmin or a >= rmax or d < cmin or c >= cmax)

    def _node_cell(self,node_ids:np.ndarray)->np.ndarray:
        # interval offsets are monotonic: locate owning sparse column then map to global cell.
        pos=np.searchsorted(self.offsets,node_ids,side='right')-1
        return self.cells[pos]

    def corridor(self,rmin:int,rmax:int,cmin:int,cmax:int)->CorridorOverlay:
        rows=max(0,rmax-rmin); cols=max(0,cmax-cmin)
        mask=np.zeros((rows,cols),dtype=bool)
        cr=self.cells//self.width; cc=self.cells%self.width
        inside=(cr>=rmin)&(cr<rmax)&(cc>=cmin)&(cc<cmax)
        sparse_pos=np.flatnonzero(inside)
        if len(sparse_pos):
            mask[(cr[sparse_pos]-rmin).astype(int),(cc[sparse_pos]-cmin).astype(int)]=True

        node_floor_z={}; node_clearance={}; node_component={}
        for p in sparse_pos.tolist():
            a,b=int(self.offsets[p]),int(self.offsets[p+1])
            for n in range(a,b):
                node_floor_z[n]=float(self.floor_z[n])
                node_clearance[n]=float(self.clearance[n])
                node_component[n]=int(self.floor_component[n])

        explicit_adj=defaultdict(list)
        node_to_base=defaultdict(list)
        base_to_node=defaultdict(list)

        directions=list(self.meta.get('directions',[]))
        portal_dirs=list(self.meta.get('portal_directions',[]))
        if not portal_dirs:
            # graph schema v1 fallback stored portal shards on the direction records.
            portal_dirs=directions

        for rec in directions:
            for shard in rec.get('edge_shards',[]):
                if not self._bbox_intersects(shard.get('bbox_rc'),rmin,rmax,cmin,cmax): continue
                with np.load(self.graph_dir/shard['file']) as d:
                    u=np.asarray(d['u'],dtype=np.int64); v=np.asarray(d['v'],dtype=np.int64)
                    dist=np.asarray(d['distance_m'],dtype=np.float32); grade=np.asarray(d['grade'],dtype=np.float32)
                    clr=np.asarray(d['min_known_clearance_m'],dtype=np.float32)
                    rel=(
                        np.asarray(d['component_relation'],dtype=np.uint8)
                        if 'component_relation' in d else np.full(len(u),3,np.uint8)
                    )
                    uc=self._node_cell(u); vc=self._node_cell(v)
                    ur,ucol=uc//self.width,uc%self.width; vr,vcol=vc//self.width,vc%self.width
                    keep=(ur>=rmin)&(ur<rmax)&(ucol>=cmin)&(ucol<cmax)&(vr>=rmin)&(vr<rmax)&(vcol>=cmin)&(vcol<cmax)
                    for uu,vv,dd,gg,cl,reln in zip(u[keep],v[keep],dist[keep],grade[keep],clr[keep],rel[keep]):
                        tup=(int(vv),float(dd),float(gg),float(cl),int(reln))
                        explicit_adj[int(uu)].append(tup)
                        explicit_adj[int(vv)].append((int(uu),float(dd),float(gg),float(cl),int(reln)))

        for rec in portal_dirs:
            for shard in rec.get('portal_shards',[]):
                if not self._bbox_intersects(shard.get('bbox_rc'),rmin,rmax,cmin,cmax): continue
                with np.load(self.graph_dir/shard['file']) as d:
                    node=np.asarray(d['node'],dtype=np.int64)
                    cell=np.asarray(d['implicit_cell_index'],dtype=np.int64)
                    dist=np.asarray(d['distance_m'],dtype=np.float32); grade=np.asarray(d['grade'],dtype=np.float32)
                    rel=(
                        np.asarray(d['component_relation'],dtype=np.uint8)
                        if 'component_relation' in d else np.full(len(node),3,np.uint8)
                    )
                    rr=cell//self.width; cc2=cell%self.width
                    keep=(rr>=rmin)&(rr<rmax)&(cc2>=cmin)&(cc2<cmax)
                    for n,cellid,dd,gg,reln in zip(node[keep],cell[keep],dist[keep],grade[keep],rel[keep]):
                        if int(n) not in node_floor_z: continue
                        node_to_base[int(n)].append((int(cellid),float(dd),float(gg),int(reln)))
                        base_to_node[int(cellid)].append((int(n),float(dd),float(gg),int(reln)))

        return CorridorOverlay(
            node_floor_z=node_floor_z,node_clearance=node_clearance,node_component=node_component,
            explicit_adj=dict(explicit_adj),node_to_base=dict(node_to_base),base_to_node=dict(base_to_node),
            exception_mask=mask,rmin=rmin,cmin=cmin,rows=rows,cols=cols,
            graph_step_m=self.step_m,graph_width=self.width,
        )
