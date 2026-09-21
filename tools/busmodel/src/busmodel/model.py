"""Bus-level recompute, against `production_adapter.gamedata`.

This is the ORACLE. It exists so that every figure the bus records publish can
be recomputed from the repo rather than recovered from a document, and so the
realization layer's bodies have something to be checked against that is not
themselves.

It replaces `scratchpad/recompute_model/`, which produced every published
figure and could not be committed: it read `recipes.csv` / `recipe_io.csv` /
`recipe_producers.csv` directly, and `gamedata.py` holds the locked claim to be
the only place in the repo that knows CSV column names. Nothing here opens a
file. Reference data arrives as `ReferenceData` and recipes are keyed by
`recipe_id`, never matched by `display_name` — storage review 6.3 records a
display-name lookup raising on `Turbo Rifle Ammo`, which is duplicated in the
shipped data.

Import boundary, exclusion form, asserted by `tests/test_import_boundary.py`:

    PERMITTED   production_adapter.contracts    types only
                production_adapter.gamedata     reference data, read-only
                production_adapter.scenario     the multiplier and its rounding
                realization.contracts           `Disposition` ONLY — the four
                                                state names live in one place
                                                or they drift
    FORBIDDEN   production_adapter.backend, .lp_backend, .analysis
                realization.buses, .residual, .realize   the code this checks
                scipy, at any depth

An oracle that could reach the solver, or the bodies it validates, is not an
oracle.

THE PRIMITIVE IS (item, producers, consumers, PARTITION), and the partition is
DECLARED. See `bus_level_recompute_and_alternate_crossover.md` amendment 3: the
same item may run on several unconnected buses by choice, and their residuals
do not pool. `BusSpec.sources` is where that lives — each bus names, per input
item, WHICH bus it draws that input from.

TWO RECOVERED RULES, both load-bearing and neither stated by the documents this
reproduces (crossover record section 1):

    external demand = 0        storage review section 9 says "external demand
                               held constant across scenarios". It was constant
                               at ZERO, which is not what the sentence conveys.
    machine floor = 1          every declared line gets a machine floor. This is
                               what gives Cable 30.00/min and Concrete 15.00/min
                               of overflow against zero automated demand.

Both are named options here rather than compiled into the arithmetic, so that a
figure computed under them says so.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from production_adapter.contracts import ItemId, ProducerClass, RecipeId
from production_adapter.gamedata import ReferenceData
from realization.contracts import Disposition

BusId = str

#: Comparison tolerance for "is this demand already an exact multiple of the
#: machine rate". Without it `ceil(199.99999999/40)` and `ceil(200.0/40)` differ
#: on a figure the game states as exact.
EPS = 1e-9


class BusModelError(RuntimeError):
    """The model declines rather than emitting a figure it cannot stand behind."""


class BusNotDeclared(BusModelError):
    """A source edge names a bus the declaration does not contain.

    Raised rather than defaulted. Under a declared partition, defaulting an
    unknown bus into existence re-merges exactly what the caller split.
    """


class CreditedFlowCycle(BusModelError):
    """A bus transitively draws on itself.

    The demand pass is a single reverse-topological traversal and is not
    iterated toward a fixed point. On a cycle the map is non-monotone and no
    termination argument is available.
    """


class DispositionUnavailable(BusModelError):
    """A declared steady state needs reference data the layer does not have.

    SUNK requires the AWESOME Sink, absent from the reference layer. Refused by
    name rather than silently downgraded to BACK_UP, which would misreport both
    the residual's fate and the power draw's stability.
    """


class SizingBasis(str, Enum):
    """Which of a consumer's two draw figures sizes the bus upstream of it.

    A BACK_UP line presents two different numbers to its source and both are
    real: it draws its nameplate rate while it runs and nothing while it is
    paused. Which one sizes the upstream bus is a modelling choice, and the
    documents this reproduces did not make it explicitly.

        AVERAGE   the mean draw. Every published table in the bus records was
                  computed on this basis, so it is the default.
        PEAK      the instantaneous draw the upstream bus must actually carry.
                  This is what amendment 4 argues from: a full-rate Iron Plate
                  build line presents 40/min of ingot draw, not its 4/min
                  average, and that is the difference between a residual of
                  6.00/min and one more smelter.

    Under WITHDRAWN the two coincide. Under MATCHED they also coincide, which is
    the state's whole point.
    """

    AVERAGE = "average"
    PEAK = "peak"


@dataclass(frozen=True)
class SourceEdge:
    """Which bus this bus draws one of its inputs from. DECLARATION.

    This is where the partition actually lives. Two buses of the same item are
    distinguishable only because their consumers name different sources: the
    Stitched Iron Plate line declares `SourceEdge("Desc_Wire_C", "wire_iron")`
    and the Cable line declares `SourceEdge("Desc_Wire_C", "wire_copper")`, and
    nothing in the solve says which is which.

    `source_bus_id=None` means the input is out of scope -- raw, or not
    modelled. Declared explicitly rather than by omission, so that an input
    nobody thought about is distinguishable from one deliberately left out.
    """

    input_item: ItemId
    source_bus_id: BusId | None


@dataclass(frozen=True)
class BusSpec:
    """What the caller states about ONE BUS. Keyed by `bus_id`, not by item.

    Item-keying is the one-bus-per-item assumption in type form: two Wire
    declarations under it are accepted and the second is silently unreachable.

    Two sizing bases, and the model must not conflate them:

        residual item        `withdrawal_per_min is None`. Sized from derived
                             demand: ceil(demand / rate) + extra_producers. R is
                             rounding leftover and may be exactly zero, which
                             for a dedicated intermediate is the design working
        build-material line  `withdrawal_per_min` is set, and it is that bus's
                             DEMAND -- not a figure compared against its
                             residual afterwards. This is what makes the basis
                             uniform: amendment 4.1 moves the build draw onto
                             its own bus, and a withdrawal that sits inside one
                             bus's demand sum and outside another's under one
                             verdict column is the defect that keeps A3.5 from
                             being a regression target.
    """

    bus_id: BusId
    item_id: ItemId
    recipe_id: RecipeId
    #: Which bus supplies each input. Declaration, never derivation.
    sources: tuple[SourceEdge, ...] = ()
    disposition: Disposition = Disposition.WITHDRAWN
    #: Producers beyond the ceil. Storage rate is a MACHINE COUNT, not a
    #: boolean: R(k) = ceil_residual + k * producer_rate, and on the screw bus
    #: the quantum is a full 40/min.
    extra_producers: int = 0
    #: Set on a build-material line. The basis is the section 8.2 geometric
    #: estimate, footprint-derived, declared by its author as a FLOOR (A3.3), so
    #: any coverage verdict against it is optimistic by an unmeasured amount.
    withdrawal_per_min: float | None = None
    #: Override `SizingBasis` for THIS bus's draw on its sources. `None` follows
    #: the solve's basis.
    #:
    #: It exists because the records contain two different BACK_UP behaviours
    #: and do not distinguish them. A2.2's BACK_UP is a production bus throttled
    #: by backpressure, idling at utilisation demand/supply, whose steady draw
    #: is its need -- that is the basis 19.02 and 15.79 were computed on. A4.2's
    #: BACK_UP is a build-material line that fills a container and PAUSES, whose
    #: draw oscillates between nameplate and zero and "must be sized against the
    #: peak". Both are correct about their own case.
    #:
    #: Set per bus rather than resolved by rule, because choosing the rule is
    #: A3.5-versus-A4.2 and that is not this package's to settle: A3.5 sizes
    #: Wire_copper against Cable's AVERAGE 9/min, while A4.2's argument applied
    #: to the same line would size it against Cable's 90/min nameplate and put
    #: four Constructors on that bus instead of one.
    presents_peak_draw: bool | None = None

    def __post_init__(self) -> None:
        if self.extra_producers < 0:
            raise ValueError(f"{self.bus_id}: extra_producers must be >= 0")
        if self.withdrawal_per_min is not None and self.withdrawal_per_min < 0:
            raise ValueError(f"{self.bus_id}: withdrawal_per_min must be >= 0")
        if (
            self.disposition is Disposition.MATCHED
            and self.withdrawal_per_min is None
        ):
            raise ValueError(
                f"{self.bus_id}: MATCHED without withdrawal_per_min has nothing "
                "to match. The state is defined as 'underclocked to the average "
                "withdrawal rate' (A4.2); without a rate there is no clock."
            )
        seen = [e.input_item for e in self.sources]
        if len(seen) != len(set(seen)):
            raise ValueError(f"{self.bus_id}: an input may name at most one source bus")

    @property
    def is_build_material_line(self) -> bool:
        return self.withdrawal_per_min is not None

    def source_of(self, input_item: ItemId) -> BusId | None:
        for e in self.sources:
            if e.input_item == input_item:
                return e.source_bus_id
        return None


@dataclass(frozen=True)
class Declaration:
    """A saved, named bus declaration and everything needed to solve it.

    `provenance` is not decoration. Every figure this package emits is quoted
    against a document, and a declaration whose source is not stated cannot be
    told apart from one reconstructed out of the output it is supposed to
    reproduce -- which is the specific trap the handoff names for this work.
    """

    name: str
    buses: tuple[BusSpec, ...]
    #: Root / out-of-scope demand per bus. The declaration root is the Space
    #: Elevator part rate: it is the game-pace dial, and `automated_demand` is
    #: derived in-scope draw, never declared (A2.1).
    external_per_min: Mapping[BusId, float] = field(default_factory=dict)
    provenance: str = ""

    def __post_init__(self) -> None:
        ids = [b.bus_id for b in self.buses]
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"duplicate bus_id: {dupes}")
        known = set(ids)
        for b in self.buses:
            for e in b.sources:
                if e.source_bus_id is not None and e.source_bus_id not in known:
                    raise BusNotDeclared(
                        f"{b.bus_id} draws {e.input_item} from {e.source_bus_id!r}, "
                        "which is not declared"
                    )
        for bus_id in self.external_per_min:
            if bus_id not in known:
                raise BusNotDeclared(f"external demand on undeclared bus {bus_id!r}")

    def bus(self, bus_id: BusId) -> BusSpec:
        for b in self.buses:
            if b.bus_id == bus_id:
                return b
        raise BusNotDeclared(bus_id)

    def buses_of_item(self, item_id: ItemId) -> tuple[BusSpec, ...]:
        """Every declared bus of one item. Length > 1 is ordinary, not an error."""
        return tuple(b for b in self.buses if b.item_id == item_id)

    def replace_recipe(self, bus_id: BusId, recipe_id: RecipeId,
                       sources: tuple[SourceEdge, ...]) -> "Declaration":
        """A copy with one bus re-wired. An alternate is a RE-WIRING event, not
        only a cheaper recipe, so the source edges are restated rather than
        carried: Stitched Iron Plate removes Reinforced Iron Plate from the
        screw bus entirely and puts it on a wire bus."""
        out = []
        for b in self.buses:
            if b.bus_id == bus_id:
                out.append(
                    BusSpec(
                        bus_id=b.bus_id,
                        item_id=b.item_id,
                        recipe_id=recipe_id,
                        sources=sources,
                        disposition=b.disposition,
                        extra_producers=b.extra_producers,
                        withdrawal_per_min=b.withdrawal_per_min,
                    )
                )
            else:
                out.append(b)
        return Declaration(
            name=f"{self.name}+{bus_id}={recipe_id}",
            buses=tuple(out),
            external_per_min=dict(self.external_per_min),
            provenance=self.provenance,
        )

    def scaled_external(self, factor: float) -> "Declaration":
        """A copy with every external demand multiplied. The crossover sweep's
        scale `s`, which multiplies the targets and nothing else."""
        return Declaration(
            name=f"{self.name}@s={factor:g}",
            buses=self.buses,
            external_per_min={k: v * factor for k, v in self.external_per_min.items()},
            provenance=self.provenance,
        )


@dataclass(frozen=True)
class ConsumerShare:
    """One consumer's claim on a bus, as a RATIO -- never a splitter tree.

    `bus_id=None` is player withdrawal for construction: a real consumer with no
    recipe behind it.
    """

    bus_id: BusId | None
    draw_per_min: float
    share: float


@dataclass(frozen=True)
class BusSolution:
    bus_id: BusId
    item_id: ItemId
    recipe_id: RecipeId
    producer_class: ProducerClass
    disposition: Disposition
    #: One machine at 100% clock.
    rate_per_min: float
    external_per_min: float
    #: DERIVED in-scope draw from this bus's consumers. Never declared.
    automated_demand_per_min: float
    #: DECLARED player withdrawal on a build-material line, 0.0 otherwise. It is
    #: INSIDE `demand_per_min` -- see `BusSpec`.
    withdrawal_per_min: float
    demand_per_min: float
    #: demand / rate, before any floor or ceil. The continuous machine-
    #: equivalent, which is the only scale-free comparison between two regimes:
    #: the integrality tax is a sum of fractional parts over a fixed number of
    #: buses and is O(1) in scale, while the continuous advantage is O(s).
    continuous_machines: float
    machines: int
    clock_percent: float
    supply_per_min: float
    residual_per_min: float
    consumers: tuple[ConsumerShare, ...]

    @property
    def utilisation(self) -> float:
        if self.supply_per_min <= 0:
            return 0.0
        return min(1.0, self.demand_per_min / self.supply_per_min)


@dataclass(frozen=True)
class Solution:
    declaration_name: str
    sizing_basis: SizingBasis
    machine_floor: int
    buses: tuple[BusSolution, ...]

    def __getitem__(self, bus_id: BusId) -> BusSolution:
        for b in self.buses:
            if b.bus_id == bus_id:
                return b
        raise BusNotDeclared(bus_id)

    @property
    def total_machines(self) -> int:
        return sum(b.machines for b in self.buses)

    @property
    def total_continuous_machines(self) -> float:
        return sum(b.continuous_machines for b in self.buses)

    @property
    def integrality_tax(self) -> float:
        """Whole machines minus continuous machine-equivalents."""
        return self.total_machines - self.total_continuous_machines


def _rate_of(data: ReferenceData, spec: BusSpec) -> float:
    recipe = data.recipes.get(spec.recipe_id)
    if recipe is None:
        raise BusModelError(f"{spec.bus_id}: no recipe {spec.recipe_id!r}")
    for item, rate in recipe.outputs:
        if item == spec.item_id:
            return rate
    raise BusModelError(
        f"{spec.bus_id}: {spec.recipe_id} does not output {spec.item_id}"
    )


def _input_rate(data: ReferenceData, spec: BusSpec, item_id: ItemId) -> float:
    for item, rate in data.recipes[spec.recipe_id].inputs:
        if item == item_id:
            return rate
    return 0.0


def _order(decl: Declaration) -> tuple[BusId, ...]:
    """Reverse-topological: a bus is settled only after every bus that draws on
    it. Demand flows from a consumer to its sources, so consumers go first."""
    consumers: dict[BusId, list[BusId]] = {b.bus_id: [] for b in decl.buses}
    for b in decl.buses:
        for e in b.sources:
            if e.source_bus_id is not None:
                consumers[e.source_bus_id].append(b.bus_id)

    order: list[BusId] = []
    mark: dict[BusId, int] = {}

    def visit(bus_id: BusId, stack: list[BusId]) -> None:
        state = mark.get(bus_id)
        if state == 2:
            return
        if state == 1:
            raise CreditedFlowCycle(" -> ".join(stack + [bus_id]))
        mark[bus_id] = 1
        for c in consumers[bus_id]:
            visit(c, stack + [bus_id])
        mark[bus_id] = 2
        order.append(bus_id)

    for b in decl.buses:
        visit(b.bus_id, [])
    return tuple(order)


def solve(
    decl: Declaration,
    data: ReferenceData,
    *,
    sizing_basis: SizingBasis = SizingBasis.AVERAGE,
    machine_floor: int = 1,
) -> Solution:
    """Solve a declaration against scenario-scaled reference data.

    `data` is already at its scenario -- `gamedata.load(root, scenario)` or
    `ReferenceData.with_scenario(...)`. The multiplier is applied to per-cycle
    amounts and rounded per input, which is not expressible on a rate, so this
    model never scales anything itself.

    `machine_floor` is the recovered min-one-machine rule; pass 0 to solve
    without it.
    """
    specs = {b.bus_id: b for b in decl.buses}
    rates = {b.bus_id: _rate_of(data, b) for b in decl.buses}
    for b in decl.buses:
        if b.disposition is Disposition.SUNK:
            raise DispositionUnavailable(
                f"{b.bus_id}: SUNK requires the AWESOME Sink, which is absent from "
                "the reference layer. A4.2 narrows what that absence costs -- a "
                "build-material line reaches a constant draw through MATCHED -- but "
                "disposal of a genuine overflow still has no model."
            )

    # bus -> [(consumer bus, input item)]
    drawn_by: dict[BusId, list[tuple[BusId, ItemId]]] = {b.bus_id: [] for b in decl.buses}
    for b in decl.buses:
        for e in b.sources:
            if e.source_bus_id is not None:
                drawn_by[e.source_bus_id].append((b.bus_id, e.input_item))

    solved: dict[BusId, BusSolution] = {}
    for bus_id in _order(decl):
        spec = specs[bus_id]
        rate = rates[bus_id]

        shares: list[ConsumerShare] = []
        automated = 0.0
        for consumer_id, item_id in drawn_by[bus_id]:
            c = solved[consumer_id]
            c_spec = specs[consumer_id]
            per_min = _input_rate(data, c_spec, item_id)
            peak = c_spec.presents_peak_draw
            if peak is None:
                peak = sizing_basis is SizingBasis.PEAK
            if c.disposition is Disposition.WITHDRAWN:
                # Drained continuously, so producers run at 100%: the draw is
                # nameplate and the average equals the peak.
                flow = c.machines * per_min
            elif peak and c.disposition is Disposition.BACK_UP:
                # Fills a container and pauses. The upstream bus has to carry
                # the nameplate rate while it runs.
                flow = c.machines * per_min
            else:
                # Average draw: actual need. Under MATCHED this is also the peak.
                flow = c.demand_per_min * per_min / rate_or_one(c.rate_per_min)
            automated += flow
            shares.append(ConsumerShare(consumer_id, flow, 0.0))

        withdrawal = spec.withdrawal_per_min or 0.0
        external = float(decl.external_per_min.get(bus_id, 0.0))
        demand = external + automated + withdrawal
        if withdrawal:
            shares.append(ConsumerShare(None, withdrawal, 0.0))
        total = sum(s.draw_per_min for s in shares)
        shares = tuple(
            ConsumerShare(s.bus_id, s.draw_per_min,
                          (s.draw_per_min / total) if total > 0 else 0.0)
            for s in shares
        )

        continuous = demand / rate if rate > 0 else 0.0
        machines = max(machine_floor, math.ceil(continuous - EPS)) + spec.extra_producers
        if spec.disposition is Disposition.MATCHED:
            # Underclocked to the average withdrawal rate: production equals
            # average consumption, so nothing overflows and nothing pauses.
            supply = demand
            clock = 100.0 * demand / (machines * rate) if machines and rate else 0.0
        else:
            supply = machines * rate
            clock = 100.0
        solved[bus_id] = BusSolution(
            bus_id=bus_id,
            item_id=spec.item_id,
            recipe_id=spec.recipe_id,
            producer_class=data.recipes[spec.recipe_id].producer_class,
            disposition=spec.disposition,
            rate_per_min=rate,
            external_per_min=external,
            automated_demand_per_min=automated,
            withdrawal_per_min=withdrawal,
            demand_per_min=demand,
            continuous_machines=continuous,
            machines=machines,
            clock_percent=clock,
            supply_per_min=supply,
            residual_per_min=supply - demand,
            consumers=shares,
        )

    return Solution(
        declaration_name=decl.name,
        sizing_basis=sizing_basis,
        machine_floor=machine_floor,
        buses=tuple(solved[b.bus_id] for b in decl.buses),
    )


def rate_or_one(rate: float) -> float:
    return rate if rate > 0 else 1.0


@dataclass(frozen=True)
class BalanceDelta:
    """One row of the storage review's section 6.1 check.

    Every modelled line at 100% of its DECLARED installed capacity, consuming
    per the reference layer, against the demand the config declares. A positive
    delta is legitimate -- consumers outside the modelled set. A negative one is
    not: the consumer is inside the same file.
    """

    bus_id: BusId
    item_id: ItemId
    declared_per_min: float
    in_config_draw_per_min: float

    @property
    def delta_per_min(self) -> float:
        return self.declared_per_min - self.in_config_draw_per_min


def balance_check(
    decl: Declaration,
    data: ReferenceData,
    installed_capacity_per_min: Mapping[BusId, float],
    declared_demand_per_min: Mapping[BusId, float],
) -> tuple[BalanceDelta, ...]:
    """The section 6.1 check, which nothing in the shipped config performs.

    Deliberately NOT part of `solve`: it takes the config's own declared
    capacity and demand columns, which A2.1 discards as a wrong column. Keeping
    it separate is what lets the defect be reproduced without the defect being
    adopted.
    """
    draw: dict[BusId, float] = {b.bus_id: 0.0 for b in decl.buses}
    for b in decl.buses:
        cap = installed_capacity_per_min.get(b.bus_id)
        if cap is None:
            continue
        rate = _rate_of(data, b)
        for e in b.sources:
            if e.source_bus_id is None:
                continue
            per_min = _input_rate(data, b, e.input_item)
            draw[e.source_bus_id] += cap / rate * per_min
    return tuple(
        BalanceDelta(
            bus_id=b.bus_id,
            item_id=b.item_id,
            declared_per_min=float(declared_demand_per_min[b.bus_id]),
            in_config_draw_per_min=draw[b.bus_id],
        )
        for b in decl.buses
        if b.bus_id in declared_demand_per_min
    )
