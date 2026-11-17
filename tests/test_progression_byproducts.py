"""By-product ledger (reframe A16/A17, decided by Greg 2026-11-17): by-products
feed production where the solve finds that useful; what is left is disposed
of: solids to the AWESOME Sink, Fuel to power, Heavy Oil Residue converted to
Fuel, any other fluid named as needing packaging."""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

from production_adapter import load
from production_adapter.contracts import ItemFlow
from progression import playthrough
from progression.byproducts import (
    CONVERT, CONVERT_NOT_OWNED, NEEDS_PACKAGING, POWER, POWER_NOT_OWNED, SINK,
    SINK_NOT_UNLOCKED, flatten, ledger, sink_unlocked,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
RESIN = "Desc_PolymerResin_C"      # solid, 12 sink points
HOR = "Desc_HeavyOilResidue_C"     # liquid
FUEL = "Desc_LiquidFuel_C"         # liquid, burned by the Fuel Generator
WATER = "Desc_Water_C"
PLASTIC = "Desc_Plastic_C"


@pytest.fixture(scope="module")
def data():
    return load(REPO)


def test_the_sink_opens_with_its_milestone():
    assert not sink_unlocked(REPO, playthrough(REPO, through_tier=1))
    assert sink_unlocked(REPO, playthrough(REPO, through_tier=2))


def _owned(tier):
    from progression import availability
    state = playthrough(REPO, through_tier=tier)
    return state, availability(REPO, state).recipe_ids


def test_solids_go_to_the_sink_once_it_is_owned(data):
    state, owned = _owned(5)
    (resin,) = ledger(REPO, data, state, (ItemFlow(RESIN, 30.0, 10.0),), {}, owned)
    assert (resin.rate_per_min, resin.disposition) == (20.0, SINK)
    assert resin.sink_points_per_min == pytest.approx(20.0 * 12)
    early, owned1 = _owned(1)
    (resin,) = ledger(REPO, data, early, (ItemFlow(RESIN, 30.0, 10.0),), {}, owned1)
    assert resin.disposition == SINK_NOT_UNLOCKED


def test_heavy_oil_residue_is_converted_to_fuel_and_the_fuel_burned(data):
    """A17 (Greg, 2026-11-17): HOR -> Residual Fuel (60 -> 40 per refinery),
    and Fuel goes to power (Fuel Generator, 20/min for 250 MW)."""
    state, owned = _owned(5)
    (hor,) = ledger(REPO, data, state, (ItemFlow(HOR, 120.0, 0.0),), {}, owned)
    assert (hor.disposition, hor.recipe_id, hor.machines) == \
        (CONVERT, "Recipe_ResidualFuel_C", pytest.approx(2.0))
    (fuel,) = hor.downstream
    assert (fuel.item_id, fuel.disposition) == (FUEL, POWER)
    assert fuel.rate_per_min == pytest.approx(80.0)
    assert fuel.generators == pytest.approx(4.0) and fuel.power_mw == pytest.approx(1000.0)


def test_leftover_fuel_is_burned_directly(data):
    state, owned = _owned(5)
    (fuel,) = ledger(REPO, data, state, (ItemFlow(FUEL, 40.0, 0.0),), {}, owned)
    assert (fuel.disposition, fuel.generator_class) == (POWER, "Build_GeneratorFuel_C")


def test_before_the_chain_is_unlocked_it_is_named(data):
    state, owned = _owned(3)
    (hor,) = ledger(REPO, data, state, (ItemFlow(HOR, 60.0, 0.0),), {}, owned)
    assert hor.disposition == CONVERT_NOT_OWNED
    (fuel,) = ledger(REPO, data, state, (ItemFlow(FUEL, 20.0, 0.0),), {}, owned)
    assert fuel.disposition == POWER_NOT_OWNED


def test_any_other_fluid_needs_packaging(data):
    state, owned = _owned(5)
    (water,) = ledger(REPO, data, state, (ItemFlow(WATER, 10.0, 0.0),), {}, owned)
    assert water.disposition == NEEDS_PACKAGING
    assert [b.item_id for b in flatten((water,))] == [WATER]


def test_what_is_consumed_or_delivered_is_not_a_by_product(data):
    flows = (ItemFlow(RESIN, 10.0, 10.0), ItemFlow(PLASTIC, 40.0, 0.0))
    state, owned = _owned(5)
    assert ledger(REPO, data, state, flows, {PLASTIC: 40.0}, owned) == ()


def test_the_factory_track_reports_its_by_products():
    spec = importlib.util.spec_from_file_location("factory_run", REPO / "tools" / "factory_run.py")
    F = sys.modules.get("factory_run") or importlib.util.module_from_spec(spec)
    if "factory_run" not in sys.modules:
        sys.modules["factory_run"] = F
        spec.loader.exec_module(F)
    doc = {
        "schema": "factory-inputs/1", "world_config_id": "default_502094",
        "playthrough": {"through_tier": 5, "milestones": [], "research": [], "alternates": []},
        "scenario": {"recipe_input_multiplier": 1.0, "machine_power_multiplier": 1.0,
                     "project_assembly_requirement_multiplier": 1.0, "fluid_input_floor": None,
                     "fluid_rounding_unit": "mL"},
        "site": {"label": "oil", "socket_ids": ["BP_ResourceNode100", "BP_ResourceNode14_609"],
                 "supply": [], "pumps_water": False},
        "goal_mix": [{"item_id": PLASTIC, "units": 1}], "goal": "balanced",
        "power_mode": "report_need", "grid_mw": 0.0, "spare_mw": 0.0, "target_scale": None,
        "infrastructure_policy": "highest_then_step_down",
    }
    run = F.run_inputs(doc)
    (hor,) = run.byproducts
    assert (hor.item_id, hor.disposition) == (HOR, CONVERT)
    assert hor.downstream[0].disposition == POWER
    assert F.record(run)["byproducts"][0]["downstream"][0]["disposition"] == POWER
