import json
from pathlib import Path
import numpy as np
from types import SimpleNamespace

from build_surface_tool.plane_fit import _footprint_family, _coarse_plane_grid

ROOT = Path(__file__).resolve().parents[3]
POLICY = json.loads((ROOT/'planning_data/analysis/policies/build_surfaces_v8.json').read_text())


def test_v8_flat_pad_class_anchors():
    assert POLICY['size_classes']['small']['minimum_short_span_foundations'] == 8
    assert POLICY['size_classes']['medium']['minimum_short_span_foundations'] == 12
    assert POLICY['size_classes']['large']['minimum_short_span_foundations'] == 20
    assert POLICY['size_classes']['very_large']['minimum_short_span_foundations'] == 32
    assert (12.0, 26.0) in _footprint_family(POLICY, 'medium')
    assert 32 in POLICY['analysis_parameters']['clearance_tolerances_m']
    assert 64 in POLICY['analysis_parameters']['clearance_tolerances_m']


def test_overhead_only_cell_remains_domain_but_not_known_ground():
    # one 2x2 coarse cell of valid map data with only cliff/overhead provenance
    h=np.full((4,4), 30.0, dtype=np.float32)
    raster=SimpleNamespace(
        source_spacing_m=1.0,
        height_m=h,
        provenance=np.full((4,4), 4, dtype=np.uint8),
        water_q=np.zeros((4,4), dtype=np.uint8),
        meta={'grid':{'x0_cm':0,'y0_cm':0}, 'provenance':{'0':{},'4':{}}},
    )
    ap=dict(POLICY['analysis_parameters'])
    ap['minimum_valid_fraction']=0.95
    grid=_coarse_plane_grid(raster,2.0,ap)
    assert bool(grid.domain[0,0])
    assert not bool(grid.fit_known[0,0])
