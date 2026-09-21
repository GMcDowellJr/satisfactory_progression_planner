"""Section 8 of docs/decisions/production_lp_formulation.md, executed.

The validation order is the record's, and the first two gate the rest:

    1  against tests/_demand_oracle.py, machine equivalents to four decimals
    2  against section 3.3 of the solver-selection record, Smart Plating 1/min
    3  raw-material columns only from section 3.2
    4  degeneracy: the same request twice, recipe order shuffled, identical answer
    5  cycles: no inverse pair active in both directions

Item 3 is where the reference figures stop agreeing with our own data; see
`test_versatile_framework_raw_column_contradicts_phase_0`, which pins the
divergence rather than asserting around it.
"""
import pathlib

import pytest

from _demand_oracle import demand
from _fixed_recipe_expectations import expectations
from production_adapter import (
    AllowedRecipes, CHALLENGE_1_25X_2X, OutputTarget, RecipeMode, ResourceCap,
    Scenario, SolveRequest, Weights, load, registered,
)
from production_adapter.lp_backend import (
    Infeasible, LpBackend, PowerStatistic, UnconsumedMode,
)

REPO = pathlib.Path(__file__).resolve().parents[1]

IRON_PLATE = "Desc_IronPlate_C"
REINFORCED_PLATE = "Desc_IronPlateReinforced_C"
SMART_PLATING = "Desc_SpaceElevatorPart_1_C"
VERSATILE_FRAMEWORK = "Desc_SpaceElevatorPart_2_C"
AUTOMATED_WIRING = "Desc_SpaceElevatorPart_3_C"
IRON_ORE = "Desc_OreIron_C"
COAL = "Desc_Coal_C"
COPPER_ORE = "Desc_OreCopper_C"


@pytest.fixture(scope="module")
def data():
    return load(REPO)


@pytest.fixture(scope="module")
def backend():
    # Every producer in these cases is fixed-power, so min == mean == max and the
    # statistic cannot change an answer. That is what keeps these cases
    # D2-independent while D2 is deferred (record section 12.1).
    return LpBackend(power_statistic=PowerStatistic.MEAN)


def _solve(backend, data, *targets, **kwargs):
    request = SolveRequest(
        outputs=tuple(OutputTarget(i, r) for i, r in targets), **kwargs
    )
    return backend.solve(request, data)


def _multipliers(response):
    return {u.recipe_id: u.machine_equivalents for u in response.recipes}


def _raw(response):
    return {r.item_id: r.rate_per_min for r in response.raw_inputs}


# --- 1. against the independent demand oracle -----------------------------

ORACLE_CASES = [
    (IRON_PLATE, 20.0),
    (REINFORCED_PLATE, 5.0),
    (SMART_PLATING, 1.0),
    (VERSATILE_FRAMEWORK, 6.0),
    (AUTOMATED_WIRING, 1.2),
]


@pytest.mark.parametrize("item,rate", ORACLE_CASES)
def test_matches_the_demand_oracle_to_four_decimals(backend, data, item, rate):
    """Section 8 item 1. Independent of every decision in the record."""
    expected = demand(item, rate).recipe_multipliers
    actual = _multipliers(_solve(backend, data, (item, rate)))
    assert set(actual) == set(expected)
    for recipe_id, multiplier in expected.items():
        assert actual[recipe_id] == pytest.approx(multiplier, abs=1e-4)


@pytest.mark.parametrize("item,rate", ORACLE_CASES)
def test_matches_the_oracle_raw_inputs(backend, data, item, rate):
    expected = demand(item, rate).raw_inputs
    actual = _raw(_solve(backend, data, (item, rate)))
    assert set(actual) == set(expected)
    for item_id, value in expected.items():
        assert actual[item_id] == pytest.approx(value, abs=1e-4)


@pytest.mark.parametrize("item,rate", ORACLE_CASES)
def test_power_and_machines_match_the_fixed_recipe_expectations(backend, data, item, rate):
    """The layer the oracle deliberately omits, via _fixed_recipe_expectations."""
    response = _solve(backend, data, (item, rate))
    expected = expectations(demand(item, rate).recipe_multipliers)
    assert expected.power.is_degenerate, "case is no longer D2-independent"
    assert response.power.scenario_mw == pytest.approx(expected.power.mean_mw, abs=1e-4)
    actual = {m.producer_class: m.effective_count for m in response.machines}
    assert set(actual) == set(expected.machines_by_producer_class)
    for producer_class, count in expected.machines_by_producer_class.items():
        assert actual[producer_class] == pytest.approx(count, abs=1e-4)


# --- 2. Smart Plating, the one section 3 figure that survives --------------

SMART_PLATING_MULTIPLIERS = {
    "Recipe_IngotIron_C": 0.7750,
    "Recipe_IronPlateReinforced_C": 0.2000,
    "Recipe_IronPlate_C": 0.3000,
    "Recipe_IronRod_C": 0.9500,
    "Recipe_Rotor_C": 0.2500,
    "Recipe_Screw_C": 0.9250,
    "Recipe_SpaceElevatorPart_1_C": 0.5000,
}


def test_smart_plating_reproduces_section_3_3(backend, data):
    """Section 8 item 2. Seven recipes, the exact multipliers, Iron Ore 23.25."""
    response = _solve(backend, data, (SMART_PLATING, 1.0))
    assert len(response.recipes) == 7
    actual = _multipliers(response)
    assert set(actual) == set(SMART_PLATING_MULTIPLIERS)
    for recipe_id, multiplier in SMART_PLATING_MULTIPLIERS.items():
        assert actual[recipe_id] == pytest.approx(multiplier, abs=1e-4)
    assert _raw(response) == pytest.approx({IRON_ORE: 23.25}, abs=1e-4)


def test_smart_plating_power_is_26_05_mw(backend, data):
    """Record section 12.4. Not section 3.2's 27.31, which carries the P1 gap."""
    response = _solve(backend, data, (SMART_PLATING, 1.0))
    assert response.power.scenario_mw == pytest.approx(26.05, abs=1e-4)
    assert response.power.canonical_mw == pytest.approx(26.05, abs=1e-4)
    assert response.power.min_mw == response.power.max_mw == pytest.approx(26.05, abs=1e-4)


def test_iron_plate_power_is_8_mw(backend, data):
    """Record section 10.3, the first validation case it asked for."""
    response = _solve(backend, data, (IRON_PLATE, 20.0))
    assert response.power.scenario_mw == pytest.approx(8.0, abs=1e-4)
    assert _raw(response) == pytest.approx({IRON_ORE: 30.0}, abs=1e-4)


# --- 3. raw-material columns from section 3.2 -----------------------------

def test_reinforced_iron_plate_raw_column(backend, data):
    assert _raw(_solve(backend, data, (REINFORCED_PLATE, 5.0))) == pytest.approx(
        {IRON_ORE: 60.0}, abs=1e-4
    )


def test_automated_wiring_raw_column(backend, data):
    assert _raw(_solve(backend, data, (AUTOMATED_WIRING, 1.2))) == pytest.approx(
        {COAL: 5.4, COPPER_ORE: 28.8, IRON_ORE: 5.4}, abs=1e-4
    )


def test_versatile_framework_raw_column_contradicts_phase_0(backend, data):
    """Section 3.2 reports Coal 144.00 and Iron Ore 144.00. Iron Ore is 216.00.

    Two independent computations against our reference layer agree on 216 — this
    backend and `tests/_demand_oracle.py`, which shares no code with it. The
    arithmetic is not close: Versatile Framework 6/min needs 36 Steel Beam/min
    (144 ore via steel) AND 3 Modular Frame/min, whose Reinforced Iron Plate and
    Iron Rod branch draws a further 72 ore. Section 3.2's figure is the steel
    branch alone.

    The session handoff lists section 3.2's raw-material columns as usable. This
    row is not. Pinned rather than worked around, in the shape of
    `test_reconstructs_phase_0_iron_plate_figure`.
    """
    actual = _raw(_solve(backend, data, (VERSATILE_FRAMEWORK, 6.0)))
    assert actual == pytest.approx({COAL: 144.0, IRON_ORE: 216.0}, abs=1e-4)
    assert actual[IRON_ORE] != pytest.approx(144.0, abs=1e-4)
    assert demand(VERSATILE_FRAMEWORK, 6.0).raw_inputs[IRON_ORE] == pytest.approx(216.0)


def test_multi_target_raw_column_inherits_the_same_divergence(backend, data):
    """Section 3.2's multi-target row reports Iron Ore 149.40; it is 244.65.

    The 95.25 gap is the Versatile Framework divergence above, unchanged by the
    other two targets. Coal and Copper Ore both still reconcile exactly, which is
    what localises the defect to the Modular Frame branch.
    """
    actual = _raw(
        _solve(backend, data, (SMART_PLATING, 1.0), (VERSATILE_FRAMEWORK, 6.0),
               (AUTOMATED_WIRING, 1.2))
    )
    assert actual == pytest.approx(
        {COAL: 149.4, COPPER_ORE: 28.8, IRON_ORE: 244.65}, abs=1e-4
    )


# --- 4. degeneracy and determinism ----------------------------------------

def test_identical_request_gives_an_identical_response(backend, data):
    """Section 8 item 4, the half that repeats the same call."""
    first = _solve(backend, data, (SMART_PLATING, 1.0))
    second = _solve(backend, data, (SMART_PLATING, 1.0))
    assert first == second


def test_shuffled_recipe_order_gives_an_identical_response(backend, data):
    """Section 8 item 4. D3a mitigation 1 is the sort in `_enabled_recipe_ids`."""
    base = list(data.base_recipes())
    forward = AllowedRecipes(mode=RecipeMode.EXPLICIT, recipe_ids=tuple(base))
    reversed_ = AllowedRecipes(mode=RecipeMode.EXPLICIT, recipe_ids=tuple(reversed(base)))
    a = _solve(backend, data, (SMART_PLATING, 1.0), allowed_recipes=forward)
    b = _solve(backend, data, (SMART_PLATING, 1.0), allowed_recipes=reversed_)
    assert a == b


def test_a_broken_tie_is_reported(backend, data):
    """Section 4 item 3. A silently-broken tie is what makes two runs disagree.

    Computer over the full recipe set is the case that ties under *default*
    weights — two alternate chains at the same objective value.
    """
    response = _solve(
        backend, data, ("Desc_Computer_C", 100.0),
        allowed_recipes=AllowedRecipes(mode=RecipeMode.ALL),
    )
    assert any("degenerate optimum" in w for w in response.warnings)


def test_the_pareto_sweep_is_where_ties_become_the_rule(backend, data):
    """Record section 12.3. Zeroing power and buildings zeroes every activity cost,
    so the recipe selection is degenerate almost everywhere — which is why the
    determinism guard is not optional for the Phase 3 sweep."""
    response = _solve(
        backend, data, (IRON_PLATE, 100.0),
        weights=Weights(resources=1.0, power=0.0, buildings=0.0),
    )
    assert any("degenerate optimum" in w for w in response.warnings)


def test_a_unique_optimum_is_not_reported_as_a_tie(backend, data):
    """The guard against the warning firing on everything and meaning nothing."""
    response = _solve(backend, data, (SMART_PLATING, 1.0))
    assert not any("degenerate optimum" in w for w in response.warnings)


# --- 5. cycles ------------------------------------------------------------

def _inverse_pair_warning(response):
    return [w for w in response.warnings if "inverse recipe pair" in w]


def test_packaging_does_not_run_in_both_directions(backend, data):
    response = _solve(backend, data, ("Desc_PackagedWater_C", 100.0))
    active = {u.recipe_id for u in response.recipes}
    assert "Recipe_PackagedWater_C" in active
    assert "Recipe_UnpackageWater_C" not in active
    assert _inverse_pair_warning(response) == []


def test_no_spurious_cycle_under_the_resources_only_sweep(backend, data):
    """Record section 12.3: the weighting that zeroes the costs making a loop pointless.

    Section 3.4 of the solver-selection record sweeps exactly this, so it is the
    case the cycle guard exists for.
    """
    response = _solve(
        backend, data, ("Desc_PackagedWater_C", 100.0),
        allowed_recipes=AllowedRecipes(mode=RecipeMode.ALL),
        weights=Weights(resources=1.0, power=0.0, buildings=0.0),
    )
    assert _inverse_pair_warning(response) == []
    for use in response.recipes:
        assert use.machine_equivalents < backend.activity_upper_bound


# --- D1 modes -------------------------------------------------------------

def test_free_names_every_leftover(backend, data):
    """The section 2.7 stopgap: the gap is visible rather than silent."""
    response = _solve(backend, data, ("Desc_Plastic_C", 100.0))
    leftovers = [w for w in response.warnings if "unconsumed output is free" in w]
    assert len(leftovers) == 1
    assert "Desc_HeavyOilResidue_C" in leftovers[0]


def test_forbid_is_infeasible_where_a_byproduct_has_no_consumer(data):
    """Section 2.2's Plastic case, which is the cost of `forbid` made concrete."""
    strict = LpBackend(PowerStatistic.MEAN, unconsumed=UnconsumedMode.FORBID)
    with pytest.raises(Infeasible, match="forbid"):
        _solve(strict, data, ("Desc_Plastic_C", 100.0))


def test_forbid_solves_where_nothing_is_left_over(data):
    strict = LpBackend(PowerStatistic.MEAN, unconsumed=UnconsumedMode.FORBID)
    response = _solve(strict, data, (IRON_PLATE, 20.0))
    assert _raw(response) == pytest.approx({IRON_ORE: 30.0}, abs=1e-4)
    for flow in response.items:
        if flow.item_id != IRON_PLATE:
            assert flow.net_per_min == pytest.approx(0.0, abs=1e-4)


def test_disposal_is_blocked_on_p5():
    with pytest.raises(NotImplementedError, match="P5"):
        LpBackend(PowerStatistic.MEAN, unconsumed=UnconsumedMode.DISPOSAL)


# --- scope and scenario ---------------------------------------------------

def test_power_excludes_extraction_is_always_stated(backend, data):
    """D5. The omission is never inferred from silence."""
    response = _solve(backend, data, (IRON_PLATE, 20.0))
    assert any("excludes extraction" in w for w in response.warnings)
    for machine in response.machines:
        assert "Miner" not in machine.producer_class
        assert "Pump" not in machine.producer_class


def test_canonical_mw_says_which_of_the_two_readings_it_is(backend, data):
    response = _solve(backend, data, (IRON_PLATE, 20.0))
    assert any("not a second solve" in w for w in response.warnings)


def test_input_multiplier_compounds_across_stages(backend, data):
    """Section 3.3 of the solver-selection record reads 30.00 ore becoming 46.88.

    That figure is unrounded and superseded by demand-expansion record 3.2.5: the
    multiplier lands on per-cycle parts. Iron Plate's 3 ingot rounds 3.75 to 4
    (40/min); Iron Ingot's 1 ore rounds 1.25 back to 1, so the second stage does
    not compound at all and the answer is 40.00. The earlier record is not edited
    — it described the adapter accurately when it was written.
    """
    scaled = data.with_scenario(Scenario(recipe_input_multiplier=1.25))
    response = _solve(backend, scaled, (IRON_PLATE, 20.0))
    assert _raw(response)[IRON_ORE] == pytest.approx(40.0, abs=1e-4)


def test_power_multiplier_separates_scenario_from_canonical(backend, data):
    """40 ingot/min against a 30/min Smelter is 1.3333 machines, not 1.25."""
    scaled = data.with_scenario(CHALLENGE_1_25X_2X)
    response = _solve(backend, scaled, (IRON_PLATE, 20.0))
    assert response.power.scenario_mw == pytest.approx(18.6667, abs=1e-4)
    assert response.power.canonical_mw == pytest.approx(9.3333, abs=1e-4)


def test_resource_cap_binds_and_says_so(backend, data):
    response = _solve(
        backend, data, (IRON_PLATE, 20.0),
        resource_caps=(ResourceCap(IRON_ORE, 30.0),),
    )
    assert _raw(response)[IRON_ORE] == pytest.approx(30.0, abs=1e-4)
    assert any("resource cap binds" in w for w in response.warnings)


def test_a_cap_routes_the_shortfall_through_a_conversion_recipe(backend, data):
    """Capping Iron Ore at 29 does NOT make Iron Plate 20/min infeasible.

    `Recipe_Iron_Limestone_C` is a base recipe that *produces* Iron Ore from Stone
    and SAM, so the model covers the missing 1 ore/min through the Converter
    rather than failing. Worth pinning: it means a resource cap is a routing
    signal, not a hard ceiling on a material, and it is the first case in this
    file that touches a variable-power producer — so it is NOT D2-independent and
    its power figure is deliberately not asserted.
    """
    response = _solve(
        backend, data, (IRON_PLATE, 20.0),
        resource_caps=(ResourceCap(IRON_ORE, 29.0),),
    )
    assert _raw(response)[IRON_ORE] == pytest.approx(29.0, abs=1e-4)
    assert "Recipe_Iron_Limestone_C" in _multipliers(response)
    assert any("resource cap binds" in w for w in response.warnings)


def test_a_cap_is_infeasible_when_no_conversion_route_is_enabled(backend, data):
    with pytest.raises(Infeasible):
        _solve(
            backend, data, (IRON_PLATE, 20.0),
            allowed_recipes=AllowedRecipes(
                mode=RecipeMode.EXPLICIT,
                recipe_ids=("Recipe_IngotIron_C", "Recipe_IronPlate_C"),
            ),
            resource_caps=(ResourceCap(IRON_ORE, 29.0),),
        )


# --- contract and seam ----------------------------------------------------

def test_machine_counts_round_up_for_presentation(backend, data):
    response = _solve(backend, data, (SMART_PLATING, 1.0))
    rounded = {m.producer_class: m.physical_count_if_rounded for m in response.machines}
    assert rounded == {
        "Build_SmelterMk1_C": 1, "Build_ConstructorMk1_C": 3, "Build_AssemblerMk1_C": 1
    }


def test_backend_is_named_in_the_response(backend, data):
    assert _solve(backend, data, (IRON_PLATE, 20.0)).backend == "scipy_highs"


def test_importing_the_backend_does_not_register_it():
    """`registered()` stays empty until a caller says otherwise.

    `test_production_adapter_gamedata.test_no_backend_is_wired_up_yet` asserts the
    same thing and would be order-dependent if this module self-registered.
    """
    assert registered() == ()


def test_power_statistic_has_no_default():
    """D2 is deferred, so no caller inherits a choice nobody made."""
    with pytest.raises(TypeError):
        LpBackend()


def test_existing_inventory_raises_rather_than_being_ignored(backend, data):
    with pytest.raises(NotImplementedError, match="Phase 4"):
        _solve(
            backend, data, (IRON_PLATE, 20.0),
            existing_inventory=(ResourceCap(IRON_ORE, 100.0),),
        )


def test_unknown_recipe_ids_raise(backend, data):
    with pytest.raises(ValueError, match="unknown recipe ids"):
        _solve(
            backend, data, (IRON_PLATE, 20.0),
            allowed_recipes=AllowedRecipes(
                mode=RecipeMode.EXPLICIT, recipe_ids=("Recipe_NotAThing_C",)
            ),
        )


def test_an_unreachable_target_says_so(backend, data):
    with pytest.raises(Infeasible, match="no enabled recipe produces"):
        _solve(
            backend, data, ("Desc_Plastic_C", 10.0),
            allowed_recipes=AllowedRecipes(
                mode=RecipeMode.EXPLICIT, recipe_ids=("Recipe_IronPlate_C",)
            ),
        )
