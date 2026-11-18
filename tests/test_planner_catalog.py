"""tools/planner_catalog.py: the planner page's choices, read through the one loader (A20).

Each vocabulary must be its owner's, and each list the reference layer's, so
the page cannot offer a value the Python would refuse or hide one it takes.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

from production_adapter import FLUID_ROUNDING_VARIANTS
from production_adapter.gamedata import load_recipe_rows, load_schematic_rows
from production_adapter.lp_backend import PowerStatistic
from progression import playthrough
from progression.byproducts import FUEL_ROUTES
from progression.infrastructure import POLICIES
from progression.playthrough import PlaythroughError

REPO = pathlib.Path(__file__).resolve().parents[1]


def _module(name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


C = _module("planner_catalog")


@pytest.fixture(scope="module")
def cat():
    return C.catalog(REPO)


def test_the_vocabularies_are_their_owners(cat):
    assert cat["power_statistics"] == [s.value for s in PowerStatistic]
    assert cat["fuel_routes"] == list(FUEL_ROUTES)
    assert cat["infrastructure_policies"] == list(POLICIES)
    assert cat["goals"] == list(_module("site_card").GOALS)
    assert cat["power_modes"] == list(_module("factory_run").POWER_MODES)
    assert cat["fluid_rounding_units"] == list(FLUID_ROUNDING_VARIANTS)


def test_every_milestone_research_and_alternate_is_offered(cat):
    rows = load_schematic_rows(REPO)
    assert [m["schematic_id"] for m in cat["milestones"]] == [
        s.schematic_id for s in rows if s.schematic_type in ("EST_Milestone", "EST_Tutorial", "EST_Custom")]
    assert [m["schematic_id"] for m in cat["research"]] == [
        s.schematic_id for s in rows if s.schematic_type == "EST_MAM"]
    assert [a["recipe_id"] for a in cat["alternates"]] == [
        r.recipe_id for r in load_recipe_rows(REPO) if r.is_alternate]


def test_each_offered_id_is_accepted_by_playthrough(cat):
    state = playthrough(REPO, milestones=[m["schematic_id"] for m in cat["milestones"]],
                        research=[r["schematic_id"] for r in cat["research"]],
                        alternates=[a["recipe_id"] for a in cat["alternates"]])
    assert len(state.milestones) == len(cat["milestones"])


def test_the_phases_are_the_project_assembly_phases(cat):
    assert [p["phase"] for p in cat["phases"]] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("tier", [0, 2, 5])
def test_the_tier_button_ticks_what_through_tier_means(tier):
    assert C.tier_milestones(REPO, tier) == list(playthrough(REPO, through_tier=tier).milestones)


def test_a_negative_tier_is_refused_by_playthrough():
    with pytest.raises(PlaythroughError, match="non-negative"):
        C.tier_milestones(REPO, -1)


def test_generators_are_the_stacks_order_obtained():
    pt = {"through_tier": 5, "milestones": [], "research": [], "alternates": []}
    got = [g["generator_class"] for g in C.generators_owned(REPO, pt)]
    assert got == ["Build_GeneratorBiomass_Automated_C", "Build_GeneratorCoal_C",
                   "Build_GeneratorFuel_C"]
    assert [g["generator_class"] for g in C.generators_owned(REPO, {**pt, "through_tier": 2})] == [
        "Build_GeneratorBiomass_Automated_C"]


def test_generator_names_are_in_the_catalog(cat):
    for cls in ("Build_GeneratorBiomass_Automated_C", "Build_GeneratorCoal_C", "Build_MinerMk1_C"):
        assert cat["producers"][cls]
