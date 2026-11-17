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

    OBSERVED in game 2026-09-21, 1.25x save on 1.2.4.0 CL#502094:
    Recipe_Cable_C costs 2 Wire at 1x and reads 3 at 1.25x, so 2.5 rounds up.
    With 3.2.4's 1.25 -> 1, 3.75 -> 4 and 12 -> 15, the rule is fully
    determined: half-to-even, half-down and truncation all give 2 here, and
    ceiling is ruled out by the 1.25 -> 1 reading.

    Storage review 10.3's two-building probe is VOID and is not the source:
    building costs do not scale with the multiplier at all, so a building's
    cost of 2 carries no information about rounding. The 6.0 -> 8.0 case
    below follows from the confirmed rule and is not itself observed.
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


# --- sub-1x floors (demand A5; reframe A15.2 B4; reconciliation R4) ---------
# Until 2026-11-17 one declared `input_amount_floor` floored solids and fluids
# alike, and sub-1x refused without it (record 3.2.3: unobserved). A5.1 then
# observed the solid floor (1) and Greg decided it is the default (A15.2 B4);
# the fluid floor's unit is still open (A5.2), so only it is declared now.

def test_sub_1x_refuses_without_a_declared_fluid_floor():
    """A5.2: the fluid floor's unit is unobserved, so it is declared, not assumed."""
    from production_adapter.scenario import FluidFloorUndeclared

    with pytest.raises(FluidFloorUndeclared, match="fluid_input_floor"):
        Scenario(recipe_input_multiplier=0.75)


@pytest.mark.parametrize("fluid_floor", [0, 1])
def test_the_solid_floor_is_the_observed_one_whatever_the_fluid_floor(fluid_floor):
    """A5.1, Greg 2026-10-26 on a 0.25x save: Iron Rod's 1 Iron Ingot reads 1
    (0.25 rounds to 0); the earlier read 3 Iron Ingot -> 0.75 -> 1 agrees."""
    s = Scenario(recipe_input_multiplier=0.25, fluid_input_floor=fluid_floor)
    assert s.apply_input_amount(1.0) == pytest.approx(1.0)    # the floor read
    assert s.apply_input_amount(3.0) == pytest.approx(1.0)    # 0.75 -> 1, rounding alone
    assert s.apply_input_amount(12.0) == pytest.approx(3.0)   # above the floor, untouched


def test_the_fluid_floor_is_what_was_declared():
    """A5.2's discriminating case: Plastic's 3 m3 Crude Oil at 0.25x is 0.75
    if the floor is one internal unit, 1 if it is one m3."""
    internal = Scenario(recipe_input_multiplier=0.25, fluid_input_floor=0)
    stated = Scenario(recipe_input_multiplier=0.25, fluid_input_floor=1)
    assert internal.apply_input_amount(3.0, FLUID_UNIT) == pytest.approx(0.75)
    assert stated.apply_input_amount(3.0, FLUID_UNIT) == pytest.approx(1.0)
    assert stated.apply_input_amount(1.0, ITEM_UNIT) == pytest.approx(1.0)


def test_the_legacy_floor_of_one_keeps_its_meaning():
    """portfolio-inputs/2 carries input_amount_floor; 1 meant solids and
    fluids at 1, and still computes exactly that."""
    legacy = Scenario(recipe_input_multiplier=0.25, input_amount_floor=1)
    assert legacy.fluid_input_floor == 1
    assert legacy.apply_input_amount(1.0) == pytest.approx(1.0)
    assert legacy.apply_input_amount(3.0, FLUID_UNIT) == pytest.approx(1.0)


@pytest.mark.parametrize("kw, match", [
    ({"input_amount_floor": 0}, "observed to be 1"),          # solids to 0: contradicts A5.1
    ({"input_amount_floor": 2}, "observed to be 1"),
    ({"input_amount_floor": 1, "fluid_input_floor": 0}, "contradicts"),
    ({"fluid_input_floor": -1}, "negative"),
])
def test_floors_that_contradict_the_read_are_refused(kw, match):
    with pytest.raises(ValueError, match=match):
        Scenario(recipe_input_multiplier=0.25, **kw)


def test_no_floor_binds_at_or_above_1x():
    """At >= 1x no positive canonical input can round below its own unit."""
    s = Scenario(recipe_input_multiplier=1.25, fluid_input_floor=1)
    assert s.apply_input_amount(1.0) == pytest.approx(1.0)
    assert s.apply_input_amount(2.5, FLUID_UNIT) == pytest.approx(3.125)


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


# --- fluid rounding is a declared field (demand-expansion Amendment 1, C) ----

def test_fluid_rounding_defaults_to_the_adapter_constant():
    from production_adapter.scenario import FLUID_ROUNDING_UNIT

    assert Scenario().fluid_rounding_unit == FLUID_ROUNDING_UNIT


@pytest.mark.parametrize("unit, expected", [("m3", 4.0), ("mL", 3.75), (None, 3.75)])
def test_fluid_rounding_variants(unit, expected):
    """3 m3 x 1.25: 4 in the displayed unit, 3.75 in the game's internal one.
    Observed 3.75 on a 1.25x save (demand A2, 2026-10-10), so "mL" is the
    default; the other two stay selectable to reproduce older figures."""
    s = Scenario(recipe_input_multiplier=1.25, fluid_rounding_unit=unit)
    assert s.apply_input_amount(3.0, FLUID_UNIT) == pytest.approx(expected)
    assert s.apply_input_amount(3.0, ITEM_UNIT) == pytest.approx(4.0)   # solids unaffected


def test_fluid_rounding_refuses_an_unknown_unit():
    with pytest.raises(ValueError, match="fluid_rounding_unit"):
        Scenario(fluid_rounding_unit="litres")


def test_canonical_keeps_the_declared_unit():
    s = Scenario(recipe_input_multiplier=1.25, fluid_rounding_unit="mL")
    assert s.canonical().is_canonical
    assert s.canonical().fluid_rounding_unit == "mL"
