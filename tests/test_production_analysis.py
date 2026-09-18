"""The comparator: it quantifies a trade-off and refuses to resolve one.

Two properties are load-bearing and both are asserted structurally rather than
trusted to review:

    it cannot recommend      no ranking vocabulary in the public surface, nothing
                             returns a single variant, caller order is preserved
    it cannot mislead        variants that do not share a feasible set are reported
                             as not comparable, never cross-priced into a number

Plan section 1.5 and formulation record section 12.2 (D3b) are what this is for.
"""
import pathlib

import pytest

from production_adapter import (
    AllowedRecipes, CHALLENGE_1_25X_2X, OutputTarget, RecipeMode, ResourceCap,
    SolveRequest, Weights, load,
)
from production_adapter.analysis import (
    Comparison, Solved, Variant, compare, power_statistic_variants,
)
from production_adapter.lp_backend import LpBackend, PowerStatistic, UnconsumedMode

REPO = pathlib.Path(__file__).resolve().parents[1]

IRON_PLATE = "Desc_IronPlate_C"
# Selection is identical under all three statistics here.
WARP_DRIVE = "Desc_SpaceElevatorPart_11_C"
# Selection differs: MAX swaps an alternate Dark Matter route for the base one.
ROCKET = "Desc_SpaceElevatorPart_12_C"


@pytest.fixture(scope="module")
def data():
    return load(REPO)


def _request(item, rate=1.0, **kwargs):
    kwargs.setdefault("allowed_recipes", AllowedRecipes(mode=RecipeMode.ALL))
    return SolveRequest(outputs=(OutputTarget(item, rate),), **kwargs)


# --- the arithmetic -------------------------------------------------------

def test_objective_matches_a_hand_calculation(data):
    """Iron Plate 20/min at default weights: 30.00 ore + 8.00 MW + 2.00 machines."""
    c = compare(power_statistic_variants(
        _request(IRON_PLATE, 20.0, allowed_recipes=AllowedRecipes(mode=RecipeMode.BASE_ONLY)),
        data,
    ))
    for variant in c.variants:
        assert variant.raw_total_per_min == pytest.approx(30.0, abs=1e-4)
        assert variant.machine_total == pytest.approx(2.0, abs=1e-4)
        assert variant.objective == pytest.approx(40.0, abs=1e-4)


def test_regret_is_zero_on_the_diagonal(data):
    c = compare(power_statistic_variants(_request(ROCKET), data))
    for label in c.labels:
        assert c.regret[(label, label)] == pytest.approx(0.0, abs=1e-9)


def test_regret_is_never_negative(data):
    """Comparable variants share a feasible set, so a plan can never undercut an optimum."""
    for item in (ROCKET, WARP_DRIVE, IRON_PLATE):
        c = compare(power_statistic_variants(_request(item), data))
        for value in c.regret.values():
            assert value is not None
            assert value >= 0.0


# --- the D2 instance ------------------------------------------------------

def test_identical_selection_shows_as_negligible_regret_everywhere(data):
    """Ballistic Warp Drive: the statistic moves the reported MW and nothing else.

    Regret is *negligible* rather than exactly zero. The recipe sets are identical,
    but the LP is degenerate and the machine equivalents differ between solves in
    the last few digits, which prices through as a relative regret around 1e-10.
    Asserting an absolute zero here would be asserting something about HiGHS'
    floating point, not about the model.
    """
    c = compare(power_statistic_variants(_request(WARP_DRIVE), data))
    for only_a, only_b in c.recipe_differences.values():
        assert only_a == () and only_b == ()
    optimum = {v.label: v.objective for v in c.variants}
    for (_, metric), value in c.regret.items():
        assert value / max(1.0, optimum[metric]) < 1e-8
    reported = {v.label: v.power_stat_mw for v in c.variants}
    assert reported["min"] < reported["mean"] < reported["max"]


def test_differing_selection_shows_as_non_zero_regret(data):
    """Thermal Propulsion Rocket: MAX picks a different Dark Matter route."""
    c = compare(power_statistic_variants(_request(ROCKET), data))
    assert any(only_a or only_b for only_a, only_b in c.recipe_differences.values())
    assert any(v > 0.0 for v in c.regret.values())


def test_power_statistic_variants_returns_the_three_in_statistic_order(data):
    variants = power_statistic_variants(_request(IRON_PLATE, 20.0), data)
    assert [v.label for v in variants] == ["min", "mean", "max"]
    assert [v.backend.power_statistic for v in variants] == [
        PowerStatistic.MIN, PowerStatistic.MEAN, PowerStatistic.MAX
    ]


def test_power_statistic_variants_refuses_a_pinned_statistic(data):
    with pytest.raises(ValueError, match="what this varies"):
        power_statistic_variants(_request(IRON_PLATE, 20.0), data,
                                 power_statistic=PowerStatistic.MEAN)


# --- the feasibility guard ------------------------------------------------

def _labels_of_incomparable(c):
    return {pair for pair in c.incomparable}


def test_a_different_scenario_is_not_cross_priced(data):
    request = _request(IRON_PLATE, 20.0)
    c = compare((
        Variant("canonical", request, data, LpBackend(PowerStatistic.MEAN)),
        Variant("challenge", request, data.with_scenario(CHALLENGE_1_25X_2X),
                LpBackend(PowerStatistic.MEAN)),
    ))
    assert c.regret[("canonical", "challenge")] is None
    assert "scenario" in c.incomparable[("canonical", "challenge")]
    assert c.regret[("canonical", "canonical")] == pytest.approx(0.0)


def test_a_different_recipe_set_is_not_cross_priced(data):
    c = compare((
        Variant("base", _request(IRON_PLATE, 20.0,
                allowed_recipes=AllowedRecipes(mode=RecipeMode.BASE_ONLY)),
                data, LpBackend(PowerStatistic.MEAN)),
        Variant("all", _request(IRON_PLATE, 20.0), data, LpBackend(PowerStatistic.MEAN)),
    ))
    assert c.regret[("base", "all")] is None
    assert "enabled recipe sets" in c.incomparable[("base", "all")]


def test_a_different_unconsumed_mode_is_not_cross_priced(data):
    request = _request(IRON_PLATE, 20.0)
    c = compare((
        Variant("free", request, data, LpBackend(PowerStatistic.MEAN)),
        Variant("forbid", request, data,
                LpBackend(PowerStatistic.MEAN, unconsumed=UnconsumedMode.FORBID)),
    ))
    assert c.regret[("free", "forbid")] is None
    assert "unconsumed mode" in c.incomparable[("free", "forbid")]


def test_a_different_cap_is_not_cross_priced(data):
    c = compare((
        Variant("uncapped", _request(IRON_PLATE, 20.0), data, LpBackend(PowerStatistic.MEAN)),
        Variant("capped", _request(IRON_PLATE, 20.0,
                resource_caps=(ResourceCap("Desc_OreIron_C", 29.0),)),
                data, LpBackend(PowerStatistic.MEAN)),
    ))
    assert c.regret[("uncapped", "capped")] is None
    assert "resource caps" in c.incomparable[("uncapped", "capped")]


def test_differing_weights_ARE_comparable(data):
    """Weights are the metric, not the constraint set — this is the whole point."""
    balanced = _request(ROCKET)
    resources_only = _request(ROCKET, weights=Weights(resources=1.0, power=0.0, buildings=0.0))
    c = compare((
        Variant("balanced", balanced, data, LpBackend(PowerStatistic.MEAN)),
        Variant("res-only", resources_only, data, LpBackend(PowerStatistic.MEAN)),
    ))
    assert c.incomparable == {}
    assert all(v is not None and v >= 0.0 for v in c.regret.values())


# --- the structural guards ------------------------------------------------

RANKING_VOCABULARY = (
    "best", "rank", "recommend", "winner", "prefer", "score", "sort", "top_", "choose",
)


def test_the_public_surface_has_no_ranking_vocabulary():
    import production_adapter.analysis as mod

    public = [n for n in dir(mod) if not n.startswith("_")]
    for name in public:
        lowered = name.lower()
        assert not any(word in lowered for word in RANKING_VOCABULARY), name
    for cls in (Comparison, Solved, Variant):
        for name in dir(cls):
            if name.startswith("_"):
                continue
            lowered = name.lower()
            assert not any(word in lowered for word in RANKING_VOCABULARY), f"{cls}.{name}"


def test_nothing_returns_a_single_variant(data):
    """The guard mirroring _demand_oracle's: it cannot pick, so it cannot become the planner."""
    c = compare(power_statistic_variants(_request(ROCKET), data))
    for name in dir(c):
        if name.startswith("_"):
            continue
        attribute = getattr(c, name)
        value = attribute() if callable(attribute) else attribute
        assert not isinstance(value, Solved), name


def test_caller_order_is_preserved_not_sorted(data):
    """A sorted output would be a ranking by another name."""
    request = _request(IRON_PLATE, 20.0)
    ordered = compare((
        Variant("zulu", request, data, LpBackend(PowerStatistic.MAX)),
        Variant("alpha", request, data, LpBackend(PowerStatistic.MIN)),
        Variant("mike", request, data, LpBackend(PowerStatistic.MEAN)),
    ))
    assert ordered.labels == ("zulu", "alpha", "mike")


def test_a_comparison_needs_at_least_two_variants(data):
    with pytest.raises(ValueError, match="at least two"):
        compare(power_statistic_variants(_request(IRON_PLATE, 20.0), data)[:1])


def test_duplicate_labels_are_rejected(data):
    request = _request(IRON_PLATE, 20.0)
    with pytest.raises(ValueError, match="unique"):
        compare((
            Variant("same", request, data, LpBackend(PowerStatistic.MIN)),
            Variant("same", request, data, LpBackend(PowerStatistic.MAX)),
        ))


def test_an_empty_label_is_rejected(data):
    with pytest.raises(ValueError, match="label"):
        Variant("  ", _request(IRON_PLATE, 20.0), data, LpBackend(PowerStatistic.MIN))


# --- presentation ---------------------------------------------------------

def test_the_table_names_every_variant_and_marks_what_cannot_be_compared(data):
    request = _request(IRON_PLATE, 20.0)
    c = compare((
        Variant("canonical", request, data, LpBackend(PowerStatistic.MEAN)),
        Variant("challenge", request, data.with_scenario(CHALLENGE_1_25X_2X),
                LpBackend(PowerStatistic.MEAN)),
    ))
    table = c.format_table()
    for label in c.labels:
        assert label in table
    assert "n/a" in table
    assert "not comparable:" in table


def test_analysis_is_not_imported_by_the_package_root():
    """Dependency direction, section 11.1. The contract package stays scipy-free."""
    import production_adapter

    assert not hasattr(production_adapter, "compare")
    assert not hasattr(production_adapter, "Variant")
