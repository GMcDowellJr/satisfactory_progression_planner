"""Adapter loading against the real reference layer."""
import pathlib

import pytest

from production_adapter import (
    BackendNotSelected, CHALLENGE_1_25X_2X, OutputTarget, ReferenceDataError,
    Scenario, SolveRequest, get_backend, load, registered,
)

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
