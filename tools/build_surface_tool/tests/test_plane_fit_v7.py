import json
from pathlib import Path
import numpy as np

from build_surface_tool.plane_fit import PlaneFitGrid, _placement_maps, _footprint_family, _paint_region_coverage

ROOT = Path(__file__).resolve().parents[3]
POLICY = json.loads((ROOT/'planning_data/analysis/policies/build_surfaces_v7.json').read_text())


def grid(n=120, resolution=16.0):
    z=np.zeros((n,n),dtype=np.float32)
    ones=np.ones_like(z,dtype=np.float32)
    return PlaneFitGrid(resolution,0.0,0.0,z,z,z,ones,np.zeros_like(z),ones,np.zeros_like(z),np.zeros_like(z),np.ones_like(z,dtype=bool),np.ones_like(z,dtype=bool),np.zeros_like(z,dtype=np.float32))


def test_small_family_contains_steel_like_rectangle():
    assert (12.0, 26.0) in _footprint_family(POLICY,'small')


def test_variable_family_prefers_largest_qualifying_small_footprint():
    g=grid()
    ranks, qualifies, orientations, metrics = _placement_maps(g,POLICY,1.0)
    r=c=60
    # A fully flat domain supports the largest configured Small footprint at this center.
    assert qualifies['small'][r,c]
    assert metrics['small']['width_foundations'][r,c] == 20
    assert metrics['small']['length_foundations'][r,c] == 40
    # Higher classes also qualify, so highest-class rank remains independent of Small's shape.
    assert ranks[r,c] == 4


def test_8x8_coverage_is_64m_physical_even_at_16m_analysis_resolution():
    g=grid(n=20,resolution=16.0)
    coverage=np.zeros((20,20),dtype=np.int32)
    rr=np.array([10]); cc=np.array([10])
    orientation=np.full((20,20),np.nan,dtype=np.float32); orientation[10,10]=0
    metrics={
        'width_foundations':np.full((20,20),np.nan,dtype=np.float32),
        'length_foundations':np.full((20,20),np.nan,dtype=np.float32),
    }
    metrics['width_foundations'][10,10]=8
    metrics['length_foundations'][10,10]=8
    _paint_region_coverage(coverage,rr,cc,g,POLICY,orientation,metrics,7)
    # 64 m / 16 m = 4 cells on each side.
    assert np.count_nonzero(coverage==7) == 16
