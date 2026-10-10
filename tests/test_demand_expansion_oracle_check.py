"""The engine against the oracle, on the chains the oracle can resolve.

`tests/_demand_oracle.py` propagates RATES down base recipes and refuses to
choose; `demand_expansion` propagates QUANTITIES per unit under a route table
and refuses to choose. At a demand of one per minute the oracle's raw inputs
per minute equal the engine's embedded resources per unit, and both apply
record 3.2.5's rounding on their own. They were written three weeks apart and
share no code; agreement is the check (plan section 11).
"""
from __future__ import annotations

import pathlib

import pytest

from _demand_oracle import demand
from production_adapter import Scenario, load

from demand_expansion import DEFAULT_ROUTES, build, expand

REPO = pathlib.Path(__file__).resolve().parents[1]

EARLY = {
    "Desc_SpaceElevatorPart_1_C": "Smart Plating",
    "Desc_SpaceElevatorPart_2_C": "Versatile Framework",
    "Desc_SpaceElevatorPart_3_C": "Automated Wiring",
    "Desc_ModularFrame_C": "Modular Frame",
    "Desc_Motor_C": "Motor",
}


@pytest.fixture(scope="module")
def graph():
    return build(load(REPO), DEFAULT_ROUTES)


@pytest.mark.parametrize("item", list(EARLY), ids=list(EARLY.values()))
@pytest.mark.parametrize("multiplier", [1.0, 1.25, 1.5])
def test_engine_resources_equal_oracle_raw_inputs(graph, item, multiplier):
    oracle = demand(item, 1.0, input_multiplier=multiplier)
    engine = expand(
        graph, item, Scenario(recipe_input_multiplier=multiplier), fluid_rounding="m3"
    )
    resources = {k: float(v) for k, v in engine.embedded.items() if graph.is_resource(k)}
    assert resources == pytest.approx(oracle.raw_inputs)


def test_engine_recipe_cycles_equal_oracle_machine_equivalents(graph):
    """The oracle's multiplier is fractional machines at 1/min; a machine runs
    60/duration cycles per minute, so cycles per unit = machines x 60/duration."""
    data = load(REPO)
    oracle = demand("Desc_SpaceElevatorPart_1_C", 1.0)
    engine = expand(graph, "Desc_SpaceElevatorPart_1_C")
    assert set(engine.recipe_cycles) == set(oracle.recipe_multipliers)
    for rid, machines in oracle.recipe_multipliers.items():
        cycles = machines * data.recipes[rid].cycles_per_min
        assert float(engine.recipe_cycles[rid]) == pytest.approx(cycles), rid
