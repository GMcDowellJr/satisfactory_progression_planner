import csv
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / 'scripts' / name
    spec = importlib.util.spec_from_file_location(name.replace('.py', ''), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


m = load_script('export_navigator_poi_state.py')

POD = '/Game/FactoryGame/World/Benefit/DropPod/BP_DropPod.BP_DropPod_C'


def poi(pid, ptype, cell, leaf):
    return {'poi_id': pid, 'poi_type': ptype, 'source_cell': cell,
            'source_object_id': f'Persistent_Level:PersistentLevel.{leaf}'}


def index(*rows):
    return {(r['source_cell'], m.leaf(r['source_object_id'])): r for r in rows}


def level(name, *actors):
    headers = [NS(type_path=t, instance_name=f'Persistent_Level:PersistentLevel.{n}') for t, n, _ in actors]
    objects = [NS(properties=p) for _, _, p in actors]
    return NS(name=name, headers=headers, objects=objects)


def test_destroyed_join_uses_cell_and_leaf():
    idx = index(poi('p1', 'power_slug_blue', 'CELL_A', 'BP_Crystal_C_1'))
    same_leaf_other_cell = [('CELL_B', 'Persistent_Level:PersistentLevel.BP_Crystal_C_1')]
    assert m.derive_state(idx, same_leaf_other_cell, {})['collected'] == []
    right_cell = [('CELL_A', 'Persistent_Level:PersistentLevel.BP_Crystal_C_1')]
    assert m.derive_state(idx, right_cell, {})['collected'] == ['p1']


def test_looted_standing_pod_is_collected_opened_pod_is_not():
    idx = index(poi('pod_looted', 'crash_site', 'C1', 'BP_DropPod36'),
                poi('pod_opened', 'crash_site', 'C2', 'BP_DropPod37'),
                poi('pod_untouched', 'crash_site', 'C3', 'BP_DropPod38'))
    save = NS(levels=[
        level('C1', (POD, 'BP_DropPod36', [['mHasBeenOpened', True], ['mHasBeenLooted', True]])),
        level('C2', (POD, 'BP_DropPod37', [['mHasBeenOpened', True]])),
        level('C3', (POD, 'BP_DropPod38', [['mDismantleRefundsIndex', 1]])),
    ])
    s = m.derive_state(idx, [], m.pod_flags(save))
    assert s['collected'] == ['pod_looted']
    assert s['collected_reason'] == {'pod_looted': 'looted_flag'}
    assert s['opened_not_looted'] == ['pod_opened']
    assert s['counts']['crash_site'] == {'total': 3, 'collected': 1, 'available': 2}


def test_looted_flag_ignored_for_non_pod_types():
    idx = index(poi('slug', 'power_slug_blue', 'C1', 'BP_DropPod36'))
    save = NS(levels=[level('C1', (POD, 'BP_DropPod36', [['mHasBeenLooted', True]]))])
    assert m.derive_state(idx, [], m.pod_flags(save))['collected'] == []


def test_state_makes_no_route_or_position_claims():
    idx = index(poi('p1', 'somersloop', 'C', 'BP_WAT1_C_1'))
    s = m.derive_state(idx, [('C', 'x.BP_WAT1_C_1')], {})
    forbidden = {'order', 'route', 'reachable', 'safe', 'location_cm', 'distance'}
    assert not forbidden.intersection(s)


def test_session_file_token():
    assert m.session_file_token('test') == 'test'
    assert m.session_file_token('Rocky (not Balboa)') == 'Rocky__not_Balboa_'
    assert m.session_file_token("everything's so green") == 'everything_s_so_green'


def test_ticks_are_utc_dotnet_ticks():
    # test_autosave_1.sav header ticks; file mtime was 2026-09-16 21:13 UTC
    assert m.ticks_to_iso(639251899920830000) == '2026-09-16T21:13:12+00:00'


def test_branch_length_error_pattern():
    msg = ("at body offset 8: archive header read 70 bytes, expected 59 "
           "(branch string '++FactoryGame+rel-main-anniversary-2026' changed length?)")
    assert m._BRANCH_LEN_ERROR.search(msg).group(1) == '70'


def test_duplicate_poi_key_rejected(tmp_path):
    p = tmp_path / 'pois.csv'
    with p.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['poi_id', 'poi_type', 'source_cell', 'source_object_id'])
        w.writeheader()
        w.writerow(poi('a', 'crash_site', 'C', 'X'))
        w.writerow(poi('b', 'crash_site', 'C', 'X'))
    try:
        m.load_poi_index(p)
    except SystemExit:
        return
    raise AssertionError('duplicate key accepted')
