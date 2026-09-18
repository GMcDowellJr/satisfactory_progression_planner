"""Plan section 11's validation set, which is what Phase 1's exit condition rests on.

    docs/plans/progression_optimizer_implementation_plan.md
        section 11  the required set, and "compare item rates, recipe rates, machine
                    equivalents, raw inputs, and power against manually calculated
                    or independently verified values"
        section 17  Phase 1 exit: "fixed production targets reconcile correctly for
                    early and late game"

The first five cases live in `test_fixed_recipe_expectations.py` and
`test_production_lp_backend.py`. This module covers the nine that did not: the five
alternate-recipe cases, the three scenario cases across every fixed-recipe target,
and the representative Phase 4/5 chain.

Every case is fixed-recipe. "Fixed" is not a property of the data past the early
game — an item can have several *base* producers — so each case names an explicit
recipe set. The guarantee that a set really is fixed is that `_demand_oracle`
resolves it without raising `AmbiguousDemand`: that raise fires exactly when an item
on the demand path has more than one enabled producer, so silence means the route is
forced and the solver had nothing to choose.

Three independent references are used, and none of them can solve:

    _demand_oracle              recipe multipliers and raw inputs, by propagation
    _fixed_recipe_expectations  power and machines for a GIVEN multiplier map
    _balance_check              that the response balances and meets the request

The third exists because the first cannot serve the late-game case. See
`test_late_game_oracle_divergence_is_byproduct_crediting`.
"""
import pathlib

import pytest

from _balance_check import violations
from _demand_oracle import demand
from _fixed_recipe_expectations import expectations
from production_adapter import (
    AllowedRecipes, CHALLENGE_1_25X_2X, OutputTarget, RecipeMode, Scenario,
    SolveRequest, load,
)
from production_adapter.lp_backend import LpBackend, PowerStatistic

REPO = pathlib.Path(__file__).resolve().parents[1]

#: Each alternate and the base recipe it displaces. Pairing is asserted, not assumed,
#: by `test_every_alternate_displaces_a_recipe_making_the_same_item`.
DISPLACES = {
    "Recipe_Alternate_ReinforcedIronPlate_2_C": "Recipe_IronPlateReinforced_C",  # Stitched Iron Plate
    "Recipe_Alternate_Wire_1_C": "Recipe_Wire_C",                                # Iron Wire
    "Recipe_Alternate_IngotSteel_1_C": "Recipe_IngotSteel_C",                    # Solid Steel Ingot
    "Recipe_Alternate_ModularFrame_C": "Recipe_ModularFrame_C",                  # Steeled Frame
    "Recipe_Alternate_Rotor_C": "Recipe_Rotor_C",                                # Steel Rotor
}

IRON_PLATE = "Desc_IronPlate_C"
REINFORCED_PLATE = "Desc_IronPlateReinforced_C"
SMART_PLATING = "Desc_SpaceElevatorPart_1_C"
VERSATILE_FRAMEWORK = "Desc_SpaceElevatorPart_2_C"
AUTOMATED_WIRING = "Desc_SpaceElevatorPart_3_C"
NUCLEAR_PASTA = "Desc_SpaceElevatorPart_9_C"

#: The five early cases, as the first five rows of section 11's set.
FIXED_RECIPE_TARGETS = [
    (IRON_PLATE, 20.0),
    (REINFORCED_PLATE, 5.0),
    (SMART_PLATING, 1.0),
    (VERSATILE_FRAMEWORK, 6.0),
    (AUTOMATED_WIRING, 1.2),
]

SCENARIOS = [
    ("input-1.25x", Scenario(recipe_input_multiplier=1.25)),
    ("power-2.0x", Scenario(machine_power_multiplier=2.0)),
    ("combined-challenge", CHALLENGE_1_25X_2X),
]


@pytest.fixture(scope="module")
def data():
    return load(REPO)


@pytest.fixture(scope="module")
def backend():
    return LpBackend(power_statistic=PowerStatistic.MEAN)


def _with_alternates(data, *alternates):
    enabled = set(data.base_recipes())
    for alternate in alternates:
        enabled.discard(DISPLACES[alternate])
        enabled.add(alternate)
    return enabled


def _explicit(enabled):
    return AllowedRecipes(mode=RecipeMode.EXPLICIT, recipe_ids=tuple(sorted(enabled)))


def _reconcile(backend, data, item, rate, enabled, scenario=None):
    """Solve, and return (response, oracle result, expectations) for comparison.

    The oracle is asked for the same recipe set and the same input multiplier, so
    any disagreement is the solver's arithmetic and not a different question.
    """
    multiplier = 1.0 if scenario is None else scenario.recipe_input_multiplier
    solved_against = data if scenario is None else data.with_scenario(scenario)
    oracle = demand(item, rate, allowed_recipes=enabled, input_multiplier=multiplier)
    response = backend.solve(
        SolveRequest(outputs=(OutputTarget(item, rate),), allowed_recipes=_explicit(enabled)),
        solved_against,
    )
    return response, oracle, expectations(oracle.recipe_multipliers)


def _assert_matches_oracle(response, oracle, expected, power_multiplier=1.0):
    actual = {u.recipe_id: u.machine_equivalents for u in response.recipes}
    assert set(actual) == set(oracle.recipe_multipliers)
    for recipe_id, multiplier in oracle.recipe_multipliers.items():
        assert actual[recipe_id] == pytest.approx(multiplier, abs=1e-4)

    raw = {r.item_id: r.rate_per_min for r in response.raw_inputs}
    assert set(raw) == set(oracle.raw_inputs)
    for item_id, value in oracle.raw_inputs.items():
        assert raw[item_id] == pytest.approx(value, abs=1e-4)

    machines = {m.producer_class: m.effective_count for m in response.machines}
    assert set(machines) == set(expected.machines_by_producer_class)
    for producer_class, count in expected.machines_by_producer_class.items():
        assert machines[producer_class] == pytest.approx(count, abs=1e-4)

    assert response.power.scenario_mw == pytest.approx(
        expected.power.mean_mw * power_multiplier, abs=1e-4
    )


# --- the curation is auditable -------------------------------------------

def test_every_alternate_displaces_a_recipe_making_the_same_item(data):
    """A swap that changed what the chain produces would not be a fixed-recipe case."""
    for alternate, displaced in DISPLACES.items():
        assert data.recipes[alternate].is_alternate
        assert not data.recipes[displaced].is_alternate
        assert {i for i, _ in data.recipes[alternate].outputs} == \
               {i for i, _ in data.recipes[displaced].outputs}


# --- section 11, the five alternate-recipe cases -------------------------

ALTERNATE_CASES = [
    ("Smart Plating + Stitched Iron Plate", SMART_PLATING, 1.0,
     ("Recipe_Alternate_ReinforcedIronPlate_2_C",)),
    ("Smart Plating + Iron Wire", SMART_PLATING, 1.0,
     ("Recipe_Alternate_Wire_1_C",)),
    ("VF + Solid Steel", VERSATILE_FRAMEWORK, 6.0,
     ("Recipe_Alternate_IngotSteel_1_C",)),
    ("VF + Steeled Frame", VERSATILE_FRAMEWORK, 6.0,
     ("Recipe_Alternate_ModularFrame_C",)),
    ("Rotor + Steel Rotor", "Desc_Rotor_C", 10.0,
     ("Recipe_Alternate_Rotor_C",)),
    ("Motor + Steel Rotor", "Desc_Motor_C", 5.0,
     ("Recipe_Alternate_Rotor_C",)),
]


@pytest.mark.parametrize("name,item,rate,alternates", ALTERNATE_CASES,
                         ids=[c[0] for c in ALTERNATE_CASES])
def test_alternate_recipe_case_reconciles(backend, data, name, item, rate, alternates):
    enabled = _with_alternates(data, *alternates)
    response, oracle, expected = _reconcile(backend, data, item, rate, enabled)
    _assert_matches_oracle(response, oracle, expected)
    assert violations(response, {item: rate}) == []
    assert expected.power.is_degenerate, f"{name} is no longer D2-independent"


def test_stitched_iron_plate_changes_the_raw_mix(backend, data):
    """The alternate is only a validation case if it actually changes the answer.

    Stitched Iron Plate makes Reinforced Iron Plate from Wire rather than Screws,
    which pulls Copper Ore into a chain that had none and drops Iron Ore by a third.
    """
    enabled = _with_alternates(data, "Recipe_Alternate_ReinforcedIronPlate_2_C")
    response, _, _ = _reconcile(backend, data, SMART_PLATING, 1.0, enabled)
    raw = {r.item_id: r.rate_per_min for r in response.raw_inputs}
    assert raw == pytest.approx(
        {"Desc_OreIron_C": 16.25, "Desc_OreCopper_C": 10.0 / 3.0}, abs=1e-4
    )


def test_iron_wire_is_inert_for_smart_plating(backend, data):
    """Section 11 pairs Smart Plating with Iron Wire; that chain contains no Wire.

    Smart Plating is Reinforced Iron Plate plus Rotor, and neither uses Wire, so
    enabling the alternate changes nothing. Kept, because "an unused alternate must
    not perturb a fixed-recipe result" is a real invariant — but recorded here so
    nobody reads this row as evidence that the Iron Wire route was exercised. It
    was not.
    """
    enabled = _with_alternates(data, "Recipe_Alternate_Wire_1_C")
    with_alternate, _, _ = _reconcile(backend, data, SMART_PLATING, 1.0, enabled)
    baseline, _, _ = _reconcile(backend, data, SMART_PLATING, 1.0, set(data.base_recipes()))

    assert "Recipe_Alternate_Wire_1_C" not in {u.recipe_id for u in with_alternate.recipes}
    assert {u.recipe_id for u in with_alternate.recipes} == \
           {u.recipe_id for u in baseline.recipes}
    assert with_alternate.power.scenario_mw == pytest.approx(
        baseline.power.scenario_mw, abs=1e-4
    )


def test_solid_steel_ingot_lowers_coal_and_raises_iron(backend, data):
    """Solid Steel Ingot burns Iron Ingot instead of Iron Ore: 144 coal -> 96."""
    enabled = _with_alternates(data, "Recipe_Alternate_IngotSteel_1_C")
    response, _, _ = _reconcile(backend, data, VERSATILE_FRAMEWORK, 6.0, enabled)
    raw = {r.item_id: r.rate_per_min for r in response.raw_inputs}
    assert raw == pytest.approx({"Desc_Coal_C": 96.0, "Desc_OreIron_C": 168.0}, abs=1e-4)


# --- section 11, the three scenario cases --------------------------------

@pytest.mark.parametrize("item,rate", FIXED_RECIPE_TARGETS)
@pytest.mark.parametrize("label,scenario", SCENARIOS, ids=[s[0] for s in SCENARIOS])
def test_scenario_case_reconciles(backend, data, item, rate, label, scenario):
    """Every fixed-recipe target under every scenario, not one target under each."""
    enabled = set(data.base_recipes())
    response, oracle, expected = _reconcile(backend, data, item, rate, enabled, scenario)
    _assert_matches_oracle(
        response, oracle, expected, power_multiplier=scenario.machine_power_multiplier
    )
    assert violations(
        response, {item: rate}, input_multiplier=scenario.recipe_input_multiplier
    ) == []


@pytest.mark.parametrize("item,rate", FIXED_RECIPE_TARGETS)
def test_canonical_power_is_the_scenario_power_divided_by_the_multiplier(
    backend, data, item, rate
):
    """`canonical_mw` and `scenario_mw` are two transforms of one set of facts."""
    response, _, _ = _reconcile(
        backend, data, item, rate, set(data.base_recipes()), CHALLENGE_1_25X_2X
    )
    assert response.power.canonical_mw == pytest.approx(
        response.power.scenario_mw / 2.0, abs=1e-4
    )


def test_the_input_multiplier_compounds_rather_than_scaling(backend, data):
    """Smart Plating at 1.25x needs 62.41 ore, not 29.06.

    The exact figure is 62.408447265625 — 1.25 raised to the number of stages the
    demand crosses, not applied once. The adapter README and section 3.3 of the
    solver-selection record both display it rounded to 62.41.
    """
    response, _, _ = _reconcile(
        backend, data, SMART_PLATING, 1.0, set(data.base_recipes()),
        Scenario(recipe_input_multiplier=1.25),
    )
    raw = {r.item_id: r.rate_per_min for r in response.raw_inputs}
    assert raw["Desc_OreIron_C"] == pytest.approx(62.408447265625, abs=1e-6)
    assert raw["Desc_OreIron_C"] > 23.25 * 1.25  # compounds, not scales


# --- section 11, the representative Phase 4/5 chain ----------------------

#: Nuclear Pasta's curated route. Base recipes, minus every Unpackage recipe, minus
#: the two byproduct routes that would otherwise leave an item with two producers.
#: `Recipe_Silica_C` goes rather than `Recipe_AluminaSolution_C`, because the latter
#: is the only source of Alumina Solution and the chain needs it; Silica therefore
#: arrives as that recipe's byproduct. `Recipe_ResidualPlastic_C` goes so Plastic
#: comes from the direct route. Both are choices, recorded rather than implied.
LATE_GAME_DROPPED = frozenset({"Recipe_Silica_C", "Recipe_ResidualPlastic_C"})


def _late_game_recipes(data):
    base = set(data.base_recipes())
    return base - {r for r in base if "Unpackage" in r} - LATE_GAME_DROPPED


def _late_game_response(backend, data):
    return backend.solve(
        SolveRequest(outputs=(OutputTarget(NUCLEAR_PASTA, 1.0),),
                     allowed_recipes=_explicit(_late_game_recipes(data))),
        data,
    )


def test_late_game_chain_balances_and_meets_the_target(backend, data):
    """Phase 1's "late game" half. 30 recipes across eight producer classes."""
    response = _late_game_response(backend, data)
    assert violations(response, {NUCLEAR_PASTA: 1.0}) == []
    assert len(response.recipes) == 30
    assert {m.producer_class for m in response.machines} == {
        "Build_AssemblerMk1_C", "Build_Blender_C", "Build_ConstructorMk1_C",
        "Build_FoundryMk1_C", "Build_ManufacturerMk1_C", "Build_HadronCollider_C",
        "Build_OilRefinery_C", "Build_SmelterMk1_C",
    }


def test_late_game_power_and_machines_reconcile_independently(backend, data):
    """`_fixed_recipe_expectations` re-derives power and machines from the CSVs.

    It is given the solver's own multipliers and computes what they imply, which is
    an independent check of the power model even though the activities came from the
    thing being checked.
    """
    response = _late_game_response(backend, data)
    expected = expectations({u.recipe_id: u.machine_equivalents for u in response.recipes})
    assert response.power.min_mw == pytest.approx(expected.power.min_mw, abs=1e-3)
    assert response.power.max_mw == pytest.approx(expected.power.max_mw, abs=1e-3)
    assert response.power.scenario_mw == pytest.approx(expected.power.mean_mw, abs=1e-3)
    machines = {m.producer_class: m.effective_count for m in response.machines}
    for producer_class, count in expected.machines_by_producer_class.items():
        assert machines[producer_class] == pytest.approx(count, abs=1e-4)


def test_late_game_exercises_the_variable_power_tier(backend, data):
    """Otherwise it is not a late-game case in the sense D2 cares about."""
    response = _late_game_response(backend, data)
    assert response.power.max_mw - response.power.min_mw == pytest.approx(2000.0, abs=1e-3)
    assert any(m.producer_class == "Build_HadronCollider_C" for m in response.machines)


def test_late_game_is_d2_independent_because_the_recipes_are_fixed(backend, data):
    """Formulation record section 14.5, made executable.

    A fixed recipe set leaves the objective nothing to choose, so all three
    statistics return the same plan and the same power range. This is why Phase 1's
    exit condition does not wait on D2 — only Phase 3 does.
    """
    enabled = _explicit(_late_game_recipes(data))
    request = SolveRequest(outputs=(OutputTarget(NUCLEAR_PASTA, 1.0),), allowed_recipes=enabled)
    plans = []
    for statistic in (PowerStatistic.MIN, PowerStatistic.MEAN, PowerStatistic.MAX):
        response = LpBackend(power_statistic=statistic).solve(request, data)
        plans.append((
            {u.recipe_id: round(u.machine_equivalents, 6) for u in response.recipes},
            round(response.power.min_mw, 6),
            round(response.power.max_mw, 6),
        ))
    assert plans[0] == plans[1] == plans[2]


def test_late_game_oracle_divergence_is_byproduct_crediting(backend, data):
    """`_demand_oracle` cannot be the reference here, and this pins exactly why.

    The oracle propagates demand without crediting byproducts; a production solver
    credits them in one balance. On this chain `Recipe_AluminaSolution_C` is the sole
    source of both Alumina Solution and Silica, so the oracle runs it once for each
    demand while the solver runs it once for both and leaves the excess as
    unconsumed output. Neither is wrong — they answer different questions — but it
    means the oracle stops being a valid reference the moment a byproduct feeds back,
    which is why `_balance_check` exists.

    Every other recipe in the chain still agrees to four decimals, which is what
    localises the divergence rather than merely asserting it.
    """
    response = _late_game_response(backend, data)
    oracle = demand(NUCLEAR_PASTA, 1.0, allowed_recipes=_late_game_recipes(data))
    solver = {u.recipe_id: u.machine_equivalents for u in response.recipes}

    assert set(solver) == set(oracle.recipe_multipliers)
    diverged = {
        recipe_id for recipe_id, multiplier in oracle.recipe_multipliers.items()
        if abs(solver[recipe_id] - multiplier) > 1e-4
    }
    assert diverged == {"Recipe_AluminaSolution_C"}
    assert oracle.recipe_multipliers["Recipe_AluminaSolution_C"] == pytest.approx(4.1, abs=1e-4)
    assert solver["Recipe_AluminaSolution_C"] == pytest.approx(3.075, abs=1e-4)
    assert any(
        "Desc_AluminaSolution_C" in w for w in response.warnings if "unconsumed" in w
    )


# --- the new reference's own guard ---------------------------------------

def test_balance_check_cannot_solve():
    """The structural guard, mirroring the oracle's and the expectations module's."""
    import inspect

    import _balance_check as mod

    assert list(inspect.signature(mod.violations).parameters)[:2] == ["response", "targets"]
    code = [
        line for line in open(mod.__file__, encoding="utf-8").read().splitlines()
        if not line.lstrip().startswith("#")
    ]
    assert not [line for line in code if line.startswith("if __name__")]
    assert not hasattr(mod, "main")
    assert not hasattr(mod, "solve")


def test_balance_check_catches_a_broken_response(backend, data):
    """A reference that never fails is not a reference."""
    response = _late_game_response(backend, data)
    assert violations(response, {NUCLEAR_PASTA: 1.0}) == []
    assert violations(response, {NUCLEAR_PASTA: 2.0}) != []
