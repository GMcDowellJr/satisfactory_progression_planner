"""The lag table: what a goal that comes online late costs, shown, not assumed.

Crossover record amendment 18 (Greg, 2026-09-24). One bucket per Project
Assembly phase; goal rates at the ratio of their totals (A15.1,
`schedule.phase_rates`); a goal whose recipe opens part-way through the phase
is REPORTED, not paced. When it opens is the player's pace, which the model
cannot know, so it is never a declared input. The caller lists the opening
points to show, and for each the table gives both ways out:

    finish late   keep the ratio rate; the goal completes `open` minutes after
                  the others: open + T
    catch up      finish at T with the others: total / (T - open), which is
                  the ratio rate / (1 - f)

**Opening points are FRACTIONS OF T**, not minutes. T is a normalisation (the
anchor at 1/min), not a play-time estimate, so "VF online a quarter of the way
through" means the same thing to a 10-hour and a 150-hour player. Minutes are
reported beside the fraction, for the anchor's own scale.

**It divides and multiplies and chooses nothing.** No min, max, sort or round;
no recommended row; rows keep goal order, then the caller's fraction order.
It builds no request. Asserted from the source.
"""
from __future__ import annotations

from dataclasses import dataclass

from production_adapter.contracts import ItemId

from .schedule import PhaseRates, ScheduleError


@dataclass(frozen=True)
class LagRow:
    goal_id: str
    item_id: ItemId
    #: the goal's rate at the ratio of the totals (A15.1)
    ratio_rate_per_min: float
    #: fraction of T elapsed before the goal's line runs
    open_fraction: float
    open_min: float
    #: at the ratio rate: completes this many minutes after T
    late_by_min: float
    finish_at_ratio_min: float
    #: to complete at T instead
    catch_up_rate_per_min: float


@dataclass(frozen=True)
class LagTable:
    horizon_min: float
    anchor_goal_id: str
    rows: tuple[LagRow, ...]


def lag_table(phase: PhaseRates, open_fractions: tuple[float, ...]) -> LagTable:
    """One row per non-anchor goal per opening fraction.

    The anchor has no rows: T is its total at its rate from minute 0 (A15.1),
    so it cannot open late by construction.

    REFUSED: no fractions; a fraction repeated; a fraction outside [0, 1).
    At 1 the goal opens as the phase ends and no rate catches up; past 1 it
    belongs to the next phase.
    """
    if not open_fractions:
        raise ScheduleError(
            "no opening fractions. The table shows the points the caller lists; "
            "there is no default, because a default is a guess at the player's pace."
        )
    if len(open_fractions) != len(set(open_fractions)):
        raise ScheduleError("an opening fraction appears twice")
    for f in open_fractions:
        if f < 0 or f >= 1:
            raise ScheduleError(
                f"opening fraction {f} is outside [0, 1). At 1 the goal opens as the "
                "phase ends and no rate catches up; past 1 it is the next phase's."
            )
    horizon = phase.horizon_min
    rows = []
    for goal_id, item_id, rate in phase.rates:
        if goal_id == phase.anchor_goal_id:
            continue
        for f in open_fractions:
            open_min = f * horizon
            rows.append(LagRow(
                goal_id=goal_id,
                item_id=item_id,
                ratio_rate_per_min=rate,
                open_fraction=f,
                open_min=open_min,
                late_by_min=open_min,
                finish_at_ratio_min=open_min + horizon,
                catch_up_rate_per_min=rate / (1 - f),
            ))
    return LagTable(horizon_min=horizon, anchor_goal_id=phase.anchor_goal_id, rows=tuple(rows))
