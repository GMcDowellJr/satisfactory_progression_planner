"""The A19 minimum bootstrap and its two unlocks helpers (crossover A19).

Greg, 2026-09-24: the bootstrap is "always the minimum to begin producing new
items" — one producer per recipe new this phase, one extractor per raw
resource those recipes consume. Every schematic in a phase's tiers is bought,
with exclusion available.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from production_adapter import load
from progression import at_tier, stock, unlocks

REPO = pathlib.Path(__file__).resolve().parents[1]
MINER1, MINER2, WATER = "Build_MinerMk1_C", "Build_MinerMk2_C", "Build_WaterPump_C"
ORE, COAL = "Desc_OreIron_C", "Desc_Coal_C"
STEEL = ("Recipe_IngotSteel_C", "Recipe_SteelBeam_C", "Recipe_SteelPipe_C",
         "Recipe_SpaceElevatorPart_2_C")


@pytest.fixture(scope="module")
def data():
    return load(REPO)


@pytest.fixture(scope="module")
def before():
    return at_tier(REPO, 2).recipe_ids, unlocks.extractors_open_at_tier(REPO, 2)


# -- unlocks helpers --------------------------------------------------------

def test_one_miner_class_is_open_before_tier_3_and_two_at_tier_4():
    two, four = unlocks.extractors_open_at_tier(REPO, 2), unlocks.extractors_open_at_tier(REPO, 4)
    assert two[ORE] == (MINER1,) and two[COAL] == (MINER1,)
    assert four[ORE] == (MINER1, MINER2)          # 4-1 unlocks Miner Mk.2
    assert "Desc_Water_C" not in two and four["Desc_Water_C"] == (WATER,)   # 3-1


def test_every_milestone_is_in_unless_excluded():
    every = unlocks.schematics_in_tiers(REPO, (3, 4))
    assert "Schematic_4-2_C" in every
    fewer = unlocks.schematics_in_tiers(REPO, (3, 4), exclude=("Schematic_4-2_C",))
    assert fewer == tuple(s for s in every if s != "Schematic_4-2_C")


def test_excluding_a_schematic_the_tiers_lack_is_refused():
    with pytest.raises(unlocks.UnlockDataError, match="do not contain"):
        unlocks.schematics_in_tiers(REPO, (3, 4), exclude=("Schematic_4_2_C",))


# -- derive_bootstrap -------------------------------------------------------

def test_the_steel_minimum_is_greg_s(data, before):
    """His example, verbatim: 1 coal miner, 1 iron miner, 1 foundry, 1
    constructor each for beam and pipe, 1 assembler for VF. Modular frame and
    iron rod are not new, so they cost nothing here."""
    open_before, extractors = before
    uses = ("Recipe_IronRod_C", "Recipe_ModularFrame_C") + STEEL
    d = stock.derive_bootstrap(data, uses, open_before=open_before,
                               extractors_open=extractors, tier=3)
    assert d.bootstrap.buildings == (
        (MINER1, 2), ("Build_FoundryMk1_C", 1), ("Build_ConstructorMk1_C", 2),
        ("Build_AssemblerMk1_C", 1))
    assert d.extractors == ((ORE, MINER1), (COAL, MINER1))
    assert "minimum" in d.basis.lower() and "excludes power" in d.basis


def test_nothing_new_is_refused(data, before):
    open_before, extractors = before
    with pytest.raises(stock.StockPassError, match="no recipe that was closed"):
        stock.derive_bootstrap(data, ("Recipe_IronRod_C",), open_before=open_before,
                               extractors_open=extractors, tier=3)


def test_two_open_extractors_are_refused_not_picked(data):
    """At tier 4 both Miner Mk.1 and Mk.2 are open; which one is a declaration."""
    with pytest.raises(stock.StockPassError, match="exactly one"):
        stock.derive_bootstrap(data, STEEL, open_before=at_tier(REPO, 2).recipe_ids,
                               extractors_open=unlocks.extractors_open_at_tier(REPO, 4),
                               tier=4)


def test_derive_bootstrap_ranks_nothing():
    src = pathlib.Path(stock.__file__).read_text(encoding="utf-8")
    (fn,) = [n for n in ast.parse(src).body
             if isinstance(n, ast.FunctionDef) and n.name == "derive_bootstrap"]
    called = {
        (n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", ""))
        for n in ast.walk(fn) if isinstance(n, ast.Call)
    }
    assert {"min", "max", "sorted", "sort", "round"}.isdisjoint(called)


# add_bootstrap (crossover A20; moved from test_phase_two_run.py's `_add`)

def test_add_bootstrap_sums_per_class_in_first_then_second_order():
    a = stock.BootstrapSet(tier=4, buildings=((MINER1, 2), ("Build_FoundryMk1_C", 1)))
    b = stock.BootstrapSet(tier=4, buildings=((MINER1, 2), ("Build_GeneratorCoal_C", 4), (WATER, 2)))
    assert stock.add_bootstrap(a, b).buildings == (
        (MINER1, 4), ("Build_FoundryMk1_C", 1), ("Build_GeneratorCoal_C", 4), (WATER, 2))


def test_add_bootstrap_refuses_mixed_tiers():
    a = stock.BootstrapSet(tier=4, buildings=((MINER1, 2),))
    b = stock.BootstrapSet(tier=2, buildings=((MINER1, 2),))
    with pytest.raises(stock.StockPassError):
        stock.add_bootstrap(a, b)
