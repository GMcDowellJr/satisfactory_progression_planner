import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from multisurface_tool import rasterize_triangles, derive_clearance, layer_count


def quad(x0,y0,x1,y1,z):
    return np.array([
        [[x0,y0,z],[x1,y0,z],[x1,y1,z]],
        [[x0,y0,z],[x1,y1,z],[x0,y1,z]],
    ],dtype=float)


def test_arch_preserves_lower_and_upper_surfaces():
    # Ground + arch underside + arch roof over the middle of the window.
    base=np.zeros((11,11),dtype=np.float32)
    tris=np.concatenate([quad(3,3,7,7,8.0), quad(3,3,7,7,12.0)],axis=0)
    g=rasterize_triangles(tris,(0,0,10,10),1.0,base_surface=base,cluster_tolerance_m=0.1,max_layers=4)
    vals=g.surfaces_m[5,5]
    vals=vals[np.isfinite(vals)]
    assert np.allclose(vals,[0,8,12])
    clr=derive_clearance(g)
    assert abs(float(clr[5,5,0])-8.0)<1e-6
    assert layer_count(g)[5,5]==3


def test_vertical_wall_does_not_create_fake_floor():
    base=np.zeros((5,5),dtype=np.float32)
    wall=np.array([[[2,0,0],[2,4,0],[2,4,10]],[[2,0,0],[2,4,10],[2,0,10]]],dtype=float)
    g=rasterize_triangles(wall,(0,0,4,4),1.0,base_surface=base,max_layers=3)
    assert np.nanmax(layer_count(g))==1
