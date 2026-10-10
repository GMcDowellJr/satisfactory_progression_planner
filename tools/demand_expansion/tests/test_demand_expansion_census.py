"""The shape of the reference layer under the default route table, pinned.

Measured 2026-10-10 on build 502094 (`game_builds.csv` docs_a81d250e96aa) by
the package's own census and, independently, by three scratch scripts over the
CSVs (plan review, Claude outputs/material-demand-plan-review-2026-10-10-1940.md).
When the data moves, a figure here moves with it and the commit says why; the
test is the record of the data's shape, not a guess at it.
"""
from __future__ import annotations

from production_adapter import load_project_assembly

from demand_expansion import census


def test_recipe_and_item_counts(default_graph):
    c = census(default_graph)
    assert (c.recipes, c.base_recipes, c.alternate_recipes) == (291, 181, 110)
    assert (c.items, c.resources) == (162, 13)


def test_one_default_recipe_per_item_is_false_in_the_data(default_graph):
    """The plan's premise, measured: 29 items have more than one base recipe
    listing them as an output. The route table is what makes a tree."""
    assert census(default_graph).base_multi_producer_items == 29


def test_the_converter_rule_and_the_enabled_set(default_graph):
    """20 base recipes have a resource as their primary output: 17 Converter
    ore conversions plus the 3 Unpackage reversals of Water, Oil and Nitrogen.
    181 - 20 - 9 other Unpackage - 2 is_alternate defects = 150 enabled."""
    c = census(default_graph)
    assert c.resource_primary_base_recipes == 20
    assert c.enabled_recipes == 150


def test_what_remains_ambiguous_after_the_pins(default_graph):
    """Structural residue, each run-dependent (record 3.1.2, LP §14.5). No
    Space Elevator delivery reaches any of these except Ficsite Ingot, which
    Biochemical Sculptor and AI Expansion Server refuse on by name."""
    assert census(default_graph).ambiguous_items == (
        "Desc_AlienProtein_C",      # four creature proteins
        "Desc_CartridgeChaos_C",    # Turbo Rifle Ammo, two recipe ids, one name
        "Desc_CrystalShard_C",      # Power Shard: three slug colours + synthetic
        "Desc_FicsiteIngot_C",      # iron / aluminium / caterium, no default
        "Desc_GenericBiomass_C",    # four biomass sources
        "Desc_LiquidFuel_C",        # Fuel vs Residual Fuel
    )


def test_the_default_graph_has_no_cycle(default_graph):
    """With byproducts not producers and Unpackage excluded, the base graph is
    a DAG. The plan's closed-loop solve is not needed for any pin set over
    these producers."""
    assert census(default_graph).cycles == ()


def test_the_primary_output_rule_agrees_with_the_name_rule(default_graph):
    """Wherever a recipe's display name names one of its outputs, that output
    is listed first. So "first output" is the data's own ordering and not a
    choice between two readings — on this build. If this fails, the two rules
    have diverged and the spec must say which one wins."""
    assert census(default_graph).name_match_is_first_output


def test_coverage_gaps_are_named_not_silent(default_graph):
    """17 consumables recipes make that items.csv does not list; 25 listed
    non-resource items no base recipe makes. Both are classification facts
    for the spec's "automatable item" rule (Amendment 1, F), reported here
    rather than swallowed by a loader that tolerates them."""
    c = census(default_graph)
    assert len(c.io_items_absent_from_items) == 17
    assert "BP_ItemDescriptorPortableMiner_C" in c.io_items_absent_from_items
    assert len(c.items_without_base_recipe) == 25
    assert "Desc_Wood_C" in c.items_without_base_recipe


def test_every_delivery_row_resolves_to_one_item(repo_root, canonical):
    rows = load_project_assembly(repo_root, canonical)
    assert len(rows) == 15
    assert [r.phase for r in rows] == [1, 2, 2, 2, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5]
    assert rows[0].item_id == "Desc_SpaceElevatorPart_1_C"
    assert rows[0].quantity_1x == 50.0
