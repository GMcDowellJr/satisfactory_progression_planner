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


# --- power in the solve (A25.3 P1; mechanics A29) ---------------------------
#
# Iron Plate 20/min: 1 smelter (4 MW) + 1 constructor (4 MW) = 8 MW at 1x.
# Coal generator: 15 coal + 45 water -> 75 MW. Grid and spare are declared.

from production_adapter import GeneratorFuel, PowerBalance  # noqa: E402
from production_adapter.gamedata import load_generators  # noqa: E402

COAL, WATER = "Desc_Coal_C", "Desc_Water_C"


@pytest.fixture(scope="module")
def coal_gen():
    rows = [g for g in load_generators(REPO)
            if g.generator_class == "Build_GeneratorCoal_C" and g.fuel_item_id == COAL]
    assert len(rows) == 1
    return rows[0]


def test_the_loader_reads_the_coal_generator_row(coal_gen):
    assert coal_gen == GeneratorFuel(
        generator_class="Build_GeneratorCoal_C", fuel_item_id=COAL,
        burn_rate_per_min=15.0, power_mw=75.0, supplemental=((WATER, 45.0),),
    )
    fuel_gens = {g.fuel_item_id for g in load_generators(REPO) if g.generator_class == "Build_GeneratorFuel_C"}
    assert "Desc_LiquidFuel_C" in fuel_gens


def _plate_request(power, caps=((IRON_ORE, 30.0),)):
    return DistrictRequest(
        targets=(DistrictTarget(IRON_PLATE),), allowed_recipes=IRON_SET,
        resource_caps=tuple(ResourceCap(i, r) for i, r in caps), power=power,
    )


def test_a_generator_is_built_to_cover_the_lanes(backend, data, coal_gen):
    """8 MW of lanes from a 0 MW grid: 8/75 of a coal generator, burning 1.6
    coal and 4.8 water per minute. The output is unchanged: power is not
    scarce, only priced."""
    r = backend.solve_district(_plate_request(
        PowerBalance(generators=(coal_gen,)),
        caps=((IRON_ORE, 30.0), (COAL, 15.0), (WATER, 45.0)),
    ), data)
    assert _rates(r) == pytest.approx({IRON_PLATE: 20.0}, abs=1e-6)
    pw = r.power
    assert pw.lane_mw == pytest.approx(8.0, abs=1e-6)
    assert pw.generated_mw == pytest.approx(8.0, abs=1e-6)
    assert pw.margin_mw == pytest.approx(0.0, abs=1e-6) and pw.binding
    [g] = pw.generators
    assert g.count == pytest.approx(8.0 / 75.0, abs=1e-6)
    assert g.fuel_per_min == pytest.approx(1.6, abs=1e-6)
    assert dict(g.supplemental_per_min) == pytest.approx({WATER: 4.8}, abs=1e-6)
    raw = {x.item_id: x.rate_per_min for x in r.plan.raw_inputs}
    assert raw == pytest.approx({IRON_ORE: 30.0, COAL: 1.6, WATER: 4.8}, abs=1e-6)


def test_the_grid_and_the_spare_margin_enter_the_row(backend, data):
    """10 MW grid, 2 MW spare, no generators: exactly the 8 MW the lanes
    need. The row is tight and no generator exists to loosen it."""
    r = backend.solve_district(_plate_request(PowerBalance(grid_mw=10.0, spare_mw=2.0)), data)
    assert _rates(r) == pytest.approx({IRON_PLATE: 20.0}, abs=1e-6)
    assert r.power.generators == () and r.power.binding
    assert r.power.margin_mw == pytest.approx(0.0, abs=1e-6)


def test_fuel_is_contested_with_production_and_power_can_be_the_limit(backend, data, coal_gen):
    """Coal capped at 1.5/min: 0.1 of a generator, 7.5 MW, so the plate chain
    runs at 7.5/8 and makes 18.75 plate/min although 30 ore would make 20.
    The power row binds; the ore cap does not."""
    r = backend.solve_district(_plate_request(
        PowerBalance(generators=(coal_gen,)),
        caps=((IRON_ORE, 30.0), (COAL, 1.5), (WATER, 45.0)),
    ), data)
    assert _rates(r) == pytest.approx({IRON_PLATE: 18.75}, abs=1e-6)
    assert r.power.binding
    assert r.power.shadow_price == pytest.approx(2.5, abs=1e-6)   # 20 plate per 8 MW
    assert {b.item_id for b in r.binding} == {COAL, WATER} - {WATER}
    assert r.power.generators[0].count == pytest.approx(0.1, abs=1e-6)


def test_no_supply_at_all_means_no_output_not_an_error(backend, data):
    """Nothing to burn and no grid: the solve reports 0 with the row binding
    rather than failing, because no floor was declared."""
    r = backend.solve_district(_plate_request(PowerBalance()), data)
    assert _rates(r) == pytest.approx({IRON_PLATE: 0.0}, abs=1e-9)
    assert r.power.binding and r.power.lane_mw == pytest.approx(0.0, abs=1e-9)


def test_a_floor_the_power_cannot_carry_is_refused_by_name(backend, data):
    with pytest.raises(Infeasible, match="even alone: Desc_IronPlate_C 1/min"):
        backend.solve_district(DistrictRequest(
            targets=(DistrictTarget(IRON_PLATE, minimum_rate=1.0),), allowed_recipes=IRON_SET,
            resource_caps=(ResourceCap(IRON_ORE, 30.0),), power=PowerBalance(),
        ), data)


def test_extraction_at_nameplate_is_a_constant_on_the_row(backend, data):
    """8 MW lanes + 3 MW extraction against an 11 MW grid: tight; against 10
    MW: 17.5 plate (7/8 of the chain)."""
    r = backend.solve_district(_plate_request(PowerBalance(grid_mw=11.0, extraction_mw=3.0)), data)
    assert _rates(r) == pytest.approx({IRON_PLATE: 20.0}, abs=1e-6)
    r = backend.solve_district(_plate_request(PowerBalance(grid_mw=10.0, extraction_mw=3.0)), data)
    assert _rates(r) == pytest.approx({IRON_PLATE: 17.5}, abs=1e-6)
    assert r.power.extraction_mw == 3.0


def test_the_demand_solve_is_untouched_by_the_power_columns(backend, data):
    """`solve` passes no PowerBalance: no generator column, no row. Pinned so
    the shared matrices cannot grow a row the demand solve did not ask for."""
    from production_adapter import OutputTarget, SolveRequest
    p = backend._build(SolveRequest(outputs=(OutputTarget(IRON_PLATE, 20.0),),
                                    allowed_recipes=IRON_SET), data)
    assert p.n_g == 0 and p.a_ub is None and p.b_ub is None
