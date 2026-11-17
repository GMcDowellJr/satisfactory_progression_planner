"""By-products: what a plan makes and nothing consumes, and where it goes.

Site-planner reframe A16, decided by Greg 2026-11-17: "By products can be sent
to AWESOME sink by default for now but should participate in production when
available and appropriate to supply." That sharpens reframe A8.3 ("by-products
are used, not free overflow"; mechanism open in A8.5).

Two halves:

- Participate: the solve already lets a by-product feed any owned recipe that
  consumes it, when that serves its objective. Reframe A8.2 measured Polymer
  Resin going to Residual Plastic once Water was available. Nothing changes
  here.
- Default disposal: what is still left over is reported with a disposition:

      sink              a solid, and the playthrough owns the AWESOME Sink
                        (sink points per minute from items.csv)
      sink_not_unlocked a solid, before the sink's milestone
      fluid_no_sink     a liquid or gas: the sink takes solids only. Packaging
                        it, or a consumer, is not modelled (open, A16)

A report, not a constraint. The solve still runs with unconsumed output FREE
(LP D1 stopgap), so a fluid by-product with nowhere to go does not make a plan
infeasible; it is named here instead. Sink power is not in the reference
layer and is not charged.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

from production_adapter.contracts import ItemFlow, ItemId
from production_adapter.gamedata import ReferenceData, load_sink_points

from .playthrough import PlaythroughState
from .unlocks import buildings_unlocked

SINK_BUILDING = "Desc_ResourceSink_C"
SINK = "sink"
SINK_NOT_UNLOCKED = "sink_not_unlocked"
FLUID_NO_SINK = "fluid_no_sink"

_TOL = 1e-6


@dataclass(frozen=True)
class Byproduct:
    item_id: ItemId
    rate_per_min: float
    disposition: str
    sink_points_per_min: float | None   # set only when disposition is SINK


def sink_unlocked(repo_root: str | pathlib.Path, state: PlaythroughState) -> bool:
    owned = state.owned_schematics
    open_buildings, _ = buildings_unlocked(repo_root, lambda s: s.schematic_id in owned)
    return SINK_BUILDING in open_buildings


def ledger(
    repo_root: str | pathlib.Path,
    data: ReferenceData,
    state: PlaythroughState,
    items: tuple[ItemFlow, ...],
    delivered: dict[ItemId, float],
) -> tuple[Byproduct, ...]:
    """Every item a plan makes beyond what it consumes and delivers, with its
    disposition. `items` are the plan's flows; `delivered` its outputs per
    minute (goal mix or targets)."""
    points = load_sink_points(repo_root)
    can_sink = sink_unlocked(repo_root, state)
    out = []
    for f in items:
        left = f.produced_per_min - f.consumed_per_min - delivered.get(f.item_id, 0.0)
        if left <= _TOL:
            continue
        if data.items[f.item_id].form != "solid":
            out.append(Byproduct(f.item_id, left, FLUID_NO_SINK, None))
        elif can_sink:
            out.append(Byproduct(f.item_id, left, SINK, left * points.get(f.item_id, 0)))
        else:
            out.append(Byproduct(f.item_id, left, SINK_NOT_UNLOCKED, None))
    return tuple(sorted(out, key=lambda b: b.item_id))
