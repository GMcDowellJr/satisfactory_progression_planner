"""Datasets A and B as rows: deterministic, id-ordered, provenance-stamped."""
from __future__ import annotations

import pytest

from production_adapter import Scenario, load_game_build, load_project_assembly

from demand_expansion import (
    DEFAULT_ROUTES, RoutePin, RouteTable, build_dataset, config_id, in_scope_targets,
    markdown_report, route_table_sha256,
)

MOTOR = "Desc_Motor_C"
TPR = "Desc_SpaceElevatorPart_8_C"


@pytest.fixture(scope="module")
def dataset(default_graph, repo_root, canonical):
    return build_dataset(
        default_graph, load_project_assembly(repo_root, canonical), load_game_build(repo_root)
    )


def test_scope_is_listed_non_resource_with_a_producer(default_graph, canonical):
    targets = in_scope_targets(default_graph)
    assert all(t in canonical.items for t in targets)
    assert not any(t in canonical.resource_items for t in targets)
    assert "Desc_NobeliskExplosive_C" not in targets      # unlisted consumable
    assert "Desc_Wood_C" not in targets                   # no recipe
    assert "Desc_FicsiteIngot_C" in targets               # ambiguous, in scope, unresolved
    assert len(targets) == 119


def test_coefficient_rows_answer_the_motor_question(dataset):
    rows = {(r["source_item_id"], r["target_item_id"]): r for r in dataset.coefficients}
    r = rows[(MOTOR, TPR)]
    assert r["per_target"] == 9.0 and r["per_target_exact"] == "9" and r["depth"] == 2
    assert r["supplied_by"] == "recipe"
    assert rows[("Desc_OreIron_C", TPR)]["supplied_by"] == "resource"
    assert rows[("Desc_HeavyOilResidue_C", "Desc_PetroleumCoke_C")]["supplied_by"] == "coproduct"
    assert r["direct_per_target"] == 0.0
    me = rows[(MOTOR, "Desc_SpaceElevatorPart_4_C")]
    assert me["direct_per_target_exact"] == "2" and me["depth"] == 1


def test_rows_are_in_id_order_and_counts_are_stamped(dataset):
    keys = [(r["source_item_id"], r["target_item_id"]) for r in dataset.coefficients]
    assert keys == sorted(keys)
    c = dataset.provenance["counts"]
    assert c["targets"] == 119
    assert c["coefficient_rows"] == len(dataset.coefficients)
    assert c["phase_rows"] == len(dataset.phases) == 74 * 5
    assert dataset.provenance["phases_complete"] == {"1": True, "2": True, "3": True, "4": True, "5": False}


def test_unresolved_names_targets_and_deliveries(dataset):
    kinds = {(u["kind"], u["item_id"]) for u in dataset.unresolved}
    assert ("delivery", "Desc_SpaceElevatorPart_10_C") in kinds
    assert ("target", "Desc_SpaceElevatorPart_10_C") in kinds
    assert ("target", "Desc_FicsiteIngot_C") in kinds
    assert all(u["refusal"].split(":")[0] in {"AmbiguousRoute", "UnproducibleItem"} for u in dataset.unresolved)


def test_phase_rows_match_aggregate(dataset):
    motor = [r for r in dataset.phases if r["item_id"] == MOTOR]
    assert [r["quantity"] for r in motor] == [0, 0, 1000, 2250, 1800]
    assert [r["growth_kind"] for r in motor] == ["none", "none", "new", "ratio", "ratio"]
    assert motor[3]["growth_ratio"] == 2.25
    assert motor[4]["complete"] is False and motor[4]["remaining_complete"] is True


def test_two_builds_are_equal(default_graph, repo_root, canonical, dataset):
    again = build_dataset(
        default_graph, load_project_assembly(repo_root, canonical), load_game_build(repo_root)
    )
    assert again.coefficients == dataset.coefficients
    assert again.phases == dataset.phases
    assert again.unresolved == dataset.unresolved
    assert again.provenance == dataset.provenance


def test_provenance_pins_the_build_and_the_table(dataset, repo_root):
    p = dataset.provenance
    assert p["game_build_id"] == "docs_a81d250e96aa"
    assert p["docs_sha256"].startswith("a81d250e96aa")
    assert p["build_number"] == "502094"
    assert p["route_table"]["sha256"] == route_table_sha256(DEFAULT_ROUTES)
    assert p["coproduct_leaves"] == ["Desc_CompactedCoal_C", "Desc_HeavyOilResidue_C", "Desc_PolymerResin_C"]
    assert p["scenario"]["fluid_rounding_unit"] == "mL"
    assert p["generated_at"] is None and p["repo_head"] is None


def test_a_configuration_error_is_not_unresolved_rows(default_graph, repo_root, canonical):
    from demand_expansion import FluidRoundingUndeclared

    with pytest.raises(FluidRoundingUndeclared):
        build_dataset(
            default_graph, load_project_assembly(repo_root, canonical), load_game_build(repo_root),
            fluid_rounding="litres",
        )


def test_config_id_and_table_hash():
    assert config_id(DEFAULT_ROUTES, Scenario(), "mL") == "default-2026-10-10/recipe1/pa1/fluid-mL"
    s = Scenario(recipe_input_multiplier=1.25, project_assembly_requirement_multiplier=2.0)
    assert config_id(DEFAULT_ROUTES, s, None) == "default-2026-10-10/recipe1.25/pa2/fluid-none"
    other = RouteTable(
        DEFAULT_ROUTES.name, DEFAULT_ROUTES.exclusions,
        DEFAULT_ROUTES.pins + (RoutePin("Desc_FicsiteIngot_C", "Recipe_FicsiteIngot_Iron_C", "iron"),),
    )
    assert route_table_sha256(other) != route_table_sha256(DEFAULT_ROUTES)


def test_markdown_report_states_its_basis(dataset, default_graph):
    md = markdown_report(dataset, default_graph)
    assert md.startswith("# Demand expansion — default-2026-10-10/recipe1/pa1/fluid-mL")
    assert "build 502094" in md
    assert "Phase 5 incomplete" in md
    assert "Last: the last phase that requires the item" in md   # not "remaining" (PR #3 review)
    assert "| Motor | 0 | 0 | 1,000 | 2,250 | 1,800+ | · · new 2.25x 0.8x | 5 |" in md
