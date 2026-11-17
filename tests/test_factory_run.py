"""tools/factory_run.py: the supply-side factory track (reconciliation R7).

Reframe A15.2 (Greg, 2026-11-17): A1 a sibling track taking a declared
factory (what is available + goals); B1 maximise a DECLARED goal mix within
supply, never inventing one; B2 highest marks for supply, stepped down where
they do not help. Sites here are the test's declarations (Rocky Desert
district A, as tests/test_portfolio_inputs.py uses it), not Greg's.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
ROCKY_A = ("BP_ResourceNode153", "BP_ResourceNode109", "BP_ResourceNode108", "BP_ResourceNode105_2463",
           "BP_ResourceNode107", "BP_ResourceNode106", "BP_ResourceNode112", "BP_ResourceNode111_3367",
           "BP_ResourceNode103", "BP_ResourceNode102_2068", "BP_ResourceNode104")
OIL_NODES = ("BP_ResourceNode100", "BP_ResourceNode14_609")
ADVANCED_STEEL = "Schematic_4-1_C"
MIX = ("Desc_IronPlateReinforced_C", "Desc_Rotor_C")


def _module(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


F = _module("factory_run")


def _doc(*, tier=3, milestones=(), sockets=ROCKY_A, mix=MIX, target=None, mode="report_need"):
    return {
        "schema": "factory-inputs/1", "world_config_id": "default_502094",
        "playthrough": {"through_tier": tier, "milestones": list(milestones), "research": [],
                        "alternates": []},
        "scenario": {"recipe_input_multiplier": 1.0, "machine_power_multiplier": 1.0,
                     "project_assembly_requirement_multiplier": 1.0, "fluid_input_floor": None,
                     "fluid_rounding_unit": "mL"},
        "site": {"label": "rocky", "socket_ids": list(sockets), "supply": [], "pumps_water": False},
        "goal_mix": [{"item_id": i, "units": 1} for i in mix],
        "goal": "balanced", "power_mode": mode, "power_statistic": "mean",
        "grid_mw": 0.0, "spare_mw": 0.0,
        "target_scale": target, "infrastructure_policy": "highest_then_step_down",
        "fuel_byproducts": "power",
    }


@pytest.fixture(scope="module")
def tier3():
    return F.run_inputs(_doc())


@pytest.fixture(scope="module")
def steel():
    return F.run_inputs(_doc(milestones=[ADVANCED_STEEL]))


# --- B1: a declared mix, maximised within supply ------------------------------

def test_the_mix_is_delivered_in_its_declared_proportions(tier3):
    assert tier3.scale > 0
    assert dict(tier3.delivered) == pytest.approx({i: tier3.scale for i in MIX})


def test_a_declared_target_is_delivered_exactly_or_refused(tier3):
    fixed = F.run_inputs(_doc(target=tier3.scale / 2))
    assert fixed.scale == pytest.approx(tier3.scale / 2)
    from production_adapter.lp_backend import Infeasible
    with pytest.raises(Infeasible):
        F.run_inputs(_doc(target=tier3.scale * 2))


@pytest.mark.parametrize("units", [5, 50, 1000])
def test_a_fixed_rate_solves_at_any_bill_scale(units):
    """Until 2026-11-17 a declared target_scale with bill units >= 5 came back
    Infeasible from solve_portfolio's fourth stage (HiGHS presolve on a pinned,
    feasible-by-construction stage). Fixed by Greg's decision: a pinned stage
    that presolve calls infeasible is re-solved once without presolve."""
    doc = _doc(tier=2, mix=("Desc_SpaceElevatorPart_1_C",), target=2.0 / units)
    doc["goal_mix"][0]["units"] = units
    run = F.run_inputs(doc)
    assert dict(run.delivered)["Desc_SpaceElevatorPart_1_C"] == pytest.approx(2.0)


# --- B2: supply at the highest mark the playthrough owns ----------------------

def test_tier_three_has_only_mk1_miners(tier3):
    assert {p.mark.highest.extractor_class for p in tier3.sockets} == {"Build_MinerMk1_C"}


def test_buying_advanced_steel_raises_supply_through_mk2(tier3, steel):
    """Same sockets; Miner Mk.2 doubles each node's rate, iron binds both times."""
    assert {p.mark.highest.extractor_class for p in steel.sockets} == {"Build_MinerMk2_C"}
    assert steel.scale == pytest.approx(2 * tier3.scale)


def test_an_undrawn_socket_builds_nothing(tier3):
    idle = [p for p in tier3.sockets if p.mark.draw_per_min == 0]
    assert idle and all(p.mark.chosen is None and p.lane is None for p in idle)


# --- B2 / Q1: step down where the higher mark does not help -------------------

def test_below_the_maximum_sockets_step_down_and_save_power(steel):
    """Half the Mk.2 maximum: each iron node draws 60/min of its 120 (normal),
    which a Mk.1 carries at 5 MW instead of Mk.2's 7.5; the lane fits Mk.1."""
    half = F.run_inputs(_doc(milestones=[ADVANCED_STEEL], target=steel.scale / 2))
    drawn = [p for p in half.sockets if p.mark.chosen is not None]
    assert drawn and all(p.mark.stepped_down for p in drawn)
    assert {p.mark.chosen.extractor_class for p in drawn} == {"Build_MinerMk1_C"}
    assert all(p.lane.mark.mark == "Mk.1" for p in drawn)
    assert half.extraction_mw_chosen < half.extraction_mw_highest


def test_oil_nodes_take_the_oil_extractor_and_a_pipe():
    """Crude Oil maps to both the Oil Extractor and the Resource Well
    Extractor; a node socket takes only the former (requires_activator)."""
    run = F.run_inputs(_doc(tier=5, sockets=OIL_NODES, mix=("Desc_Plastic_C",)))
    assert {p.mark.highest.extractor_class for p in run.sockets} == {"Build_OilPump_C"}
    assert {p.lane.mark.capability_type for p in run.sockets if p.lane} == {"pipeline"}


def test_a_well_satellite_takes_the_well_extractor_not_the_oil_pump():
    """Without the requires_activator family a satellite would be ranked
    against the Oil Extractor, which outrates it, and take an extractor it
    cannot hold (mutation-checked, 2026-11-17)."""
    run = F.run_inputs(_doc(tier=9, sockets=("BP_FrackingSatellite45",), mix=("Desc_Plastic_C",)))
    assert {p.mark.highest.extractor_class for p in run.sockets} == {"Build_FrackingExtractor_C"}


# --- the record ----------------------------------------------------------------

def test_the_record_echoes_its_inputs_and_states_its_reading(tier3):
    rec = json.loads(json.dumps(F.record(tier3), default=str))
    assert rec["schema"] == "factory-plan/1"
    assert rec["inputs"]["schema"] == "factory-inputs/1"
    assert len(rec["sockets"]) == len(tier3.sockets)
    assert any("equal share" in w for w in rec["warnings"])


def test_the_cli_writes_the_record(tmp_path):
    inputs = tmp_path / "f.json"
    inputs.write_text(json.dumps(_doc()), encoding="utf-8")
    out = tmp_path / "plan.json"
    assert F.main(["--inputs", str(inputs), "--export", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["schema"] == "factory-plan/1"


# --- refusals ------------------------------------------------------------------

def _broken(path, value):
    d = _doc()
    target = d
    for k in path[:-1]:
        target = target[k]
    target[path[-1]] = value
    return d


@pytest.mark.parametrize("doc, match", [
    (_broken(("goal_mix",), []), "never invented"),
    (_broken(("goal_mix",), [{"item_id": "Desc_OreIron_C", "units": 1}]), "raw resource"),
    (_broken(("goal_mix",), [{"item_id": "Desc_Computer_C", "units": 1}]), "cannot make"),
    (_broken(("goal_mix",), [{"item_id": "Desc_Rotor_C", "units": 0}]), "positive"),
    (_broken(("infrastructure_policy",), "lowest"), "infrastructure_policy"),
    (_broken(("schema",), "factory-inputs/0"), "this reads"),
    (_broken(("power_mode",), "magic"), "power_mode"),
    (_broken(("power_statistic",), "typical"), "power_statistic"),
    (_broken(("fuel_byproducts",), "burn"), "fuel_byproducts"),
    (_broken(("grid_mw",), 100.0), "report_need"),
    (_broken(("site", "supply"), [{"item_id": "Desc_Water_C", "rate_per_min": 10}]), "never free"),
])
def test_a_bad_document_is_refused_by_name(doc, match):
    with pytest.raises(F.FactoryRunError, match=match):
        F.run_inputs(doc)


def test_missing_and_unknown_keys_are_refused():
    d = _doc()
    del d["goal"]
    with pytest.raises(F.FactoryRunError, match="missing"):
        F.run_inputs(d)
    d = copy.deepcopy(_doc())
    d["extra"] = 1
    with pytest.raises(F.FactoryRunError, match="not known"):
        F.run_inputs(d)


def test_pumped_water_needs_the_water_extractor():
    """Codex on PR #15: Water Extractors come with Coal Power (tier 3); a
    state without it cannot pump Water."""
    d = _doc(tier=2)
    d["site"]["pumps_water"] = True
    d["power_mode"] = "grid"
    with pytest.raises(F.FactoryRunError, match="Build_WaterPump_C is not unlocked"):
        F.run_inputs(d)


@pytest.mark.parametrize("tier, milestones, rate, miner, belt", [
    (1, [], 60.0, "Build_MinerMk1_C", "Mk.1"),                       # Mk.1 belt only
    (3, [ADVANCED_STEEL], 120.0, "Build_MinerMk1_C", "Mk.2"),        # no Logistics Mk.3
    (3, [ADVANCED_STEEL, "Schematic_5-3_C"], 240.0, "Build_MinerMk2_C", "Mk.3"),
])
def test_a_socket_is_capped_by_the_lane_it_can_feed(tier, milestones, rate, miner, belt):
    """One extractor has one output, so a pure node's supply is capped by the
    fastest belt owned (Codex on PR #15, 2026-11-17). With Advanced Steel but
    no Logistics Mk.3, the 120/min belt binds and a pure Mk.1 already fills
    it, so the step-down keeps Mk.1 (Q1)."""
    d = _doc(tier=tier, milestones=milestones, sockets=("BP_ResourceNode114",),
             mix=("Desc_IronIngot_C",))
    run = F.run_inputs(d)
    (p,) = run.sockets
    assert run.scale == pytest.approx(rate)
    assert (p.mark.chosen.extractor_class, p.lane.lanes, p.lane.mark.mark) == (miner, 1, belt)
