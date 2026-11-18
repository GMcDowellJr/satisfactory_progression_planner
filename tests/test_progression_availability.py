"""Playthrough state and milestone-level availability (reconciliation R5).

Site-planner reframe A15.2, decided by Greg 2026-11-17: availability follows the
milestones owned (Q2), "tier N" is a shortcut for every milestone up to N, marks
follow what is unlocked (B2), and recipe status is owned / in pool / MAM research
/ locked (B5, Q3).
"""
from __future__ import annotations

import pathlib

import pytest

from production_adapter.gamedata import load_generators, load_logistics
from progression import (
    PlaythroughError, RecipeStatus, at_tier, availability, generators_available, playthrough,
)
from progression.unlocks import (
    buildings_unlocked, extractors_open_at_tier, generators_open_at_tier,
)

REPO = pathlib.Path(__file__).resolve().parents[1]

ADVANCED_STEEL = "Schematic_4-1_C"      # Miner Mk.2, tier 4
LOGISTICS_MK3 = "Schematic_5-3_C"       # Belt and lift Mk.3, tier 4
TURBOFUEL_RESEARCH = "Research_Sulfur_TurboFuel_C"
COMPACTED_RESEARCH = "Research_Sulfur_CompactedCoal_C"
TURBOFUEL = "Recipe_Alternate_Turbofuel_C"          # is_alternate false: a research recipe
COMPACTED_COAL = "Recipe_Alternate_EnrichedCoal_C"  # is_alternate true
CAST_SCREWS = "Recipe_Alternate_Screw_C"


def _marks(a, kind):
    return [c.mark for c in a.capabilities(kind)]


# --- the shortcut is the tier filter, exactly --------------------------------

@pytest.mark.parametrize("tier", range(10))
def test_through_tier_reproduces_at_tier(tier):
    """One grant join (unlocks.recipe_grants) serves both, so they cannot drift."""
    a = availability(REPO, playthrough(REPO, through_tier=tier))
    assert a.recipe_ids == at_tier(REPO, tier).recipe_ids
    assert a.extractors == extractors_open_at_tier(REPO, tier)
    classes = tuple(dict.fromkeys(g.generator_class for g in load_generators(REPO)))
    assert generators_available(REPO, a.state, classes) == \
        generators_open_at_tier(REPO, tier, classes)


@pytest.mark.parametrize("tier", range(10))
def test_through_tier_logistics_match_the_parsed_tiers(tier):
    """The milestone-name join agrees with the tier parsed from the same text."""
    a = availability(REPO, playthrough(REPO, through_tier=tier))
    caps, _ = load_logistics(REPO)
    assert {c.capability_id for c in a.logistics} == \
        {c.capability_id for c in caps if c.unlock_tier <= tier}


def test_the_milestone_join_agrees_with_the_building_route():
    """For belts, lifts and miners the `unlock` text's milestone and the build
    recipe's unlocking schematic are the same schematic (measured 2026-11-17).
    Pipelines have no Desc_PipelineMk<N>_C build class and are not checked."""
    names = {"belt": "ConveyorBelt", "conveyor_lift": "ConveyorLift", "miner": "Miner"}
    caps, _ = load_logistics(REPO)
    for c in caps:
        if c.capability_type not in names:
            continue
        desc = f"Desc_{names[c.capability_type]}{c.mark.replace('.', '')}_C"
        for tier in range(10):
            state = playthrough(REPO, through_tier=tier)
            by_name = c in availability(REPO, state).logistics
            open_b, _ = buildings_unlocked(REPO, lambda s: s.schematic_id in state.milestones)
            assert by_name == (desc in open_b), (c.capability_id, tier)


# --- B2: what Greg described --------------------------------------------------

def test_start_of_phase_two_with_steel_has_no_mk2_miner_or_mk3_belt():
    """'if we are just starting phase 2 and steel then we won't yet have access
    to mk2 miners or mk3 belts' (Greg, 2026-11-17)."""
    a = availability(REPO, playthrough(REPO, through_tier=3))
    assert _marks(a, "miner") == ["Mk.1"]
    assert _marks(a, "belt") == ["Mk.1", "Mk.2"]
    assert all("MinerMk2" not in c for cs in a.extractors.values() for c in cs)


def test_buying_a_milestone_opens_its_mark_and_nothing_else():
    steel = availability(REPO, playthrough(REPO, through_tier=3, milestones=[ADVANCED_STEEL]))
    assert _marks(steel, "miner") == ["Mk.1", "Mk.2"]
    assert _marks(steel, "belt") == ["Mk.1", "Mk.2"]          # Logistics Mk.3 not bought
    both = availability(REPO, playthrough(
        REPO, through_tier=3, milestones=[ADVANCED_STEEL, LOGISTICS_MK3]))
    assert _marks(both, "belt") == ["Mk.1", "Mk.2", "Mk.3"]


def test_no_mk4_belt_anywhere_in_phase_two():
    """'if we're talking about phase 2 mark 4 belts shouldn't be part of the
    consideration' — phase 2 is tiers 3 and 4; Mk.4 is tier 5."""
    a = availability(REPO, playthrough(REPO, through_tier=4))
    assert "Mk.4" not in _marks(a, "belt")


# --- B5 / Q3: recipe status --------------------------------------------------

def test_status_partitions_every_production_recipe():
    a = availability(REPO, playthrough(REPO, through_tier=4))
    assert set(a.status) >= set(a.recipe_ids)
    assert a.with_status(RecipeStatus.OWNED) == a.recipe_ids


def test_pool_alternates_are_in_pool_until_held():
    fresh = availability(REPO, playthrough(REPO, through_tier=0))
    assert fresh.status[CAST_SCREWS] is RecipeStatus.IN_POOL
    held = availability(REPO, playthrough(REPO, through_tier=0, alternates=[CAST_SCREWS]))
    assert held.status[CAST_SCREWS] is RecipeStatus.OWNED
    assert CAST_SCREWS in held.recipe_ids


def test_research_recipes_are_owned_only_once_researched():
    """Turbofuel is not an alternate and no milestone grants it; Compacted Coal
    is an alternate that MAM Sulfur research unlocks (reframe A12.2)."""
    before = availability(REPO, playthrough(REPO, through_tier=5))
    assert before.status[TURBOFUEL] is RecipeStatus.MAM_RESEARCH
    assert before.status[COMPACTED_COAL] is not RecipeStatus.OWNED
    after = availability(REPO, playthrough(
        REPO, through_tier=5, research=[TURBOFUEL_RESEARCH, COMPACTED_RESEARCH]))
    assert after.status[TURBOFUEL] is RecipeStatus.OWNED
    assert after.status[COMPACTED_COAL] is RecipeStatus.OWNED


def test_a_later_band_drive_alternate_is_locked_not_mam_research():
    """Adhered Iron Plate is unlocked only by a hard-drive (EST_Alternate)
    schematic and sits in a later pool band: progression comes first, so it is
    LOCKED at tier 0 (Codex review on PR #15, 2026-11-17)."""
    adhered = "Recipe_Alternate_AdheredIronPlate_C"
    a = availability(REPO, playthrough(REPO, through_tier=0))
    assert adhered in a.pool.not_yet
    assert a.status[adhered] is RecipeStatus.LOCKED


def test_late_recipes_are_locked_early_unless_research_reaches_them():
    """Tier-9 base recipes at tier 0: LOCKED, or MAM_RESEARCH where some MAM
    schematic also unlocks them (several converter recipes are). Never owned."""
    a = availability(REPO, playthrough(REPO, through_tier=0))
    late = set(at_tier(REPO, 9).recipe_ids) - set(at_tier(REPO, 8).recipe_ids)
    seen = {a.status[r] for r in late}
    assert RecipeStatus.LOCKED in seen
    assert seen <= {RecipeStatus.LOCKED, RecipeStatus.MAM_RESEARCH}


def test_the_pool_is_read_at_the_highest_milestone_owned():
    a = availability(REPO, playthrough(REPO, through_tier=3, milestones=[ADVANCED_STEEL]))
    assert a.pool_tier == 4


def test_the_report_says_what_it_does_not_model():
    text = availability(REPO, playthrough(REPO, through_tier=2)).report()
    assert "schematic_dependencies is not walked" in text
    assert "through tier 2" in text


# --- refusals -----------------------------------------------------------------

@pytest.mark.parametrize("kw, match", [
    ({}, "declare through_tier"),
    ({"milestones": ["Schematic_Nope_C"]}, "not in schematics.csv"),
    ({"milestones": [TURBOFUEL_RESEARCH]}, "not a Milestone"),
    ({"through_tier": 1, "research": [ADVANCED_STEEL]}, "not a MAM schematic"),
    ({"through_tier": 1, "alternates": ["Recipe_IronPlate_C"]}, "not alternates"),
    ({"through_tier": -1}, "non-negative"),
])
def test_a_bad_declaration_is_refused_by_name(kw, match):
    with pytest.raises(PlaythroughError, match=match):
        playthrough(REPO, **kw)
