import numpy as np
from build_surface_tool.regions import label_regions_at_plane
from build_surface_tool.terrain import make_sweep_grid

META={'grid':{'x0_cm':0,'y0_cm':0},'provenance':{'0':{'accuracy_m':None},'1':{'accuracy_m':0.2}}}


def test_sweep_is_monotonic_and_resolution_uses_max_obstruction():
    terrain=np.array([
        [0,0,0,0],
        [0,0,9,0],
        [0,0,0,0],
        [0,0,0,0],
    ],dtype=np.float32)
    water=np.full_like(terrain,np.nan)
    prov=np.ones_like(terrain,dtype=np.uint8)
    water_q=np.zeros_like(terrain,dtype=np.uint8)
    g=make_sweep_grid(terrain,water,prov,water_q,META,1,2,water_obstruction_mode='surface')
    # The one 9m spike keeps its 2x2 coarse cell blocked below 9m.
    assert g.obstruction_m[0,1] == 9
    low,_=label_regions_at_plane(g.domain,g.obstruction_m,8)
    high,_=label_regions_at_plane(g.domain,g.obstruction_m,10)
    assert np.count_nonzero(high) >= np.count_nonzero(low)
    assert low[0,1] == 0
    assert high[0,1] > 0


def test_water_surface_is_temporary_obstruction():
    terrain=np.zeros((4,4),dtype=np.float32)
    water=np.full_like(terrain,np.nan)
    water[0:2,0:2]=5
    prov=np.ones_like(terrain,dtype=np.uint8)
    water_q=np.zeros_like(terrain,dtype=np.uint8); water_q[0:2,0:2]=1
    g=make_sweep_grid(terrain,water,prov,water_q,META,1,2,water_obstruction_mode='surface')
    assert g.obstruction_m[0,0] == 5
    below,_=label_regions_at_plane(g.domain,g.obstruction_m,4)
    above,_=label_regions_at_plane(g.domain,g.obstruction_m,6)
    assert below[0,0] == 0
    assert above[0,0] > 0
