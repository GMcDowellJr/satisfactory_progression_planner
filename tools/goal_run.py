#!/usr/bin/env python3
"""The goal run: every layer once, in order, and each layer's answer side by side.

Phase 2 deliverable 5, first cut. Design note 2026-09-23 (O1-O4 accepted by Greg
the same day). Replaces `scratchpad/first50_run.py`.

    solve -> realize(declared lines) -> project_goals -> stock.bill_for

**It adds no arithmetic.** Every number in `GoalRunReport` is an object a layer
returned, carried unaltered — asserted by identity in the tests. The only value
computed here is `machines`, the realization's lane machines summed per producer
class, and that is a regrouping of counts the declaration already determined (O1).

**It cannot choose, and that is the guardrail.** The target, the recipe set, the
partition and the stock declaration are all handed in. The module contains no call
that builds a `SolveRequest`, `OutputTarget`, `BusDeclaration` or `SourceEdge`, so
it cannot become a planner by drift. Asserted by inspection in
`tests/test_goal_run.py`, alongside:

    once       each layer is called at exactly one site, and no call sits in a
               loop. The bill is NOT fed back into a line's `withdrawal_bill` in
               the same run (O2) — that second realization is A5's loop, the
               machines that build the machines. A caller who wants a bill-sized
               line runs again with the bill attached, visibly
    unranked   no min, max or sort anywhere. Goals and buses keep caller order,
               and the binding goal is left to the reader (O3) until D2 gives the
               goal build a meaning for T

**`paced_run` (A13, D2)** composes `run` twice with the scheduler between, so
that `run` itself stays single-pass:

    floor    every line storage OFF -> the smallest build that meets usage ->
             a bill over those machines
    pace     each storing line's rate = its item's bill / T
             (`progression.schedule`)
    paced    storing lines clocked to that rate -> the reported build

The paced demand is usage plus a non-negative rate, so every paced line has at
least the floor's machines, and a bill summed over the floor is a FLOOR of the
paced build's. That is enough, by Greg's standing position that a floor
suffices, and it is why there is no third pass. Asserted: two `run` calls, and
neither sits in a loop.

Location. Like `production_cli.py`, this is a joint above three packages, so it
lives at `tools/` root and sets up `sys.path` itself; none of the packages may
import upward to hold it.
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys
from dataclasses import dataclass

REPO = pathlib.Path(__file__).resolve().parents[1]
for _src in ("production_adapter", "progression", "realization"):
    _path = str(REPO / "tools" / _src / "src")
    if _path not in sys.path:
        sys.path.insert(0, _path)

from production_adapter import ReferenceData, SolveRequest, SolveResponse  # noqa: E402
from production_adapter.contracts import ItemId, ProducerClass  # noqa: E402
from production_adapter.gamedata import ConstructionData  # noqa: E402
from progression import schedule, stock  # noqa: E402
from progression.unlocks import SchematicId  # noqa: E402
from realization import (  # noqa: E402
    Capability, ExtractionRate, ProjectedGoal, RealizationReport,
    RealizationRequest, project_goals, realize,
)

#: (goal_id, item_id, total) — `project_goals`' own input shape, passed through.
Goal = tuple[str, ItemId, float]


@dataclass(frozen=True)
class StockDeclaration:
    """Everything `stock.bill_for` takes except the machine counts.

    The counts are the one input the run supplies itself (O1). The rest is the
    caller's declaration and crosses unaltered, including the pairing rules
    `bill_for` enforces — unlocks with their costs, phases with their table.
    """

    bootstrap: stock.BootstrapSet
    unlocks: tuple[SchematicId, ...] | None = None
    unlock_costs: dict[SchematicId, tuple[tuple[ItemId, float], ...]] | None = None
    project_assembly: tuple[stock.ProjectAssemblyRequirement, ...] | None = None
    phases: tuple[int, ...] | None = None


@dataclass(frozen=True)
class GoalRunReport:
    """Each layer's answer, as it was returned. Nothing restated, nothing ranked.

    `machines` is the set the bill was summed over, so a reader can see that the
    stock pass costed THIS build and not some other. It is in discovery order
    (bus order, then lane order), not sorted.

    The bill is a floor for the same reasons `stock` gives, plus one this run
    adds: it is summed over the realized lines only, so a build-material line
    the caller has not yet declared contributes no machines of its own.
    """

    data: ReferenceData
    solve: SolveResponse
    realization: RealizationReport
    goals: tuple[ProjectedGoal, ...]
    machines: tuple[tuple[ProducerClass, int], ...]
    stock: stock.StockPass


def machines_of(report: RealizationReport) -> tuple[tuple[ProducerClass, int], ...]:
    """Lane machines summed per producer class, in discovery order.

    A regrouping, not a count: every machine here is one the declaration already
    put on a lane. A lane with no machines contributes nothing and is not listed,
    because `BootstrapSet` treats a declared zero as an error and the same shape
    should not carry one here.
    """
    counts: dict[ProducerClass, int] = {}
    for bus in report.buses:
        for lane in bus.lanes:
            if lane.machines:
                counts[lane.producer_class] = counts.get(lane.producer_class, 0) + lane.machines
    return tuple(counts.items())


def goals_for_phases(
    data: ReferenceData,
    requirements: tuple[stock.ProjectAssemblyRequirement, ...],
    phases: tuple[int, ...],
) -> tuple[Goal, ...]:
    """Goal triples from the Project Assembly table, for the declared phases (O4).

    Optional: `run` takes goals as handed in, and this is a convenience a caller
    may use to build them. Scaled by the scenario's Project Assembly multiplier
    through the same `apply_project_assembly_quantity` the stock pass uses, so a
    goal and the bill's delivery term cannot disagree on a quantity.

    One goal per table row, in table order. A phase that asks for an item twice
    would give two goals; the shipped table has no such phase.
    """
    wanted = set(phases)
    return tuple(
        (
            f"phase {r.phase} {r.phase_name}: {r.item_id}",
            r.item_id,
            data.scenario.apply_project_assembly_quantity(r.quantity_1x),
        )
        for r in requirements
        if r.phase in wanted
    )


def run(
    *,
    data: ReferenceData,
    backend,
    solve: SolveRequest,
    logistics: tuple[tuple[Capability, ...], tuple[ExtractionRate, ...]],
    realization: RealizationRequest,
    goals: tuple[Goal, ...],
    construction: ConstructionData,
    declared_stock: StockDeclaration,
) -> GoalRunReport:
    """One goal run. Each layer once; nothing chosen here.

    `backend` is anything with the adapter's `solve(request, data)`. It is handed
    in so the power statistic, and any other solver setting, stays the caller's.
    `logistics` is `load_logistics`' return, unpacked for `realize`.

    Raises whatever a layer raises. A refusal from any layer is the run's answer,
    not something to catch and approximate.
    """
    capabilities, extraction = logistics
    response = backend.solve(solve, data)
    report = realize(response, data, capabilities, extraction, realization)
    projected = project_goals(report.buses, goals)
    machines = machines_of(report)
    bill = stock.bill_for(
        data,
        construction,
        bootstrap=declared_stock.bootstrap,
        machines=machines,
        unlocks=declared_stock.unlocks,
        unlock_costs=declared_stock.unlock_costs,
        project_assembly=declared_stock.project_assembly,
        phases=declared_stock.phases,
    )
    return GoalRunReport(
        data=data,
        solve=response,
        realization=report,
        goals=projected,
        machines=machines,
        stock=bill,
    )


class PacedRunError(ValueError):
    """A paced run declines rather than pacing something twice."""


@dataclass(frozen=True)
class PacedRunReport:
    """Both passes, the horizon, and the rates the second was paced to.

    `floor` is the storage-off build the bill was summed over; `paced` is the
    build that bill paces. Side by side so the gap between them is visible:
    that gap is what keeps the bill a floor.
    """

    horizon_min: float
    storage_rates: dict[ItemId, float]
    floor: GoalRunReport
    paced: GoalRunReport


def paced_run(
    *,
    data: ReferenceData,
    backend,
    solve: SolveRequest,
    logistics: tuple[tuple[Capability, ...], tuple[ExtractionRate, ...]],
    realization: RealizationRequest,
    goals: tuple[Goal, ...],
    construction: ConstructionData,
    declared_stock: StockDeclaration,
    horizon_min: float,
) -> PacedRunReport:
    """A13 (D2). The floor pass, the rates, the paced pass. Nothing chosen here.

    `horizon_min` is T. `schedule.horizon_from_anchor` is the default
    derivation, and an override is just a different number passed here.

    REFUSED, before anything runs:

        a Project Assembly term in `declared_stock`   the goal item reaches its
            line as the solve's target already, and pacing the delivery term
            too counts it twice: 1/min + 50/50 = 2/min (P1)
        two STORING buses of one item   the item's bill would pace both, which
            doubles it. Which line stores is the caller's declaration

    Which unlocks are paced is the caller's too: `declared_stock.unlocks` is
    the set THIS stage buys (P1), not the cumulative tier set.

    A storing line whose item has no bill is paced to 0.0. It clocks to usage
    and reports `stores_nothing` (P5).
    """
    if declared_stock.project_assembly is not None or declared_stock.phases is not None:
        raise PacedRunError(
            "a paced run excludes the Project Assembly term (P1). The goal item "
            "reaches its line as the solve's target, and pacing its delivery "
            "as well counts it twice."
        )
    storing_items = [b.item_id for b in realization.buses if b.stores]
    if len(storing_items) != len(set(storing_items)):
        raise PacedRunError(
            "two storing buses carry one item, so its bill would pace both. "
            "Declare which one stores."
        )

    floor_request = dataclasses.replace(
        realization,
        buses=tuple(dataclasses.replace(b, stores=False) for b in realization.buses),
    )
    common = dict(
        data=data, backend=backend, solve=solve, logistics=logistics,
        goals=goals, construction=construction, declared_stock=declared_stock,
    )
    floor = run(realization=floor_request, **common)

    rates = schedule.storage_rates(floor.stock.bills, horizon_min)
    paced_request = dataclasses.replace(
        realization,
        buses=tuple(
            dataclasses.replace(b, storage_per_min=rates.get(b.item_id, 0.0))
            if b.stores else b
            for b in realization.buses
        ),
    )
    paced = run(realization=paced_request, **common)

    return PacedRunReport(
        horizon_min=horizon_min,
        storage_rates=rates,
        floor=floor,
        paced=paced,
    )
