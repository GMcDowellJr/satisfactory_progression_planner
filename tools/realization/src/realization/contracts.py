"""Types the realization layer emits.

This layer is POST-SOLVE. It consumes a `SolveResponse` and reference data and
adds no capability to the solver: there is no objective here, nothing is ranked,
and nothing in this package can reach `linprog`.

Import tripwire, exclusion form (supersedes output-contract-respec §1's
inclusion form, which was incompatible with `gamedata.py`'s locked "only place
that knows the CSV column names"):

    PERMITTED   production_adapter.contracts    types only
                production_adapter.gamedata     reference data, read-only
    FORBIDDEN   production_adapter.backend
                production_adapter.lp_backend
                production_adapter.analysis

Asserted by `tests/test_import_boundary.py`, not by this docstring.

THE PRIMITIVE IS THE BUS, NOT THE LANE. Respec §5 treats a lane as belonging to
one product; shared intermediates make that false — a starter base makes
Reinforced Iron Plate and Rotors and both draw on one screw bus. A lane is a
parallel producer line INSIDE a bus. See
docs/decisions/bus_allocation_backpressure_and_residual.md.

Rates are per minute throughout, matching the adapter. Machine counts here are
INTEGER — this layer is where `MachineCount.effective_count` stops being
fractional, which is the one thing the adapter contract delegates to its caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from production_adapter.contracts import ItemId, ProducerClass, RecipeId
#: Owned by `gamedata`, not redefined here — a loader cannot live apart from the
#: type it returns without `gamedata` importing this package back.
from production_adapter.gamedata import Capability, ExtractionRate

DesignTier = int          # 0..9, declared by the caller
CapabilityId = str        # belt_mk2, miner_mk1, pipeline_mk1, ...
Mark = str                # "Mk.1" .. "Mk.6"


# --------------------------------------------------------------------------
# declarations
# --------------------------------------------------------------------------

class Disposition(str, Enum):
    """What drains a bus's residual. This is a STEADY STATE, not a transient.

    A storage container draws no power and is a finite buffer: when it fills,
    the producers feeding it pause. So "producers at 100% with stock
    accumulating" is a transient of duration capacity/residual and is not a
    state the tool reports. The fill dynamics are part of the game and are
    deliberately not modelled.
    """

    BACK_UP = "back_up"      # no drain. Producers idle at demand/supply.
                             # Power LINEAR in utilisation. No stock. Default:
                             # this is what an unattended factory does.
    SUNK = "sunk"            # smart splitter -> storage, overflow -> AWESOME
                             # Sink. Producers never stop, draw is CONSTANT.
                             # Blocked: the Sink is absent from the reference
                             # layer (handoff open item 8).
    WITHDRAWN = "withdrawn"  # the player drains the container. NOT emitted —
                             # it depends on player behaviour and §9 keeps
                             # player time out of the model.


class ClockMode(str, Enum):
    """Whether clocks are set deliberately. Only meaningful under BACK_UP.

    Backpressure already makes a lane exact; what an explicit clock buys is the
    POWER CURVE, not the exactness. Power is convex in clock (exponent
    1.321929) and linear in duty cycle, so the saving grows with slack:
    +0.2% at 99.5% utilisation, +7.4% at 80%, +25% at 50%.

    This corrects respec §4.5, which states that underclocking is the only
    lever that makes a lane exact.
    """

    BACKPRESSURE = "backpressure"   # let belts idle the machines. Zero effort.
    EXPLICIT = "explicit"           # set a clock per lane. Convex saving.


class ClockDistribution(str, Enum):
    """How an explicit clock spreads across a lane's machines (respec §4.3).

    Valid only for a FIXED machine set. It does not choose the set: power is
    strictly decreasing in machine count, so it would always answer "more".
    """

    AVERAGED = "averaged"   # every machine at the same clock; power-optimal
    SPLIT = "split"         # n at 100% + one at the remainder; reportable


@dataclass(frozen=True)
class BusDeclaration:
    """What the caller states about one item's bus.

    Storage rate is a MACHINE COUNT, not a boolean. The residual is quantised —
    at the ceil it is whatever rounding left, and it cannot be raised except by
    a whole producer:

        R(k) = ceil_residual + k * producer_rate

    On the screw bus (199/min demand, 40/min producers) the ceil yields 1/min.
    Meaningful storage costs a machine and arrives 40/min at a time.
    """

    item_id: ItemId
    extra_producers: int = 0
    disposition: Disposition = Disposition.BACK_UP
    clock_mode: ClockMode = ClockMode.BACKPRESSURE
    clock_distribution: ClockDistribution = ClockDistribution.AVERAGED

    def __post_init__(self) -> None:
        if self.extra_producers < 0:
            raise ValueError(f"{self.item_id}: extra_producers must be >= 0")


@dataclass(frozen=True)
class NodeDeclaration:
    """A placed extractor — an INPUT contract (respec §3.2 surface 5).

    "Maximise each node" is a declared default with an override, named as
    declared rather than assumed; the caller raises the clock deliberately and
    the layer never raises it on the caller's behalf.
    """

    item_id: ItemId
    extractor_class: ProducerClass
    purity: Literal["impure", "normal", "pure", "none"]
    count: int = 1
    clock_percent: float = 100.0


@dataclass(frozen=True)
class RealizationRequest:
    design_tier: DesignTier
    buses: tuple[BusDeclaration, ...] = ()
    nodes: tuple[NodeDeclaration, ...] = ()
    trunk_capability: CapabilityId | None = None

    def declaration_for(self, item_id: ItemId) -> BusDeclaration:
        for b in self.buses:
            if b.item_id == item_id:
                return b
        return BusDeclaration(item_id=item_id)


# --------------------------------------------------------------------------
# buses and lanes
# --------------------------------------------------------------------------

BindingSide = Literal["input", "output"]


class ClockCause(str, Enum):
    """Why a lane is not at 100%. Without this a reader cannot tell whether a
    clock is a choice or a constraint."""

    FULL = "full"                    # at 100%
    DECLARED = "declared"            # ClockMode.EXPLICIT set it
    BACKPRESSURE = "backpressure"    # derived: supply exceeds bus demand
    RATIO_LIMITED = "ratio_limited"  # starved — the branch cannot carry the
                                     # draw, or the bus is in deficit and
                                     # geometry decided the shortfall


@dataclass(frozen=True)
class LaneInput:
    item_id: ItemId
    rate_per_min: float
    carrier: Capability   # minimum sufficient Mk at the declared tier


@dataclass(frozen=True)
class Lane:
    """One parallel producer line inside a bus."""

    recipe_id: RecipeId
    producer_class: ProducerClass
    machines: int
    clock_percent: float
    clock_cause: ClockCause
    output_item: ItemId
    output_rate_per_min: float
    binding_side: BindingSide
    binding_rate_per_min: float
    trunk: Capability
    inputs: tuple[LaneInput, ...]
    power_mw: float


@dataclass(frozen=True)
class ConsumerShare:
    """One consumer's claim on a bus, as a RATIO — never a splitter tree.

    A single returned topology reproduces §5.5's set-valued defect, because
    splitter trees tie constantly. And in the supply-adequate case the topology
    does not need to encode the ratio at all: backpressure converges to each
    consumer's draw on any connected layout with adequate belts.
    """

    recipe_id: RecipeId
    draw_per_min: float
    share: float          # draw / total bus demand


@dataclass(frozen=True)
class BusResidual:
    """supply - TOTAL bus demand. A property of the BUS, never of a lane.

    Per-lane overflow is not physical: backpressure moves surplus between a
    bus's consumers before anything can be stored. This also retires respec
    §4.6's consumed-downstream / dead classification as a separate output —
    consumed-downstream surplus is consumed automatically, so the distinction
    is already inside the demand sum and what is left is dead by construction.
    """

    item_id: ItemId
    rate_per_min: float
    disposition: Disposition
    #: Power the disposition costs against the cheapest alternative. Under
    #: BACK_UP this is the convex saving an explicit clock would have made;
    #: under SUNK it is the cost of running producers the demand does not need.
    power_cost_mw: float


@dataclass(frozen=True)
class Bus:
    """(item, producer set, consumer set). The primitive."""

    item_id: ItemId
    recipe_id: RecipeId
    supply_per_min: float
    demand_per_min: float
    lanes: tuple[Lane, ...]
    consumers: tuple[ConsumerShare, ...]
    residual: BusResidual

    @property
    def machines(self) -> int:
        return sum(l.machines for l in self.lanes)

    @property
    def is_isolable(self) -> bool:
        """One consumer can be isolated; two or more must merge. Derived, not
        declared — a rejoin point is a multi-consumer bus."""
        return len(self.consumers) <= 1

    @property
    def in_deficit(self) -> bool:
        """Supply below demand. The ONLY case where splitter geometry decides
        outcomes, because nobody backs up and the nominal ratio picks who
        starves. Adding one producer removes the problem rather than solving
        it."""
        return self.supply_per_min < self.demand_per_min - 1e-9


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ProjectedGoal:
    """Respec §6 — rate and T both DERIVED from the declared build."""

    goal_id: str
    item_id: ItemId
    total_required: float
    rate_per_min: float
    minutes_to_complete: float


@dataclass(frozen=True)
class RealizationReport:
    buses: tuple[Bus, ...]
    extraction: tuple[NodeDeclaration, ...]
    projections: tuple[ProjectedGoal, ...]
    total_power_mw: float
    design_tier: DesignTier
    #: An alternate recipe is a RE-WIRING event, not only a cheaper recipe:
    #: Stitched Iron Plate removes Reinforced Iron Plate from the screw bus
    #: entirely (199 -> 124/min). A report is valid for a RECIPE SET, and these
    #: are the unlocks that would invalidate it. Derived from the consumer
    #: sets, declaration-shaped rather than an optimisation.
    invalidating_unlocks: tuple[RecipeId, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------
# refusals
# --------------------------------------------------------------------------

class RealizationError(RuntimeError):
    """The layer declines rather than emitting a figure it cannot stand behind."""


class CreditedFlowCycle(RealizationError):
    """An item is a byproduct of a recipe that transitively consumes it.

    The demand pass is a single reverse-topological traversal and is not
    iterated toward a fixed point. On a cycle the map is non-monotone and no
    termination argument is available.
    See docs/decisions/toggle_propagation_and_demand_pass.md §5.
    """


class TierUnavailable(RealizationError):
    """No capability of the required type is unlocked at the declared tier."""


class LaneInfeasible(RealizationError):
    """No whole number of machines fits the trunk on the binding side."""


class DispositionUnavailable(RealizationError):
    """A declared disposition needs reference data the layer does not have.

    SUNK requires the AWESOME Sink, absent from the reference layer. Refused by
    name rather than silently downgraded to BACK_UP, which would misreport both
    the residual's fate and the power draw's stability.
    """
