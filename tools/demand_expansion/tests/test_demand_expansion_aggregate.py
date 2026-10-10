"""Phase aggregation against VALIDATION.md table 2 and the self-count rule.

Delivery rows come from the loader; the module is handed them (record §6).
"""
from __future__ import annotations

from fractions import Fraction as F

import pytest

from production_adapter import Scenario, load_project_assembly

from demand_expansion import DemandExpansionError, aggregate

MOTOR = "Desc_Motor_C"
SP = "Desc_SpaceElevatorPart_1_C"
ME = "Desc_SpaceElevatorPart_4_C"
BS = "Desc_SpaceElevatorPart_10_C"   # Biochemical Sculptor
AES = "Desc_SpaceElevatorPart_12_C"  # AI Expansion Server


@pytest.fixture(scope="module")
def deliveries(repo_root, canonical):
    return load_project_assembly(repo_root, canonical)


@pytest.fixture(scope="module")
def table(default_graph, deliveries):
    return aggregate(default_graph, deliveries)


def test_phases_and_completeness(table):
    assert table.phases == (1, 2, 3, 4, 5)
    assert table.complete == {1: True, 2: True, 3: True, 4: True, 5: False}
    assert {(u.phase, u.item_id) for u in table.unresolved} == {(5, BS), (5, AES)}
    assert all(u.refusal.startswith("AmbiguousRoute: Desc_FicsiteIngot_C") for u in table.unresolved)
    assert len(table.deliveries) == 15
    assert len(table.cells) == 72


def test_motors_per_phase_table_2(table):
    """0 / 0 / 1,000 / 2,250 / 1,800 at 1x. Phase 5 is a lower bound in the
    strict sense: the two refused deliveries are not counted."""
    cells = table.item(MOTOR)
    assert [c.quantity for c in cells] == [0, 0, 1000, 2250, 1800]
    assert [c.previous for c in cells] == [0, 0, 0, 1000, 2250]
    assert [c.growth.kind for c in cells] == ["none", "none", "new", "ratio", "ratio"]
    assert [c.growth.ratio for c in cells] == [None, None, None, F(9, 4), F(4, 5)]
    assert [c.cumulative for c in cells] == [0, 0, 1000, 3250, 5050]
    assert [c.remaining for c in cells] == [5050, 5050, 4050, 1800, 0]
    assert [c.complete for c in cells] == [True, True, True, True, False]
    assert [c.cumulative_complete for c in cells] == [True, True, True, True, False]
    assert [c.remaining_complete for c in cells] == [False, False, False, False, True]
    assert table.first_phase(MOTOR) == 3
    assert table.last_phase(MOTOR) == 5


def test_a_delivered_item_counts_as_itself(table):
    """Phase 3 delivers 500 Modular Engines; phase 4's 250 rockets embed 2.5
    each; phase 5's 200 warp drives embed 2.5 each through the rocket."""
    assert [c.quantity for c in table.item(ME)] == [0, 0, 500, 625, 500]
    assert table.item(ME)[3].growth.ratio == F(5, 4)


def test_smart_plating_across_the_game(table):
    """50 delivered, 1,000 delivered, 1,000 via Modular Engine (2 each), 1,250
    via the rocket (5 each), 1,000 via the warp drive (5 each)."""
    assert [c.quantity for c in table.item(SP)] == [50, 1000, 1000, 1250, 1000]
    assert table.item(SP)[1].growth.ratio == 20
    assert table.item(SP)[2].growth.ratio == 1


def test_an_item_never_required_has_no_cells(table):
    assert table.item("Desc_Wood_C") == ()
    assert table.first_phase("Desc_Wood_C") is None


def test_project_assembly_multiplier_is_its_own_column(default_graph, deliveries):
    """0.25x: phase 1's 50 Smart Plating becomes 13 (12.5 -> 13, observed
    2026-09-22), and the scaled quantity is what gets expanded."""
    t = aggregate(default_graph, deliveries, Scenario(project_assembly_requirement_multiplier=0.25))
    assert t.project_assembly_multiplier == 0.25
    assert t.recipe_input_multiplier == 1.0
    assert [c.quantity for c in t.item(SP)] == [13, 250, 250, 315, 250]
    assert t.deliveries[0].quantity_1x == 50.0
    assert t.deliveries[0].quantity == 13


def test_the_scenario_of_record_shape(default_graph, deliveries):
    """1.25x recipes, 2x deliveries: the Motor cells double the 1.25x per-unit
    figures (3 / 16.5 / 16.5), and the fluid rule in force is reported."""
    t = aggregate(default_graph, deliveries, Scenario(
        recipe_input_multiplier=1.25, project_assembly_requirement_multiplier=2.0,
    ))
    assert [c.quantity for c in t.item(MOTOR)] == [0, 0, 3000, 8250, 6600]
    assert t.fluid_rounding_unit == "mL"


def test_previous_means_previous_in_the_sequence(default_graph, deliveries):
    """A caller naming phases 3 and 5 only gets phase 3 as phase 5's previous."""
    subset = tuple(d for d in deliveries if d.phase in (3, 5))
    t = aggregate(default_graph, subset)
    assert t.phases == (3, 5)
    cells = t.item(MOTOR)
    assert cells[1].previous == 1000
    assert cells[1].growth.ratio == F(9, 5)
    assert cells[0].remaining == 1800 and not cells[0].remaining_complete


def test_no_deliveries_is_refused(default_graph):
    with pytest.raises(DemandExpansionError):
        aggregate(default_graph, ())
