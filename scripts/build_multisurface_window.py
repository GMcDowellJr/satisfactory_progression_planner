from __future__ import annotations
import argparse, json, sys, zlib
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'tools'/'multisurface_tool'/'src'
if str(SRC) not in sys.path: sys.path.insert(0,str(SRC))
from multisurface_tool import rasterize_triangles, save_npz, derive_clearance, layer_count

NODATA=-32768

def decode_i16(path,h,w):
    a=np.frombuffer(zlib.decompress(Path(path).read_bytes()),dtype='<i2').reshape(h,w)
    return np.cumsum(a.astype(np.int32),axis=1).astype(np.int16)

def load_base(terrain_dir,bounds,step_m):
    td=Path(terrain_dir); meta=json.loads((td/'meta.json').read_text())
    h=int(meta['grid']['height']); w=int(meta['grid']['width'])
    native=float(meta['grid']['spacing_cm'])/100.0
    if abs(step_m/native-round(step_m/native))>1e-6: raise ValueError('step_m must be integer multiple of native terrain spacing')
    raw=decode_i16(td/'height.i16.z',h,w)
    z=raw.astype(np.float32)/10.0; z[raw==NODATA]=np.nan
    east0=float(meta['grid']['x0_cm'])/100.0; north0=-float(meta['grid']['y0_cm'])/100.0
    xmin,ymin,xmax,ymax=bounds
    xs=np.arange(xmin,xmax+step_m*0.5,step_m); ys=np.arange(ymax,ymin-step_m*0.5,-step_m)
    cc=np.rint((xs-east0)/native).astype(int); rr=np.rint((north0-ys)/native).astype(int)
    return z[np.ix_(rr,cc)]

def main(argv=None):
    p=argparse.ArgumentParser(description='Prototype a multi-surface terrain window from world-space triangle geometry.')
    p.add_argument('--triangles',required=True,help='NPZ containing triangles[T,3,3] in planner east/north/up metres')
    p.add_argument('--terrain-dir',required=True)
    p.add_argument('--bounds',nargs=4,type=float,required=True,metavar=('XMIN','YMIN','XMAX','YMAX'))
    p.add_argument('--step-m',type=float,default=2.0)
    p.add_argument('--max-layers',type=int,default=6)
    p.add_argument('--cluster-tolerance-m',type=float,default=0.75)
    p.add_argument('--out',required=True)
    a=p.parse_args(argv)
    d=np.load(a.triangles); triangles=d['triangles']
    bounds=tuple(a.bounds); base=load_base(a.terrain_dir,bounds,a.step_m)
    g=rasterize_triangles(triangles,bounds,a.step_m,base_surface=base,cluster_tolerance_m=a.cluster_tolerance_m,max_layers=a.max_layers)
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    save_npz(g,out/'multisurface_window.npz')
    np.savez_compressed(out/'multisurface_derived.npz',clearance_m=derive_clearance(g),layer_count=layer_count(g))
    summary={
        'bounds':list(bounds),'step_m':a.step_m,'triangles':int(triangles.shape[0]),
        'cells':int(g.shape[0]*g.shape[1]),
        'multi_layer_cells':int((layer_count(g)>=2).sum()),
        'three_plus_layer_cells':int((layer_count(g)>=3).sum()),
        'contract':'triangles are world-space planner east/north/up metres; base terrain is inserted as a surface, never overwritten by max-Z',
    }
    (out/'summary.json').write_text(json.dumps(summary,indent=2), newline="\n")
    print(json.dumps(summary,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
