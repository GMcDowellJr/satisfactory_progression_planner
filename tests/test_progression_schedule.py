"""`progression.schedule`: a horizon, and a bill over it as a rate. A13 (D2).

It divides and does nothing else, and that is its guardrail. The arithmetic
tests are short because there is little arithmetic; the inspection tests are
the ones that matter.
"""
from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass

import pytest

from progression import schedule

SOURCE = (
    pathlib.Path(__file__).resolve().parents[1]
    / "tools" / "progression" / "src" / "progression" / "schedule.py"
)
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class _Bill:
    bootstrap_units: float
    remainder_units: float


def test_the_horizon_is_the_anchor_total_at_the_anchor_rate():
    """50 Smart Plating at 1/min: Greg's worked number."""
    assert schedule.horizon_from_anchor(50.0, 1.0) == 50.0


def test_a_bill_over_the_horizon_is_whole_bill_over_t():
    """500 rotors in 50 minutes is 10/min (Greg, 2026-09-23). Bootstrap and
    remainder are both paced: the current tier's build plus the next tier's
    start (P1)."""
    rates = schedule.storage_rates(
        {"rotor": _Bill(0.0, 500.0), "plate": _Bill(25.0, 375.0)}, 50.0,
    )
    assert rates == {"rotor": 10.0, "plate": 8.0}


def test_bill_order_is_kept():
    bills = {"b": _Bill(0, 1), "a": _Bill(0, 1)}
    assert list(schedule.storage_rates(bills, 1.0)) == ["b", "a"]


@pytest.mark.parametrize("total,rate", [(0.0, 1.0), (50.0, 0.0), (-1.0, 1.0)])
def test_a_horizon_that_cannot_be_stated_is_refused(total, rate):
    with pytest.raises(schedule.ScheduleError):
        schedule.horizon_from_anchor(total, rate)


def test_a_non_positive_horizon_is_refused():
    with pytest.raises(schedule.ScheduleError):
        schedule.storage_rates({"x": _Bill(0, 1)}, 0.0)


# --------------------------------------------------------------------------
# it divides — read from the source
# --------------------------------------------------------------------------

def test_the_only_arithmetic_is_adding_the_halves_and_dividing():
    """Amended for D3: one multiplication is admitted, and only inside
    `carry_estimate`, whose result cannot be netted (stock.net_of refuses it).
    Everywhere else the rule is A13's: add and divide."""
    ops = {type(n.op) for n in ast.walk(TREE) if isinstance(n, ast.BinOp)}
    assert ops <= {ast.Add, ast.Div, ast.Mult}
    for fn in [n for n in TREE.body if isinstance(n, ast.FunctionDef)]:
        mults = [n for n in ast.walk(fn) if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult)]
        if fn.name == "carry_estimate":
            assert len(mults) == 1
        else:
            assert not mults, fn.name


def test_nothing_is_ranked_or_rounded():
    called = {
        (n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", ""))
        for n in ast.walk(TREE) if isinstance(n, ast.Call)
    }
    assert {"min", "max", "sorted", "sort", "round", "ceil", "floor"}.isdisjoint(called)


def test_it_imports_no_layer():
    """Adapter contract types only. No realization, no stock, no solver."""
    imported = set()
    for n in ast.walk(TREE):
        if isinstance(n, ast.Import):
            imported.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            imported.add(("." * n.level) + (n.module or ""))
    assert imported <= {"__future__", "collections.abc", "production_adapter.contracts"}


# --------------------------------------------------------------------------
# D3 — rates over a netted bill, and a carry estimate that never nets
# --------------------------------------------------------------------------

def test_rates_of_divides_quantities_by_t_in_order():
    rates = schedule.rates_of({"b": 500.0, "a": 0.0}, 50.0)
    assert rates == {"b": 10.0, "a": 0.0}
    assert list(rates) == ["b", "a"]


def test_rates_of_agrees_with_storage_rates_on_a_whole_bill():
    """Same division, different input shape (P4)."""
    bills = {"plate": _Bill(25.0, 1100.0), "rotor": _Bill(0.0, 62.0)}
    whole = {i: b.bootstrap_units + b.remainder_units for i, b in bills.items()}
    assert schedule.rates_of(whole, 50.0) == schedule.storage_rates(bills, 50.0)


@pytest.mark.parametrize("quantities,horizon", [({"x": -1.0}, 50.0), ({"x": 1.0}, 0.0)])
def test_rates_of_refuses_a_negative_quantity_or_horizon(quantities, horizon):
    with pytest.raises(schedule.ScheduleError):
        schedule.rates_of(quantities, horizon)


def test_a_carry_estimate_is_prior_rate_times_gap():
    est = schedule.carry_estimate({"plate": 22.5, "rotor": 1.24}, 20.0)
    assert est.estimated_units == pytest.approx({"plate": 450.0, "rotor": 24.8})
    assert est.gap_min == 20.0
    assert est.prior_rates == {"plate": 22.5, "rotor": 1.24}


def test_a_negative_gap_is_refused():
    with pytest.raises(schedule.ScheduleError):
        schedule.carry_estimate({"x": 1.0}, -1.0)


def test_a_carry_estimate_has_nothing_shaped_like_a_declaration():
    """No `units` pairs, so it cannot be passed where a DeclaredOnHand's
    contents are read. `stock.net_of` refuses the type outright as well."""
    est = schedule.carry_estimate({"x": 1.0}, 1.0)
    assert not hasattr(est, "units")
