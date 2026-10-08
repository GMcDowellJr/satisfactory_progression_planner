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
