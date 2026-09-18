import pytest

from production_adapter import (
    AllowedRecipes, OutputTarget, PowerReport, RecipeMode, ResourceCap,
    SolveRequest, Weights,
)

SP = "Desc_SpaceElevatorPart_1_C"


def test_minimal_request():
    r = SolveRequest(outputs=(OutputTarget(SP, 1.0),))
    assert r.allowed_recipes.mode is RecipeMode.BASE_ONLY
    assert r.weights.complexity == 0.0


@pytest.mark.parametrize("rate", [0.0, -1.0])
def test_target_rate_must_be_positive(rate):
    with pytest.raises(ValueError):
        OutputTarget(SP, rate)


def test_request_needs_a_target():
    with pytest.raises(ValueError, match="at least one output"):
        SolveRequest(outputs=())


def test_duplicate_targets_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        SolveRequest(outputs=(OutputTarget(SP, 1.0), OutputTarget(SP, 2.0)))


def test_item_cannot_be_both_input_and_output():
    with pytest.raises(ValueError, match="both an output and an input"):
        SolveRequest(outputs=(OutputTarget(SP, 1.0),), resource_caps=(ResourceCap(SP, 10.0),))


def test_explicit_mode_needs_recipe_ids():
    with pytest.raises(ValueError):
        AllowedRecipes(mode=RecipeMode.EXPLICIT)


def test_recipe_ids_meaningless_outside_explicit_mode():
    with pytest.raises(ValueError, match="meaningless"):
        AllowedRecipes(mode=RecipeMode.ALL, recipe_ids=("Recipe_IronPlate_C",))


def test_complexity_weight_is_disabled_pending_fork_delta_f2():
    with pytest.raises(NotImplementedError, match="F2"):
        Weights(complexity=1.0)


def test_negative_weights_rejected():
    with pytest.raises(ValueError):
        Weights(power=-1.0)


def test_power_range_must_be_ordered():
    with pytest.raises(ValueError):
        PowerReport(canonical_mw=1, scenario_mw=1, min_mw=10, max_mw=1)
