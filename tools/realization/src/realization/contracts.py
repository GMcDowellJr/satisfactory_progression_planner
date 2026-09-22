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

THE PRIMITIVE IS (item, producers, consumers, PARTITION). Respec §5 treats a lane
as belonging to one product; shared intermediates make that false — a starter
base makes Reinforced Iron Plate and Rotors and both draw on one screw bus. A
lane is a parallel producer line INSIDE a bus. See
docs/decisions/bus_allocation_backpressure_and_residual.md.

THE PARTITION IS DECLARED, NOT DERIVED. The same item may run on several
unconnected buses by choice: Iron Wire from Iron Ingot feeding Stitched Iron
Plate is a different bus from Wire from Copper Ingot feeding Cable and the build
stock, and their residuals DO NOT POOL. Bus record §1 derived isolation from
consumer count — that rule is contradicted by
docs/decisions/bus_level_recompute_and_alternate_crossover.md amendment 3, and
the consumer set is now what a declared partition must COVER rather than what
induces it.

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
#: Names one bus of one item. DECLARED by the caller, never derived: "wire_iron"
#: and "wire_copper" are two buses of Wire and are different objects.
BusId = str


# --------------------------------------------------------------------------
# declarations
# --------------------------------------------------------------------------

class Disposition(str, Enum):
    """A bus's STEADY STATE. Declared PER BUS. What drains its residual follows.

    Per-bus, not per-factory: several states run at once in one factory. The
    production chain drains continuously with producers at 100% (WITHDRAWN)
    while a build-material line either fills a container and pauses (BACK_UP) or
    is clocked to its average draw (MATCHED). A residual without its own bus's
    state is meaningless, which is how two documents computed R under different
    states and mistook the difference for an error. See
    bus_level_recompute_and_alternate_crossover.md amendment 3 A3.2, amendment 4
    A4.2.

    A storage container draws no power and is a finite buffer, so "producers at
    100% with stock accumulating and nothing withdrawing" is a transient of
    duration capacity/residual and is not a state the tool reports. The fill
    dynamics are part of the game and are deliberately not modelled.
    """

    BACK_UP = "back_up"      # no drain. Producers idle at demand/supply. Power
                             # LINEAR in utilisation. The line fills its
                             # container and pauses, so its draw on the upstream
                             # bus OSCILLATES between nameplate and zero and has
                             # to be sized against the peak.
    SUNK = "sunk"            # smart splitter -> storage, overflow -> AWESOME
                             # Sink. Producers never stop, draw is CONSTANT.
                             # Blocked: the Sink is absent from the reference
                             # layer. A4.2 NARROWS what that absence costs — it
                             # no longer gates constant power, only disposal of
                             # a genuine overflow.
    WITHDRAWN = "withdrawn"  # drained continuously, so producers run at 100%
                             # and the residual is rounding slop — small,
                             # sawtoothed, often exactly zero. This is the
                             # production chain's state and every figure in A3.5
                             # was computed under it. §9 still keeps player TIME
                             # out of the model: a state is not a duration.
    MATCHED = "matched"      # A4.2. Underclocked to the AVERAGE withdrawal rate.
                             # Production equals average consumption, so nothing
                             # overflows and nothing pauses; power is CONSTANT
                             # and the container buffers the player's burstiness
                             # rather than an overflow. Needs nothing the
                             # reference layer is missing. On the Iron Plate
                             # build line, 0.19 MW against 4.00, and 4/min of
                             # ingot draw against a 40/min peak.


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
class SourceEdge:
    """Which bus this bus draws one of its inputs from. DECLARATION.

    This is where the partition actually lives. Two buses of the same item are
    distinguishable only because their consumers name different sources: the
    Stitched Iron Plate line declares `SourceEdge("Wire", "wire_iron")` and the
    Cable line declares `SourceEdge("Wire", "wire_copper")`, and nothing in the
    solve says which is which.

    `source_bus_id=None` means the input is out of scope — raw, or not modelled.
    """

    input_item: ItemId
    source_bus_id: BusId | None


class WithdrawalBasis(str, Enum):
    """Where a declared withdrawal rate came from. Two, and NOT interchangeable.

    Amendment 5 §A5.5. A verdict is only as good as the floor it was measured
    against, and the two floors here have different provenance and different
    error characteristics. A basis is therefore part of what a caller DECLARES
    alongside the rate, and `Coverage` carries it out again.

    A value's meaning is FIXED at what it means on the day it is added. When
    phase 5 wires the spatial bounds, that is a THIRD value, not this one
    silently widening — forward-only applied to an enum.
    """

    GEOMETRIC_FLOOR = "geometric_floor"
    #: §8.2's footprint-derived estimate plus one extra 8m foundation on the
    #: short axis for movement and splitters. Declared by its author as a FLOOR
    #: (A3.3), so any verdict computed against it is optimistic by an unmeasured
    #: amount.

    DERIVED_WHOLE_GAME_FLOOR = "derived_whole_game_floor"
    #: The whole-game construction bill's CANONICAL terms, summed from
    #: `building_recipe_io.csv` per building against settled machine counts,
    #: plus `schematic_costs.csv` and `project_assembly_requirements.csv`.
    #:
    #: The SPATIAL terms — belt and pipe length, foundation area — are ABSENT
    #: by construction: their lower bounds are phase 5's and are not wired to
    #: demand. Their absence is what keeps this a floor, which is the property
    #: A5.5 needs, so it is a definition rather than a shortfall.
    #:
    #: Its distance from the truth is NOT uniform across items. Cable,
    #: Reinforced Iron Plate, Rotor and Wire are dominated by machine
    #: construction and this is close. Concrete is dominated by the spatial
    #: term — 371 of 545 building recipes consume it, almost all structural —
    #: and this is a floor by a wide and unmeasured margin.
    #:
    #: Nothing in the repo produces this basis yet. The value exists so that a
    #: stock pass can be written without the verdict silently changing meaning
    #: while `Coverage.basis` still reads the same.


@dataclass(frozen=True)
class BusDeclaration:
    """What the caller states about ONE BUS. Keyed by `bus_id`, not by item.

    Item-keying was the one-bus-per-item assumption in type form: two Wire
    declarations under it were accepted and the second was silently unreachable.

    Two sizing bases, and the model must not conflate them:

        residual item        has in-scope consumers. Sized from derived demand:
                             ceil(demand / rate) + extra_producers. R is rounding
                             leftover and may be exactly zero, which for a
                             dedicated intermediate is the design working
        build-material line  `withdrawal_per_min` is set. Sized from a DECLARED
                             rate — the §8.2 geometric estimate, footprint-
                             derived with one extra 8m foundation on the short
                             axis, and declared by its author as a FLOOR (A3.3).
                             Two ways to run it, and `disposition` picks:
                               BACK_UP  whole machines, fills and pauses.
                                        Oscillating draw sized against nameplate
                               MATCHED  one machine clocked to the withdrawal.
                                        Constant draw, no overflow, no pause

    A build-material line is by construction a bus the SOLVE DOES NOT RUN, so
    there is no `RecipeUse` to attribute its recipe from. `recipe_id` is where
    the caller supplies it. Without it the line is refused by name and cannot be
    sized at all — P30, 2026-09-22.

    Storage rate is a MACHINE COUNT, not a boolean. The residual is quantised —
    at the ceil it is whatever rounding left, and it cannot be raised except by
    a whole producer:

        R(k) = ceil_residual + k * producer_rate

    On the screw bus (199/min demand, 40/min producers) the ceil yields 1/min.
    Meaningful storage costs a machine and arrives 40/min at a time.
    """

    bus_id: BusId
    item_id: ItemId
    #: P30. Which recipe this bus runs, when the caller states it. `None` — the
    #: default — means ATTRIBUTE it from the solve, which is the only behaviour
    #: that existed before 2026-09-22 and stays the behaviour for every
    #: production bus.
    #:
    #: It exists for the buses the SOLVE DOES NOT RUN. A build-material line —
    #: Concrete, Cable, the Iron Plate build stock — has no `RecipeUse` to be
    #: attributed from, so without this field it cannot be sized at all, and
    #: `buses.buses_from_response` refuses it by name. `busmodel.BusSpec`
    #: already carries a `recipe_id`; this is the realization contract catching
    #: up to its own oracle.
    #:
    #: Naming a recipe is the CALLER choosing one, not this layer. The standing
    #: guardrail is that nothing here selects a recipe, and a declaration is not
    #: a selection — it is the same authority `sources` already carries. Where
    #: the solve DID run the named recipe, the solve's `RecipeUse` is still what
    #: is attributed: the declaration disambiguates, it does not replace.
    recipe_id: RecipeId | None = None
    #: Which bus supplies each input. An input absent from this tuple is out of
    #: scope. Declaration, never derivation.
    sources: tuple[SourceEdge, ...] = ()
    extra_producers: int = 0
    #: Set on a build-material line, `None` on a residual item. Units are per
    #: minute and the basis is `WithdrawalBasis.GEOMETRIC_FLOOR` — see
    #: `Coverage`, which cannot be constructed without saying so.
    withdrawal_per_min: float | None = None
    #: WHERE that rate came from. Defaults to the geometric floor, which is the
    #: WEAKEST and most-caveated basis — a caller who forgets gets the most
    #: pessimistic label rather than an unearned upgrade. That is why a default
    #: is safe here and is not on `Coverage.basis`, where any default would
    #: launder a caveat on the way out instead of applying one.
    withdrawal_basis: WithdrawalBasis = WithdrawalBasis.GEOMETRIC_FLOOR
    disposition: Disposition = Disposition.BACK_UP
    clock_mode: ClockMode = ClockMode.BACKPRESSURE
    clock_distribution: ClockDistribution = ClockDistribution.AVERAGED

    def __post_init__(self) -> None:
        if self.extra_producers < 0:
            raise ValueError(f"{self.bus_id}: extra_producers must be >= 0")
        if self.withdrawal_per_min is not None and self.withdrawal_per_min < 0:
            raise ValueError(f"{self.bus_id}: withdrawal_per_min must be >= 0")
        # P29. MATCHED is defined as "underclocked to the AVERAGE WITHDRAWAL
        # RATE", so without a rate there is nothing to match and no clock to
        # derive. Refused at construction rather than downstream, because the
        # alternative is `clock_for` dividing by a `None` three calls later and
        # reporting it as an arithmetic fault.
        #
        # The converse is LEGAL and deliberately not checked: a withdrawal
        # without MATCHED is a BACK_UP build-material line, which is the other
        # of the two sizings A4.2 names.
        if self.disposition is Disposition.MATCHED and self.withdrawal_per_min is None:
            raise ValueError(
                f"{self.bus_id}: Disposition.MATCHED requires withdrawal_per_min — "
                "it is the rate being matched. A build-material line with no "
                "declared withdrawal is sized as BACK_UP instead."
            )
        seen = [e.input_item for e in self.sources]
        if len(seen) != len(set(seen)):
            raise ValueError(f"{self.bus_id}: an input may name at most one source bus")

    @property
    def is_build_material_line(self) -> bool:
        return self.withdrawal_per_min is not None


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

    def __post_init__(self) -> None:
        ids = [b.bus_id for b in self.buses]
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise ValueError(f"duplicate bus_id: {dupes}")

    def declaration_for(self, bus_id: BusId) -> BusDeclaration:
        """The declaration for one bus.

        RAISES on an unknown bus rather than defaulting one into existence.
        Under a declared partition a default is not a sensible fallback: which
        bus an item runs on is precisely what the caller states, and inventing
        one re-merges the buses the caller split.
        """
        for b in self.buses:
            if b.bus_id == bus_id:
                return b
        raise BusNotDeclared(bus_id)

    def declarations_for_item(self, item_id: ItemId) -> tuple[BusDeclaration, ...]:
        """Every declared bus of one item. Length > 1 is ordinary, not an error."""
        return tuple(b for b in self.buses if b.item_id == item_id)


# --------------------------------------------------------------------------
# buses and lanes
# --------------------------------------------------------------------------

BindingSide = Literal["input", "output"]


class RecipeProvenance(str, Enum):
    """Where a bus's recipe came from. P30, 2026-09-22.

    Before P30 there was one answer and it did not need a name. With
    `BusDeclaration.recipe_id` there are two, and they are NOT the same claim:
    one is read out of the solve, the other is read out of the request.
    """

    SOLVED = "solved"      # matched to a `RecipeUse` in the `SolveResponse`.
                           # The solve ran this recipe and sized it
    DECLARED = "declared"  # named by `BusDeclaration.recipe_id` and absent
                           # from the response. The solve has NO ACCOUNT of
                           # this bus — not a zero-sized one


@dataclass(frozen=True)
class BusRecipe:
    """The attribution result for one bus: which recipe, and on whose word.

    Not emitted in `RealizationReport` — `Bus.recipe_id` is what a reader sees.
    It is a type rather than a bare `RecipeUse` so that `machine_equivalents`
    can be ABSENT rather than zero.

    That distinction is the whole point. `_demand`'s external term is
    `machine_equivalents * rate - automated`, floored at zero: the demand the
    solve sized this recipe for that the declaration does not model. On a
    DECLARED bus the solve sized nothing, and writing 0.0 there would make
    "the solve has no account of this bus" indistinguishable from "the solve
    says its external demand is zero" — a measurement and an absence wearing
    one number. `Coverage.basis` has no default for the same reason.

    Invariant, enforced below: SOLVED carries a figure, DECLARED carries None.
    """

    recipe_id: RecipeId
    provenance: RecipeProvenance
    #: `RecipeUse.machine_equivalents` when SOLVED. `None` when DECLARED, and
    #: `None` means UNAVAILABLE, never zero.
    machine_equivalents: float | None = None

    def __post_init__(self) -> None:
        if self.provenance is RecipeProvenance.SOLVED and self.machine_equivalents is None:
            raise ValueError(
                f"{self.recipe_id}: a SOLVED attribution carries the solve's "
                "machine_equivalents"
            )
        if self.provenance is RecipeProvenance.DECLARED and self.machine_equivalents is not None:
            raise ValueError(
                f"{self.recipe_id}: a DECLARED attribution has no "
                "machine_equivalents — the solve did not run this bus"
            )


class ClockCause(str, Enum):
    """Why a lane is not at 100%. Without this a reader cannot tell whether a
    clock is a choice or a constraint."""

    FULL = "full"                    # at 100%
    DECLARED = "declared"            # ClockMode.EXPLICIT set a CLOCK
    MATCHED = "matched"              # derived from a declared RATE: the clock
                                     # that makes output equal the declared
                                     # withdrawal. Distinct from DECLARED
                                     # because the caller stated a draw, not a
                                     # percentage, and the percentage moves when
                                     # the scenario multiplier does
    BACKPRESSURE = "backpressure"    # derived: supply exceeds bus demand
    RATIO_LIMITED = "ratio_limited"  # starved — the branch cannot carry the
                                     # draw, or the bus is in deficit and
                                     # geometry decided the shortfall


@dataclass(frozen=True)
class LaneInput:
    item_id: ItemId
    rate_per_min: float
    carrier: Capability   # minimum sufficient Mk at the declared tier
    #: Which bus this draw lands on. `None` = out of scope (raw, or not
    #: modelled). Without it a draw on Wire cannot be attributed to wire_iron or
    #: wire_copper and the two buses re-merge downstream.
    source_bus_id: BusId | None = None


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

    `recipe_id=None` is player withdrawal for construction — a real consumer
    (A3.1 names it as the third on the Wire bus) with no recipe behind it.
    """

    recipe_id: RecipeId | None
    draw_per_min: float
    #: draw / total AUTOMATED bus demand. Withdrawal is NOT in the denominator
    #: and carries `None`: it is covered by the residual rather than sized into
    #: the bus, which is what makes A3.5's `R >= withdraw` verdict meaningful.
    share: float | None

    @property
    def is_withdrawal(self) -> bool:
        return self.recipe_id is None


@dataclass(frozen=True)
class BusResidual:
    """supply - TOTAL bus demand. A property of the BUS, never of a lane.

    Per-lane overflow is not physical: backpressure moves surplus between a
    bus's consumers before anything can be stored. This also retires respec
    §4.6's consumed-downstream / dead classification as a separate output —
    consumed-downstream surplus is consumed automatically, so the distinction
    is already inside the demand sum and what is left is dead by construction.
    """

    bus_id: BusId
    item_id: ItemId
    rate_per_min: float
    #: The bus's steady state. REQUIRED and never defaulted — this field is the
    #: "no stateless residual" tripwire in type form.
    disposition: Disposition
    #: Power the disposition costs against the cheapest alternative. Under
    #: BACK_UP this is the convex saving an explicit clock would have made;
    #: under SUNK it is the cost of running producers the demand does not need.
    power_cost_mw: float


@dataclass(frozen=True)
class Bus:
    """(item, producers, consumers, PARTITION). The primitive.

    Two buses of one item are DIFFERENT OBJECTS and their residuals do not pool.
    Grouping a report's buses by `item_id` re-merges what the caller declared
    apart — on the worked case that turns (wire_iron R 20.62, wire_copper R
    16.00) into a single R 13.12 on 30 machines instead of 31. The arithmetic is
    fine; it describes a factory nobody built.
    """

    bus_id: BusId
    item_id: ItemId
    recipe_id: RecipeId
    supply_per_min: float
    #: DERIVED in-scope draw from this bus's consumers. Not declared — that was
    #: A2.1's standing half, and the config's `automated_demand_per_min` field
    #: is the defect it names.
    automated_demand_per_min: float
    #: DECLARED player withdrawal, 0.0 on a residual item. Deliberately NOT
    #: summed into `automated_demand_per_min`: it does not size the bus, it is
    #: what the residual has to cover.
    withdrawal_per_min: float
    lanes: tuple[Lane, ...]
    consumers: tuple[ConsumerShare, ...]
    residual: BusResidual

    @property
    def machines(self) -> int:
        return sum(l.machines for l in self.lanes)

    @property
    def in_deficit(self) -> bool:
        """Supply below automated demand. The ONLY case where splitter geometry
        decides outcomes, because nobody backs up and the nominal ratio picks
        who starves. Adding one producer removes the problem rather than solving
        it."""
        return self.supply_per_min < self.automated_demand_per_min - 1e-9


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

#: `WithdrawalBasis` moved up to the declarations section on 2026-09-21: once
#: `BusDeclaration` carries a basis, the basis is a declaration concept and has
#: to be defined before the dataclass that defaults to it.


@dataclass(frozen=True)
class Coverage:
    """Whether a bus's residual covers its declared withdrawal.

    `basis` has NO DEFAULT, deliberately. A3.3 makes the floor caveat a
    labelling requirement, and a labelling requirement routed through
    `RealizationReport.warnings` is free text that nothing can assert. Here the
    verdict cannot be constructed without stating what it was measured against,
    which is the repo's standing rule that a structural guardrail beats a policy.

    `covers=True` therefore means "covers the floor", never "covers".
    """

    bus_id: BusId
    item_id: ItemId
    residual_per_min: float
    withdrawal_per_min: float
    basis: WithdrawalBasis
    covers: bool


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
    #: One entry per build-material line. Empty is not "everything covers" — it
    #: is "no line declared a withdrawal". Never a string in `warnings`.
    coverage: tuple[Coverage, ...] = field(default_factory=tuple)
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

    NARROWED by amendment 4. This is no longer the only route to a constant
    draw: a build-material line reaches one through MATCHED, which needs nothing
    that is missing. The refusal now bites only on a line with a genuine
    overflow to dispose of.
    """


class BusNotDeclared(RealizationError):
    """A bus was referenced that the request does not declare.

    Raised rather than defaulted. Under a declared partition, defaulting an
    unknown bus into existence re-merges exactly what the caller split.
    """


class PartitionIncomplete(RealizationError):
    """The declared partition does not cover the consumer set exactly.

    A consumer claimed by no declared bus, or by more than one. This is what
    replaces `Bus.is_isolable`: the partition is not derived from the consumer
    count, but a declared partition is CHECKED against the consumer set, and a
    gap is refused by name rather than silently merged.
    """
