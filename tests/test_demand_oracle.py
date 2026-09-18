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
    """A 1.25x setting raises raw demand by more than 1.25x — that is correct."""
    base = demand(SMART_PLATING, 1.0).raw_inputs[IRON_ORE]
    scaled = demand(SMART_PLATING, 1.0, input_multiplier=1.25).raw_inputs[IRON_ORE]
    assert scaled > base * 1.25
    assert scaled == pytest.approx(62.408447265625)


def test_multiplier_applies_once_per_stage():
    """Iron Plate -> Ingot -> Ore is two stages, so 30 * 1.25 ** 2."""
    r = demand(IRON_PLATE, 20.0, input_multiplier=1.25)
    assert r.raw_inputs[IRON_ORE] == pytest.approx(30.0 * 1.25 ** 2)
    assert r.raw_inputs[IRON_ORE] == pytest.approx(46.875)


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
