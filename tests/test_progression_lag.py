"""The lag table (crossover amendment 18). One bucket per phase; late goals reported.

Worked: phase 2 anchored on Smart Plating at 1/min, T = 1000; SP 1000, VF
1000, AW 100 -> ratio rates 1.0, 1.0, 0.1. VF online a quarter of the way in:
finish 250 minutes late at 1.0/min, or run 1.333/min to finish at T.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from progression import lag, schedule

SP, VF, AW = "Desc_SpaceElevatorPart_1_C", "Desc_SpaceElevatorPart_2_C", "Desc_SpaceElevatorPart_3_C"
PHASE_2 = (("SP", SP, 1000.0), ("VF", VF, 1000.0), ("AW", AW, 100.0))
FRACTIONS = (0.125, 0.25, 0.5, 0.9)


@pytest.fixture(scope="module")
def table():
    phase = schedule.phase_rates(PHASE_2, anchor_goal_id="SP", anchor_rate_per_min=1.0)
    return lag.lag_table(phase, FRACTIONS)


def test_the_anchor_has_no_rows_and_order_is_kept(table):
    assert [(r.goal_id, r.open_fraction) for r in table.rows] == [
        (g, f) for g in ("VF", "AW") for f in FRACTIONS]
    assert table.horizon_min == 1000.0 and table.anchor_goal_id == "SP"


def test_versatile_framework_catch_up_rates(table):
    vf = [r for r in table.rows if r.goal_id == "VF"]
    assert [r.catch_up_rate_per_min for r in vf] == pytest.approx([8 / 7, 4 / 3, 2.0, 10.0])
    assert [r.open_min for r in vf] == pytest.approx([125.0, 250.0, 500.0, 900.0])
    assert [r.finish_at_ratio_min for r in vf] == pytest.approx([1125.0, 1250.0, 1500.0, 1900.0])
    assert all(r.late_by_min == r.open_min for r in vf)
    assert all(r.ratio_rate_per_min == pytest.approx(1.0) for r in vf)


def test_automated_wiring_scales_with_its_ratio(table):
    aw = [r for r in table.rows if r.goal_id == "AW"]
    assert [r.catch_up_rate_per_min for r in aw] == pytest.approx([0.8 / 7, 0.4 / 3, 0.2, 1.0])


def test_catch_up_finishes_at_t(table):
    """Total / catch-up rate + open == T, for every row."""
    totals = {g: t for g, _, t in PHASE_2}
    for r in table.rows:
        assert r.open_min + totals[r.goal_id] / r.catch_up_rate_per_min == pytest.approx(1000.0)


def test_fractions_are_pace_free():
    """The same fractions at a different anchor rate (T = 500): the catch-up
    multiple and the finish-late share of T are unchanged."""
    slow = lag.lag_table(schedule.phase_rates(PHASE_2, anchor_goal_id="SP",
                                              anchor_rate_per_min=1.0), (0.25,))
    fast = lag.lag_table(schedule.phase_rates(PHASE_2, anchor_goal_id="SP",
                                              anchor_rate_per_min=2.0), (0.25,))
    for s, f in zip(slow.rows, fast.rows):
        assert f.catch_up_rate_per_min / f.ratio_rate_per_min == pytest.approx(
            s.catch_up_rate_per_min / s.ratio_rate_per_min)
        assert f.late_by_min / fast.horizon_min == pytest.approx(s.late_by_min / slow.horizon_min)


@pytest.mark.parametrize("fractions, match", [
    ((), "no opening fractions"),
    ((0.25, 0.25), "twice"),
    ((-0.1,), "outside"),
    ((1.0,), "outside"),
    ((1.5,), "outside"),
])
def test_bad_fractions_are_refused(fractions, match):
    phase = schedule.phase_rates(PHASE_2, anchor_goal_id="SP", anchor_rate_per_min=1.0)
    with pytest.raises(schedule.ScheduleError, match=match):
        lag.lag_table(phase, fractions)


def test_it_ranks_nothing_and_builds_no_request():
    src = pathlib.Path(lag.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    called = {
        (n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", ""))
        for n in ast.walk(tree) if isinstance(n, ast.Call)
    }
    assert {"min", "max", "sorted", "sort", "round",
            "OutputTarget", "SolveRequest"}.isdisjoint(called)
