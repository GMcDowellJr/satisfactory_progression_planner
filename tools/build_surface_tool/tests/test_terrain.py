import numpy as np
from build_surface_tool.terrain import make_working_grid

META={'grid':{'x0_cm':0,'y0_cm':0},'provenance':{'0':{'accuracy_m':None},'1':{'accuracy_m':0.2}}}


def test_water_and_cliff_breaks():
    z=np.zeros((8,8),dtype=np.float32)
    z[:,4:]=10
    prov=np.ones((8,8),dtype=np.uint8)
    water=np.zeros((8,8),dtype=np.uint8)
    water[0,0]=1
    g=make_working_grid(z,prov,water,META,1,1,1,1,water_exclusion=True)
    assert not g.usable[0,0]
    assert not g.usable[:,3].any()
    assert not g.usable[:,4].any()
    assert g.usable[:,1].all()
