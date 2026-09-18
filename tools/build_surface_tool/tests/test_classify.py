import json
from pathlib import Path
from build_surface_tool.classify import classify_size, classify_shape

ROOT=Path(__file__).resolve().parents[3]
POLICY=json.loads((ROOT/'planning_data/analysis/policies/build_surfaces_v3.json').read_text())


def test_size_anchors():
    assert classify_size(8, 4096, POLICY) == 'small'
    assert classify_size(24, 49152, POLICY) == 'medium'
    assert classify_size(48, 196608, POLICY) == 'large'
    assert classify_size(80, 409600, POLICY) == 'very_large'


def test_shape():
    assert classify_shape(24,32,POLICY)[0] == 'good'
    assert classify_shape(24,48,POLICY)[0] == 'workable'
    assert classify_shape(24,60,POLICY)[0] == 'linear'
