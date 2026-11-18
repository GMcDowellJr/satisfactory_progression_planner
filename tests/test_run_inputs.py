"""run_plan.run_inputs and run_plan.handoff: the run track from documents (reframe A20).

The browser planner declares a run as run-inputs/1 and hands a step to the
factory track with every factory declaration explicit. Both are checked in
Python, so the page shows Python's refusal and never fills a gap itself.
"""
from __future__ import annotations

import copy
import importlib.util
import inspect
import pathlib
import sys

import pytest

from production_adapter import Scenario
from production_adapter.lp_backend import PowerStatistic
from progression import playthrough

REPO = pathlib.Path(__file__).resolve().parents[1]
SP = "Desc_SpaceElevatorPart_1_C"
ROCKY_A = ("BP_ResourceNode153", "BP_ResourceNode109", "BP_ResourceNode108", "BP_ResourceNode105_2463",
           "BP_ResourceNode107", "BP_ResourceNode106", "BP_ResourceNode112", "BP_ResourceNode111_3367",
           "BP_ResourceNode103", "BP_ResourceNode102_2068", "BP_ResourceNode104")
BIO = "Build_GeneratorBiomass_Automated_C"


def _module(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


R = _module("run_plan")
F = _module("factory_run")


def _run(**over):
    doc = {
        "schema": "run-inputs/1",
        "playthrough": {"through_tier": 2, "milestones": [], "research": [], "alternates": []},
        "scenario": {"recipe_input_multiplier": 1.0, "machine_power_multiplier": 1.0,
                     "project_assembly_requirement_multiplier": 1.0, "fluid_input_floor": None,
                     "fluid_rounding_unit": "mL"},
        "phase": 1, "horizon_min": None, "horizon_fraction": 1.0,
        "power_statistic": "mean", "fuel_byproducts": "power",
        "standing_generators": {}, "generation_mix": None,
    }
    doc.update(over)
    return doc


def _decl(**over):
    d = {"world_config_id": "default_502094", "label": "rocky", "socket_ids": list(ROCKY_A),
         "supply": [], "pumps_water": False, "power_mode": "report_need",
         "power_statistic": "mean", "fuel_byproducts": "power", "power_from_site": False,
         "goal": "balanced", "grid_mw": 0.0, "spare_mw": 0.0,
         "infrastructure_policy": "highest_then_step_down", "fixed_rate": True}
    d.update(over)
    return d


def test_the_document_plans_what_the_keywords_plan():
    by_doc = R.record(R.run_inputs(_run()))
    by_kw = R.record(R.plan_phase(REPO, state=playthrough(REPO, through_tier=2), scenario=Scenario(),
                                  phase=1, horizon_fraction=1.0, power_statistic=PowerStatistic.MEAN,
                                  fuel_byproducts="power"))
    assert by_doc == by_kw


def test_the_shapes_are_factory_inputs_shapes():
    assert R.PLAYTHROUGH_KEYS == F.PLAYTHROUGH_KEYS
    assert R.SCENARIO_KEYS == F.SCENARIO_KEYS
    from progression.byproducts import FUEL_ROUTES
    assert R.FUEL_ROUTES == FUEL_ROUTES


def test_the_hand_off_takes_every_to_factory_inputs_argument():
    """No factory declaration may come from to_factory_inputs' keyword
    defaults: the hand-off names every parameter after the plan."""
    params = [p for p in inspect.signature(R.to_factory_inputs).parameters if p != "plan"]
    assert sorted(R.HANDOFF_KEYS) == sorted(params)


def test_missing_and_unknown_keys_are_refused():
    doc = _run()
    del doc["power_statistic"]
    with pytest.raises(R.RunPlanError, match=r"missing \['power_statistic'\]"):
        R.run_inputs(doc)
    with pytest.raises(R.RunPlanError, match=r"not known \['tier'\]"):
        R.run_inputs(_run(tier=2))
    bad = _run()
    del bad["playthrough"]["alternates"]
    with pytest.raises(R.RunPlanError, match=r"inputs.playthrough: missing \['alternates'\]"):
        R.run_inputs(bad)


@pytest.mark.parametrize("over, match", [
    ({"schema": "run-inputs/0"}, "this reads run-inputs/1"),
    ({"phase": "1"}, "phase: a whole number"),
    ({"phase": True}, "phase: a whole number"),
    ({"power_statistic": None}, "power_statistic None"),
    ({"fuel_byproducts": "sink"}, "fuel_byproducts 'sink'"),
    ({"standing_generators": None}, "standing_generators: an object"),
    ({"generation_mix": {}}, "generation_mix: null"),
    ({"horizon_min": 30.0}, "exactly one"),
    ({"horizon_fraction": None}, "exactly one"),
])
def test_a_bad_declaration_is_refused_by_name(over, match):
    with pytest.raises(R.RunPlanError, match=match):
        R.run_inputs(_run(**over))


def test_content_refusals_come_from_their_owners():
    from progression.playthrough import PlaythroughError
    from progression.power_stack import PowerStackError
    with pytest.raises(PlaythroughError, match="not in schematics.csv"):
        R.run_inputs(_run(playthrough={"through_tier": None, "milestones": ["Schematic_Nope_C"],
                                       "research": [], "alternates": []}))
    with pytest.raises(PowerStackError, match="non-negative integers"):
        R.run_inputs(_run(standing_generators={BIO: 1.5}))


def test_a_step_hands_off_as_the_keywords_would():
    plan = R.run_inputs(_run())
    by_kw = R.to_factory_inputs(plan, world_config_id="default_502094", label="rocky",
                                socket_ids=ROCKY_A, power_mode="report_need", power_statistic="mean",
                                fuel_byproducts="power", power_from_site=False, goal="balanced",
                                supply=(), pumps_water=False, grid_mw=0.0, spare_mw=0.0,
                                infrastructure_policy="highest_then_step_down", fixed_rate=True)
    doc = R.handoff(_run(), _decl())
    assert doc == by_kw
    run = F.run_inputs(doc)
    assert dict(run.delivered)[SP] == pytest.approx(2.0)


def test_the_hand_off_carries_standing_units_and_the_mix():
    doc = R.handoff(_run(playthrough={"through_tier": 4, "milestones": [], "research": [],
                                      "alternates": []},
                         standing_generators={BIO: 6},
                         generation_mix={"Build_GeneratorCoal_C": 1.0}), _decl())
    assert doc["standing_generators"] == {BIO: 6}
    assert doc["generation_mix"] == {"Build_GeneratorCoal_C": 1.0}


@pytest.mark.parametrize("over, match", [
    ({"fixed_rate": None}, "handoff.fixed_rate: true or false"),
    ({"power_from_site": "no"}, "handoff.power_from_site: true or false"),
    ({"socket_ids": []}, "at least one socket"),
    ({"supply": [{"item_id": "Desc_Coal_C"}]}, r"handoff.supply\[0\]: missing \['rate_per_min'\]"),
])
def test_a_bad_hand_off_is_refused_by_name(over, match):
    with pytest.raises(R.RunPlanError, match=match):
        R.handoff(_run(), _decl(**over))


def test_a_missing_hand_off_key_is_refused():
    d = _decl()
    del d["goal"]
    with pytest.raises(R.RunPlanError, match=r"handoff: missing \['goal'\]"):
        R.handoff(_run(), d)


def test_a_blocked_step_is_not_handed_off():
    blocked = _run(phase=2, playthrough={"through_tier": 3, "milestones": [], "research": [],
                                          "alternates": []}, horizon_fraction=0.25)
    with pytest.raises(R.RunPlanError, match="blocked parts"):
        R.handoff(blocked, _decl())


def test_the_factory_track_still_refuses_what_the_hand_off_passes_through():
    """power_mode is the factory's to refuse, not re-checked here."""
    doc = R.handoff(_run(), _decl(power_mode="island"))
    with pytest.raises(F.FactoryRunError, match="power_mode 'island'"):
        F.run_inputs(copy.deepcopy(doc))
