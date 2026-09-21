import pytest

from production_adapter import (
    CHALLENGE_1_25X_2X, FLUID_UNIT, ITEM_UNIT, MARGINAL_PEAK_DEBOTTLENECK, Scenario,
)


def test_default_is_canonical():
    assert Scenario().is_canonical


def test_challenge_preset():
    s = CHALLENGE_1_25X_2X
    assert (s.recipe_input_multiplier, s.machine_power_multiplier) == (1.25, 2.0)
    assert not s.is_canonical


def test_scenario_of_record_is_not_the_challenge_preset():
    """1.25 / 2.0 / 2.0. CHALLENGE_1_25X_2X carries PA 1.0 and is a different save."""
    s = MARGINAL_PEAK_DEBOTTLENECK
    assert (s.recipe_input_multiplier, s.machine_power_multiplier,
            s.project_assembly_requirement_multiplier) == (1.25, 2.0, 2.0)
    assert s != CHALLENGE_1_25X_2X
    assert s.apply_project_assembly_quantity(1000) == pytest.approx(2000)


def test_there_is_no_rate_shaped_input_transform():
    """Record 3.2.5: rounding is not expressible on a rate, so the method is gone.

    Its absence is the guard. A caller reaching for it gets an AttributeError at
    the call site rather than a silently unrounded answer.
    """
    assert not hasattr(Scenario(), "apply_input_rate")


def test_inputs_round_and_outputs_do_not():
    """The asymmetry is the whole point: the setting raises cost, not yield."""
    s = Scenario(recipe_input_multiplier=1.25)
    assert s.apply_input_amount(3.0) == pytest.approx(4.0)     # 3.75 rounds up
    assert s.apply_output_rate(20.0) == pytest.approx(20.0)


def test_the_two_directions_observed_in_game():
    """Record 3.2.4, read from a live 1.25x save on 1.2.4.0 CL#502094."""
    s = Scenario(recipe_input_multiplier=1.25)
    assert s.apply_input_amount(1.0) == pytest.approx(1.0)     # 1.25 rounds down
    assert s.apply_input_amount(3.0) == pytest.approx(4.0)     # 3.75 rounds up
    assert s.apply_input_amount(12.0) == pytest.approx(15.0)   # exact, the control


def test_halves_go_away_from_zero_not_to_even():
    """Record 3.2.5 adopted half-away-from-zero. `round()` would give 2 here.

    UNOBSERVED in game: 3.2.4's reads were 1.25, 3.75 and 15, none of them a tie.
    Storage review 10.3 proposes the two-building read that settles it. This test
    asserts the adopted rule, not a measurement.
    """
    s = Scenario(recipe_input_multiplier=1.25)
    assert s.apply_input_amount(2.0) == pytest.approx(3.0)     # 2.5 -> 3, not 2
    assert s.apply_input_amount(6.0) == pytest.approx(8.0)     # 7.5 -> 8


def test_one_x_is_the_identity_even_for_a_fractional_fluid():
    """Recipe_Battery_C draws 2.5 m3 of Sulfuric Acid. At 1x the game states 2.5.

    Rounding an unmultiplied cost would invent one, so the 1x path never rounds.
    """
    s = Scenario(recipe_input_multiplier=1.0, machine_power_multiplier=2.0)
    assert s.apply_input_amount(2.5, FLUID_UNIT) == pytest.approx(2.5)
    assert s.apply_input_amount(3.0, ITEM_UNIT) == pytest.approx(3.0)


def test_power_scales():
    assert Scenario(machine_power_multiplier=2.0).apply_power(4.0) == pytest.approx(8.0)


def test_project_assembly_multiplier_is_separate():
    s = Scenario(project_assembly_requirement_multiplier=0.5)
    assert s.apply_project_assembly_quantity(1000) == pytest.approx(500)
    assert s.apply_input_amount(3.0) == pytest.approx(3.0)


def test_sub_1x_refuses_without_a_declared_floor():
    """Record 3.2.3: the floor rule is unobserved, so it is declared, not assumed."""
    with pytest.raises(ValueError, match="input_amount_floor"):
        Scenario(recipe_input_multiplier=0.75)


def test_a_declared_floor_admits_sub_1x():
    held = Scenario(recipe_input_multiplier=0.25, input_amount_floor=1)
    assert held.apply_input_amount(1.0) == pytest.approx(1.0)   # 0.25 -> 0, held at 1
    assert held.apply_input_amount(12.0) == pytest.approx(3.0)

    allowed = Scenario(recipe_input_multiplier=0.25, input_amount_floor=0)
    assert allowed.apply_input_amount(1.0) == pytest.approx(0.0)


@pytest.mark.parametrize("kw", [
    {"recipe_input_multiplier": 0},
    {"machine_power_multiplier": -1},
    {"project_assembly_requirement_multiplier": 0.0},
])
def test_multipliers_must_be_positive(kw):
    with pytest.raises(ValueError):
        Scenario(**kw)


def test_multipliers_must_be_numeric():
    with pytest.raises(TypeError):
        Scenario(recipe_input_multiplier="1.25")


def test_canonical_returns_an_unmodified_scenario():
    assert CHALLENGE_1_25X_2X.canonical().is_canonical
