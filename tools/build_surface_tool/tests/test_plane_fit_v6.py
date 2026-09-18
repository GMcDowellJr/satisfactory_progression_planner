import json
from pathlib import Path
import numpy as np

from build_surface_tool.plane_fit import PlaneFitGrid, _plane_metrics, _even_window_origin
from build_surface_tool.calibration import validate_calibration_summary

ROOT=Path(__file__).resolve().parents[3]
POLICY=json.loads((ROOT/'planning_data/analysis/policies/build_surfaces_v6.json').read_text())


def grid(z, known=None, overhead=None):
    z=np.asarray(z,dtype=np.float32)
    ones=np.ones_like(z,dtype=np.float32)
    if known is None: known=np.ones_like(z,dtype=bool)
    if overhead is None: overhead=np.zeros_like(z,dtype=np.float32)
    return PlaneFitGrid(1.0,0.0,0.0,z,z,z,ones,np.zeros_like(z),ones,np.zeros_like(z),np.zeros_like(z),np.ones_like(z,dtype=bool),np.asarray(known,bool),np.asarray(overhead,np.float32))


def test_even_window_edge_filter_is_aligned_with_platform_window():
    z=np.arange(64,dtype=np.float32).reshape(8,8)
    m=_plane_metrics(grid(z),(4,4),POLICY['analysis_parameters'])
    assert _even_window_origin((4,4)) == (-1,-1)
    assert m['edge_mean_clearance'][4,4] >= -1e-5
    assert m['mean_clearance'][4,4] >= -1e-5


def test_cliff_only_cells_can_be_ambiguity_not_platform_height():
    z=np.full((7,7),10,dtype=np.float32)
    z[3,3]=50
    known=np.ones_like(z,dtype=bool); known[3,3]=False
    overhead=np.zeros_like(z,dtype=np.float32); overhead[3,3]=1
    ap=dict(POLICY['analysis_parameters']); ap['minimum_fit_known_fraction']=0.8; ap['minimum_edge_known_fraction']=0.8
    m=_plane_metrics(grid(z,known,overhead),(3,3),ap)
    assert m['platform_z'][3,3] == 10
    assert m['overhead_ambiguous_fraction'][3,3] > 0


def test_committed_phm_calibration_summary_passes_expectations():
    summary=json.loads((ROOT/'planning_data/analysis/calibration/PHM_steel_deck_502094/calibration_summary.json').read_text())
    expected=json.loads((ROOT/'planning_data/analysis/calibration/PHM_steel_deck_502094/expected.json').read_text())
    result=validate_calibration_summary(summary,expected)
    assert result['status']=='PASS'
