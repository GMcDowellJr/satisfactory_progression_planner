import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    path = ROOT / 'scripts' / name
    spec = importlib.util.spec_from_file_location(name.replace('.py',''), path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_gateway_orientation_preserves_endpoint_facts():
    m = load_script('build_travel_topology.py')
    row = m._gateway_row(
        gateway_id=7,
        topo_a=10,
        topo_b=3,
        source='portal',
        a_state_type='explicit', a_state_id=99, a_xyz=(1.0, 2.0, 20.0),
        b_state_type='base', b_state_id=42, b_xyz=(4.0, 6.0, 8.0),
        distance_m=5.0, grade=2.4, clearance_m=3.0, relation=3,
    )
    assert row['topology_u'] == 3
    assert row['topology_v'] == 10
    assert row['u_state_type'] == 'base'
    assert row['u_state_id'] == 42
    assert row['v_state_type'] == 'explicit'
    assert row['v_state_id'] == 99
    assert row['delta_z_m'] == 12.0
    assert row['distance_m'] == 5.0
    assert row['grade'] == 2.4


def test_canonical_snap_schema_has_no_runtime_cost_fields():
    m = load_script('build_foot_exploration_data.py')
    forbidden = {
        'connector_cost_m', 'estimated_4m_ramps', 'safe', 'is_safe',
        'topology_cache_index', 'weighted_distance_m',
    }
    assert not forbidden.intersection(m.SNAP_FIELDS)
    assert not forbidden.intersection(m.CANDIDATE_FIELDS)


def test_hazard_facts_are_not_safety_policy():
    m = load_script('build_foot_exploration_data.py')
    facts = m.hazard_facts({
        'hostiles_nearby': {'Desc_HogAlpha_C': 1},
        'nearest_hostile_cm': 1250,
        'nearest_gas_cm': 500,
    })
    assert facts['nearest_hostile_m'] == 12.5
    assert facts['nearest_gas_m'] == 5.0
    assert 'has_alpha_hostile' not in facts
    assert 'safe' not in facts
