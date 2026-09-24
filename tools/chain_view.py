#!/usr/bin/env python3
"""The per-chain view: a realized build, grouped by chains the caller declares.

Greg, 2026-09-23 (after D3). A VIEW ONLY. It reads a `RealizationReport` and
regroups what is already there; no machine count, clock, rate or residual moves,
and nothing here can make one move — it calls no layer.

    chain     a caller-declared tuple of bus ids, e.g. ingot -> plate -> RIP.
              Membership is by BUS ID and never by item: grouping by item
              re-merges buses the caller declared apart (`realization.Bus`)
    overlap   ALLOWED. A bus may sit in several chains (RIP feeds both the
              plate chain and the rod chain). Each chain's totals include it,
              so chain totals do NOT add up to the build; the build total is
              read from the report once and printed on its own line, and every
              shared bus is named
    belts     PER BELT, never summed across items. Each bus shows its FLOW
              (its lanes' output at their clocks: the average the belt
              carries) beside its NAMEPLATE (`supply_per_min`: what it carries
              while every machine runs, which is what a belt must fit under
              BACK_UP, A5.2). No belt Mk is chosen here. What the chain
              draws from outside it is listed per (item, source bus): the feed
              a separately built chain would actually need
    paced     `render_paced` puts the floor and paced builds side by side, so
              the chains the pacing grew are visible

Buses in no chain are listed as `(unchained)` rather than dropped: absence from
the view must not read as absence from the build.

Guardrails, asserted from the source in `tests/test_chain_view.py`:

    V1  calls no layer: no realize, solve, run, paced_run, bill_for, and no
        `dataclasses.replace`. It cannot size anything because it cannot ask
        anything to be sized
    V2  no min, max, sorted or sort. Chains keep caller order, buses keep the
        chain's declared order, boundary draws keep discovery order
    V3  the bus objects in a view ARE the report's (identity)

Location: `tools/` root beside `goal_run.py`. It imports `realization` types
only, and nothing from `goal_run`, so a caller passes
`paced.floor.realization` and `paced.paced.realization` in.
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
from production_adapter.gamedata import ReferenceData  # noqa: E402
from realization import Bus, BusId, RealizationReport  # noqa: E402

UNCHAINED = "(unchained)"


class ChainViewError(ValueError):
    """A chain declaration the view declines rather than guesses at."""


@dataclass(frozen=True)
class Chain:
    """Caller-declared. Bus order is the order the view prints them in."""

    chain_id: str
    bus_ids: tuple[BusId, ...]


@dataclass(frozen=True)
class BoundaryDraw:
    """What a chain draws on one item from one source outside it.

    `source_bus_id` None is out of scope (raw ore, or an input no declared bus
    carries), exactly as `LaneInput` states it. The rate is the lane inputs'
    rates summed for that (item, source) pair: one feed, so the sum is a real
    flow and not a mixture of items.
    """

    item_id: ItemId
    source_bus_id: BusId | None
    rate_per_min: float


@dataclass(frozen=True)
class ChainView:
    chain_id: str
    #: The report's own `Bus` objects, in the chain's declared order (V3).
    buses: tuple[Bus, ...]
    #: Lane machines per producer class, discovery order. A regrouping.
    machines: tuple[tuple[ProducerClass, int], ...]
    boundary: tuple[BoundaryDraw, ...]

    @property
    def total_machines(self) -> int:
        return sum(n for _, n in self.machines)


@dataclass(frozen=True)
class BuildView:
    chains: tuple[ChainView, ...]
    #: Buses in no chain; None when every bus is in one.
    unchained: ChainView | None
    #: Buses in more than one chain, in report order. Non-empty means the
    #: chain totals double-count them and do not add up to the build.
    shared: tuple[BusId, ...]
    #: Read from the report, never from the chains.
    build_machines: int


def _check(report: RealizationReport, chains: tuple[Chain, ...]) -> None:
    known = {b.bus_id for b in report.buses}
    seen_ids: set[str] = set()
    for c in chains:
        if c.chain_id == UNCHAINED:
            raise ChainViewError(f"{UNCHAINED!r} is the view's own group name")
        if c.chain_id in seen_ids:
            raise ChainViewError(f"chain {c.chain_id!r} is declared twice")
        seen_ids.add(c.chain_id)
        if not c.bus_ids:
            raise ChainViewError(f"chain {c.chain_id!r} names no bus")
        if len(set(c.bus_ids)) != len(c.bus_ids):
            raise ChainViewError(f"chain {c.chain_id!r} names a bus twice")
        unknown = [b for b in c.bus_ids if b not in known]
        if unknown:
            raise ChainViewError(
                f"chain {c.chain_id!r} names {unknown}, which the report does "
                f"not hold. Membership is by bus id, not item"
            )


def _chain_view(chain_id: str, buses: tuple[Bus, ...]) -> ChainView:
    members = {b.bus_id for b in buses}
    counts: dict[ProducerClass, int] = {}
    draws: dict[tuple[ItemId, BusId | None], float] = {}
    for bus in buses:
        for lane in bus.lanes:
            if lane.machines:
                counts[lane.producer_class] = counts.get(lane.producer_class, 0) + lane.machines
            for i in lane.inputs:
                if i.source_bus_id in members:
                    continue
                key = (i.item_id, i.source_bus_id)
                draws[key] = draws.get(key, 0.0) + i.rate_per_min
    return ChainView(
        chain_id=chain_id,
        buses=buses,
        machines=tuple(counts.items()),
        boundary=tuple(BoundaryDraw(item, src, rate) for (item, src), rate in draws.items()),
    )


def view(report: RealizationReport, chains: tuple[Chain, ...]) -> BuildView:
    """Group `report`'s buses by the declared chains. Refuses, never repairs."""
    _check(report, chains)
    by_id = {b.bus_id: b for b in report.buses}
    membership: dict[BusId, int] = {}
    for c in chains:
        for b in c.bus_ids:
            membership[b] = membership.get(b, 0) + 1
    unchained = tuple(b for b in report.buses if b.bus_id not in membership)
    return BuildView(
        chains=tuple(
            _chain_view(c.chain_id, tuple(by_id[b] for b in c.bus_ids)) for c in chains
        ),
        unchained=_chain_view(UNCHAINED, unchained) if unchained else None,
        shared=tuple(b.bus_id for b in report.buses if membership.get(b.bus_id, 0) > 1),
        build_machines=sum(b.machines for b in report.buses),
    )


def _name(data: ReferenceData, item_id: ItemId) -> str:
    return data.items[item_id].display_name if item_id in data.items else item_id


def flow_of(bus: Bus) -> float:
    """The bus's lanes' output at their clocks. A regrouping of lane figures:
    automated demand plus storage plus withdrawal on a PACED or MATCHED line,
    usage on a BACK_UP one."""
    return sum(l.output_rate_per_min for l in bus.lanes)


def _groups(v: BuildView) -> tuple[ChainView, ...]:
    return v.chains + ((v.unchained,) if v.unchained is not None else ())


def _footer(v: BuildView) -> list[str]:
    lines = [f"build total {v.build_machines} machines (read from the report)"]
    if v.shared:
        lines.append(
            f"shared buses, counted in every chain holding them: {', '.join(v.shared)}. "
            f"Chain totals do not add up to the build"
        )
    return lines


def render(v: BuildView, data: ReferenceData, *, title: str = "chains") -> str:
    lines = ["=" * 78, title]
    for c in _groups(v):
        mix = " ".join(f"{p.removeprefix('Build_').removesuffix('_C')} {n}" for p, n in c.machines)
        lines.append(f"chain {c.chain_id}   machines {c.total_machines}   ({mix})")
        lines.append(f'    {"bus":18s}{"item":26s}{"flow/min":>10s}{"nameplate":>11s}{"mach":>6s}')
        for b in c.buses:
            lines.append(
                f"    {b.bus_id:18s}{_name(data, b.item_id):26s}"
                f"{flow_of(b):10.2f}{b.supply_per_min:11.2f}{b.machines:6d}"
            )
        lines.append("    draws from outside")
        for d in c.boundary:
            src = d.source_bus_id or "out of scope"
            lines.append(f"      {_name(data, d.item_id):26s}{src:18s}{d.rate_per_min:9.2f}/min")
    lines.extend(_footer(v))
    return "\n".join(lines)


def render_paced(
    floor: BuildView, paced: BuildView, data: ReferenceData, *, title: str = "chains, floor | paced"
) -> str:
    """Floor and paced side by side. Both views must hold the same chains and
    buses: the paced pass only changes storage rates, so a difference in shape
    means the two views were not built from one run."""
    fg, pg = _groups(floor), _groups(paced)
    if [(c.chain_id, [b.bus_id for b in c.buses]) for c in fg] != [
        (c.chain_id, [b.bus_id for b in c.buses]) for c in pg
    ]:
        raise ChainViewError("floor and paced views differ in chains or buses")
    lines = ["=" * 100, title]
    for fc, pc in zip(fg, pg):
        lines.append(
            f"chain {fc.chain_id}   machines {fc.total_machines} | {pc.total_machines}"
        )
        lines.append(
            f'    {"bus":18s}{"item":26s}{"flow/min":>20s}{"nameplate":>20s}{"mach":>10s}'
        )
        for fb, pb in zip(fc.buses, pc.buses):
            lines.append(
                f"    {fb.bus_id:18s}{_name(data, fb.item_id):26s}"
                f"{flow_of(fb):10.2f} |{flow_of(pb):8.2f}"
                f"{fb.supply_per_min:10.2f} |{pb.supply_per_min:8.2f}"
                f"{fb.machines:5d} |{pb.machines:3d}"
            )
        lines.append("    draws from outside")
        pd = {(d.item_id, d.source_bus_id): d.rate_per_min for d in pc.boundary}
        fd = {(d.item_id, d.source_bus_id): d.rate_per_min for d in fc.boundary}
        keys = list(fd) + [k for k in pd if k not in fd]
        for item, src in keys:
            lines.append(
                f"      {_name(data, item):26s}{(src or 'out of scope'):18s}"
                f"{fd.get((item, src), 0.0):9.2f} |{pd.get((item, src), 0.0):9.2f}/min"
            )
    lines.append(
        f"build total {floor.build_machines} | {paced.build_machines} machines "
        f"(read from the reports)"
    )
    shared = floor.shared or paced.shared
    if shared:
        lines.append(
            f"shared buses, counted in every chain holding them: {', '.join(shared)}. "
            f"Chain totals do not add up to the build"
        )
    return "\n".join(lines)
