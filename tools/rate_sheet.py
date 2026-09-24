#!/usr/bin/env python3
"""The per-phase rate sheet: what each line of a paced build does per minute. REPORTED.

Greg, 2026-09-24. The tool's stated goal is how many of each part to make per
minute at a stage of the game; this is that answer, read off one paced run. A
VIEW ONLY, like `chain_view` and `storage_view`: it reads a `RealizationReport`
and the run's goals and sizes nothing.

    scale      THE RUN'S RATE, never a multiple of it (Greg, 2026-09-24).
               Rates are not linear in the anchor rate: a faster run builds
               more machines, whose build-material bill is billed back into
               the storage rates. Phase 2 at 2 SP/min sits 0.2-0.7% above
               double the 1/min run on the iron and copper lines. So a sheet
               holds only for the anchor rate it was run at, the anchor rate
               is READ from the run's goals and printed, and a different
               rate is a different run. The view takes no rate argument
    per line   a row per bus in the report's order:
                 machines, clock   per lane; they hold at this rate only
                 supply            nameplate (`supply_per_min`): every machine
                                   at 100%, what the belt must fit
                 flow              the lanes' output at their clocks
                 downstream        in-scope draw by other lines
                 storage           the paced storage rate
                 other             flow - downstream - storage. On a goal
                                   line it is the goal delivery; the view does
                                   not attribute it, and the goal table beside
                                   the rows states the goal rates
                 raw               out-of-scope inputs (a node: ore, coal,
                                   limestone), per item in discovery order
    goals      the run's projected goals, as returned

Guardrails, asserted from the source in `tests/test_rate_sheet.py`:

    R1  calls no layer and no `dataclasses.replace`; imports no goal_run,
        progression, backend or realize
    R2  no min, max, sorted, sort or round; rows keep the report's order
    R3  a row's bus IS the report's object; no field of a row is a bool
    R4  no scale: `sheet` takes no rate or factor, and nothing in the module
        multiplies a report rate

Location: `tools/` root beside `storage_view.py`, for the same reason (C7).
"""
from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass

REPO = pathlib.Path(__file__).resolve().parents[1]
for _src in ("production_adapter", "realization"):
    _path = str(REPO / "tools" / _src / "src")
    if _path not in sys.path:
        sys.path.insert(0, _path)

from production_adapter.contracts import ItemId, ProducerClass  # noqa: E402
from realization import Bus, RealizationReport  # noqa: E402


class RateSheetError(ValueError):
    """The view declines rather than printing a sheet it cannot label."""


@dataclass(frozen=True)
class LaneClock:
    producer_class: ProducerClass
    machines: int
    clock_percent: float


@dataclass(frozen=True)
class RateRow:
    """One bus, per minute, at the run's rate."""

    bus: Bus
    lanes: tuple[LaneClock, ...]
    supply_per_min: float
    flow_per_min: float
    downstream_per_min: float
    storage_per_min: float
    other_per_min: float
    #: (item, rate/min) drawn from outside the partition, discovery order
    raw: tuple[tuple[ItemId, float], ...]


@dataclass(frozen=True)
class RateSheet:
    phase: str
    anchor_goal_id: str
    #: READ from the anchor goal of the run. The sheet holds at this rate only
    anchor_rate_per_min: float
    horizon_min: float
    total_power_mw: float
    goals: tuple
    rows: tuple[RateRow, ...]


def sheet(
    report: RealizationReport,
    goals: tuple,
    *,
    phase: str,
    anchor_goal_id: str,
    horizon_min: float,
) -> RateSheet:
    """One row per bus, in the report's order.

    `goals` is the run's `ProjectedGoal`s as returned (`paced.goals`).
    REFUSED: a non-positive horizon; an anchor that names no goal.
    """
    if horizon_min <= 0:
        raise RateSheetError(f"a horizon must be positive, got {horizon_min}")
    anchor = [g for g in goals if g.goal_id == anchor_goal_id]
    if not anchor:
        raise RateSheetError(
            f"the anchor {anchor_goal_id!r} names no goal of the run. The sheet is "
            "labelled by the rate it was run at, read from that goal."
        )

    rows: list[RateRow] = []
    for bus in report.buses:
        flow = sum(lane.output_rate_per_min for lane in bus.lanes)
        raw: dict[ItemId, float] = {}
        for lane in bus.lanes:
            for i in lane.inputs:
                if i.source_bus_id is None:
                    raw[i.item_id] = raw.get(i.item_id, 0.0) + i.rate_per_min
        rows.append(RateRow(
            bus=bus,
            lanes=tuple(LaneClock(l.producer_class, l.machines, l.clock_percent)
                        for l in bus.lanes),
            supply_per_min=bus.supply_per_min,
            flow_per_min=flow,
            downstream_per_min=bus.automated_demand_per_min,
            storage_per_min=bus.storage_per_min,
            other_per_min=flow - bus.automated_demand_per_min - bus.storage_per_min,
            raw=tuple(raw.items()),
        ))
    return RateSheet(
        phase=phase,
        anchor_goal_id=anchor_goal_id,
        anchor_rate_per_min=anchor[0].rate_per_min,
        horizon_min=horizon_min,
        total_power_mw=report.total_power_mw,
        goals=tuple(goals),
        rows=tuple(rows),
    )


def _short(item_id: str) -> str:
    return item_id.removeprefix("Desc_").removesuffix("_C")


def render(s: RateSheet) -> str:
    """Plain text. Figures to 3 places by format only; the sheet holds full floats."""
    out = [
        f"RATE SHEET  {s.phase}",
        f"  at anchor {s.anchor_goal_id} = {s.anchor_rate_per_min:.3f}/min"
        f"  (holds at this rate only; another rate is another run)",
        f"  T = {s.horizon_min:.1f} min   power {s.total_power_mw:.2f} MW",
        "",
        "  goals",
    ]
    for g in s.goals:
        out.append(f"    {_short(g.item_id):28s} {g.rate_per_min:9.3f}/min"
                   f"  total {g.total_required:9.1f}  in {g.minutes_to_complete:9.1f} min")
    out += ["", f"  {'bus':26s} {'machines @ clock':28s} {'supply':>8s} {'flow':>9s}"
                f" {'downstr':>9s} {'storage':>9s} {'other':>9s}  raw"]
    for r in s.rows:
        clocks = ", ".join(f"{l.machines}x{_short(l.producer_class.removeprefix('Build_'))}"
                           f"@{l.clock_percent:.1f}%" for l in r.lanes)
        raw = ", ".join(f"{_short(i)} {q:.3f}" for i, q in r.raw)
        out.append(f"  {r.bus.bus_id:26s} {clocks:28s} {r.supply_per_min:8.2f}"
                   f" {r.flow_per_min:9.3f} {r.downstream_per_min:9.3f}"
                   f" {r.storage_per_min:9.3f} {r.other_per_min:9.3f}  {raw}")
    return "\n".join(out)
