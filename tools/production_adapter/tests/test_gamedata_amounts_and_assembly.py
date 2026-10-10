"""Per-cycle output amounts and the Project Assembly loader (demand-expansion
record Amendment 1, items D and G)."""
from __future__ import annotations

import pathlib

import pytest

from production_adapter import (
    ReferenceDataError, Scenario, load, load_project_assembly,
)

REPO = pathlib.Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def data():
    return load(REPO)


def test_output_amounts_are_the_stated_counts(data):
    """Two Computers per 36 s is the rate 3.3333333333333335 in recipe_io.csv;
    the stated count is 2. A quantity engine needs the count, not the float."""
    r = data.recipes["Recipe_Alternate_Computer_2_C"]
    assert r.outputs == (("Desc_Computer_C", 3.3333333333333335),)
    assert r.output_amounts == (("Desc_Computer_C", 2.0, "items"),)
    rocket = data.recipes["Recipe_SpaceElevatorPart_8_C"]
    assert rocket.output_amounts == (("Desc_SpaceElevatorPart_8_C", 2.0, "items"),)


def test_coproducts_keep_the_games_order(data):
    plastic = data.recipes["Recipe_Plastic_C"]
    assert [i for i, _, _ in plastic.output_amounts] == [
        "Desc_Plastic_C", "Desc_HeavyOilResidue_C",
    ]
    assert plastic.output_amounts[1][2] == "m3"


def test_outputs_do_not_scale(data):
    scaled = data.with_scenario(Scenario(recipe_input_multiplier=1.25))
    r = scaled.recipes["Recipe_SpaceElevatorPart_4_C"]
    assert r.output_amounts == data.recipes["Recipe_SpaceElevatorPart_4_C"].output_amounts
    assert r.input_amounts[0] == ("Desc_Motor_C", 3.0, "items")   # 2 x 1.25 = 2.5 -> 3


def test_project_assembly_resolves_by_name(data):
    rows = load_project_assembly(REPO, data)
    assert len(rows) == 15
    assert rows[0].item_id == "Desc_SpaceElevatorPart_1_C"
    assert rows[0].delivery_unlocks == "Tiers 3 and 4"
    assert rows[-1].item_id == "Desc_SpaceElevatorPart_11_C"
    assert rows[-1].quantity_1x == 200.0


def test_project_assembly_refuses_an_unresolvable_name(data, tmp_path):
    ref = tmp_path / "planning_data" / "game" / "reference"
    ref.mkdir(parents=True)
    (ref / "project_assembly_requirements.csv").write_text(
        "phase,phase_name,item_name,quantity_default_1x,delivery_unlocks,source_id,verified_on\n"
        "1,Distribution Platform,Smart Plates,50,Tiers 3 and 4,x,2026-01-01\n",
        encoding="utf-8", newline="\n",
    )
    with pytest.raises(ReferenceDataError, match="matches 0 items"):
        load_project_assembly(tmp_path, data)


def test_game_build_is_one_row():
    from production_adapter import load_game_build

    b = load_game_build(REPO)
    assert b.game_build_id == "docs_a81d250e96aa"
    assert (b.game_version, b.build_number) == ("1.2.4.0", "502094")
    assert b.docs_sha256.startswith("a81d250e96aa") and len(b.docs_sha256) == 64
