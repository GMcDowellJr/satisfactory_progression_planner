import pytest

from production_adapter import CHALLENGE_1_25X_2X, Scenario


def test_default_is_canonical():
    assert Scenario().is_canonical


def test_challenge_preset():
    s = CHALLENGE_1_25X_2X
    assert (s.recipe_input_multiplier, s.machine_power_multiplier) == (1.25, 2.0)
    assert not s.is_canonical


def test_inputs_scale_and_outputs_do_not():
    """The asymmetry is the whole point: the setting raises cost, not yield."""
    s = Scenario(recipe_input_multiplier=1.25)
    assert s.apply_input_rate(30.0) == pytest.approx(37.5)
    assert s.apply_output_rate(20.0) == pytest.approx(20.0)


def test_power_scales():
    assert Scenario(machine_power_multiplier=2.0).apply_power(4.0) == pytest.approx(8.0)


def test_project_assembly_multiplier_is_separate():
    s = Scenario(project_assembly_requirement_multiplier=0.5)
    assert s.apply_project_assembly_quantity(1000) == pytest.approx(500)
    assert s.apply_input_rate(30.0) == pytest.approx(30.0)


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
