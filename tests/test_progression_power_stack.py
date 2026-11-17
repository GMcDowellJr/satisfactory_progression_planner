"""The staged generation ledger (reframe A18, decided by Greg 2026-11-17):
generators in the order obtained; the class obtained last carries the need;
earlier classes are backup up to their max; biomass from hand-gathered leaves
or wood through constructors. A report: it never reduces the plan's need."""
from __future__ import annotations

import pathlib

import pytest

from production_adapter import load
from progression import availability, playthrough
from progression.power_stack import (
    BACKUP, PRIMARY, PowerStackError, generators_in_order_obtained, power_stack,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
BIO, COAL = "Build_GeneratorBiomass_Automated_C", "Build_GeneratorCoal_C"


@pytest.fixture(scope="module")
def data():
    return load(REPO)


def _stack(data, tier, need, standing=None, milestones=()):
    state = playthrough(REPO, through_tier=tier, milestones=list(milestones))
    return power_stack(REPO, data, state, need, availability(REPO, state).recipe_ids, standing)


def test_generators_join_in_the_order_obtained():
    order = generators_in_order_obtained(REPO, playthrough(REPO, through_tier=9))
    assert [(c, t) for c, _, t in order] == [
        (BIO, 0), (COAL, 3), ("Build_GeneratorFuel_C", 5), ("Build_GeneratorNuclear_C", 8)]
    assert [n for _, n, _ in order] == ["HUB Upgrade 6", "Coal Power", "Petroleum Power",
                                        "Nuclear Power"]


def test_early_game_biomass_carries_the_need_from_hand_gathered_fuel(data):
    """208.4 MW on 30 MW burners: 7 built. Solid Biofuel at 4/min per burner."""
    (bio,) = _stack(data, 2, 208.4).lines
    assert (bio.role, bio.units) == (PRIMARY, 7.0)
    feed = {f.fuel_item_id: f.per_min for f in bio.feeds}
    assert feed["Desc_Biofuel_C"] == pytest.approx(208.4 / 30 * 4)
    leaves = next(c for c in bio.biofuel if c.source_item_id == "Desc_Leaves_C")
    # 120 Biomass -> 60 Biofuel; 120 Leaves -> 60 Biomass
    assert leaves.biofuel_constructors == pytest.approx(feed["Desc_Biofuel_C"] / 60)
    assert leaves.by_hand_per_min == pytest.approx(feed["Desc_Biofuel_C"] * 4)
    assert leaves.owned


def test_once_coal_is_owned_burners_are_backup_up_to_their_max(data):
    stack = _stack(data, 4, 208.4, standing={BIO: 6})
    bio, coal = stack.lines
    assert (coal.role, coal.units) == (PRIMARY, 3.0)
    assert (bio.role, bio.units, bio.output_mw) == (BACKUP, 6.0, 180.0)
    assert stack.headroom_mw == pytest.approx(3 * 75 - 208.4 + 180)
    water = dict(next(f for f in coal.feeds if f.fuel_item_id == "Desc_Coal_C").supplemental)
    assert water["Desc_Water_C"] == pytest.approx(208.4 / 75 * 45)


def test_the_stack_never_reduces_the_plans_need(data):
    """A18: the biofuel chain's constructors are named, not netted."""
    stack = _stack(data, 2, 208.4)
    assert stack.need_mw == 208.4 and stack.lines[0].output_mw == 208.4


@pytest.mark.parametrize("kw, match", [
    ({"standing": {COAL: 2}}, "not unlocked"),
    ({"standing": {BIO: -1}}, "non-negative"),
])
def test_bad_declarations_are_refused(data, kw, match):
    with pytest.raises(PowerStackError, match=match):
        _stack(data, 2, 100.0, **kw)


def test_a_state_with_no_generator_is_refused(data):
    state = playthrough(REPO, milestones=["Schematic_3-2_C"])
    with pytest.raises(PowerStackError, match="no generator"):
        power_stack(REPO, data, state, 10.0, ())
