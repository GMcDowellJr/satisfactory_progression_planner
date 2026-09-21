"""Bus construction and lane decomposition inside a bus.

Replaces `lanes.py`, which asked the wrong question. It offered
`machines_per_lane(recipe, trunk)` — a per-recipe function — where divisibility
is against the bus's CONSUMER draws, not the producer's output alone.

    bus       (item, producer set, consumer set)
    lane      one parallel producer line inside a bus, whose throughput fits
              one belt of the design tier's Mk on its binding side
    binding   max(input rate, output rate) for the line, each item compared
              against the trunk independently — a line is limited by whichever
              single item first fills a belt, since each item rides its own

Two results that shape everything here, both from
docs/decisions/bus_allocation_backpressure_and_residual.md:

**Backpressure allocates.** A splitter round-robins over outputs that can
accept and skips a blocked one, so a satisfied consumer backs up and the
surplus reaches the others. In steady state any connected topology with
adequate belts converges to each consumer's draw, provided supply >= demand.
So the layer emits ratios and three checks, never a splitter tree.

**The multiplier moves divisibility, not just cost.** At 1x a Smelter's 30
ingot/min feeds one Plate Constructor exactly. At 1.25x the Constructor draws
40 (3 ingot/cycle rounds to 4), so the ratio is 4 : 3 and a lane of w smelters
feeds 0.75w constructors — integral only when w is a multiple of 4. The locked
rounding rule has a LAYOUT consequence, not only a cost one.
"""
from __future__ import annotations

from production_adapter.contracts import ItemId, RecipeId, SolveResponse
from production_adapter.gamedata import Capability, ReferenceData

from .contracts import (
    Bus, ConsumerShare, Lane, RealizationRequest,
)


def machines_per_lane(
    data: ReferenceData,
    recipe_id: RecipeId,
    trunk: Capability,
) -> int:
    """How many producers of `recipe_id` one trunk belt carries on the binding side.

    Returns 0 when a single machine already exceeds the trunk; the caller
    raises `LaneInfeasible` rather than emitting a fractional lane.
    """
    raise NotImplementedError


def integral_lane_widths(
    data: ReferenceData,
    recipe_id: RecipeId,
    consumers: tuple[ConsumerShare, ...],
    trunk: Capability,
) -> tuple[int, ...]:
    """Lane widths that leave every downstream consumer at a whole machine.

    A width w is integral when w * producer_rate divides evenly into each
    consumer's per-machine draw. At 1.25x on a Mk.2 trunk the ingot bus admits
    w = 4 and nothing else, because 4 is the only multiple of 4 that fits.

    Empty means no width is integral under this trunk — the bus cannot be kept
    isolated at this tier and must merge. That is a finding to report, not an
    error: `Bus.is_isolable` already says multi-consumer buses merge anyway.
    """
    raise NotImplementedError


def decompose(
    data: ReferenceData,
    recipe_id: RecipeId,
    demand_per_min: float,
    consumers: tuple[ConsumerShare, ...],
    trunk: Capability,
    request: RealizationRequest,
) -> tuple[Lane, ...]:
    """Split a bus's producers into whole lanes.

    Machine count is the bus total — `ceil(demand / rate) + extra_producers` —
    and lanes partition it. Distribution across lanes is by minimum total
    machines, balanced, one clock. Fill-then-spill is dominated: equal machines
    and equal residual, worse power, and two clock settings rather than one.

    Power does NOT decide the machine count. P = P_base * (D/r)^e * N^(1-e)
    with e > 1 is strictly decreasing in N without bound, so a power objective
    always answers "more machines" and has no interior optimum.
    """
    raise NotImplementedError


def partition(
    response: SolveResponse,
    data: ReferenceData,
    item_id: ItemId,
) -> tuple[ConsumerShare, ...]:
    """Every consumer's claim on one item, as ratios summing to 1.

    Measured example, scenario of record, one base assembler each of
    Reinforced Iron Plate and Rotor:

        screw bus 199/min  ->  RIP 75 (37.7%)   Rotor 124 (62.3%)

    The tool emits this and stops. Reconciling 37.7% with a buildable ratio is
    the player's, across two lattices that are NOT interchangeable:

        producer partition   shares k/N with N producers. ZERO elements.
                             Fifths are free at N = 5.
        splitter tree        a splitter divides by 2 or 3, a merger adds, so
                             every reachable fraction has a 3-SMOOTH
                             denominator (2^i * 3^j). Fifths are unreachable.

    (3-smooth holds for acyclic trees; feeding a stream back upstream reaches
    arbitrary rationals.)
    """
    raise NotImplementedError


def buses_from_response(
    response: SolveResponse,
    data: ReferenceData,
    request: RealizationRequest,
    capabilities: tuple[Capability, ...],
) -> tuple[Bus, ...]:
    """Every bus in the solve, in reverse topological order of the credited flow.

    Reads `RecipeUse.machine_equivalents` and `ItemFlow`, and nothing else from
    the response. Does not re-derive the solve.
    """
    raise NotImplementedError


def feasibility(bus: Bus) -> tuple[str, ...]:
    """The three checks that replace emitting a splitter topology.

        supply >= demand        otherwise the bus is in deficit, nobody backs
                                up, and the nominal ratio decides who starves
        branch capacity         every consumer's branch carries its draw, or
                                it starves regardless of backpressure
        connectivity            a consumer reachable from the producers

    Returns the failures, empty when the bus is sound. Deficit is reported
    rather than repaired: the repair is one more producer, and choosing to
    build it is the caller's.
    """
    raise NotImplementedError
