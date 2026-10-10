"""Dataset C against VALIDATION.md table 5: hand-derived alternate deltas,
the declaration refusals, and the sweep's shape on this build."""
from __future__ import annotations

from fractions import Fraction as F

import pytest

from production_adapter import Scenario, load_recipe_unlocks
from production_adapter.gamedata import Item, PowerRange, Recipe, ReferenceData

from demand_expansion import (
    DEFAULT_ROUTES, AlternatePin, DeclarationError, DemandExpansionError, RoutePin,
    RouteTable, build, compare, config_id, expand, sensitivity, sweep,
)

STEELED = "Recipe_Alternate_ModularFrame_C"
IRON_WIRE = "Recipe_Alternate_Wire_1_C"
MF = "Desc_ModularFrame_C"
CABLE = "Desc_Cable_C"


def _rows(s, target):
    return {r["source_item_id"]: r for r in s.rows if r["target_item_id"] == target}


def test_steeled_frame_on_modular_frame(canonical):
    """Default 3 RIP + 12 Iron Rod -> 2 MF: 24 Iron Ore. Steeled 2 RIP + 10
    Steel Pipe -> 3 MF: (2x12 + 10x1.5)/3 = 13 Iron Ore, 5 Coal new, Iron
    Ingot 24 -> 8 (steel does not pass through Iron Ingot)."""
    s = sensitivity(canonical, DEFAULT_ROUTES, STEELED)
    assert s.applicable and s.item_id == MF
    rows = _rows(s, MF)
    assert (rows["Desc_OreIron_C"]["default_exact"], rows["Desc_OreIron_C"]["alternate_exact"]) == ("24", "13")
    assert rows["Desc_OreIron_C"]["ratio"] == pytest.approx(13 / 24)
    assert rows["Desc_Coal_C"]["change_kind"] == "new" and rows["Desc_Coal_C"]["alternate_exact"] == "5"
    assert rows["Desc_IronIngot_C"]["alternate_exact"] == "8"
    assert rows["Desc_SteelPipe_C"]["change_kind"] == "new"
    # Iron Rod does not vanish: each RIP still takes 12 screws = 3 rods.
    # (3x3 + 12)/2 = 21/2 by default; 2x3/3 = 2 under Steeled Frame.
    assert (rows["Desc_IronRod_C"]["default_exact"], rows["Desc_IronRod_C"]["alternate_exact"]) == ("21/2", "2")
    assert MF in s.targets_changed and "Desc_SpaceElevatorPart_2_C" in s.targets_changed
    assert s.targets_newly_resolved == () and s.targets_newly_refused == ()


def test_iron_wire_on_cable(canonical, repo_root):
    """Default Wire 1 Copper Ingot -> 2; Iron Wire 5 Iron Ingot -> 9. Cable
    takes 2 Wire: Copper Ore 1 -> 0 removed, Iron Ore 0 -> 10/9 new."""
    s = sensitivity(canonical, DEFAULT_ROUTES, IRON_WIRE, unlocks=load_recipe_unlocks(repo_root))
    rows = _rows(s, CABLE)
    assert rows["Desc_OreCopper_C"]["change_kind"] == "removed"
    assert rows["Desc_OreCopper_C"]["default_exact"] == "1"
    assert rows["Desc_OreIron_C"]["change_kind"] == "new"
    assert rows["Desc_OreIron_C"]["alternate_exact"] == str(F(10, 9))
    assert s.unlock == "T1 Alternate: Iron Wire"


def test_an_explicit_configuration_is_a_route_table(canonical):
    """Explicit mode: the engine under a table carrying the pin."""
    table = DEFAULT_ROUTES.with_alternate(MF, STEELED, "explicit")
    e = expand(build(canonical, table), MF)
    assert e.embedded["Desc_OreIron_C"] == 13 and e.embedded["Desc_Coal_C"] == 5
    assert table.name == "default-2026-10-10+Recipe_Alternate_ModularFrame_C"
    assert config_id(table, Scenario(), "mL") == f"{table.name}/recipe1/pa1/fluid-mL"
    hand_built = RouteTable("x", alternates=(AlternatePin(MF, STEELED, "r"),))
    assert config_id(hand_built, Scenario(), "mL") == f"x/recipe1/pa1/fluid-mL/alt-{STEELED}"


def test_rows_are_in_id_order_and_never_ranked(canonical):
    s = sensitivity(canonical, DEFAULT_ROUTES, STEELED)
    keys = [(r["source_item_id"], r["target_item_id"]) for r in s.rows]
    assert keys == sorted(keys)


# --- declarations ------------------------------------------------------------

def test_alternate_pin_refusals(canonical):
    with pytest.raises(DeclarationError, match="not in the reference layer"):
        build(canonical, RouteTable("x", alternates=(AlternatePin(MF, "Recipe_Nope_C", "r"),)))
    with pytest.raises(DeclarationError, match="flags it base"):
        build(canonical, RouteTable("x", alternates=(AlternatePin(MF, "Recipe_ModularFrame_C", "r"),)))
    with pytest.raises(DeclarationError, match="primary output is"):
        build(canonical, RouteTable("x", alternates=(AlternatePin(CABLE, STEELED, "r"),)))
    with pytest.raises(DeclarationError, match="is a resource"):
        build(canonical, RouteTable("x", alternates=(AlternatePin("Desc_Coal_C", "Recipe_Alternate_Coal_1_C", "r"),)))
    with pytest.raises(DeclarationError, match="both a RoutePin and an AlternatePin"):
        RouteTable("x", pins=(RoutePin(MF, "Recipe_ModularFrame_C", "r"),),
                   alternates=(AlternatePin(MF, STEELED, "r"),))
    with pytest.raises(DeclarationError, match="two alternate pins"):
        RouteTable("x", alternates=(AlternatePin(MF, STEELED, "r"), AlternatePin(MF, STEELED, "r")))


def test_inapplicable_alternates_are_named_not_skipped(canonical):
    plastic = sensitivity(canonical, DEFAULT_ROUTES, "Recipe_Alternate_Plastic_1_C")
    assert not plastic.applicable and "both a RoutePin and an AlternatePin" in plastic.reason
    coal = sensitivity(canonical, DEFAULT_ROUTES, "Recipe_Alternate_Coal_1_C")
    assert not coal.applicable and "is a resource" in coal.reason
    with pytest.raises(DemandExpansionError):
        sensitivity(canonical, DEFAULT_ROUTES, "Recipe_Nope_C")


def test_compare_needs_one_reference_data(canonical, repo_root):
    from production_adapter import load

    other = build(load(repo_root), DEFAULT_ROUTES)
    with pytest.raises(DemandExpansionError, match="same ReferenceData"):
        compare(build(canonical, DEFAULT_ROUTES), other)


# --- the sweep on this build --------------------------------------------------

def test_sweep_shape(canonical, repo_root):
    results = sweep(canonical, DEFAULT_ROUTES, unlocks=load_recipe_unlocks(repo_root))
    assert len(results) == 110
    assert [r.alternate_recipe_id for r in results] == sorted(r.alternate_recipe_id for r in results)
    inapplicable = {r.alternate_name for r in results if not r.applicable}
    assert inapplicable == {
        "Alternate: Automated Miner",   # primary output not in items.csv
        "Alternate: Charcoal", "Alternate: Biocoal",   # make Coal, a resource
        "Alternate: Recycled Plastic", "Alternate: Recycled Rubber",   # conflict with base pins
    }
    assert sum(len(r.rows) for r in results) == 6187
    # Heavy Oil Residue has no primary producer under the default table, so
    # its alternate resolves targets and anything routed through Petroleum
    # Coke newly refuses them. Reported, not folded.
    by_name = {r.alternate_name: r for r in results}
    assert len(by_name["Alternate: Heavy Oil Residue"].targets_newly_resolved) == 4
    assert len(by_name["Alternate: Tempered Caterium Ingot"].targets_newly_refused) == 9
    assert by_name["Alternate: Compacted Coal"].unlock == "T3 Compacted Coal; T4 Alternate: Compacted Coal"


# --- synthetic: newly resolved and newly refused ------------------------------

def _data(recipes, outputs, alternates=()):
    items = {i for ins in recipes.values() for i, _ in ins} | set(outputs.values())
    return ReferenceData(
        game_build_id="synthetic",
        recipes={
            rid: Recipe(
                recipe_id=rid, display_name=rid, is_alternate=rid in alternates, duration_sec=60.0,
                producer_class="Build_X_C", inputs=tuple(ins), outputs=((outputs[rid], 1.0),),
                power=PowerRange(1.0, 1.0),
                input_amounts=tuple((i, a, "items") for i, a in ins),
                output_amounts=((outputs[rid], 1.0, "items"),),
            )
            for rid, ins in recipes.items()
        },
        producers={}, items={i: Item(i, i, "solid", i == "Ore") for i in items},
        resource_items=frozenset({"Ore"}),
    )


def test_an_alternate_can_resolve_an_ambiguity_and_create_one():
    """B has two base recipes (ambiguous); A needs B. Enabling an alternate
    for B resolves A. C is made only by an alternate; enabling it makes C
    expandable, and D (needing C) resolves too."""
    data = _data(
        {"R_A": (("B", 1.0),), "R_B1": (("Ore", 1.0),), "R_B2": (("Ore", 2.0),),
         "R_B_alt": (("Ore", 3.0),), "R_D": (("C", 1.0),), "R_C_alt": (("Ore", 1.0),)},
        {"R_A": "A", "R_B1": "B", "R_B2": "B", "R_B_alt": "B", "R_D": "D", "R_C_alt": "C"},
        alternates={"R_B_alt", "R_C_alt"},
    )
    base = RouteTable("synthetic")
    s = sensitivity(data, base, "R_B_alt")
    assert s.targets_newly_resolved == ("A", "B")
    assert s.rows == ()   # nothing to compare: both were refused before
    s2 = sensitivity(data, base, "R_C_alt")
    assert s2.targets_newly_resolved == ("C", "D")
