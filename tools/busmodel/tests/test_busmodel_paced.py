"""PACED in the oracle. Amendment 13 (D2), mirroring `realization`.

A12.1 pinned STORAGE == AVERAGE "so that the day D2 gives a storing line a
target clock, this test is where the two rules are seen to part". They do NOT
part, and this file is where that is pinned instead. With PACED a new derived
value (P3), a paced consumer is not WITHDRAWN, so AVERAGE's record rule
(WITHDRAWN draws nameplate) never reaches it; and under STORAGE its supply at
its clock IS its demand, which is usage. Every basis sizes a paced line the
same way, and the basis question does not arise for it. The A12.1 test is left
as it stands: its equality still holds on every declaration it covers.
"""
from __future__ import annotations

import dataclasses

import pytest

from busmodel import declarations as decls
from busmodel.model import SOLVE_BASES, BusSpec, solve
from realization.contracts import Disposition

RATE = 3.0   # a declared storage rate on every paced line, per minute


def _paced(decl):
    """Every storing line without a withdrawal paced at RATE; every line with a
    withdrawal storage-off MATCHED. Record paths dropped, so each line derives
    from the toggle and the rate alone."""
    return dataclasses.replace(
        decl,
        buses=tuple(
            dataclasses.replace(b, stores=True, recorded_disposition=None, storage_per_min=RATE)
            if b.withdrawal_per_min is None
            else dataclasses.replace(b, stores=False, recorded_disposition=None)
            for b in decl.buses
        ),
    )


@pytest.fixture(scope="module")
def paced(scenario_of_record):
    return _paced(decls.worked_case_a4(scenario_of_record))


def test_every_basis_sizes_a_paced_declaration_the_same(paced, scenario_of_record):
    solutions = [solve(paced, scenario_of_record, sizing_basis=b) for b in SOLVE_BASES]
    first = solutions[0]
    for other in solutions[1:]:
        assert [b.machines for b in other.buses] == [b.machines for b in first.buses]
        for x, y in zip(other.buses, first.buses):
            assert x.automated_demand_per_min == pytest.approx(y.automated_demand_per_min)


def test_a_paced_line_is_clocked_to_its_demand_and_stores_its_rate(paced, scenario_of_record):
    s = solve(paced, scenario_of_record)
    for spec in paced.buses:
        b = s[spec.bus_id]
        if spec.disposition is not Disposition.PACED:
            continue
        assert b.supply_per_min == pytest.approx(b.demand_per_min), spec.bus_id
        assert b.clock_percent <= 100.0 + 1e-9, spec.bus_id
        assert b.storage_per_min == RATE
        assert b.demand_per_min == pytest.approx(
            b.external_per_min + b.automated_demand_per_min + RATE), spec.bus_id


def test_paced_and_matched_at_one_rate_are_the_same_arithmetic(paced, scenario_of_record):
    """P4, pinned on this side too."""
    matched = dataclasses.replace(
        paced,
        buses=tuple(
            dataclasses.replace(b, stores=False, storage_per_min=None, withdrawal_per_min=RATE)
            if b.disposition is Disposition.PACED else b
            for b in paced.buses
        ),
    )
    a, b = solve(paced, scenario_of_record), solve(matched, scenario_of_record)
    assert [x.machines for x in a.buses] == [y.machines for y in b.buses]
    for x, y in zip(a.buses, b.buses):
        assert x.clock_percent == pytest.approx(y.clock_percent)
        assert x.supply_per_min == pytest.approx(y.supply_per_min)


def test_a_paced_line_with_nothing_to_pace_stores_nothing(scenario_of_record):
    decl = decls.worked_case_a4(scenario_of_record)
    zero = dataclasses.replace(decl, buses=tuple(
        dataclasses.replace(b, stores=True, recorded_disposition=None, storage_per_min=0.0)
        if b.withdrawal_per_min is None else b
        for b in decl.buses
    ))
    s = solve(zero, scenario_of_record)
    paced_ids = [b.bus_id for b in zero.buses if b.disposition is Disposition.PACED]
    assert paced_ids
    assert all(s[i].stores_nothing for i in paced_ids)


@pytest.mark.parametrize("kw", [
    dict(stores=False, storage_per_min=1.0),
    dict(storage_per_min=1.0, withdrawal_per_min=1.0),
    dict(storage_per_min=-1.0),
])
def test_a_rate_that_would_pace_twice_or_pace_nothing_is_refused(kw):
    with pytest.raises(ValueError):
        BusSpec(bus_id="x", item_id="Desc_Rotor_C", recipe_id="Recipe_Rotor_C", **kw)
