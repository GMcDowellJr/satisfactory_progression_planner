"""`progression.district`: the composer, and what it refuses. Crossover A26/A27.

    composes   count * nominal * clock * (1 - reserve), summed per item,
               declaration order first, then every undeclared raw at 0.0
    refuses    an unknown (extractor, purity) row, a non-resource item, a
               clock outside (0, 2.5], a reserve outside [0, 1), a count < 1,
               a display name matching 0 or several recipes
    never      min, max, sorted, round (asserted from the source)

Synthetic rate rows below; the real table's figures are pinned by
tests/test_district_phase2.py through the declaration.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from production_adapter.contracts import ResourceCap
from production_adapter.gamedata import ExtractionRate
from progression import DistrictDefinition, DistrictError, NodeCount, district, resource_caps

MK1 = "Build_MinerMk1_C"
IRON, COAL, STONE, COPPER, WATER = (
    "Desc_OreIron_C", "Desc_Coal_C", "Desc_Stone_C", "Desc_OreCopper_C", "Desc_Water_C",
)
RESOURCES = (IRON, COAL, STONE, COPPER, WATER)


def _rate(purity: str, nominal: float, extractor: str = MK1) -> ExtractionRate:
    return ExtractionRate(
        extractor_class=extractor, purity=purity, purity_multiplier=1.0,
        nominal_rate_min=nominal, max_250_rate_min=nominal * 2.5, unit="items/min",
    )


RATES = (_rate("impure", 30.0), _rate("normal", 60.0), _rate("pure", 120.0),
         _rate("normal", 120.0, "Build_MinerMk2_C"))


def test_composes_declared_order_then_closes_the_rest():
    d = DistrictDefinition(
        nodes=(NodeCount(COAL, "pure", 2), NodeCount(IRON, "normal", 1), NodeCount(IRON, "pure", 1)),
        extractor_class=MK1, extraction_clock=1.0,
    )
    caps = resource_caps(d, RATES, RESOURCES)
    assert caps[:2] == (ResourceCap(COAL, 240.0), ResourceCap(IRON, 180.0))
    closed = caps[2:]
    # the closing caps keep the order they were given, which is the reference
    # layer's, so the cap list is the same in every process
    assert [c.item_id for c in closed] == [STONE, COPPER, WATER]
    assert all(c.rate_per_min == 0.0 for c in closed)


def test_clock_and_reserve_scale_the_cap():
    d = DistrictDefinition(
        nodes=(NodeCount(IRON, "pure", 3),), extractor_class=MK1,
        extraction_clock=0.25, reserve_fraction=0.2,
    )
    assert resource_caps(d, RATES, RESOURCES)[0] == ResourceCap(IRON, pytest.approx(72.0))


def test_the_extractor_class_selects_the_row():
    d = DistrictDefinition(nodes=(NodeCount(IRON, "normal", 1),),
                           extractor_class="Build_MinerMk2_C", extraction_clock=1.0)
    assert resource_caps(d, RATES, RESOURCES)[0].rate_per_min == 120.0


@pytest.mark.parametrize("purity", ["pure ", "Pure", "rich"])
def test_an_unknown_purity_row_is_refused_by_name(purity):
    d = DistrictDefinition(nodes=(NodeCount(IRON, purity, 1),), extractor_class=MK1,
                           extraction_clock=1.0)
    with pytest.raises(DistrictError, match="0 rows"):
        resource_caps(d, RATES, RESOURCES)


def test_a_manufactured_item_cannot_be_a_node():
    d = DistrictDefinition(nodes=(NodeCount("Desc_IronPlate_C", "pure", 1),),
                           extractor_class=MK1, extraction_clock=1.0)
    with pytest.raises(DistrictError, match="not a raw resource"):
        resource_caps(d, RATES, RESOURCES)


@pytest.mark.parametrize("clock", [0.0, -0.5, 2.5001])
def test_clock_outside_the_game_range_is_refused(clock):
    with pytest.raises(DistrictError, match="extraction_clock"):
        DistrictDefinition(nodes=(NodeCount(IRON, "pure", 1),), extractor_class=MK1,
                           extraction_clock=clock)


@pytest.mark.parametrize("reserve", [-0.1, 1.0])
def test_reserve_outside_the_unit_interval_is_refused(reserve):
    with pytest.raises(DistrictError, match="reserve_fraction"):
        DistrictDefinition(nodes=(NodeCount(IRON, "pure", 1),), extractor_class=MK1,
                           extraction_clock=1.0, reserve_fraction=reserve)


def test_a_count_below_one_is_refused():
    with pytest.raises(DistrictError, match="count"):
        NodeCount(IRON, "pure", 0)


def test_no_nodes_is_refused():
    with pytest.raises(DistrictError, match="at least one node"):
        DistrictDefinition(nodes=(), extractor_class=MK1, extraction_clock=1.0)


# --- name resolution against the real reference layer ---------------------

REPO = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def data():
    from production_adapter import load
    return load(REPO)


def test_reference_order_is_items_csv_order_and_covers_every_resource(data):
    from progression import resources_in_reference_order
    ordered = resources_in_reference_order(data)
    assert set(ordered) == set(data.resource_items)
    assert ordered[0] == "Desc_LiquidOil_C"   # items.csv row 1 (2026-10-08)


def test_display_names_resolve_in_order_and_keep_the_prefix(data):
    from progression import recipe_ids_by_name
    ids = recipe_ids_by_name(data, ("Alternate: Solid Steel Ingot", "Steel Ingot", "Screws"))
    assert ids == ("Recipe_Alternate_IngotSteel_1_C", "Recipe_IngotSteel_C", "Recipe_Screw_C")


@pytest.mark.parametrize("name", ["Solid Steel Ingot", "Screw", "Compacted Coal"])
def test_a_name_matching_no_row_is_refused(data, name):
    from progression import recipe_ids_by_name
    with pytest.raises(DistrictError, match="matched 0 rows"):
        recipe_ids_by_name(data, (name,))


# --- guardrail ------------------------------------------------------------

def _called_names(tree: ast.AST) -> set[str]:
    return {
        n.func.id for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }


def test_the_composer_cannot_choose():
    """No min, max, sorted or round anywhere in the module: a cap is arithmetic
    on declared readings, and the first ranking call would be the first
    decision nobody made (AGENTS.md, "Layers report; they don't choose")."""
    tree = ast.parse(inspect.getsource(district))
    assert {"min", "max", "sorted", "sort", "round"}.isdisjoint(_called_names(tree))


# --- nodes of another extractor class; extraction at nameplate (A29) --------

WATER_RATES = RATES + (ExtractionRate(
    extractor_class="Build_WaterPump_C", purity="none", purity_multiplier=1.0,
    nominal_rate_min=120.0, max_250_rate_min=300.0, unit="m3/min",
),)


def test_a_node_may_name_its_own_extractor_class():
    d = DistrictDefinition(
        nodes=(NodeCount(IRON, "pure", 1), NodeCount(WATER, "none", 2, extractor_class="Build_WaterPump_C")),
        extractor_class=MK1, extraction_clock=0.5,
    )
    caps = resource_caps(d, WATER_RATES, RESOURCES)
    assert caps[:2] == (ResourceCap(IRON, 60.0), ResourceCap(WATER, 120.0))


def test_extraction_nameplate_mw_counts_every_declared_extractor():
    from progression import extraction_nameplate_mw
    d = DistrictDefinition(
        nodes=(NodeCount(IRON, "pure", 3), NodeCount(WATER, "none", 2, extractor_class="Build_WaterPump_C")),
        extractor_class=MK1, extraction_clock=0.25,   # the clock does not enter: nameplate (P2)
    )
    assert extraction_nameplate_mw(d, {MK1: 5.0, "Build_WaterPump_C": 20.0}) == 55.0


def test_extraction_nameplate_mw_refuses_an_unknown_class_by_name():
    from progression import extraction_nameplate_mw
    d = DistrictDefinition(nodes=(NodeCount(IRON, "pure", 1),), extractor_class=MK1, extraction_clock=1.0)
    with pytest.raises(DistrictError, match="Build_MinerMk1_C: no base power"):
        extraction_nameplate_mw(d, {})


# --- the bill, summed from declared sources (A31) ----------------------------

def test_bill_units_sums_sources_in_first_seen_order():
    from progression import bill_units
    out = bill_units((
        ("project assembly phase 2", (("Desc_SpaceElevatorPart_2_C", 1000.0),)),
        ("Schematic_5-1_C", (("Desc_Motor_C", 100.0), ("Desc_SpaceElevatorPart_2_C", 5.0))),
        ("Schematic_5-2_C", (("Desc_Motor_C", 100.0),)),
    ))
    assert list(out.items()) == [("Desc_SpaceElevatorPart_2_C", 1005.0), ("Desc_Motor_C", 200.0)]


@pytest.mark.parametrize("units", [0.0, -1.0])
def test_bill_units_refuses_an_item_at_nothing(units):
    from progression import bill_units
    with pytest.raises(DistrictError, match="bill source 'x': Desc_Motor_C"):
        bill_units((("x", (("Desc_Motor_C", units),)),))


# --- discovery: what the site can make at all (A31 O34, v5.5 Stage 2) --------

IRON_SET = ("Recipe_IngotIron_C", "Recipe_IronPlate_C", "Recipe_IronRod_C", "Recipe_Screw_C",
            "Recipe_IngotCopper_C", "Recipe_Wire_C", "Recipe_Cable_C",
            "Recipe_IronPlateReinforced_C", "Recipe_Alternate_ReinforcedIronPlate_2_C",
            "Recipe_Alternate_Wire_1_C")
PLATE, RIP, CABLE, WIRE, COPPER_INGOT = (
    "Desc_IronPlate_C", "Desc_IronPlateReinforced_C", "Desc_Cable_C", "Desc_Wire_C", "Desc_CopperIngot_C",
)


def _caps(**per):
    return tuple(ResourceCap(i, r) for i, r in per.items())


def test_discovery_is_a_forward_closure_from_the_capped_raws(data):
    from progression import discover
    reach = {x.item_id: x for x in discover(
        data, IRON_SET, _caps(Desc_OreIron_C=30.0, Desc_OreCopper_C=0.0), (PLATE, RIP, CABLE, WIRE),
    )}
    assert reach[PLATE].makeable and reach[RIP].makeable
    # Wire is reachable through Iron Wire even with copper closed, so Cable is too
    assert reach[WIRE].makeable and reach[CABLE].makeable


def test_an_unreachable_item_names_the_raws_a_node_would_have_to_declare(data):
    from progression import discover
    no_iron_wire = tuple(r for r in IRON_SET if r != "Recipe_Alternate_Wire_1_C")
    [cable] = discover(data, no_iron_wire, _caps(Desc_OreIron_C=30.0, Desc_OreCopper_C=0.0), (CABLE,))
    assert not cable.makeable and cable.missing_raws == ("Desc_OreCopper_C",) and not cable.no_recipe


def test_an_uncapped_raw_counts_as_absent(data):
    """A28.1 T1: a raw with no cap row was never declared; discovery does not
    assume it exists."""
    from progression import discover
    [ingot] = discover(data, IRON_SET, _caps(Desc_OreIron_C=30.0), (COPPER_INGOT,))
    assert not ingot.makeable and ingot.missing_raws == ("Desc_OreCopper_C",)


def test_an_item_no_enabled_recipe_makes_is_said_so(data):
    from progression import discover
    [plastic] = discover(data, IRON_SET, _caps(Desc_OreIron_C=30.0), ("Desc_Plastic_C",))
    assert not plastic.makeable and plastic.no_recipe and plastic.missing_raws == ()


def test_a_raw_with_a_cap_is_makeable_by_itself(data):
    from progression import discover
    [ore] = discover(data, IRON_SET, _caps(Desc_OreIron_C=30.0), ("Desc_OreIron_C",))
    assert ore.makeable and not ore.no_recipe


def test_discovery_keeps_the_order_asked(data):
    from progression import discover
    out = discover(data, IRON_SET, _caps(Desc_OreIron_C=30.0), (CABLE, PLATE))
    assert [x.item_id for x in out] == [CABLE, PLATE]
