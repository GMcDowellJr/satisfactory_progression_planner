"""Adapter loading against the real reference layer."""
import pathlib

import pytest

from production_adapter import (
    BackendNotSelected, CHALLENGE_1_25X_2X, OutputTarget, ReferenceDataError,
    Scenario, SolveRequest, get_backend, load, registered,
)
from production_adapter.gamedata import UNJOINABLE_BUILD_RECIPES, load_construction

REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def data():
    return load(REPO)


def test_loads_the_whole_reference_layer(data):
    assert len(data.recipes) == 291
    assert len(data.producers) == 11
    assert len(data.resource_items) == 13
    assert data.game_build_id.startswith("docs_")


def test_every_recipe_has_a_producer_and_power(data):
    for r in data.recipes.values():
        assert r.producer_class in data.producers
        assert r.power.max_mw > 0 or r.producer_class == "Build_QuantumEncoder_C"


def test_variable_power_producers_carry_a_range(data):
    pasta = data.recipes["Recipe_SpaceElevatorPart_9_C"]
    assert data.producers[pasta.producer_class].is_variable_power
    assert (pasta.power.min_mw, pasta.power.max_mw) == (500.0, 1500.0)
    assert pasta.power.mean_mw == 1000.0


def test_fixed_power_producer_ignores_stray_variable_fields(data):
    """Ballistic Warp Drive carries variable-power fields the game ignores."""
    bwd = data.recipes["Recipe_SpaceElevatorPart_11_C"]
    assert not data.producers[bwd.producer_class].is_variable_power
    assert (bwd.power.min_mw, bwd.power.max_mw) == (55.0, 55.0)


def test_smelter_power_is_present(data):
    """The 73-recipe hole P1 closed. 0 MW here means the fix regressed."""
    assert data.producers["Build_SmelterMk1_C"].base_power_mw == 4.0


def test_base_recipe_count(data):
    assert len(data.base_recipes()) == 181


def test_scenario_rounds_inputs_and_leaves_outputs_alone(data):
    """Record 3.2.5: the multiplier lands on per-cycle parts, not on the rate.

    Iron Plate costs 3 Iron Ingot per cycle. 3 x 1.25 = 3.75 rounds to 4, so the
    scaled rate is 40/min and not 37.5 — the linear figure this test asserted
    until 2026-09-21 was the adapter's behaviour, not the game's.
    """
    plain = data.recipes["Recipe_IronPlate_C"]
    scaled = data.with_scenario(Scenario(recipe_input_multiplier=1.25)).recipes["Recipe_IronPlate_C"]
    assert plain.input_amounts[0][1:] == (3.0, "items")
    assert scaled.input_amounts[0][1] == pytest.approx(4.0)
    assert scaled.inputs[0][1] == pytest.approx(40.0)
    assert scaled.inputs[0][1] != pytest.approx(plain.inputs[0][1] * 1.25)
    assert scaled.outputs[0][1] == pytest.approx(plain.outputs[0][1])


def test_the_in_game_read_reproduces_on_the_real_reference_rows(data):
    """Record 3.2.4, read from a live 1.25x save on 1.2.4.0 CL#502094.

    Smart Plating 1 -> 1 (down), Modular Frame 3 -> 4 (up), 12 -> 15 (exact). The
    control row is what rules out per-recipe or per-stage rounding: 12 moves by
    exactly its unrounded value while 3 does not.
    """
    scaled = data.with_scenario(Scenario(recipe_input_multiplier=1.25))
    smart = dict((i, a) for i, a, _ in scaled.recipes["Recipe_SpaceElevatorPart_1_C"].input_amounts)
    frame = dict((i, a) for i, a, _ in scaled.recipes["Recipe_ModularFrame_C"].input_amounts)
    assert smart["Desc_IronPlateReinforced_C"] == pytest.approx(1.0)
    assert smart["Desc_Rotor_C"] == pytest.approx(1.0)
    assert frame["Desc_IronPlateReinforced_C"] == pytest.approx(4.0)
    assert frame["Desc_IronRod_C"] == pytest.approx(15.0)


def test_a_power_only_scenario_leaves_inputs_untouched(data):
    """No input transform at 1x, so nothing is re-derived and nothing rounds."""
    plain = data.recipes["Recipe_Battery_C"]
    scaled = data.with_scenario(Scenario(machine_power_multiplier=2.0)).recipes["Recipe_Battery_C"]
    assert scaled.inputs == plain.inputs
    assert ("Desc_SulfuricAcid_C", 2.5, "m3") in scaled.input_amounts


def test_scenario_scales_power(data):
    scaled = data.with_scenario(CHALLENGE_1_25X_2X)
    assert scaled.recipes["Recipe_IronPlate_C"].power.max_mw == pytest.approx(8.0)


def test_canonical_data_is_not_mutated_by_a_scenario(data):
    before = data.recipes["Recipe_IronPlate_C"].inputs
    data.with_scenario(CHALLENGE_1_25X_2X)
    assert data.recipes["Recipe_IronPlate_C"].inputs == before


def test_missing_reference_layer_raises_rather_than_guessing(tmp_path):
    with pytest.raises(ReferenceDataError, match="missing reference table"):
        load(tmp_path)


def test_no_backend_is_wired_up_yet():
    assert registered() == ()
    with pytest.raises(BackendNotSelected, match="F1"):
        get_backend().solve(
            SolveRequest(outputs=(OutputTarget("Desc_IronPlate_C", 20.0),)), None
        )


# --------------------------------------------------------------------------
# construction costs — the Build Gun set, and the join that does not follow
# the name convention
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def construction():
    return load_construction(REPO)


def test_the_build_gun_set_loads_whole(construction, data):
    """549 build recipes, one of which joins to no building. The count is a
    regression pin against the extraction pass, not an independent expectation."""
    assert len(construction.by_building_class) == 548
    assert construction.game_build_id == data.game_build_id


def test_every_production_building_resolves_through_its_building_class(construction, data):
    """`Build_X_C -> Desc_X_C` is the join, and this is what says so. Eleven of
    eleven; a producer that stops following it raises rather than being costed
    at zero."""
    for producer_class in data.producers:
        cost = construction.for_producer(producer_class)
        assert cost.items, f"{producer_class} resolved to a building with no cost"


def test_the_recipe_name_convention_is_wrong_on_the_smelter_and_the_foundry(construction):
    """THE REASON THE JOIN GOES THROUGH THE BUILDING CLASS.

    Read from building_recipes.csv, 2026-09-22:

        Recipe_SmelterBasicMk1_C  builds  Desc_SmelterMk1_C   the SMELTER
        Recipe_SmelterMk1_C       builds  Desc_FoundryMk1_C   the FOUNDRY

    The two are swapped relative to `Build_X_C -> Recipe_X_C`. That mapping
    does not merely fail on them — `Recipe_SmelterMk1_C` exists, so a naive
    join SUCCEEDS and charges every Smelter the Foundry's bill. A silent wrong
    answer, not a lookup error.

    Costs read from building_recipe_io.csv, not restated from a note:
    the Smelter is 5 Iron Rod + 8 Wire, the Foundry is 20 Concrete + 10
    Modular Frame + 10 Rotor.
    """
    smelter = construction.for_producer("Build_SmelterMk1_C")
    foundry = construction.for_producer("Build_FoundryMk1_C")

    assert smelter.display_name == "Smelter"
    assert smelter.build_recipe_id == "Recipe_SmelterBasicMk1_C"
    assert dict(smelter.items) == {"Desc_IronRod_C": 5.0, "Desc_Wire_C": 8.0}

    assert foundry.display_name == "Foundry"
    assert foundry.build_recipe_id == "Recipe_SmelterMk1_C"
    assert dict(foundry.items) == {
        "Desc_Cement_C": 20.0, "Desc_ModularFrame_C": 10.0, "Desc_Rotor_C": 10.0,
    }

    # The naive mapping, spelled out so the defect cannot be reintroduced by
    # someone who finds the join indirect and "simplifies" it.
    for producer_class in ("Build_SmelterMk1_C", "Build_FoundryMk1_C"):
        naive = "Recipe_" + producer_class[len("Build_"):]
        assert construction.for_producer(producer_class).build_recipe_id != naive


def test_an_unknown_producer_is_refused_rather_than_costed_at_zero(construction):
    """A zero-cost building understates a bill that is already declared a
    floor, and an understated floor is the one failure the floor argument
    cannot absorb."""
    with pytest.raises(ReferenceDataError, match="no Build Gun recipe"):
        construction.for_producer("Build_NotAThing_C")
    with pytest.raises(ReferenceDataError, match="not a Build_\\*_C producer class"):
        construction.for_producer("Desc_ConstructorMk1_C")


def test_the_one_unjoinable_build_recipe_is_allowlisted_by_name(construction):
    """`Recipe_PipelinePumpMK2_C` carries an empty `building_class` — one row of
    549. Named with its reason, in the same shape as the Portable Miner gap,
    rather than swallowed by a truthy test that would also swallow the next
    one."""
    assert UNJOINABLE_BUILD_RECIPES == {"Recipe_PipelinePumpMK2_C"}


def test_construction_costs_take_no_scenario(construction):
    """§8, measured twice: a Constructor is 2 Reinforced Iron Plate + 8 Cable at
    1x and at 1.25x alike, and 8 x 1.25 = 10, so no rounding rule produces 8.
    `load_construction` therefore accepts no scenario at all — one that was
    accepted and ignored would be a parameter that cannot refuse."""
    import inspect

    assert list(inspect.signature(load_construction).parameters) == ["repo_root"]
    constructor = construction.for_producer("Build_ConstructorMk1_C")
    assert dict(constructor.items) == {
        "Desc_IronPlateReinforced_C": 2.0, "Desc_Cable_C": 8.0,
    }


def test_every_build_recipe_io_row_is_an_input():
    """The `direction == "input"` filter in `load_construction` is DEAD TODAY,
    and this is what makes that a measured fact rather than a hope.

    All 851 rows of building_recipe_io.csv are inputs, so removing the filter
    changes no figure — a mutation against it survives, and correctly. The
    filter stays because a future extraction that emits an output row (a
    dismantle refund, say) would otherwise be summed into every building's cost
    silently. If this test starts failing, the filter has become load-bearing
    and the cost figures need re-checking, not the filter removing.
    """
    import csv

    path = REPO / "planning_data" / "game" / "reference" / "building_recipe_io.csv"
    with path.open(encoding="utf-8") as fh:
        directions = {r["direction"] for r in csv.DictReader(fh)}
    assert directions == {"input"}
