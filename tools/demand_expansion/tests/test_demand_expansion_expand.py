"""The engine against docs/demand_expansion/VALIDATION.md.

The fixtures were derived by hand and by scratch scripts over the CSVs before
the engine existed (plan review, 2026-10-10). The engine reproduces them; it
is not their source.
"""
from __future__ import annotations

from fractions import Fraction as F

import pytest

from production_adapter import Scenario
from production_adapter.gamedata import Item, PowerRange, Recipe, ReferenceData

from demand_expansion import (
    AlternatePin, AmbiguousRoute, CycleDetected, FluidRoundingUndeclared, NotExpandable,
    RouteTable, UnproducibleItem, build, expand,
)

MOTOR = "Desc_Motor_C"
ME = "Desc_SpaceElevatorPart_4_C"      # Modular Engine
TPR = "Desc_SpaceElevatorPart_8_C"     # Thermal Propulsion Rocket
BWD = "Desc_SpaceElevatorPart_11_C"    # Ballistic Warp Drive
SP = "Desc_SpaceElevatorPart_1_C"      # Smart Plating


def at(mult, fluid="m3"):
    return dict(scenario=Scenario(recipe_input_multiplier=mult), fluid_rounding=fluid)


# --- the Motor question -------------------------------------------------------

def test_motor_direct_in_modular_engine(default_graph):
    e = expand(default_graph, ME)
    assert e.direct[MOTOR] == 2
    assert e.embedded[MOTOR] == 2
    assert e.depth[MOTOR] == 1


def test_motor_embedded_in_the_rocket_by_two_paths(default_graph):
    """5 ME x 2 Motor + 2 Turbo Motor x 4 Motor, per 2 rockets: 9."""
    e = expand(default_graph, TPR)
    assert MOTOR not in e.direct
    assert e.embedded[MOTOR] == 9
    assert e.depth[MOTOR] == 2
    assert e.recipe_cycles["Recipe_SpaceElevatorPart_4_C"] == F(5, 2)
    assert e.recipe_cycles["Recipe_MotorTurbo_C"] == 1


def test_motor_embedded_in_the_warp_drive(default_graph):
    e = expand(default_graph, BWD)
    assert e.embedded[MOTOR] == 9
    assert e.depth[MOTOR] == 3


@pytest.mark.parametrize("target, expected", [
    (ME,  {1.0: 2, 1.25: 3, 1.5: 3, 2.0: 4}),
    (TPR, {1.0: 9, 1.25: F(33, 2), 1.5: 21, 2.0: 36}),
    (BWD, {1.0: 9, 1.25: F(33, 2), 1.5: 42, 2.0: 72}),
])
def test_motor_under_recipe_multipliers(default_graph, target, expected):
    """VALIDATION.md table 1. 1.25x on the rocket: round(6.25)=6 ME and
    round(2.5)=3 Turbo Motor per 2 rockets, round(5)=5 Motor per Turbo Motor,
    (6x3 + 3x5)/2. The two ties rest on the Cable 2.5 -> 3 read of 2026-09-21."""
    for mult, value in expected.items():
        e = expand(default_graph, target, **at(mult))
        assert e.embedded[MOTOR] == value, (target, mult)


def test_motor_is_independent_of_the_fluid_variant(default_graph):
    values = {
        fr: expand(default_graph, TPR, **at(1.25, fr)).embedded[MOTOR]
        for fr in ("m3", "mL", None)
    }
    assert set(values.values()) == {F(33, 2)}


def test_the_phase_totals(default_graph):
    """VALIDATION.md table 2: 500 ME, 250 TPR, 200 BWD at 1x deliveries."""
    motors = lambda t: expand(default_graph, t).embedded[MOTOR]
    assert 500 * motors(ME) == 1000
    assert 250 * motors(TPR) == 2250
    assert 200 * motors(BWD) == 1800


# --- the fluid variant is material -------------------------------------------

def test_fluid_rounding_variants_separate_on_the_rocket(default_graph):
    """VALIDATION.md table 3. Solids agree; Crude Oil per rocket differs by
    6.7% between "m3" and "mL"; "mL" and None coincide because no fluid count
    on this chain has a fractional millilitre."""
    m3 = expand(default_graph, TPR, **at(1.25, "m3")).embedded
    ml = expand(default_graph, TPR, **at(1.25, "mL")).embedded
    none = expand(default_graph, TPR, **at(1.25, None)).embedded
    assert m3["Desc_OreIron_C"] == ml["Desc_OreIron_C"] == F(39403, 16)
    assert m3["Desc_NitrogenGas_C"] == 403
    assert ml["Desc_NitrogenGas_C"] == F(1625, 4)
    assert m3["Desc_LiquidOil_C"] == F(1761, 2)
    assert ml["Desc_LiquidOil_C"] == F(26415, 32)
    assert ml == none
    assert abs(m3["Desc_LiquidOil_C"] / ml["Desc_LiquidOil_C"] - 1) > F(6, 100)


def test_rocket_at_1x(default_graph):
    e = expand(default_graph, TPR)
    assert e.embedded["Desc_NitrogenGas_C"] == 200
    assert e.embedded["Desc_Water_C"] == F(649, 2)
    assert e.embedded["Desc_LiquidOil_C"] == F(837, 4)
    assert e.embedded["Desc_OreIron_C"] == F(2679, 4)


def test_the_default_fluid_variant_is_the_observed_one(default_graph):
    """Amendment 2: Plastic at 1.25x shows 3.75 Crude Oil per cycle. Until that
    read this test asserted a refusal; a declared "mL" and no declaration now
    agree, and "m3" is the pre-read figure."""
    undeclared = expand(default_graph, TPR, scenario=Scenario(recipe_input_multiplier=1.25))
    assert undeclared.fluid_rounding_unit == "mL"
    assert undeclared.embedded["Desc_LiquidOil_C"] == F(26415, 32)
    assert undeclared.embedded == expand(default_graph, TPR, **at(1.25, "mL")).embedded
    with pytest.raises(FluidRoundingUndeclared):
        expand(default_graph, TPR, scenario=Scenario(recipe_input_multiplier=1.25),
               fluid_rounding="litres")
    with pytest.raises(FluidRoundingUndeclared):
        expand(default_graph, TPR, fluid_rounding="litres")   # at 1x too: never stamped


def test_plastic_at_1_25x_is_the_in_game_read(default_graph):
    """Greg, 2026-10-10, 1.25x save, 1.2.4.0 CL#502094: 3.75 Crude Oil per
    cycle, 20 Plastic and 10 Heavy Oil Residue per minute. Per unit of Plastic
    that is 1.875 Crude Oil and 0.5 HOR; the 1x recipe is 3 per 2."""
    e = expand(default_graph, "Desc_Plastic_C", scenario=Scenario(recipe_input_multiplier=1.25))
    assert e.direct == {"Desc_LiquidOil_C": F(15, 8)}
    assert e.coproducts == {"Desc_HeavyOilResidue_C": F(1, 2)}
    assert e.recipe_cycles == {"Recipe_Plastic_C": F(1, 2)}


def test_ml_and_none_cannot_differ_on_this_build(canonical):
    """Every per-cycle fluid count is a multiple of 0.5 m3 and every selectable
    multiplier a multiple of 0.25, so a scaled fluid is a whole number of
    millilitres. If a fractional count ever arrives, the two variants separate
    and the rule needs a second read."""
    for r in canonical.recipes.values():
        for _, amount, unit in r.input_amounts:
            if unit == "m3":
                assert (F(repr(amount)) * 2).denominator == 1, (r.recipe_id, amount)


# --- refusals ----------------------------------------------------------------

@pytest.mark.parametrize("target", [
    "Desc_SpaceElevatorPart_10_C",   # Biochemical Sculptor
    "Desc_SpaceElevatorPart_12_C",   # AI Expansion Server
])
def test_ficsite_ingot_is_refused_by_name(default_graph, target):
    with pytest.raises(AmbiguousRoute) as info:
        expand(default_graph, target)
    assert info.value.item_id == "Desc_FicsiteIngot_C"
    assert len(info.value.candidates) == 3
    assert info.value.path[0] == target


def test_every_other_delivery_expands(default_graph, repo_root, canonical):
    from production_adapter import load_project_assembly

    refused = set()
    for row in load_project_assembly(repo_root, canonical):
        try:
            expand(default_graph, row.item_id)
        except AmbiguousRoute:
            refused.add(row.item_id)
    assert refused == {"Desc_SpaceElevatorPart_10_C", "Desc_SpaceElevatorPart_12_C"}


def test_pre_scaled_data_is_refused(repo_root):
    """`load(repo_root, scenario)` is a supported path and its inputs are
    already rounded; building a graph from it would scale them again (3
    Motors -> 4 at 1.25x) or label 1.25x figures as 1x. Refused at build."""
    from production_adapter import load
    from demand_expansion import DEFAULT_ROUTES, DemandExpansionError, build

    with pytest.raises(DemandExpansionError, match="already carries"):
        build(load(repo_root, Scenario(recipe_input_multiplier=1.25)), DEFAULT_ROUTES)


def test_a_resource_is_not_a_target(default_graph):
    with pytest.raises(NotExpandable):
        expand(default_graph, "Desc_OreIron_C")


def test_turbofuel_is_unproducible_under_the_default_table(default_graph):
    """Its only base-flagged recipe is the is_alternate defect, excluded."""
    with pytest.raises(UnproducibleItem):
        expand(default_graph, "Desc_LiquidTurboFuel_C")


# --- coproducts and structure ------------------------------------------------

def test_coproducts_are_reported_not_netted(default_graph):
    """3 Crude Oil -> 2 Plastic + 1 Heavy Oil Residue."""
    e = expand(default_graph, "Desc_Plastic_C")
    assert e.direct == {"Desc_LiquidOil_C": F(3, 2)}
    assert e.coproducts == {"Desc_HeavyOilResidue_C": F(1, 2)}
    assert "Desc_HeavyOilResidue_C" not in e.embedded


def test_a_coproduct_leaf_is_reported_not_expanded(default_graph):
    """Petroleum Coke: 4 Heavy Oil Residue -> 12. HOR has no primary producer
    under the default table and is a coproduct of Plastic and Rubber, so the
    requirement is stated per unit and the walk stops there (Amendment 4)."""
    e = expand(default_graph, "Desc_PetroleumCoke_C")
    assert e.embedded == {"Desc_HeavyOilResidue_C": F(1, 3)}
    assert e.coproduct_leaves == ("Desc_HeavyOilResidue_C",)
    assert e.depth["Desc_HeavyOilResidue_C"] == 1
    with pytest.raises(NotExpandable, match="made only as a coproduct"):
        expand(default_graph, "Desc_HeavyOilResidue_C")


def test_a_declared_alternate_turns_a_leaf_back_into_an_item(canonical):
    """"The HOR alt just makes more": with it declared, HOR has a producer,
    is expanded into Crude Oil, and the coke target reaches the resource."""
    table = RouteTable(
        "x", alternates=(AlternatePin("Desc_HeavyOilResidue_C", "Recipe_Alternate_HeavyOilResidue_C", "r"),),
    )
    g = build(canonical, table)
    assert "Desc_HeavyOilResidue_C" not in g.coproduct_leaves
    e = expand(g, "Desc_PetroleumCoke_C")
    assert e.embedded["Desc_LiquidOil_C"] == F(1, 4)
    assert e.coproduct_leaves == ()


def test_smart_plating_matches_the_phase_0_reconciliation(default_graph):
    """23.25 Iron Ore per Smart Plating: the figure `tests/_demand_oracle.py`
    and Candidate A agreed on in Phase 0, now as a quantity per unit."""
    e = expand(default_graph, SP)
    assert e.embedded["Desc_OreIron_C"] == F(93, 4)
    assert e.recipe_cycles["Recipe_IngotIron_C"] == F(93, 4)
    assert e.recipe_cycles["Recipe_Screw_C"] == F(37, 4)


def _synthetic(recipes: dict[str, tuple[tuple[str, float], ...]], outputs: dict[str, str]):
    """A tiny ReferenceData: recipe -> inputs, recipe -> its one output."""
    items = {i for ins in recipes.values() for i, _ in ins} | set(outputs.values())
    return ReferenceData(
        game_build_id="synthetic",
        recipes={
            rid: Recipe(
                recipe_id=rid, display_name=rid, is_alternate=False, duration_sec=60.0,
                producer_class="Build_X_C",
                inputs=tuple((i, a) for i, a in ins),
                outputs=((outputs[rid], 1.0),),
                power=PowerRange(1.0, 1.0),
                input_amounts=tuple((i, a, "items") for i, a in ins),
                output_amounts=((outputs[rid], 1.0, "items"),),
            )
            for rid, ins in recipes.items()
        },
        producers={},
        items={i: Item(i, i, "solid", i == "Ore") for i in items},
        resource_items=frozenset({"Ore"}),
    )


def test_a_cycle_is_refused_by_name():
    data = _synthetic(
        {"R_A": (("B", 1.0),), "R_B": (("A", 1.0), ("Ore", 1.0))},
        {"R_A": "A", "R_B": "B"},
    )
    g = build(data, RouteTable("synthetic"))
    with pytest.raises(CycleDetected) as info:
        expand(g, "A")
    assert info.value.loop == ("A", "B", "A")


def test_depth_is_the_shortest_path():
    """A needs B and C; C needs B. B is at depth 1, not 2."""
    data = _synthetic(
        {"R_A": (("B", 1.0), ("C", 1.0)), "R_C": (("B", 2.0),), "R_B": (("Ore", 1.0),)},
        {"R_A": "A", "R_C": "C", "R_B": "B"},
    )
    e = expand(build(data, RouteTable("synthetic")), "A")
    assert e.depth == {"B": 1, "C": 1, "Ore": 2}
    assert e.embedded == {"B": 3, "C": 1, "Ore": 3}
