from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import zlib
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

CHUNK_TAG = 0x222222229E2A83C1
PREAMBLE_BYTES = 49
FOUNDATION_8X4 = "/Game/FactoryGame/Buildable/Building/Foundation/Build_Foundation_8x4_01.Build_Foundation_8x4_01_C"


class _Reader:
    def __init__(self, data: bytes, pos: int = 0):
        self.data = data; self.pos = pos
    @property
    def remaining(self): return len(self.data) - self.pos
    def i32(self): v=struct.unpack_from('<i',self.data,self.pos)[0]; self.pos+=4; return v
    def i8(self): v=struct.unpack_from('<b',self.data,self.pos)[0]; self.pos+=1; return v
    def f32(self): v=struct.unpack_from('<f',self.data,self.pos)[0]; self.pos+=4; return v
    def f64(self): v=struct.unpack_from('<d',self.data,self.pos)[0]; self.pos+=8; return v
    def u64(self): v=struct.unpack_from('<Q',self.data,self.pos)[0]; self.pos+=8; return v
    def bytes(self,n): b=self.data[self.pos:self.pos+n]; self.pos+=n; return b
    def string(self):
        n=self.i32()
        if n==0: return ''
        if n>0:
            b=self.bytes(n)
            if b[-1:] == b'\0': b=b[:-1]
            return b.decode('utf-8')
        n=-n; b=self.bytes(2*n)
        if b[-2:] == b'\0\0': b=b[:-2]
        return b.decode('utf-16-le')
    def ref(self): return (self.string(), self.string())


def save_build_version(path: Path) -> int:
    data=Path(path).read_bytes()
    if len(data)<12: raise ValueError('save is too short')
    return int(struct.unpack_from('<i',data,8)[0])


def decompress_save_body(path: Path) -> bytes:
    data=Path(path).read_bytes()
    tag=struct.pack('<Q',CHUNK_TAG)
    offset=data.find(tag,12)
    if offset<0: raise ValueError('modern Satisfactory chunk tag not found')
    r=_Reader(data,offset); out=[]
    while r.remaining >= PREAMBLE_BYTES:
        start=r.pos
        if r.u64()!=CHUNK_TAG: raise ValueError(f'bad chunk tag at {start}')
        max_plain=struct.unpack_from('<q',data,r.pos)[0]; r.pos+=8
        algo=r.i8()
        if algo!=3: raise ValueError(f'unsupported compressor {algo} at {start}')
        first_c=struct.unpack_from('<q',data,r.pos)[0];r.pos+=8
        first_p=struct.unpack_from('<q',data,r.pos)[0];r.pos+=8
        comp=struct.unpack_from('<q',data,r.pos)[0];r.pos+=8
        plain=struct.unpack_from('<q',data,r.pos)[0];r.pos+=8
        if (first_c,first_p)!=(comp,plain): raise ValueError(f'chunk size mismatch at {start}')
        if not (0<=comp<=r.remaining and 0<plain<=max_plain): raise ValueError(f'invalid chunk sizes at {start}')
        blob=r.bytes(comp); chunk=zlib.decompress(blob)
        if len(chunk)!=plain: raise ValueError(f'inflated length mismatch at {start}')
        out.append(chunk)
    if r.remaining: raise ValueError(f'{r.remaining} trailing save bytes after chunk stream')
    return b''.join(out)


def _parse_lightweight_candidate(body: bytes, start: int):
    r=_Reader(body,start); version=r.i32(); class_count=r.i32()
    if version not in (2,4) or not (1<=class_count<=10000): raise ValueError('not a lightweight header')
    classes=[]
    for _ in range(class_count):
        level,path=r.ref()
        if level!='' or not path.startswith('/Game/FactoryGame/Buildable/'):
            raise ValueError('not a buildable class reference')
        count=r.i32()
        if count<0: raise ValueError('negative buildable count')
        rows=[]
        for i in range(count):
            quat=[r.f64() for _ in range(4)]
            pos=[r.f64() for _ in range(3)]
            scale=[r.f64() for _ in range(3)]
            swatch=r.ref(); r.ref(); r.ref(); r.ref()
            colors=[[r.f32() for _ in range(4)] for __ in range(2)]
            r.ref(); r.i8(); recipe=r.ref(); r.ref(); r.i32()
            if version>=4: r.i8(); r.i32()
            rows.append({'instance_index':i,'quat':quat,'pos':pos,'scale':scale,'swatch':swatch[1],'recipe':recipe[1]})
        classes.append((path,rows))
    return version,classes,r.pos


def extract_lightweight_buildables(path: Path):
    body=decompress_save_body(path)
    needle=b'/Game/FactoryGame/Buildable/'
    at=0; candidates=[]
    while True:
        off=body.find(needle,at)
        if off<0: break
        at=off+1
        if off<16: continue
        try:
            path_len=struct.unpack_from('<i',body,off-4)[0]
            level_len=struct.unpack_from('<i',body,off-8)[0]
            version=struct.unpack_from('<i',body,off-16)[0]
            class_count=struct.unpack_from('<i',body,off-12)[0]
            if level_len!=0 or path_len<=1 or version not in (2,4) or not (1<=class_count<=10000): continue
            parsed=_parse_lightweight_candidate(body,off-16)
            if any('Foundation' in p for p,_ in parsed[1]): candidates.append((off-16,parsed))
        except Exception:
            continue
    if not candidates: raise ValueError('lightweight-buildable blob not found')
    # The real subsystem candidate is the largest successfully parsed foundation-bearing blob.
    start,(version,classes,end)=max(candidates,key=lambda x:sum(len(rows) for _,rows in x[1][1]))
    return {'build_version':save_build_version(path),'blob_version':version,'blob_offset':start,'blob_end':end,'classes':classes}


def foundation_dataframe(path: Path, class_path: str = FOUNDATION_8X4, foundation_height_m: float = 4.0) -> pd.DataFrame:
    parsed=extract_lightweight_buildables(path)
    rows=[]
    target=[]
    for p,instances in parsed['classes']:
        if p==class_path: target=instances; break
    for rec in target:
        q=rec['quat']; pos=rec['pos']; scale=rec['scale']
        origin_z=float(pos[2])/100.0
        rows.append({
            'instance_index':int(rec['instance_index']),'class_path':class_path,
            'x_cm':float(pos[0]),'y_cm':float(pos[1]),'z_cm':float(pos[2]),
            'east_m':float(pos[0])/100.0,'north_m':-float(pos[1])/100.0,
            'origin_elevation_m':origin_z,'foundation_height_m':float(foundation_height_m),
            'top_elevation_m':origin_z+float(foundation_height_m)/2.0,
            'quat_x':q[0],'quat_y':q[1],'quat_z':q[2],'quat_w':q[3],
            'scale_x':scale[0],'scale_y':scale[1],'scale_z':scale[2],
            'recipe_path':rec['recipe'],'save_build':parsed['build_version'],
        })
    return pd.DataFrame(rows)


def select_flat_component(df: pd.DataFrame, z_m: float, spacing_m: float = 8.0, tolerance_m: float = 0.05,
                          largest: bool = True) -> pd.DataFrame:
    subset=df[np.isclose(df['origin_elevation_m'].astype(float),float(z_m),atol=float(tolerance_m))].copy()
    if subset.empty: raise ValueError(f'no foundations at origin Z={z_m:g} m')
    pts=subset[['east_m','north_m']].to_numpy(float)
    tree=cKDTree(pts); pairs=tree.query_pairs(r=float(spacing_m)*1.01)
    adj=[[] for _ in range(len(subset))]
    for a,b in pairs:
        # Edge adjacency only: diagonal 8x8 centers are ~11.31 m apart and excluded by radius.
        adj[a].append(b);adj[b].append(a)
    seen=set(); comps=[]
    for i in range(len(subset)):
        if i in seen: continue
        stack=[i];seen.add(i);comp=[]
        while stack:
            j=stack.pop();comp.append(j)
            for k in adj[j]:
                if k not in seen: seen.add(k);stack.append(k)
        comps.append(comp)
    comp=max(comps,key=len) if largest else comps[0]
    out=subset.iloc[sorted(comp)].copy().reset_index(drop=True)
    out.insert(0,'fixture_foundation_id',[f'fnd_{i+1:04d}' for i in range(len(out))])
    return out


def edge_mask(df: pd.DataFrame, spacing_m: float = 8.0) -> np.ndarray:
    east=df['east_m'].to_numpy(float); north=df['north_m'].to_numpy(float)
    x0=float(east.min()); y0=float(north.min())
    gx=np.rint((east-x0)/spacing_m).astype(int); gy=np.rint((north-y0)/spacing_m).astype(int)
    coords=set(zip(gx,gy)); return np.array([any((x+dx,y+dy) not in coords for dx,dy in ((1,0),(-1,0),(0,1),(0,-1))) for x,y in zip(gx,gy)],bool)
