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


# --- reframe A21: option sets, presets, page defaults ----------------------------

def test_the_option_sets_are_the_game_menus_as_recorded():
    """Demand record §3.2.1; the viewer's copy (which drops sub-1x R) agrees."""
    from demand_expansion.viewer import PROJECT_ASSEMBLY_MULTIPLIERS, RECIPE_MULTIPLIERS
    assert C.PROJECT_ASSEMBLY_OPTIONS == PROJECT_ASSEMBLY_MULTIPLIERS
    assert set(RECIPE_MULTIPLIERS) <= set(C.RECIPE_INPUT_OPTIONS)
    assert C.MACHINE_POWER_OPTIONS == (0.25, 0.5, 0.75, 1.0, 2.0, 5.0)


def test_every_page_default_is_a_value_its_owner_accepts(cat):
    d = C.PAGE_DEFAULTS
    for key, options in cat["scenario_options"].items():
        assert d["scenario"][key] in options, key
    assert d["scenario"]["fluid_rounding_unit"] in cat["fluid_rounding_units"]
    assert d["run"]["power_statistic"] in cat["power_statistics"]
    assert d["run"]["fuel_byproducts"] in cat["fuel_routes"]
    assert d["run"]["phase"] in [p["phase"] for p in cat["phases"]]
    assert d["run"]["horizon_fraction"] in cat["horizon_presets"]
    h = d["handoff"]
    assert h["power_mode"] in cat["power_modes"] and h["goal"] in cat["goals"]
    assert h["infrastructure_policy"] in cat["infrastructure_policies"]
    assert h["power_statistic"] in cat["power_statistics"] and h["fuel_byproducts"] in cat["fuel_routes"]
    assert d["bank"]["splitter"] in cat["splitters"]


def test_the_defaults_plan_and_hand_off_end_to_end():
    """The page's defaults make a run that plans and a factory that runs, once a
    site is picked (the site has no default)."""
    R, F = _module("run_plan"), _module("factory_run")
    d = C.PAGE_DEFAULTS
    gens = C.generators_owned(REPO, {"through_tier": d["through_tier"], "milestones": [],
                                     "research": [], "alternates": []})
    run = {"schema": "run-inputs/1",
           "playthrough": {"through_tier": None, "milestones": C.tier_milestones(REPO, d["through_tier"]),
                           "research": [], "alternates": []},
           "scenario": d["scenario"], "phase": d["run"]["phase"], "horizon_min": None,
           "horizon_fraction": d["run"]["horizon_fraction"],
           "power_statistic": d["run"]["power_statistic"], "fuel_byproducts": d["run"]["fuel_byproducts"],
           "standing_generators": {g["generator_class"]: d["standing_units"] for g in gens},
           "generation_mix": d["generation_mix"]}
    assert not R.run_inputs(run).blocked
    h = {k: v for k, v in d["handoff"].items() if k != "goal_source"}
    doc = R.handoff(run, {**h, "world_config_id": "default_502094", "label": "rocky",
                          "socket_ids": ["BP_ResourceNode103", "BP_ResourceNode106"]})
    assert F.run_inputs(doc).scale > 0


def test_horizons_cover_every_phase_and_preset(cat):
    rows = C.horizons(REPO, C.PAGE_DEFAULTS["scenario"])
    assert [r["phase"] for r in rows] == [p["phase"] for p in cat["phases"]]
    assert all([h["fraction"] for h in r["horizons"]] == list(C.HORIZON_PRESETS) for r in rows)
