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
    (resin,) = ledger(REPO, data, state, (ItemFlow(RESIN, 30.0, 10.0),), {}, owned, fuel_route="power")
    assert (resin.rate_per_min, resin.disposition) == (20.0, SINK)
    assert resin.sink_points_per_min == pytest.approx(20.0 * 12)
    early, owned1 = _owned(1)
    (resin,) = ledger(REPO, data, early, (ItemFlow(RESIN, 30.0, 10.0),), {}, owned1, fuel_route="power")
    assert resin.disposition == SINK_NOT_UNLOCKED


def test_heavy_oil_residue_is_converted_to_fuel_and_the_fuel_burned(data):
    """A17 (Greg, 2026-11-17): HOR -> Residual Fuel (60 -> 40 per refinery),
    and Fuel goes to power (Fuel Generator, 20/min for 250 MW)."""
    state, owned = _owned(5)
    (hor,) = ledger(REPO, data, state, (ItemFlow(HOR, 120.0, 0.0),), {}, owned, fuel_route="power")
    assert (hor.disposition, hor.recipe_id, hor.machines) == \
        (CONVERT, "Recipe_ResidualFuel_C", pytest.approx(2.0))
    (fuel,) = hor.downstream
    assert (fuel.item_id, fuel.disposition) == (FUEL, POWER)
    assert fuel.rate_per_min == pytest.approx(80.0)
    assert fuel.generators == pytest.approx(4.0) and fuel.power_mw == pytest.approx(1000.0)


def test_leftover_fuel_is_burned_directly(data):
    state, owned = _owned(5)
    (fuel,) = ledger(REPO, data, state, (ItemFlow(FUEL, 40.0, 0.0),), {}, owned, fuel_route="power")
    assert (fuel.disposition, fuel.generator_class) == (POWER, "Build_GeneratorFuel_C")


def test_before_the_chain_is_unlocked_it_is_named(data):
    state, owned = _owned(3)
    (hor,) = ledger(REPO, data, state, (ItemFlow(HOR, 60.0, 0.0),), {}, owned, fuel_route="power")
    assert hor.disposition == CONVERT_NOT_OWNED
    (fuel,) = ledger(REPO, data, state, (ItemFlow(FUEL, 20.0, 0.0),), {}, owned, fuel_route="power")
    assert fuel.disposition == POWER_NOT_OWNED


def test_any_other_fluid_needs_packaging(data):
    state, owned = _owned(5)
    (water,) = ledger(REPO, data, state, (ItemFlow(WATER, 10.0, 0.0),), {}, owned, fuel_route="power")
    assert water.disposition == NEEDS_PACKAGING
    assert [b.item_id for b in flatten((water,))] == [WATER]


def test_what_is_consumed_or_delivered_is_not_a_by_product(data):
    flows = (ItemFlow(RESIN, 10.0, 10.0), ItemFlow(PLASTIC, 40.0, 0.0))
    state, owned = _owned(5)
    assert ledger(REPO, data, state, flows, {PLASTIC: 40.0}, owned, fuel_route="power") == ()


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
        "power_mode": "report_need", "power_statistic": "mean", "grid_mw": 0.0, "spare_mw": 0.0, "target_scale": None,
        "infrastructure_policy": "highest_then_step_down",
        "fuel_byproducts": "power", "standing_generators": {},
    }
    run = F.run_inputs(doc)
    (hor,) = run.byproducts
    assert (hor.item_id, hor.disposition) == (HOR, CONVERT)
    assert hor.downstream[0].disposition == POWER
    assert F.record(run)["byproducts"][0]["downstream"][0]["disposition"] == POWER


# --- Codex review on PR #15, 2026-11-17 ---------------------------------------

def test_a_solid_with_no_sink_points_is_unsinkable(data):
    """Uranium Waste has 0 sink points: storage or processing, never the sink."""
    from progression.byproducts import UNSINKABLE
    state, owned = _owned(9)
    (waste,) = ledger(REPO, data, state, (ItemFlow("Desc_NuclearWaste_C", 10.0, 0.0),), {},
                      owned, fuel_route="power")
    assert waste.disposition == UNSINKABLE and waste.sink_points_per_min is None


def test_generator_fuel_and_waste_are_folded_into_the_flows():
    """A solve's items are recipe flows only: fuel a generator burns is not in
    them, and neither is the waste it makes."""
    from production_adapter.contracts import GeneratorUse
    from production_adapter.gamedata import load_generators
    from progression.byproducts import with_generators

    rows = load_generators(REPO)
    nuke = next(g for g in rows if g.byproduct)
    use = GeneratorUse(nuke.generator_class, nuke.fuel_item_id, count=2.0,
                       mw=2 * nuke.power_mw, fuel_per_min=2 * nuke.burn_rate_per_min,
                       supplemental_per_min=tuple((i, 2 * r) for i, r in nuke.supplemental))
    flows = (ItemFlow(nuke.fuel_item_id, 2 * nuke.burn_rate_per_min, 0.0),)
    out = {f.item_id: f for f in with_generators(flows, (use,), rows)}
    fuel = out[nuke.fuel_item_id]
    assert fuel.produced_per_min - fuel.consumed_per_min == pytest.approx(0.0)
    (waste_item, waste_rate), = nuke.byproduct
    assert out[waste_item].produced_per_min == pytest.approx(2 * waste_rate)


def test_in_grid_mode_burned_fuel_is_not_a_leftover():
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
        "power_mode": "grid", "power_statistic": "mean", "grid_mw": 0.0, "spare_mw": 0.0,
        "target_scale": None, "infrastructure_policy": "highest_then_step_down",
        "fuel_byproducts": "power", "standing_generators": {},
    }
    run = F.run_inputs(doc)
    # measured 2026-11-17: the site makes Fuel and burns ~27/min of it
    assert {g.fuel_item_id for g in run.power.generators} == {FUEL}
    # so Fuel is no top-level leftover; it appears only downstream of the
    # residue's conversion (before the fix it was also listed on its own)
    assert FUEL not in {b.item_id for b in run.byproducts}


# --- reframe A18 (Greg, 2026-11-17): fuel to a generator, or packaged ----------

def test_packaged_fuel_goes_to_storage_with_overflow_to_the_sink(data):
    """'all fuel goes to generator or gets packaged for use [in] recipes that
    require unpacking or storage (with overflow to sink) for jet-pack and
    vehicles'. Packaged Fuel: 40 Fuel + 40 Empty Canisters -> 40 Packaged Fuel
    per Packager."""
    from progression.byproducts import PACKAGE, STORE_OVERFLOW_SINK
    state, owned = _owned(5)
    (fuel,) = ledger(REPO, data, state, (ItemFlow(FUEL, 80.0, 0.0),), {}, owned,
                     fuel_route="package")
    assert (fuel.disposition, fuel.recipe_id) == (PACKAGE, "Recipe_Fuel_C")
    assert fuel.machines == pytest.approx(2.0) and fuel.containers_per_min == pytest.approx(80.0)
    (stored,) = fuel.downstream
    assert (stored.item_id, stored.disposition) == ("Desc_Fuel_C", STORE_OVERFLOW_SINK)
    assert stored.sink_points_per_min == pytest.approx(80.0 * 270)


def test_converted_residue_follows_the_declared_fuel_route(data):
    from progression.byproducts import PACKAGE
    state, owned = _owned(5)
    (hor,) = ledger(REPO, data, state, (ItemFlow(HOR, 60.0, 0.0),), {}, owned,
                    fuel_route="package")
    assert hor.disposition == CONVERT and hor.downstream[0].disposition == PACKAGE


def test_the_fuel_route_has_no_default(data):
    import inspect
    assert inspect.signature(ledger).parameters["fuel_route"].default is inspect.Parameter.empty
    state, owned = _owned(5)
    with pytest.raises(ValueError, match="fuel_route"):
        ledger(REPO, data, state, (), {}, owned, fuel_route="burn")


def test_every_generator_fluid_has_one_packaging_recipe(data):
    """Read from the data (Codex on PR #15: a hand list missed the gases)."""
    from production_adapter.gamedata import load_generators
    from progression.byproducts import packaging_recipe
    fluids = {g.fuel_item_id for g in load_generators(REPO)
              if data.items[g.fuel_item_id].form != "solid"}
    found = {f: packaging_recipe(data, f) for f in sorted(fluids)}
    assert all(v is not None for v in found.values()), found
    assert found["Desc_RocketFuel_C"][1] == "Desc_GasTank_C"
    assert found["Desc_LiquidFuel_C"][1] == "Desc_FluidCanister_C"


def test_a_declared_package_route_is_never_overridden_by_power(data):
    """Rocket Fuel under fuel_route 'package' is packaged (or named not owned),
    never burned."""
    from progression.byproducts import PACKAGE, PACKAGE_NOT_OWNED
    state, owned = _owned(9)
    flows = (ItemFlow("Desc_RocketFuel_C", 20.0, 0.0),)
    # at tier 9 alone the packaging recipe is not owned (it needs research)
    (rf,) = ledger(REPO, data, state, flows, {}, owned, fuel_route="package")
    assert (rf.disposition, rf.recipe_id) == (PACKAGE_NOT_OWNED, "Recipe_PackagedRocketFuel_C")
    (rf,) = ledger(REPO, data, state, flows, {}, owned + ("Recipe_PackagedRocketFuel_C",),
                   fuel_route="package")
    assert rf.disposition == PACKAGE and rf.container_item_id == "Desc_GasTank_C"
    assert rf.containers_per_min == pytest.approx(10.0)   # 120 fuel : 60 tanks


def test_packaged_overflow_needs_the_sink(data):
    """Codex on PR #15: storage stays, but without the AWESOME Sink the overflow
    route is named unavailable, with no sink points."""
    from progression.byproducts import PACKAGE, STORE_NO_SINK
    from progression import availability
    tier5 = playthrough(REPO, through_tier=5)
    no_sink = playthrough(REPO, milestones=[m for m in tier5.milestones if m != "Schematic_2-5_C"])
    owned = availability(REPO, no_sink).recipe_ids
    (fuel,) = ledger(REPO, data, no_sink, (ItemFlow(FUEL, 20.0, 0.0),), {}, owned,
                     fuel_route="package")
    assert fuel.disposition == PACKAGE
    (stored,) = fuel.downstream
    assert stored.disposition == STORE_NO_SINK and stored.sink_points_per_min is None
