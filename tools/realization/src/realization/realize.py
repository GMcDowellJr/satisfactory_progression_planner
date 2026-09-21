"""The realization layer's entry point (output-contract respec §11 item 4).

    realize(response, data, logistics, request) -> RealizationReport

Post-solve. Consumes a `SolveResponse` plus reference data, adds no capability
to the solver, and cannot reach one. The demand pass is a SINGLE traversal in
reverse topological order of the credited flow graph — not a fixed-point
iteration, no tolerance, no iteration cap. See
docs/decisions/toggle_propagation_and_demand_pass.md.

Order of operations, and each step is one visit per lane:

    1  build the credited flow graph from the response
    2  check it for cycles; refuse by name on one (CreditedFlowCycle)
    3  reverse-topological traversal, computing per BUS:
         demand -> trunk selection -> lane decomposition -> machines
         -> clock -> power -> residual -> input draw
       input draw is the demand contribution to the buses upstream, so the
       traversal never revisits
    4  residual per bus = supply - TOTAL consumer demand (never per lane)
    5  project the §6 goals from the declared build
"""
from __future__ import annotations

from production_adapter.contracts import ItemId, SolveResponse
from production_adapter.gamedata import ReferenceData

from .contracts import (
    Bus, Capability, ExtractionRate, ProjectedGoal, RealizationReport,
    RealizationRequest,
)


def realize(
    response: SolveResponse,
    data: ReferenceData,
    capabilities: tuple[Capability, ...],
    extraction: tuple[ExtractionRate, ...],
    request: RealizationRequest,
) -> RealizationReport:
    """Turn a solved plan into the equipment that builds it at the declared tier.

    Raises rather than guessing: `CreditedFlowCycle` on a byproduct that feeds
    back, `TierUnavailable` when the declared tier unlocks nothing of a needed
    type, `LaneInfeasible` when one machine already exceeds the trunk.
    """
    raise NotImplementedError


def credited_flow_order(
    response: SolveResponse,
    data: ReferenceData,
) -> tuple[str, ...]:
    """Recipe ids in reverse topological order of the CREDITED flow graph.

    Credited means byproducts are edges too: crediting a byproduct against
    demand adds an edge from its producer to every consumer of that item. The
    recipe graph can be acyclic while the credited graph is not, which is
    exactly the case this must detect.

    Raises `CreditedFlowCycle` naming the item. It is refused, not iterated
    toward — on a cycle the update map is non-monotone (overflow is a sawtooth
    in demand and enters with a negative sign), and no termination argument is
    available. This is the standing `_demand_oracle` defect made explicit
    rather than a new restriction.
    """
    raise NotImplementedError


def project_goals(
    buses: tuple[Bus, ...],
    totals: tuple[tuple[str, ItemId, float], ...],
) -> tuple[ProjectedGoal, ...]:
    """Respec §6 — rates for everything, totals for milestones/MAM/Space Elevator.

    The DECLARATION is machine count. Rate is derived from machines at the
    lane's clock; T is derived from rate against the canonical total; the
    binding item is argmax T. No player-time parameter enters, so §9 holds, and
    the tool recommends neither a rate nor a duration.

    Checked against the worked case: Smart Plating is 1 RIP + 1 Rotor on a 30 s
    cycle, so one Assembler yields 2/min and 100 units takes 50 minutes exactly.

    The two named ways to shorten T — somersloop, or a second line — are both
    changes to the BUILD, which is the declaration. They are inputs the player
    varies and reads T back from, not levers this function pulls.

    A somersloop'd lane is currently OUTSIDE what the tool describes: the
    output multiplier and power penalty are absent from the reference layer
    (respec §10.6). Such a lane must be refused by name rather than silently
    reported at its unslooped figure.
    """
    raise NotImplementedError
