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
    ops = {type(n.op) for n in ast.walk(TREE) if isinstance(n, ast.BinOp)}
    assert ops <= {ast.Add, ast.Div}


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
