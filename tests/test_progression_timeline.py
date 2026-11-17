"""Project Assembly duration with storage-priority banks (reconciliation R8).

Reframe A15.2 B3 and Q6, decided by Greg 2026-11-17. The fixture follows the
shape of Greg's Smart Plating practice: a bank of underclocked constructors
making 73 Iron Plate/min for storage, ahead of the PA lanes on the same
ingot feed. The feed, bill and PA rate below are the TEST's numbers, not
measured ones.
"""
from __future__ import annotations

import math
import pathlib

import pytest

from progression import playthrough
from progression.timeline import (
    SMART, STANDARD, StorageBank, TimelineError, container_options, pa_duration,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
SP = "Desc_SpaceElevatorPart_1_C"
VF = "Desc_SpaceElevatorPart_2_C"
PLATE = "Desc_IronPlate_C"
INGOTS_FOR_73_PLATES = 73 * 3 / 2      # Iron Plate: 3 ingots -> 2 plates


def _bank(**kw):
    base = dict(name="plates", storage_item=PLATE, feed_per_min=240.0,
                bank_intake_per_min=INGOTS_FOR_73_PLATES, bank_output_per_min=73.0,
                capacity_units=4800.0, pa_items=(SP,), splitter=SMART)
    base.update(kw)
    return StorageBank(**base)


# --- without banks: bill / rate ------------------------------------------------

def test_without_banks_each_part_takes_bill_over_rate():
    t = pa_duration({SP: 2500.0, VF: 1000.0}, {SP: 10.0, VF: 5.0})
    assert t.duration_min == pytest.approx(250.0)
    assert t.delay_min == pytest.approx(0.0)


# --- B3: smart splitter, bank first --------------------------------------------

def test_a_smart_bank_fills_first_then_pa_gets_everything():
    b = _bank()
    assert b.bank_take_per_min == pytest.approx(INGOTS_FOR_73_PLATES)
    assert b.fill_rate_per_min == pytest.approx(73.0)
    assert b.fill_min == pytest.approx(4800 / 73)
    t = pa_duration({SP: 2500.0}, {SP: 10.0}, (b,))
    # while filling the PA lane runs at its feed share; the delay is the
    # filling time times the share it lost
    assert t.delay_min == pytest.approx(b.fill_min * (1 - b.pa_share_filling))
    assert t.stock_at_finish == (("plates", PLATE, pytest.approx(4800.0)),)


def test_a_bank_that_takes_the_whole_feed_stalls_pa_until_full():
    """Greg's first try, as the model reads it: storage starves the PA lane."""
    b = _bank(feed_per_min=INGOTS_FOR_73_PLATES)
    assert b.pa_share_filling == pytest.approx(0.0)
    t = pa_duration({SP: 2500.0}, {SP: 10.0}, (b,))
    assert t.duration_min == pytest.approx(b.fill_min + 250.0)


def test_a_bank_larger_than_the_phase_never_fills():
    b = _bank(capacity_units=1e9)
    t = pa_duration({SP: 2500.0}, {SP: 10.0}, (b,))
    assert t.duration_min == pytest.approx(2500.0 / (10.0 * b.pa_share_filling))
    (_, _, units), = t.stock_at_finish
    assert units == pytest.approx(73.0 * t.duration_min)


# --- B3: the standard splitter as the bootstrap --------------------------------

def test_a_standard_splitter_offers_only_its_share():
    """Round-robin over three outputs, one to the bank: the bank is offered
    80 of 240 ingots/min and takes all of it (it could take 109.5)."""
    b = _bank(splitter=STANDARD, standard_share=1 / 3)
    assert b.bank_take_per_min == pytest.approx(80.0)
    assert b.pa_share_filling == pytest.approx(2 / 3)
    assert b.fill_rate_per_min == pytest.approx(73.0 * 80 / INGOTS_FOR_73_PLATES)
    smart = pa_duration({SP: 2500.0}, {SP: 10.0}, (_bank(),))
    standard = pa_duration({SP: 2500.0}, {SP: 10.0}, (b,))
    assert standard.banks[0].fill_min > smart.banks[0].fill_min   # fills slower


# --- Q6: container options -----------------------------------------------------

def test_container_options_follow_the_milestones():
    """Storage Container from the start; Industrial with Logistics Mk.3."""
    early = container_options(REPO, playthrough(REPO, through_tier=3), stack_size=200, count=1)
    assert [(o.building_class, o.capacity_units) for o in early] == \
        [("Desc_StorageContainerMk1_C", 4800.0)]
    later = container_options(REPO, playthrough(REPO, through_tier=4), stack_size=200, count=2)
    assert [o.capacity_units for o in later] == [9600.0, 19200.0]


def test_no_container_unlocked_is_refused():
    state = playthrough(REPO, milestones=["Schematic_3-2_C"])   # no HUB tutorials
    with pytest.raises(TimelineError, match="no storage container"):
        container_options(REPO, state, stack_size=200, count=1)


# --- refusals --------------------------------------------------------------------

@pytest.mark.parametrize("kw, match", [
    ({"splitter": "priority"}, "splitter"),
    ({"splitter": STANDARD}, "standard_share"),
    ({"standard_share": 0.5}, "standard_share"),
    ({"splitter": STANDARD, "standard_share": 1.0}, r"\(0, 1\)"),
    ({"capacity_units": 0.0}, "capacity_units must be positive"),
    ({"pa_items": ()}, "PA parts"),
])
def test_a_bad_bank_is_refused(kw, match):
    with pytest.raises(TimelineError, match=match):
        _bank(**kw)


def test_a_part_with_no_rate_or_two_banks_is_refused():
    with pytest.raises(TimelineError, match="no positive PA rate"):
        pa_duration({SP: 10.0}, {})
    with pytest.raises(TimelineError, match="composition is not modelled"):
        pa_duration({SP: 10.0}, {SP: 1.0}, (_bank(), _bank(name="again")))
    with pytest.raises(TimelineError, match="does not hold"):
        pa_duration({VF: 10.0}, {VF: 1.0}, (_bank(),))


def test_the_report_states_what_it_leaves_out():
    text = pa_duration({SP: 2500.0}, {SP: 10.0}, (_bank(),)).report()
    assert "withdrawals" in text and "linear" in text
    assert not math.isinf(pa_duration({SP: 1.0}, {SP: 1.0}).duration_min)
