"""The viewer payload: engine results for every multiplier combination."""
from __future__ import annotations

import json

import pytest

from production_adapter import load_game_build, load_project_assembly

from demand_expansion import (
    PROJECT_ASSEMBLY_MULTIPLIERS, RECIPE_MULTIPLIERS, viewer_payload,
)

MOTOR = "Desc_Motor_C"
SP = "Desc_SpaceElevatorPart_1_C"


@pytest.fixture(scope="module")
def payload(default_graph, repo_root, canonical):
    return viewer_payload(default_graph, load_project_assembly(repo_root, canonical), load_game_build(repo_root))


def test_option_sets_are_the_records(payload):
    """Record 3.2.1, less the sub-1x recipe settings (floor rule open)."""
    assert RECIPE_MULTIPLIERS == (1.0, 1.25, 1.5, 1.75, 2.0)
    assert PROJECT_ASSEMBLY_MULTIPLIERS == (0.25, 0.5, 0.75, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0)
    assert payload["recipe_multipliers"] == ["1", "1.25", "1.5", "1.75", "2"]
    assert payload["pa_multipliers"] == ["0.25", "0.5", "0.75", "1", "2", "5", "10", "25", "50", "100"]
    assert set(payload["by_combo"]) == {f"{r}|{p}" for r in payload["recipe_multipliers"] for p in payload["pa_multipliers"]}


def _series(payload, combo, item):
    return [row[2] for row in payload["by_combo"][combo]["phases"] if row[0] == item]


def test_the_motor_figures_in_the_page(payload):
    assert _series(payload, "1|1", MOTOR) == [0, 0, 1000, 2250, 1800]
    assert _series(payload, "1.25|2", MOTOR) == [0, 0, 3000, 8250, 6600]
    assert _series(payload, "1|0.25", SP)[0] == 13            # 12.5 -> 13, observed
    assert _series(payload, "2|100", MOTOR)[2] == 500 * 100 * 4   # 4 Motors per Modular Engine at 2x


def test_coefficients_follow_only_the_recipe_multiplier(payload):
    rows = {(r[0], r[1]): r for r in payload["by_recipe"]["1.25"]["coefficients"]}
    assert rows[(MOTOR, "Desc_SpaceElevatorPart_8_C")][2] == 16.5
    assert rows[(MOTOR, "Desc_SpaceElevatorPart_4_C")][3] == 3      # direct, 2.5 -> 3
    assert rows[("Desc_HeavyOilResidue_C", "Desc_PetroleumCoke_C")][5] == "c"


def test_payload_is_deterministic_json_and_bounded(default_graph, repo_root, canonical, payload):
    again = viewer_payload(default_graph, load_project_assembly(repo_root, canonical), load_game_build(repo_root))
    assert again == payload
    text = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    assert len(text) < 4_000_000
    assert payload["provenance"]["fluid_rounding_unit"] == "mL"
    assert payload["coproduct_leaves"] == ["Desc_CompactedCoal_C", "Desc_HeavyOilResidue_C", "Desc_PolymerResin_C"]
