import json
from pathlib import Path
import numpy as np

from build_surface_tool.plane_fit import PlaneFitGrid, _plane_metrics, _placement_maps

ROOT = Path(__file__).resolve().parents[3]
POLICY = json.loads((ROOT/'planning_data/analysis/policies/build_surfaces_v5.json').read_text())


def grid(z, resolution=16.0):
    z=np.asarray(z,dtype=np.float32)
    ones=np.ones_like(z,dtype=np.float32)
    return PlaneFitGrid(resolution,0.0,0.0,z,z,z,ones,np.zeros_like(z),ones,np.zeros_like(z),np.zeros_like(z),np.ones_like(z,dtype=bool),np.ones_like(z,dtype=bool),np.zeros_like(z,dtype=np.float32))


def test_flat_plane_is_set_to_highest_working_cell():
    z=np.array([[10,10,10],[10,12,10],[10,10,10]],dtype=np.float32)
    m=_plane_metrics(grid(z,1.0),(3,3),POLICY['analysis_parameters'])
    assert m['platform_z'][1,1] == 12
    assert m['max_clearance'][1,1] == 2


def test_edge_drop_is_detected_separately():
    z=np.full((5,5),10,dtype=np.float32)
    z[1,1:4]=0
    m=_plane_metrics(grid(z,1.0),(3,3),POLICY['analysis_parameters'])
    assert m['platform_z'][2,2] == 10
    assert m['edge_mean_clearance'][2,2] > 0


def test_more_clearance_never_removes_qualifying_centers():
    z=np.zeros((100,100),dtype=np.float32)
    z[:,50:]=6
    g=grid(z)
    r4,*_= _placement_maps(g,POLICY,4)
    r8,*_= _placement_maps(g,POLICY,8)
    assert np.count_nonzero(r8) >= np.count_nonzero(r4)


def test_large_flat_area_qualifies_very_large():
    g=grid(np.zeros((100,100),dtype=np.float32))
    ranks,*_= _placement_maps(g,POLICY,1)
    assert ranks[50,50] == 4
