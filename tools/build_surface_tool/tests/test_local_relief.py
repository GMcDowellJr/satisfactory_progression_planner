import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np

from build_surface_tool.local_relief import ReliefGrid, _footprint_relief, _placement_maps

ROOT = Path(__file__).resolve().parents[3]
POLICY = json.loads((ROOT/'planning_data/analysis/policies/build_surfaces_v4.json').read_text())


def grid(z):
    z=np.asarray(z,dtype=np.float32)
    ones=np.ones_like(z,dtype=np.float32)
    return ReliefGrid(16.0,0.0,0.0,z,z,z,ones,np.zeros_like(z),ones,np.zeros_like(z),np.zeros_like(z),np.ones_like(z,dtype=bool))


def test_window_relief_uses_local_max_minus_min_and_full_window():
    g=grid(np.array([[0,0,0],[0,4,0],[0,0,0]],dtype=np.float32))
    relief, mn, mx, valid=_footprint_relief(g,(3,3))
    assert valid[1,1]
    assert relief[1,1] == 4
    assert not valid[0,0]


def test_larger_relief_tolerance_only_adds_qualifying_centers():
    z=np.zeros((50,50),dtype=np.float32)
    z[:,25:]=6
    g=grid(z)
    r4,*_= _placement_maps(g,POLICY,4)
    r8,*_= _placement_maps(g,POLICY,8)
    assert np.count_nonzero(r8) >= np.count_nonzero(r4)


def test_highest_class_wins_at_center():
    g=grid(np.zeros((100,100),dtype=np.float32))
    ranks,*_= _placement_maps(g,POLICY,2)
    # Interior of a large flat domain should qualify as very large.
    assert ranks[50,50] == 4
