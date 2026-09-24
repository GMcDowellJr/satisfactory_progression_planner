#!/usr/bin/env python3
"""The storage-fill view: what a paced build puts into storage over T. REPORTED.

D4 P7, crossover record amendment 15, against A7.3. A VIEW ONLY, like
`chain_view`: it reads a `RealizationReport` and a horizon and sizes nothing.

    fill       a paced storing line's `storage_per_min` x T: the units it puts
               into storage by the end of the stage. On a paced line this is
               the item's owed bill by construction, so the view is a check on
               where that bill will sit, not a new quantity
    capacity   A7.3: slots x cached_stack_size(item). Canonical and
               scenario-invariant. The stack size is read from items.csv, the
               sole resource authority. The slot count is DECLARED by the
               caller per bus, with its container count; the two A7.3 figures
               are exposed as constants for convenience, nothing more
    reported   minutes to fill the declared capacity (inf for a line storing
               nothing, A7.3's "never"), and fill as a fraction of it. No
               verdict: a fraction over 1.0 is a number, not a refusal

"Storage fills quickly" (Greg's standing observation) is this formula at the
phase-span T: a stage of hundreds of minutes multiplies every rate.

Guardrails, asserted from the source in `tests/test_storage_view.py`:

    S1  calls no layer and no `dataclasses.replace`; imports no goal_run,
        progression, backend or realize
    S2  no min, max, sorted, sort or round; buses keep the report's order
    S3  a row's bus IS the report's object; no field of a row is a bool

Location: `tools/` root beside `chain_view.py`, for the same reason (C7).
"""
from __future__ import annotations

import csv
import math
import pathlib
import sys
from dataclasses import dataclass

REPO = pathlib.Path(__file__).resolve().parents[1]
for _src in ("production_adapter", "realization"):
    _path = str(REPO / "tools" / _src / "src")
    if _path not in sys.path:
        sys.path.insert(0, _path)

from production_adapter.contracts import ItemId  # noqa: E402
from realization import Bus, BusId, RealizationReport  # noqa: E402

#: A7.3, stated by Greg: slots per container. Convenience only; the caller
#: declares which one a bus stores into.
STORAGE_CONTAINER_SLOTS = 24
INDUSTRIAL_STORAGE_CONTAINER_SLOTS = 48


class StorageViewError(ValueError):
    """The view declines rather than showing a capacity it cannot read."""


@dataclass(frozen=True)
class Containers:
    """What a bus stores into: `count` containers of `slots` slots. DECLARED."""

    slots: int
    count: int

    def __post_init__(self) -> None:
        if self.slots <= 0 or self.count <= 0:
            raise ValueError(
                "a container declaration has positive slots and count. A bus "
                "with no storage is left out, not declared as zero."
            )


@dataclass(frozen=True)
class StorageFill:
    """One bus's fill over T. Capacity fields are None when none was declared."""

    bus: Bus
    rate_per_min: float
    fill_units: float
    stack_size: int
    containers: Containers | None
    capacity_units: float | None
    minutes_to_fill: float | None
    fill_of_capacity: float | None


@dataclass(frozen=True)
class StorageView:
    horizon_min: float
    rows: tuple[StorageFill, ...]


def stack_sizes(repo_root: str | pathlib.Path = REPO) -> dict[ItemId, int]:
    """`cached_stack_size` per item, from items.csv."""
    path = pathlib.Path(repo_root) / "planning_data" / "game" / "reference" / "items.csv"
    with path.open(encoding="utf-8") as fh:
        return {
            r["item_id"]: int(r["cached_stack_size"])
            for r in csv.DictReader(fh) if r["cached_stack_size"]
        }


def view(
    report: RealizationReport,
    horizon_min: float,
    *,
    containers: dict[BusId, Containers] | None = None,
    stacks: dict[ItemId, int] | None = None,
) -> StorageView:
    """One row per bus, in the report's order. A bus storing nothing fills 0.

    A container declared for a bus the report does not hold is refused: a
    declaration that names nothing would read as covered.
    """
    if horizon_min <= 0:
        raise StorageViewError(f"a horizon must be positive, got {horizon_min}")
    stacks = stack_sizes() if stacks is None else stacks
    declared = dict(containers or {})
    ids = {b.bus_id for b in report.buses}
    unknown = [bus_id for bus_id in declared if bus_id not in ids]
    if unknown:
        raise StorageViewError(f"containers declared for buses not in the report: {unknown}")

    rows: list[StorageFill] = []
    for bus in report.buses:
        if bus.item_id not in stacks:
            raise StorageViewError(f"{bus.item_id}: no stack size in items.csv")
        rate = bus.storage_per_min
        stack = stacks[bus.item_id]
        c = declared.get(bus.bus_id)
        if c is None:
            capacity = minutes = fraction = None
        else:
            capacity = float(c.slots * stack * c.count)
            minutes = capacity / rate if rate > 0 else math.inf
            fraction = rate * horizon_min / capacity
        rows.append(StorageFill(
            bus=bus, rate_per_min=rate, fill_units=rate * horizon_min,
            stack_size=stack, containers=c, capacity_units=capacity,
            minutes_to_fill=minutes, fill_of_capacity=fraction,
        ))
    return StorageView(horizon_min=horizon_min, rows=tuple(rows))
