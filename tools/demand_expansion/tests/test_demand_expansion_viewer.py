"""The viewer payload: reference facts, the route table, the alternates list,
and the engine's results as the oracle the page checks itself against."""
from __future__ import annotations

import json

import pytest

from production_adapter import load_game_build, load_project_assembly, load_recipe_unlocks

from demand_expansion import (
    FIXTURE_COMBOS, PROJECT_ASSEMBLY_MULTIPLIERS, RECIPE_MULTIPLIERS, viewer_payload,
)

MOTOR = "Desc_Motor_C"
SP = "Desc_SpaceElevatorPart_1_C"


@pytest.fixture(scope="module")
def payload(default_graph, repo_root, canonical):
    return viewer_payload(
        default_graph, load_project_assembly(repo_root, canonical), load_game_build(repo_root),
        load_recipe_unlocks(repo_root),
    )


def test_option_sets_are_the_records(payload):
    """Record 3.2.1, less the sub-1x recipe settings (floor rule open)."""
    assert RECIPE_MULTIPLIERS == (1.0, 1.25, 1.5, 1.75, 2.0)
    assert PROJECT_ASSEMBLY_MULTIPLIERS == (0.25, 0.5, 0.75, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0)
    assert payload["recipe_multipliers"] == ["1", "1.25", "1.5", "1.75", "2"]
    assert payload["pa_multipliers"] == ["0.25", "0.5", "0.75", "1", "2", "5", "10", "25", "50", "100"]


def test_reference_facts_and_route_table(payload):
    assert len(payload["recipes"]) == 291
    plastic = payload["recipes"]["Recipe_Plastic_C"]
    assert plastic["in"] == [["Desc_LiquidOil_C", 3.0, "m3"]]
    assert plastic["out"] == [["Desc_Plastic_C", 2.0, "items"], ["Desc_HeavyOilResidue_C", 1.0, "m3"]]
    assert payload["routes"]["name"] == "default-2026-10-10"
    assert payload["routes"]["pins"] == [["Desc_Plastic_C", "Recipe_Plastic_C"], ["Desc_Rubber_C", "Recipe_Rubber_C"]]
    assert len(payload["routes"]["exclusions"]) == 14
    assert len(payload["deliveries"]) == 15 and payload["deliveries"][0][2] == SP
    assert payload["fluid_rounding_unit"] == "mL"


def test_alternates_list_names_the_inapplicable(payload):
    alts = payload["alternates"]
    assert len(alts) == 110
    by_name = {a[1]: a for a in alts}
    assert by_name["Alternate: Steeled Frame"][2] == "Desc_ModularFrame_C"
    assert by_name["Alternate: Steeled Frame"][3] == "T4 Alternate: Steeled Frame"
    assert by_name["Alternate: Steeled Frame"][4] == ""
    assert "resource" in by_name["Alternate: Charcoal"][4]
    assert "not listed" in by_name["Alternate: Automated Miner"][4]
    assert "base-recipe pin" in by_name["Alternate: Recycled Plastic"][4]
    assert sum(1 for a in alts if a[4]) == 5


def test_the_oracle_carries_the_motor_figures(payload):
    assert set(payload["oracle"]["coefficients"]) == {"1", "1.25", "1.5", "1.75", "2"}
    rows = {(r[0], r[1]): r for r in payload["oracle"]["coefficients"]["1.25"]}
    assert rows[(MOTOR, "Desc_SpaceElevatorPart_8_C")][2] == 16.5
    assert rows[(MOTOR, "Desc_SpaceElevatorPart_4_C")][3] == 3
    assert rows[("Desc_HeavyOilResidue_C", "Desc_PetroleumCoke_C")][5] == "C"
    assert rows[("Desc_OreIron_C", "Desc_SpaceElevatorPart_8_C")][5] == "R"
    assert FIXTURE_COMBOS == ((1.0, 1.0), (1.25, 2.0))
    cells = payload["oracle"]["phases"]["1.25|2"]["cells"]
    assert [c[2] for c in cells if c[0] == MOTOR] == [0, 0, 3000, 8250, 6600]
    assert payload["oracle"]["phases"]["1|1"]["complete"]["5"] is False


def test_payload_is_deterministic_json_and_bounded(default_graph, repo_root, canonical, payload):
    again = viewer_payload(
        default_graph, load_project_assembly(repo_root, canonical), load_game_build(repo_root),
        load_recipe_unlocks(repo_root),
    )
    assert again == payload
    assert len(json.dumps(payload, separators=(",", ":"), sort_keys=True)) < 1_500_000
