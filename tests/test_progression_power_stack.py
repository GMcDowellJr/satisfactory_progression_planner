"""The staged generation ledger (reframe A18 and A19, decided by Greg
2026-11-17): generators in the order obtained; standing generators keep
carrying load into later phases; Biomass Burners are backup once another class
is owned; each type alone demonstrates the need; a declared mix says how the
rest is supplied. A report: it never reduces the plan's need."""
from __future__ import annotations

import pathlib

import pytest

from production_adapter import load
from progression import availability, playthrough
from progression.power_stack import (
    BACKUP, IDLE, MIX, PRIMARY, STANDING, PowerStackError, generators_in_order_obtained,
    power_stack,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
BIO, COAL = "Build_GeneratorBiomass_Automated_C", "Build_GeneratorCoal_C"


@pytest.fixture(scope="module")
def data():
    return load(REPO)


FUEL = "Build_GeneratorFuel_C"


def _stack(data, tier, need, standing=None, milestones=(), mix=None):
    state = playthrough(REPO, through_tier=tier, milestones=list(milestones))
    return power_stack(REPO, data, state, need, availability(REPO, state).recipe_ids, standing,
                       mix)


def test_generators_join_in_the_order_obtained():
    order = generators_in_order_obtained(REPO, playthrough(REPO, through_tier=9))
    assert [(c, t) for c, _, t in order] == [
        (BIO, 0), (COAL, 3), ("Build_GeneratorFuel_C", 5), ("Build_GeneratorNuclear_C", 8)]
    assert [n for _, n, _ in order] == ["HUB Upgrade 6", "Coal Power", "Petroleum Power",
                                        "Nuclear Power"]


def test_early_game_biomass_carries_the_need_from_hand_gathered_fuel(data):
    """208.4 MW on 30 MW burners: 7 built. Solid Biofuel at 4/min per burner."""
    (bio,) = _stack(data, 2, 208.4).lines
    assert (bio.role, bio.new_units, bio.load_mw) == (PRIMARY, 7.0, 208.4)
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
    assert (coal.role, coal.new_units) == (PRIMARY, 3.0)
    assert (bio.role, bio.standing_units, bio.new_units) == (BACKUP, 6.0, 0.0)
    assert (bio.load_mw, bio.capacity_mw) == (0.0, 180.0)
    assert stack.headroom_mw == pytest.approx(3 * 75 - 208.4 + 180)
    water = dict(next(f for f in coal.feeds if f.fuel_item_id == "Desc_Coal_C").supplemental)
    assert water["Desc_Water_C"] == pytest.approx(208.4 / 75 * 45)


def test_the_stack_never_reduces_the_plans_need(data):
    """A18: the biofuel chain's constructors are named, not netted."""
    stack = _stack(data, 2, 208.4)
    assert stack.need_mw == 208.4 and stack.lines[0].load_mw == 208.4


@pytest.mark.parametrize("kw, match", [
    ({"standing": {COAL: 2}}, "not unlocked"),
    ({"standing": {BIO: -1}}, "non-negative"),
    ({"mix": {COAL: 1.0}}, "not unlocked"),
    ({"mix": {BIO: 0.5}}, "sum to 0.5"),
    ({"mix": {BIO: 0.0}}, "positive"),
])
def test_bad_declarations_are_refused(data, kw, match):
    with pytest.raises(PowerStackError, match=match):
        _stack(data, 2, 100.0, **kw)


def test_a_state_with_no_generator_is_refused(data):
    state = playthrough(REPO, milestones=["Schematic_3-2_C"])
    with pytest.raises(PowerStackError, match="no generator"):
        power_stack(REPO, data, state, 10.0, ())


# --- A19: later phases, each type alone, the declared mix -----------------------

def test_each_type_alone_demonstrates_the_need(data):
    """A19: how many of each type the need would take by itself, with feeds."""
    stack = _stack(data, 5, 500.0)
    alone = {a.generator_class: a for a in stack.alone}
    assert {c: a.units for c, a in alone.items()} == {BIO: 17.0, COAL: 7.0, FUEL: 2.0}
    coal = {f.fuel_item_id: f.per_min for f in alone[COAL].feeds}
    assert coal["Desc_Coal_C"] == pytest.approx(500 / 75 * 15)


def test_standing_generators_keep_carrying_load_in_a_later_phase(data):
    """A19: three coal generators built in phase 2 still run at tier 5; the
    class obtained last (fuel) carries what they leave; burners stay backup."""
    stack = _stack(data, 5, 500.0, standing={BIO: 6, COAL: 3})
    bio, coal, fuel = stack.lines
    assert (coal.role, coal.standing_units, coal.new_units, coal.load_mw) == (STANDING, 3.0, 0.0, 225.0)
    assert (fuel.role, fuel.new_units, fuel.load_mw) == (PRIMARY, 2.0, 275.0)
    assert (bio.role, bio.load_mw, bio.capacity_mw) == (BACKUP, 0.0, 180.0)
    assert stack.headroom_mw == pytest.approx(225 + 2 * 250 + 180 - 500)


def test_standing_units_above_the_need_leave_the_newest_class_idle(data):
    stack = _stack(data, 5, 100.0, standing={COAL: 3})
    _, coal, fuel = stack.lines
    assert (coal.load_mw, fuel.role, fuel.new_units, fuel.load_mw) == (100.0, PRIMARY, 0.0, 0.0)


def test_a_declared_mix_shares_what_standing_units_leave(data):
    """A19's separate ratio system: half coal, half fuel of the 275 MW the
    standing coal leaves; coal's share is netted against its standing units."""
    stack = _stack(data, 5, 500.0, standing={COAL: 3}, mix={COAL: 0.5, FUEL: 0.5})
    bio, coal, fuel = stack.lines
    assert (coal.role, coal.load_mw, coal.new_units) == (MIX, 362.5, 2.0)   # 225 + 137.5
    assert (fuel.role, fuel.load_mw, fuel.new_units) == (MIX, 137.5, 1.0)
    assert (bio.role, bio.capacity_mw) == (BACKUP, 0.0)
    assert stack.mix == ((COAL, 0.5), (FUEL, 0.5))


def test_an_owned_class_with_no_load_is_idle(data):
    _, coal, _ = _stack(data, 5, 500.0).lines
    assert (coal.role, coal.new_units, coal.feeds[0].per_min) == (IDLE, 0.0, 0.0)


def test_burners_named_in_the_mix_carry_load(data):
    """Backup is the default for burners once coal is owned, not a rule the
    declared mix cannot override."""
    bio, coal = _stack(data, 4, 200.0, mix={BIO: 0.25, COAL: 0.75}).lines
    assert (bio.role, bio.load_mw, bio.new_units) == (MIX, 50.0, 2.0)
    assert (coal.role, coal.load_mw, coal.new_units) == (MIX, 150.0, 2.0)


# --- A19: the supply check, given what is left ----------------------------------

def test_the_supply_check_reads_only_lines_carrying_load(data):
    """Backup burners burn only on a spike: not checked. An uncapped supply
    covers; Water with no Water Extractor is named."""
    from progression.power_stack import COVERED, NO_PUMP, supply_check
    stack = _stack(data, 4, 208.4, standing={BIO: 6})
    check = supply_check(stack, {"Desc_Coal_C": None}, water_extractor_owned=False)
    assert {c.generator_class for c in check.checks} == {COAL}
    by = {(c.fuel_item_id, c.item_id): c.status for c in check.checks}
    assert by[("Desc_Coal_C", "Desc_Coal_C")] == COVERED
    assert by[("Desc_Coal_C", "Desc_Water_C")] == NO_PUMP
    assert check.fed_by == ((COAL, ()),)
    ok = supply_check(stack, {"Desc_Coal_C": None}, water_extractor_owned=True)
    assert ok.fed_by == ((COAL, ("Desc_Coal_C",)),)


def test_biomass_fuel_the_site_lacks_is_gathered_by_hand(data):
    from progression.power_stack import BY_HAND, supply_check
    check = supply_check(_stack(data, 2, 100.0), {}, water_extractor_owned=False)
    assert {c.status for c in check.checks} == {BY_HAND}
    assert check.fed_by[0][0] == BIO and "Desc_Biofuel_C" in check.fed_by[0][1]
