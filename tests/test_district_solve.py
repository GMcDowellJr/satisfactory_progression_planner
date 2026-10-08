"""`LpBackend.solve_district`: the supply-side solve, crossover A27.2.

    maximises   sum w_i * out_i within the caps, after every floor
    refuses     a floor that cannot be met (named; alone first, then jointly
                with the scale that would fit), a weighted output no cap
                bounds (Unbounded), unconsumed=forbid
    reports     per-target rates in request order, excluded targets at 0,
                binding caps with shadow prices, the goal's weights
    leaves      `solve` untouched: its cases in test_production_lp_backend.py
                are the regression guard for the shared matrices

Real reference data, canonical scenario, small explicit recipe sets so each
figure can be checked by hand.
"""
from __future__ import annotations

import pathlib

import pytest

from production_adapter import (
    AllowedRecipes, DistrictRequest, DistrictTarget, RecipeMode, ResourceCap, Weights, load,
)
from production_adapter.lp_backend import (
    Infeasible, LpBackend, PowerStatistic, Unbounded, UnconsumedMode,
)

REPO = pathlib.Path(__file__).resolve().parents[1]

IRON_ORE, COPPER_ORE = "Desc_OreIron_C", "Desc_OreCopper_C"
IRON_INGOT, IRON_PLATE, IRON_ROD, SCREW = (
    "Desc_IronIngot_C", "Desc_IronPlate_C", "Desc_IronRod_C", "Desc_IronScrew_C",
)
COPPER_INGOT, WIRE = "Desc_CopperIngot_C", "Desc_Wire_C"
#: Iron Ingot 30 ore -> 30 ingot; Plate 30 ingot -> 20 plate; Rod 15 ingot -> 15 rod;
#: Screw 10 rod -> 40 screw; Copper Ingot 30 ore -> 30; Wire 15 ingot -> 30 wire
IRON_SET = AllowedRecipes(mode=RecipeMode.EXPLICIT, recipe_ids=(
    "Recipe_IngotIron_C", "Recipe_IronPlate_C", "Recipe_IronRod_C", "Recipe_Screw_C",
))
IRON_COPPER_SET = AllowedRecipes(mode=RecipeMode.EXPLICIT, recipe_ids=(
    "Recipe_IngotIron_C", "Recipe_IronPlate_C", "Recipe_IngotCopper_C", "Recipe_Wire_C",
))


@pytest.fixture(scope="module")
def data():
    return load(REPO)


@pytest.fixture(scope="module")
def backend():
    return LpBackend(power_statistic=PowerStatistic.MEAN)


def _rates(response):
    return {t.item_id: t.rate_per_min for t in response.targets}


def test_one_target_takes_the_whole_cap(backend, data):
    """30 ore/min -> 30 ingot -> 20 plate. The cap binds with a shadow price of
    2/3 plate per ore."""
    r = backend.solve_district(DistrictRequest(
        targets=(DistrictTarget(IRON_PLATE),), allowed_recipes=IRON_SET,
        resource_caps=(ResourceCap(IRON_ORE, 30.0),),
    ), data)
    assert _rates(r) == pytest.approx({IRON_PLATE: 20.0}, abs=1e-6)
    assert r.weighted_output == pytest.approx(20.0, abs=1e-6)
    assert [b.item_id for b in r.binding] == [IRON_ORE]
    assert r.binding[0].cap_per_min == 30.0
    assert r.binding[0].shadow_price == pytest.approx(2.0 / 3.0, abs=1e-6)
    # the plan's ledger carries the output as the item's net flow
    plate = [f for f in r.plan.items if f.item_id == IRON_PLATE][0]
    assert plate.net_per_min == pytest.approx(20.0, abs=1e-6)


def test_weights_decide_where_the_cap_goes_and_floors_hold_first(backend, data):
    """Plate: 2/3 per ore. Rod: 1 per ore. Equal weights -> all rods. A plate
    floor of 2/min costs 3 ore and is met before the rest goes to rods."""
    r = backend.solve_district(DistrictRequest(
        targets=(DistrictTarget(IRON_PLATE, minimum_rate=2.0), DistrictTarget(IRON_ROD)),
        allowed_recipes=IRON_SET, resource_caps=(ResourceCap(IRON_ORE, 30.0),),
    ), data)
    assert _rates(r) == pytest.approx({IRON_PLATE: 2.0, IRON_ROD: 27.0}, abs=1e-6)
    plate, rod = r.targets
    assert plate.at_floor and not rod.at_floor
    assert r.weighted_output == pytest.approx(29.0, abs=1e-6)


def test_a_heavier_weight_moves_the_cap(backend, data):
    """Plate weighted 2: 2 * 2/3 > 1, so the ore goes to plate."""
    r = backend.solve_district(DistrictRequest(
        targets=(DistrictTarget(IRON_PLATE, weight=2.0), DistrictTarget(IRON_ROD)),
        allowed_recipes=IRON_SET, resource_caps=(ResourceCap(IRON_ORE, 30.0),),
    ), data)
    assert _rates(r) == pytest.approx({IRON_PLATE: 20.0, IRON_ROD: 0.0}, abs=1e-6)


def test_an_excluded_target_is_reported_at_zero_in_request_order(backend, data):
    r = backend.solve_district(DistrictRequest(
        targets=(DistrictTarget(IRON_ROD, weight=0.0), DistrictTarget(IRON_PLATE)),
        allowed_recipes=IRON_SET, resource_caps=(ResourceCap(IRON_ORE, 30.0),),
    ), data)
    assert [t.item_id for t in r.targets] == [IRON_ROD, IRON_PLATE]
    assert r.targets[0].excluded and r.targets[0].rate_per_min == 0.0
    assert not r.targets[1].excluded


def test_weight_zero_with_a_floor_is_a_trickle(backend, data):
    """Held at its floor and no more: the rest of the ore goes to the weighted target."""
    r = backend.solve_district(DistrictRequest(
        targets=(DistrictTarget(IRON_PLATE, weight=0.0, minimum_rate=2.0), DistrictTarget(IRON_ROD)),
        allowed_recipes=IRON_SET, resource_caps=(ResourceCap(IRON_ORE, 30.0),),
    ), data)
    assert _rates(r) == pytest.approx({IRON_PLATE: 2.0, IRON_ROD: 27.0}, abs=1e-6)
    assert r.targets[0].at_floor and not r.targets[0].excluded


def test_a_floor_unreachable_alone_is_named(backend, data):
    with pytest.raises(Infeasible, match=r"even alone: Desc_IronPlate_C 21/min"):
        backend.solve_district(DistrictRequest(
            targets=(DistrictTarget(IRON_PLATE, minimum_rate=21.0),),
            allowed_recipes=IRON_SET, resource_caps=(ResourceCap(IRON_ORE, 30.0),),
        ), data)


def test_floors_reachable_alone_but_not_together_name_the_scale_and_the_cap(backend, data):
    """Plate 10 needs 15 ore, rod 20 needs 20 ore: 35 > 30. Together they fit
    to 30/35 of their values, and the ore cap is what binds."""
    with pytest.raises(Infeasible) as e:
        backend.solve_district(DistrictRequest(
            targets=(DistrictTarget(IRON_PLATE, minimum_rate=10.0),
                     DistrictTarget(IRON_ROD, minimum_rate=20.0)),
            allowed_recipes=IRON_SET, resource_caps=(ResourceCap(IRON_ORE, 30.0),),
        ), data)
    msg = str(e.value)
    assert "reachable alone but not together" in msg
    assert "0.857" in msg
    assert "Desc_OreIron_C" in msg


def test_an_uncapped_weighted_output_is_refused_as_unbounded(backend, data):
    with pytest.raises(Unbounded, match="Desc_OreIron_C"):
        backend.solve_district(DistrictRequest(
            targets=(DistrictTarget(IRON_PLATE),), allowed_recipes=IRON_SET,
        ), data)


def test_forbid_mode_has_nothing_to_maximise(data):
    strict = LpBackend(PowerStatistic.MEAN, unconsumed=UnconsumedMode.FORBID)
    with pytest.raises(NotImplementedError, match="leftover"):
        strict.solve_district(DistrictRequest(
            targets=(DistrictTarget(IRON_PLATE),), allowed_recipes=IRON_SET,
            resource_caps=(ResourceCap(IRON_ORE, 30.0),),
        ), data)


def test_the_goal_is_carried_and_only_breaks_ties(backend, data):
    """Two caps, two targets in different chains: each cap goes to its own
    product whatever the goal, so the goal cannot change the rates, and it
    is printed back unchanged."""
    goal = Weights(resources=0.0, power=1.0, buildings=0.0)
    r = backend.solve_district(DistrictRequest(
        targets=(DistrictTarget(IRON_PLATE), DistrictTarget(WIRE)),
        allowed_recipes=IRON_COPPER_SET,
        resource_caps=(ResourceCap(IRON_ORE, 30.0), ResourceCap(COPPER_ORE, 15.0)),
        weights=goal,
    ), data)
    assert r.goal == goal
    assert _rates(r) == pytest.approx({IRON_PLATE: 20.0, WIRE: 30.0}, abs=1e-6)
    assert {b.item_id for b in r.binding} == {IRON_ORE, COPPER_ORE}


def test_a_zero_cap_closes_a_resource_and_reports_its_price(backend, data):
    """Copper capped at 0: no wire, and the binding report says what a unit of
    copper would be worth here (one wire per half ore: 2.0)."""
    r = backend.solve_district(DistrictRequest(
        targets=(DistrictTarget(IRON_PLATE), DistrictTarget(WIRE)),
        allowed_recipes=IRON_COPPER_SET,
        resource_caps=(ResourceCap(IRON_ORE, 30.0), ResourceCap(COPPER_ORE, 0.0)),
    ), data)
    assert _rates(r) == pytest.approx({IRON_PLATE: 20.0, WIRE: 0.0}, abs=1e-6)
    copper = [b for b in r.binding if b.item_id == COPPER_ORE][0]
    assert copper.cap_per_min == 0.0
    assert copper.shadow_price == pytest.approx(2.0, abs=1e-6)
