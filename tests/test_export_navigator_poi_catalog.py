import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / 'scripts' / name
    spec = importlib.util.spec_from_file_location(name.replace('.py', ''), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = load_script('export_navigator_poi_catalog.py')

FIELDS = ['poi_id', 'poi_type', 'source_object_id', 'source_cell', 'source_category',
          'source_class', 'east_m', 'north_m', 'elevation_m', 'source_game_build', 'source_sha256']
BUILD = '++FactoryGame+rel-main-anniversary-2026-CL-502094'


def row(pid, ptype, oid, e, n, z, build=BUILD):
    return dict(poi_id=pid, poi_type=ptype, source_object_id=oid, source_cell='c',
                source_category='x', source_class='BP_DropPod_C', east_m=str(e),
                north_m=str(n), elevation_m=str(z), source_game_build=build, source_sha256='0' * 64)


def test_coord_frame_matches_runtime_log_sample():
    # BP_DropPod14_389 from FactoryGame.log 2026-09-16: X=-43144 Y=145820 Z=7472
    assert m.to_ue_cm(-431.44, -1458.2, 74.72) == {'x': -43144.0, 'y': 145820.0, 'z': 7472.0}


def test_negative_zero_is_normalized():
    assert str(m.to_ue_cm(0.0, 0.0, 0.0)['y']) == '0.0'


def test_match_key_is_suffix_after_first_colon():
    assert m.match_key('Persistent_Level:PersistentLevel.BP_DropPod2_10') == 'PersistentLevel.BP_DropPod2_10'
    with pytest.raises(ValueError):
        m.match_key('no_separator')


def test_catalog_makes_no_order_route_or_state_claims():
    rows = [row('poi_1_0002', 'somersloop', 'L:PersistentLevel.B', 1, 2, 3),
            row('poi_1_0001', 'crash_site', 'L:PersistentLevel.A', 4, 5, 6)]
    cat = m.build_catalog(rows, [], None)
    assert [p['id'] for p in cat['pois']] == ['poi_1_0001', 'poi_1_0002']  # id order, not route order
    assert {p['state'] for p in cat['pois']} == {'unknown'}
    assert cat['state_source'] is None
    forbidden = {'order', 'sequence', 'route', 'reachable', 'safe', 'collected', 'distance_from_player'}
    for p in cat['pois']:
        assert not forbidden.intersection(p)
    assert [p['match_verified'] for p in cat['pois']] == [True, False]


def test_duplicate_match_key_rejected():
    rows = [row('poi_1_0001', 'crash_site', 'A:PersistentLevel.X', 0, 0, 0),
            row('poi_1_0002', 'crash_site', 'B:PersistentLevel.X', 0, 0, 0)]
    with pytest.raises(SystemExit):
        m.build_catalog(rows, [], None)


def test_mixed_builds_rejected():
    rows = [row('poi_1_0001', 'crash_site', 'A:P.X', 0, 0, 0),
            row('poi_1_0002', 'crash_site', 'A:P.Y', 0, 0, 0, build='other')]
    with pytest.raises(SystemExit):
        m.build_catalog(rows, [], None)


def test_foot_facts_are_facts_not_policy(tmp_path):
    snap = tmp_path / 'snap.csv'
    with snap.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['poi_id', 'snap_status', 'global_component_rank',
                                          'snap_spatial_distance_m', 'snap_dz_m'])
        w.writeheader()
        w.writerow(dict(poi_id='poi_1_0001', snap_status='SNAPPED', global_component_rank=13,
                        snap_spatial_distance_m=149.49, snap_dz_m=139.386))
    facts = m.load_foot_facts(snap)
    cat = m.build_catalog([row('poi_1_0001', 'crash_site', 'A:P.X', 0, 0, 0)], [], facts)
    f = cat['pois'][0]['foot_topology_facts']
    assert f['primary_network_member'] is False
    assert not {'reachable', 'safe', 'accessible'}.intersection(f)
    assert cat['foot_topology_facts_note']


def test_end_to_end_deterministic(tmp_path):
    src = tmp_path / 'pois.csv'
    with src.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerow(row('poi_1_0001', 'crash_site', 'A:P.X', -7.5, 2.25, 1))
    out1, out2 = tmp_path / 'a.json', tmp_path / 'b.json'
    assert m.main(['--pois', str(src), '--out', str(out1)]) == 0
    assert m.main(['--pois', str(src), '--out', str(out2)]) == 0
    assert out1.read_bytes() == out2.read_bytes()
    cat = json.loads(out1.read_text(encoding='utf-8'))
    assert cat['pois'][0]['location_cm'] == {'x': -750.0, 'y': -225.0, 'z': 100.0}
