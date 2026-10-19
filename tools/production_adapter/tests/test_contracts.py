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


# --- the district solve's contracts (crossover A27.2) -----------------------

from production_adapter import DistrictRequest, DistrictTarget  # noqa: E402

VF = "Desc_SpaceElevatorPart_2_C"
ORE = "Desc_OreIron_C"


def test_district_target_defaults_to_weight_one_and_no_floor():
    t = DistrictTarget(VF)
    assert t.weight == 1.0 and t.minimum_rate is None and t.is_active


def test_district_target_weight_zero_without_floor_is_inactive():
    assert not DistrictTarget(VF, weight=0.0).is_active
    assert DistrictTarget(VF, weight=0.0, minimum_rate=0.5).is_active


def test_district_target_rejects_negative_weight_and_non_positive_floor():
    with pytest.raises(ValueError, match="weight"):
        DistrictTarget(VF, weight=-1.0)
    with pytest.raises(ValueError, match="minimum_rate"):
        DistrictTarget(VF, minimum_rate=0.0)


def test_district_request_needs_a_target():
    with pytest.raises(ValueError, match="at least one target"):
        DistrictRequest(targets=())


def test_district_request_rejects_duplicates():
    with pytest.raises(ValueError, match="duplicate"):
        DistrictRequest(targets=(DistrictTarget(VF), DistrictTarget(VF, weight=2.0)))


def test_district_request_refuses_all_excluded():
    """Exclusion is per target; a request with nothing active is not a solve."""
    with pytest.raises(ValueError, match="weight 0 and no floor"):
        DistrictRequest(targets=(DistrictTarget(VF, weight=0.0), DistrictTarget(SP, weight=0.0)))


def test_district_request_target_cannot_also_be_capped():
    with pytest.raises(ValueError, match="both a target and a capped input"):
        DistrictRequest(targets=(DistrictTarget(ORE),), resource_caps=(ResourceCap(ORE, 1.0),))


def test_a_bill_product_has_positive_units_and_is_active_at_weight_zero():
    t = DistrictTarget(VF, weight=0.0, bill_units=1000.0)
    assert t.is_bill and t.is_active
    with pytest.raises(ValueError, match="bill_units must be positive"):
        DistrictTarget(VF, bill_units=0.0)


def test_bill_total_sums_bill_products_only():
    r = DistrictRequest(targets=(DistrictTarget(VF, bill_units=1000.0), DistrictTarget(SP, bill_units=200.0),
                                 DistrictTarget(ORE if False else "Desc_Motor_C")))
    assert r.bill_total == 1200.0
