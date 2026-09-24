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
    # `dataclasses` admitted 2026-09-24 for `PhaseRates` (crossover A15): a
    # standard-library record type, not a layer
    assert imported <= {"__future__", "collections.abc", "dataclasses",
                        "production_adapter.contracts"}


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


# --------------------------------------------------------------------------
# P6 — several goals on one T, anchored on a goal the caller names (A15)
# --------------------------------------------------------------------------

SP, VF, AW = "Desc_SpaceElevatorPart_1_C", "Desc_SpaceElevatorPart_2_C", "Desc_SpaceElevatorPart_3_C"
PHASE_2 = (("sp", SP, 1000.0), ("vf", VF, 1000.0), ("aw", AW, 100.0))


def test_phase_2_anchored_on_smart_plating_at_one_per_minute():
    """T = 1000 min; VF paces to 1/min, AW to 0.1/min. Caller order kept."""
    got = schedule.phase_rates(PHASE_2, anchor_goal_id="sp", anchor_rate_per_min=1.0)
    assert got.horizon_min == 1000.0
    assert got.anchor_goal_id == "sp"
    assert got.rates == (("sp", SP, 1.0), ("vf", VF, 1.0), ("aw", AW, 0.1))


def test_the_anchor_is_the_callers_and_moves_t():
    """Anchoring AW at 0.2/min gives T = 500, and every rate doubles."""
    got = schedule.phase_rates(PHASE_2, anchor_goal_id="aw", anchor_rate_per_min=0.2)
    assert got.horizon_min == pytest.approx(500.0)
    assert [r for _, _, r in got.rates] == pytest.approx([2.0, 2.0, 0.2])


def test_every_goal_completes_at_t():
    got = schedule.phase_rates(PHASE_2, anchor_goal_id="vf", anchor_rate_per_min=2.5)
    totals = {g: t for g, _, t in PHASE_2}
    for goal_id, _, rate in got.rates:
        assert totals[goal_id] / rate == pytest.approx(got.horizon_min)


@pytest.mark.parametrize("goals, anchor, match", [
    (PHASE_2, "nope", "names no goal"),
    (PHASE_2 + (("sp", "x", 1.0),), "sp", "goal id appears twice"),
    (PHASE_2 + (("sp2", SP, 5.0),), "sp", "one item"),
    ((("sp", SP, 0.0),), "sp", "must be positive"),
])
def test_a_phase_that_cannot_be_paced_is_refused(goals, anchor, match):
    with pytest.raises(schedule.ScheduleError, match=match):
        schedule.phase_rates(goals, anchor_goal_id=anchor, anchor_rate_per_min=1.0)
