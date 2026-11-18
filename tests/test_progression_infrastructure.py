"""Extractor and belt marks: highest available, stepped down where it does not help.

Reframe A15.2 B2 and Q1, decided by Greg 2026-11-17; reconciliation R6.
"""
from __future__ import annotations

import pathlib

import pytest

from production_adapter.gamedata import load_logistics
from production_adapter.scenario import Scenario
from progression import availability, playthrough
from progression.infrastructure import (
    HIGHEST_THEN_STEP_DOWN, POLICIES, InfrastructureError, belt_for, extractor_options,
    highest_extractor, step_down_extractor,
)
from progression.power import load_power_tables

REPO = pathlib.Path(__file__).resolve().parents[1]
IRON = "Desc_OreIron_C"
OIL = "Desc_LiquidOil_C"
ADVANCED_STEEL = "Schematic_4-1_C"


@pytest.fixture(scope="module")
def rates():
    return load_logistics(REPO)[1]


@pytest.fixture(scope="module")
def base_mw():
    return load_power_tables(REPO).extractors


def _avail(tier, *milestones):
    return availability(REPO, playthrough(REPO, through_tier=tier, milestones=list(milestones)))


def _iron(avail, rates, base_mw, purity="pure", scenario=Scenario()):
    return extractor_options(avail, IRON, purity, rates, base_mw, scenario)


def test_the_policy_is_named():
    assert POLICIES == (HIGHEST_THEN_STEP_DOWN,)


# --- supply half: the highest mark the playthrough has ------------------------

def test_options_follow_milestones_not_phase(rates, base_mw):
    start = _iron(_avail(3), rates, base_mw)
    assert [o.extractor_class for o in start] == ["Build_MinerMk1_C"]
    steel = _iron(_avail(3, ADVANCED_STEEL), rates, base_mw)
    assert [o.extractor_class for o in steel] == ["Build_MinerMk1_C", "Build_MinerMk2_C"]
    assert highest_extractor(steel).nominal_rate_min == 240.0   # pure


def test_the_power_multiplier_reaches_the_options(rates, base_mw):
    """Reframe A7: P scales extractors."""
    one = _iron(_avail(4), rates, base_mw)
    five = _iron(_avail(4), rates, base_mw, scenario=Scenario(machine_power_multiplier=5.0))
    assert [o.mw * 5 for o in one] == pytest.approx([o.mw for o in five])


# --- realize half: step down where the higher mark does not help (Q1) ---------

def test_a_draw_the_lower_mark_carries_steps_down(rates, base_mw):
    """Pure iron drawn at 100/min: Mk.1 (120/min) carries it at 4.17 MW by the
    draw; Mk.2 would charge 6.25 MW. Same delivered rate, lower power."""
    choice = step_down_extractor("s1", IRON, "pure", 100.0, _iron(_avail(4), rates, base_mw))
    assert choice.chosen.extractor_class == "Build_MinerMk1_C"
    assert choice.stepped_down
    assert choice.mw_saved == pytest.approx(15 * 100 / 240 - 5 * 100 / 120)


def test_a_draw_only_the_higher_mark_carries_keeps_it(rates, base_mw):
    choice = step_down_extractor("s1", IRON, "pure", 200.0, _iron(_avail(4), rates, base_mw))
    assert choice.chosen.extractor_class == "Build_MinerMk2_C"
    assert not choice.stepped_down


def test_an_undrawn_socket_builds_nothing(rates, base_mw):
    choice = step_down_extractor("s1", IRON, "normal", 0.0, _iron(_avail(4), rates, base_mw, "normal"))
    assert choice.chosen is None and "not drawn" in choice.reason


def test_a_draw_beyond_the_socket_is_refused(rates, base_mw):
    with pytest.raises(InfrastructureError, match="exceeded the socket's cap"):
        step_down_extractor("s1", IRON, "pure", 241.0, _iron(_avail(4), rates, base_mw))


def test_no_extractor_unlocked_is_refused(rates, base_mw):
    with pytest.raises(InfrastructureError, match="no extractor is unlocked"):
        extractor_options(_avail(0), OIL, "normal", rates, base_mw, Scenario())


# --- belts (Q1: "less than 60/min use a mk1 belt instead of the mk2") ---------

@pytest.mark.parametrize("flow, mark", [(45.0, "Mk.1"), (59.0, "Mk.1"), (60.0, "Mk.1"),
                                        (61.0, "Mk.2"), (120.0, "Mk.2")])
def test_a_lane_takes_the_lowest_belt_that_carries_it(flow, mark):
    choice = belt_for(flow, _avail(3))
    assert (choice.lanes, choice.mark.mark) == (1, mark)
    assert choice.highest.mark == "Mk.2"
    assert choice.stepped_down == (mark != "Mk.2")


def test_past_the_highest_mark_a_flow_needs_lanes():
    """At tier 4 the highest belt is Mk.3 (270/min): 360/min is two lanes of
    180, each on Mk.3 (Mk.2 carries 120). The case the Nov-10 spec named."""
    choice = belt_for(360.0, _avail(4, "Schematic_5-3_C"))
    assert (choice.lanes, choice.mark.mark) == (2, "Mk.3")


def test_lanes_step_down_too():
    """300/min with Mk.1 and Mk.2 only: three lanes of 100, each on Mk.2."""
    choice = belt_for(300.0, _avail(3))
    assert (choice.lanes, choice.mark.mark) == (3, "Mk.2")


def test_pipes_follow_the_same_rule():
    assert belt_for(250.0, _avail(3), "pipeline").mark.mark == "Mk.1"
    with pytest.raises(InfrastructureError, match="no pipeline is unlocked"):
        belt_for(10.0, _avail(2), "pipeline")


def test_a_non_positive_flow_is_refused():
    with pytest.raises(InfrastructureError, match="positive"):
        belt_for(0.0, _avail(3))
