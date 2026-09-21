"""Tests for the reconciliation oracle, including its refusal to choose."""
import pytest

from _demand_oracle import AmbiguousDemand, OracleResult, UnproducibleItem, demand

SMART_PLATING = "Desc_SpaceElevatorPart_1_C"
IRON_PLATE = "Desc_IronPlate_C"
IRON_ORE = "Desc_OreIron_C"


def test_iron_plate_chain():
    r = demand(IRON_PLATE, 20.0)
    assert r.raw_inputs == pytest.approx({IRON_ORE: 30.0})
    assert r.recipe_multipliers["Recipe_IronPlate_C"] == pytest.approx(1.0)
    assert r.recipe_multipliers["Recipe_IngotIron_C"] == pytest.approx(1.0)


def test_smart_plating_matches_the_phase_0_reconciliation():
    """These are the figures Candidate A produced during solver evaluation."""
    r = demand(SMART_PLATING, 1.0)
    assert r.raw_inputs[IRON_ORE] == pytest.approx(23.25)
    expected = {
        "Recipe_SpaceElevatorPart_1_C": 0.5,
        "Recipe_IronPlateReinforced_C": 0.2,
        "Recipe_Rotor_C": 0.25,
        "Recipe_IronPlate_C": 0.3,
        "Recipe_IronRod_C": 0.95,
        "Recipe_Screw_C": 0.925,
        "Recipe_IngotIron_C": 0.775,
    }
    assert r.recipe_multipliers == pytest.approx(expected)


def test_scales_linearly():
    one, ten = demand(SMART_PLATING, 1.0), demand(SMART_PLATING, 10.0)
    assert ten.raw_inputs[IRON_ORE] == pytest.approx(one.raw_inputs[IRON_ORE] * 10)


def test_input_multiplier_compounds_across_stages():
    """A 1.25x setting raises raw demand by more than 1.25x — that is correct.

    62.408447265625 was this assertion until 2026-09-21: 1.25 raised to the
    stages the demand crosses, with nothing rounded. Demand-expansion record
    3.2.5 supersedes it — the multiplier lands on per-cycle parts and rounds per
    input, and on this chain most of it rounds away. It still compounds rather
    than scaling once, which is what this test is for; it is simply much smaller
    than the unrounded arithmetic said.
    """
    base = demand(SMART_PLATING, 1.0).raw_inputs[IRON_ORE]
    scaled = demand(SMART_PLATING, 1.0, input_multiplier=1.25).raw_inputs[IRON_ORE]
    assert scaled > base * 1.25
    assert scaled == pytest.approx(33.5)


def test_multiplier_applies_once_per_stage():
    """Iron Plate -> Ingot -> Ore is two stages, but only the first one rounds up.

    Iron Plate's 3 ingot goes to 3.75 and rounds to 4 (40/min); Iron Ingot's
    single ore goes to 1.25 and rounds back to 1, so the second stage does not
    compound at all. 46.875 — 30 * 1.25 ** 2 — was the unrounded figure.
    """
    r = demand(IRON_PLATE, 20.0, input_multiplier=1.25)
    assert r.raw_inputs[IRON_ORE] == pytest.approx(40.0)
    assert r.raw_inputs[IRON_ORE] < 30.0 * 1.25 ** 2


def test_the_oracle_and_the_adapter_round_the_same_way():
    """The two implementations are deliberately separate; this pins them together.

    `_demand_oracle` reimplements record 3.2.5 from the CSVs rather than
    importing `production_adapter.scenario`, so that it stays an independent
    check. Independent is not the same as free to disagree: both land on 33.50
    ore for Smart Plating and 40.00 for Iron Plate, and the LP backend's own
    tests assert those same two figures from the other side.
    """
    assert demand(SMART_PLATING, 1.0, input_multiplier=1.25).raw_inputs[IRON_ORE] \
        == pytest.approx(33.5)
    assert demand(IRON_PLATE, 20.0, input_multiplier=1.25).raw_inputs[IRON_ORE] \
        == pytest.approx(40.0)


def test_sub_1x_refuses_rather_than_assuming_a_floor():
    """Record 3.2.3: below 1x an input can round to zero and the rule is unobserved."""
    with pytest.raises(ValueError, match="floor"):
        demand(IRON_PLATE, 20.0, input_multiplier=0.75)


# --- the guardrail -------------------------------------------------------

def test_refuses_to_choose_between_recipes():
    """The structural guard. A thing that cannot choose cannot become a solver."""
    allowed = {"Recipe_IngotIron_C", "Recipe_Alternate_IngotIron_C", "Recipe_IronPlate_C"}
    with pytest.raises(AmbiguousDemand) as e:
        demand(IRON_PLATE, 20.0, allowed_recipes=allowed)
    assert "does not choose" in str(e.value)


def test_raises_when_nothing_produces_an_item():
    with pytest.raises(UnproducibleItem):
        demand(IRON_PLATE, 20.0, allowed_recipes={"Recipe_IronRod_C"})


def test_rejects_unknown_recipe_ids():
    with pytest.raises(ValueError):
        demand(IRON_PLATE, 1.0, allowed_recipes={"Recipe_NotAThing_C"})


def test_has_no_command_line_entry_point():
    """Keeping it un-runnable is half the guardrail."""
    import _demand_oracle as mod
    code = [
        ln for ln in open(mod.__file__, encoding="utf-8").read().splitlines()
        if not ln.lstrip().startswith("#")
    ]
    assert not [ln for ln in code if ln.startswith("if __name__")]
    assert not [ln for ln in code if ln.startswith(("import argparse", "import sys"))]
    assert not hasattr(mod, "main")


def test_reports_no_power_or_machine_counts():
    """Scope guard: the oracle checks arithmetic, it does not model factories."""
    assert set(OracleResult.__dataclass_fields__) == {"recipe_multipliers", "raw_inputs"}
