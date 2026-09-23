"""PACED — a storing line clocked to a declared storage rate. Amendment 13 (D2).

The rate is the scheduler's (`progression.schedule`): a bill over the horizon T.
This layer receives a RATE and never T, so §9 holds. What is asserted here:

    derived     stores=True plus a rate is PACED; everything that would pace a
                line twice, or pace a non-storing one, is refused
    clocked     the line runs at (consumers + storage + external) / nameplate,
                so what it makes beyond its consumers and its external demand
                is its storage rate, exactly
    draw        a paced consumer draws its usage, its supply at its clock (A12
                Q2's rule, not a second one), and its peak is that same figure
    P4          PACED and storage-off MATCHED at the same rate are the same
                arithmetic. Pinned so that a divergence is seen
    P5          a paced line with nothing to pace reports `stores_nothing`

Fixtures are the worked case at 1x, tier 4 (see `_realization_builders`).
"""
from __future__ import annotations

import dataclasses

import pytest

import _realization_builders as build
from realization import buses as B
from realization.contracts import (
    BusDeclaration, ClockCause, Disposition, RealizationRequest, SourceEdge,
)
from realization.residual import draw_is_stable

ROTOR_RATE = 1.5   # a declared storage rate on the rotor line, per minute


def _rotor(**kw) -> BusDeclaration:
    base = dict(bus_id="rotor", item_id=build.I_ROTOR,
                sources=(SourceEdge(build.I_SCREW, "screws"),
                         SourceEdge(build.I_IRON_ROD, None)))
    base.update(kw)
    return BusDeclaration(**base)


def _request(rotor: BusDeclaration) -> RealizationRequest:
    buses = tuple(rotor if b.bus_id == "rotor" else b for b in build.worked_buses())
    return RealizationRequest(design_tier=4, buses=buses)


def _buses(reference, logistics, rotor):
    capabilities, _ = logistics
    return {
        b.bus_id: b
        for b in B.buses_from_response(
            build.worked_response(), reference, _request(rotor), capabilities,
        )
    }


# --------------------------------------------------------------------------
# derived, and what is refused
# --------------------------------------------------------------------------

def test_a_storing_line_with_a_rate_is_paced():
    assert _rotor(storage_per_min=ROTOR_RATE).disposition is Disposition.PACED
    assert _rotor(storage_per_min=0.0).disposition is Disposition.PACED
    assert _rotor().disposition is Disposition.WITHDRAWN   # D1 unchanged


@pytest.mark.parametrize("kw,fragment", [
    (dict(stores=False, storage_per_min=1.0), "stores=False"),
    (dict(storage_per_min=1.0, recorded_disposition=Disposition.WITHDRAWN), "record path"),
    (dict(storage_per_min=1.0, withdrawal_per_min=1.0), "withdrawal"),
    (dict(storage_per_min=-1.0), ">= 0"),
])
def test_a_rate_that_would_pace_twice_or_pace_nothing_is_refused(kw, fragment):
    with pytest.raises(ValueError, match=fragment):
        _rotor(**kw)


def test_a_rate_beside_a_bill_is_refused():
    from realization.contracts import BillTerm, WithdrawalBasis, WithdrawalBill

    bill = WithdrawalBill(
        bootstrap_units=1.0, remainder_units=1.0,
        terms=frozenset({BillTerm.MACHINE_CONSTRUCTION, BillTerm.BOOTSTRAP_SET}),
        basis=WithdrawalBasis.DERIVED_WHOLE_GAME_FLOOR,
    )
    with pytest.raises(ValueError, match="withdrawal"):
        _rotor(storage_per_min=1.0, withdrawal_bill=bill)


# --------------------------------------------------------------------------
# clocked
# --------------------------------------------------------------------------

def test_a_paced_line_makes_its_consumers_external_and_storage_exactly(reference, logistics):
    """The round trip: clocked output less what is drawn and asked of it is the
    declared rate, so a bill of rate * T is finished at T."""
    paced = _buses(reference, logistics, _rotor(storage_per_min=ROTOR_RATE))["rotor"]
    unpaced = _buses(reference, logistics, _rotor(stores=False))["rotor"]
    made = sum(l.output_rate_per_min for l in paced.lanes)
    usage_and_external = sum(l.output_rate_per_min for l in unpaced.lanes)
    assert made == pytest.approx(usage_and_external + ROTOR_RATE)
    assert {l.clock_cause for l in paced.lanes} == {ClockCause.PACED}
    assert all(l.clock_percent <= 100.0 for l in paced.lanes)
    assert paced.storage_per_min == ROTOR_RATE


def test_a_rate_beyond_one_machine_adds_a_machine(reference, logistics):
    """The rate is inside the sizing demand: usage plus build-material need,
    Greg's bus sizing rule. Rotor's nameplate at 1x is 4/min."""
    small = _buses(reference, logistics, _rotor(storage_per_min=0.5))["rotor"]
    large = _buses(reference, logistics, _rotor(storage_per_min=6.0))["rotor"]
    assert large.machines > small.machines


# --------------------------------------------------------------------------
# draw — what a paced consumer costs its source
# --------------------------------------------------------------------------

def test_a_paced_consumer_draws_its_usage_and_peaks_at_it(reference, logistics):
    """Supply at its clock is its demand, so draw = usage = peak: exactly what
    the rotor's own lanes take of screws at their clocks. The unpaced storing
    rotor, by contrast, draws its nameplate, which its lanes take only at 100%."""
    buses = _buses(reference, logistics, _rotor(storage_per_min=ROTOR_RATE))
    (p,) = [c for c in buses["screws"].consumers if c.recipe_id == build.R_ROTOR]
    taken = sum(
        i.rate_per_min for l in buses["rotor"].lanes for i in l.inputs
        if i.item_id == build.I_SCREW
    )
    assert p.draw_per_min == pytest.approx(taken)
    assert p.draw_per_min == pytest.approx(p.peak_per_min)
    assert all(l.clock_percent < 100.0 for l in buses["rotor"].lanes)


def test_a_paced_line_draws_constant_power():
    assert draw_is_stable(_rotor(storage_per_min=ROTOR_RATE))
    assert not draw_is_stable(_rotor())   # WITHDRAWN, unchanged


# --------------------------------------------------------------------------
# P4 — pinned equality with storage-off MATCHED
# --------------------------------------------------------------------------

def test_paced_and_matched_at_one_rate_are_the_same_arithmetic(reference, logistics):
    """P4 (Greg, 2026-09-23): kept as two declarations of different intent — a
    fill rate the player draws down by T, against the player's own draw — and
    pinned equal here so that the day they part is visible."""
    paced = _buses(reference, logistics, _rotor(storage_per_min=ROTOR_RATE))
    matched = _buses(reference, logistics, _rotor(stores=False, withdrawal_per_min=ROTOR_RATE))
    assert matched["rotor"].residual.disposition is Disposition.MATCHED
    for bus_id in paced:
        a, b = paced[bus_id], matched[bus_id]
        assert a.machines == b.machines, bus_id
        assert [l.clock_percent for l in a.lanes] == pytest.approx(
            [l.clock_percent for l in b.lanes]), bus_id
        assert a.automated_demand_per_min == pytest.approx(b.automated_demand_per_min), bus_id


# --------------------------------------------------------------------------
# P5 — nothing to pace
# --------------------------------------------------------------------------

def test_a_paced_line_with_nothing_to_pace_stores_nothing(reference, logistics):
    zero = _buses(reference, logistics, _rotor(storage_per_min=0.0))["rotor"]
    some = _buses(reference, logistics, _rotor(storage_per_min=ROTOR_RATE))["rotor"]
    assert zero.stores_nothing
    assert not some.stores_nothing


def test_a_paced_line_with_nothing_to_pace_clocks_to_usage(reference, logistics):
    """'Not just running the machine full.' Same clocks as storage off."""
    zero = _buses(reference, logistics, _rotor(storage_per_min=0.0))["rotor"]
    off = _buses(reference, logistics, _rotor(stores=False))["rotor"]
    assert sum(l.output_rate_per_min for l in zero.lanes) == pytest.approx(
        sum(l.output_rate_per_min for l in off.lanes))
