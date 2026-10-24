"""Rail reach by standard ramp class, no bridges.
Grid: 8 m (one foundation), block-mean of the 1 m heightfield.
Edge: 8-neighbour step; track grade = |dz| / horizontal (8 or 11.3 m).
Classes: 1:8 (12.5%), 2:8 (25%), 4:8 (50%).
Blocked: no-data; water deeper than DEEP_M or of unknown depth.
"""
import sys,json,math,numpy as np
sys.path.insert(0,'tools/corridor_tool/src')
from pathlib import Path
from corridor_tool.field import decode_i16,decode_u8,NODATA
from scipy import sparse
from scipy.sparse.csgraph import connected_components,dijkstra
OUT=__import__('pathlib').Path(__file__).resolve().parent/'out'; OUT.mkdir(exist_ok=True); SP=str(OUT)+'/'
base=Path('planning_data/world/spatial/heightmap_build_502094'); meta=json.load(open(base/'meta.json'))
H=W=7500; B=8; DEEP_M=3.0
h=decode_i16(base/'height.i16.z',H,W); wz=decode_i16(base/'water.i16.z',H,W); wq=decode_u8(base/'waterq.u8.z',H,W)
z=h.astype(np.float32)/10; z[h==NODATA]=np.nan
depth=np.where(wq==1,np.maximum(wz.astype(np.float32)/10-z,0),np.nan)
n=H//B; zc=z[:n*B,:n*B].reshape(n,B,n,B)
with np.errstate(all='ignore'):
  Z=np.nanmean(zc,axis=(1,3)); valid_frac=np.isfinite(zc).mean(axis=(1,3))
  wet=(wq[:n*B,:n*B].reshape(n,B,n,B)!=0).mean(axis=(1,3))
  D=np.nanmax(depth[:n*B,:n*B].reshape(n,B,n,B),axis=(1,3))
  unknown=(wq[:n*B,:n*B].reshape(n,B,n,B)==2).mean(axis=(1,3))
blocked=(valid_frac<0.5)|~np.isfinite(Z)|((wet>0.5)&((D>=DEEP_M)|(unknown>0.5)))
del h,wz,wq,z,depth,zc
east0=meta['grid']['x0_cm']/100; north0=-meta['grid']['y0_cm']/100
idx=np.arange(n*n).reshape(n,n)
rows=[];cols=[];grades=[];lens=[]
for dr,dc in ((0,1),(1,0),(1,1),(1,-1)):
  r0=slice(0,n-dr); c0=slice(max(0,-dc),n-max(0,dc)); r1=slice(dr,n); c1=slice(max(0,dc),n-max(0,-dc)) if dc>=0 else slice(0,n+dc)
  if dc<0: c0=slice(1,n); c1=slice(0,n-1)
  a=idx[r0,c0].ravel(); b=idx[r1,c1].ravel(); L=B*math.hypot(dr,dc)
  g=np.abs(Z[r1,c1]-Z[r0,c0]).ravel()/L
  ok=~blocked[r0,c0].ravel()&~blocked[r1,c1].ravel()&np.isfinite(g)
  rows.append(a[ok]);cols.append(b[ok]);grades.append(g[ok]);lens.append(np.full(ok.sum(),L))
rows=np.concatenate(rows);cols=np.concatenate(cols);grades=np.concatenate(grades);lens=np.concatenate(lens)
hubs=[dict(key=h['key'],e=h['east_m'],n=h['north_m']) for h in json.load(open(OUT.parent/'hubs.json'))]
def rc(e,nn): return int(round((north0-nn)/B)),int(round((e-east0)/B))
CLASSES={'1:8':0.125,'2:8':0.25,'4:8':0.5}
out={'grid_m':B,'n':n,'east0':east0,'north0':north0,'classes':{}}
labels_by={}
for name,t in CLASSES.items():
  m=grades<=t
  G=sparse.coo_matrix((lens[m],(rows[m],cols[m])),shape=(n*n,n*n)).tocsr(); G=G+G.T
  nc,lab=connected_components(G,directed=False); labels_by[name]=lab
  sizes=np.bincount(lab)
  snaps={}
  for hb in hubs:
    r,c=rc(hb['e'],hb['n']); R=20  # search 160 m for the largest reachable component
    best=None
    for rr in range(max(0,r-R),min(n,r+R+1)):
      for cc in range(max(0,c-R),min(n,c+R+1)):
        if blocked[rr,cc]: continue
        i=idx[rr,cc]; s=sizes[lab[i]]
        d=math.hypot(rr-r,cc-c)*B
        key=(s,-d)
        if best is None or key>best[0]: best=(key,i,d)
    snaps[hb['key']]=dict(node=int(best[1]),comp=int(lab[best[1]]),comp_km2=round(sizes[lab[best[1]]]*B*B/1e6,2),snap_m=round(best[2]))
  # pairwise path length within class
  keys=[h['key'] for h in hubs]; src=[snaps[k]['node'] for k in keys]
  dist=dijkstra(G,indices=src,directed=False)
  pair={f"{a}-{b}":(None if not np.isfinite(dist[i,src[j]]) else round(float(dist[i,src[j]])/1000,2)) for i,a in enumerate(keys) for j,b in enumerate(keys) if j>i}
  out['classes'][name]=dict(limit=t,components=int(nc),snaps=snaps,pairs=pair)
  print(name,{k:(v['comp'],v['comp_km2'],v['snap_m']) for k,v in snaps.items()})
  print('  ',{k:v for k,v in pair.items()})
# reach raster: which class first connects a cell to the core (C1's component)
reach=np.zeros(n*n,np.uint8)
for code,name in ((3,'4:8'),(2,'2:8'),(1,'1:8')):
  lab=labels_by[name]; core=lab[out['classes'][name]['snaps']['C1']['node']]
  reach[lab==core]=code
reach=reach.reshape(n,n); reach[blocked]=0
np.save(SP+'reach.npy',reach)
json.dump(out,open(SP+'slope_reach.json','w',newline='\n'),indent=1)
print('reach cells', {k:int((reach==k).sum()) for k in range(4)})
np.save(SP+'Z.npy',Z.astype(np.float32)); np.save(SP+'blocked.npy',blocked)
for name in ('2:8','4:8'): np.save(SP+f"lab_{name[0]}.npy",labels_by[name].astype(np.int32))
