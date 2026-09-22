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

Bodies written 2026-09-21. Two gaps the bodies made visible and did not close,
because closing either is a patch to a signature rather than a body:

    NO GOAL INPUT    `realize` takes no goals and no totals, so
                     `RealizationReport.projections` is ALWAYS empty from this
                     entry point. `project_goals` is the surface, and a caller
                     that wants §6 projections calls it directly with the
                     canonical totals. Empty therefore means "realize was not
                     given any goals", never "no goal completes"
    NO SOMERSLOOP    `project_goals` is required to refuse a somersloop'd lane
                     by name. Nothing in `Lane` expresses a somersloop — the
                     output multiplier and power penalty are absent from the
                     reference layer (respec §10.6) — so there is nothing to
                     detect and nothing is refused. The refusal has no site
                     until the reference layer has the multiplier
"""
from __future__ import annotations

import math

from production_adapter.contracts import ItemId, RecipeId, SolveResponse
from production_adapter.gamedata import ReferenceData

from .buses import (
    _attribute, _input_rate, _recipe, buses_from_response, feasibility,
    integral_lane_widths,
)
from .capabilities import extraction_rate
from .contracts import (
    Bus, BusId, BusNotDeclared, Capability, Coverage, CreditedFlowCycle,
    ExtractionRate, ProjectedCoverage, ProjectedGoal, RealizationReport,
    RealizationRequest,
)
from .residual import EPS, coverage_for, projected_coverage_for


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

    `extraction` is READ, not carried. Each declared node is priced against the
    table, which refuses an unknown extractor, an unknown purity and a clock
    outside [1, 250] — the table is the only thing in the layer that can say a
    node declaration is unbuildable, and a parameter that nothing reads is a
    parameter that cannot refuse. The report carries the DECLARATIONS
    (`RealizationReport.extraction` is `tuple[NodeDeclaration, ...]`), because
    the declaration is the input contract and the rate is derived from it.

    Power is the sum of the lanes'. It therefore inherits `power_at_clock`'s
    refusal: a bus on a Converter, Particle Accelerator or Quantum Encoder
    raises rather than reporting free machines. That is the standing signature
    gap, not a property of this function.
    """
    buses = buses_from_response(response, data, request, capabilities)

    for node in request.nodes:
        extraction_rate(extraction, node)

    coverage: list[Coverage] = []
    projected: list[ProjectedCoverage] = []
    warnings: list[str] = []
    for bus in buses:
        declaration = request.declaration_for(bus.bus_id)
        # Mutually exclusive at the declaration, so at most one of the two
        # returns a verdict and neither function has to know about the other.
        verdict = coverage_for(bus, declaration)
        if verdict is not None:
            coverage.append(verdict)
        projection = projected_coverage_for(bus, declaration)
        if projection is not None:
            projected.append(projection)
        warnings.extend(feasibility(bus))

        trunk = bus.lanes[0].trunk if bus.lanes else None
        if trunk is not None and not integral_lane_widths(
            data, bus.recipe_id, bus.consumers, trunk
        ):
            warnings.append(
                f"{bus.bus_id}: no lane width on {trunk.capability_id} leaves "
                "every consumer at a whole machine, so the bus cannot be kept "
                "isolated at this tier and must merge. A finding, not an error."
            )
        for lane in bus.lanes:
            if lane.clock_percent <= EPS:
                warnings.append(
                    f"{bus.bus_id}: {lane.machines} machine(s) at 0% clock under "
                    f"{lane.clock_cause.value}. Building past the ceil costs build "
                    "cost and footprint and buys nothing, and a 0% clock is not "
                    "buildable in game."
                )

    return RealizationReport(
        buses=buses,
        extraction=request.nodes,
        #: ALWAYS empty here — `realize` takes no goals. See the module
        #: docstring; `project_goals` is the surface that fills this.
        projections=(),
        total_power_mw=sum(lane.power_mw for bus in buses for lane in bus.lanes),
        design_tier=request.design_tier,
        coverage=tuple(coverage),
        projected_coverage=tuple(projected),
        invalidating_unlocks=_invalidating_unlocks(data, buses),
        warnings=tuple(warnings),
    )


def credited_flow_order(
    response: SolveResponse,
    data: ReferenceData,
    request: RealizationRequest,
) -> tuple[BusId, ...]:
    """BUS ids in reverse topological order of the CREDITED flow graph.

    Bus ids, not recipe ids. Two buses of the same item — and here, of the same
    recipe — are distinct nodes with distinct draws, so a recipe-keyed order
    cannot express the graph. The edges come from each declaration's `sources`.

    Credited means byproducts are edges too: crediting a byproduct against
    demand adds an edge from its producer to every consumer of that item. The
    recipe graph can be acyclic while the credited graph is not, which is
    exactly the case this must detect.

    The derived edge set is therefore every item a declared bus PRODUCES that
    another declared bus's recipe CONSUMES — not only the secondary outputs.
    A byproduct is the motivating case and not the boundary: Recycled Plastic
    and Recycled Rubber each take the other's product as a primary input and
    close a loop with no byproduct anywhere in it. Restricting the derivation
    to secondary outputs under-detects, and an under-detecting cycle check is
    the one kind that cannot be relied on.

    Raises `CreditedFlowCycle` naming the BUS and the item. It is refused, not
    iterated toward — on a cycle the update map is non-monotone (overflow is a
    sawtooth in demand and enters with a negative sign), and no termination
    argument is available. This is the standing `_demand_oracle` defect made
    explicit rather than a new restriction.

    A credited edge is added only where the consumer's declaration is SILENT
    about that item. A declaration that names a source bus already supplies the
    edge; one that names `source_bus_id=None` has declared the draw out of
    scope, and a declaration outranks a derivation here as everywhere else —
    otherwise an out-of-scope byproduct would manufacture cycles in plans that
    have none.
    """
    order: list[BusId] = []
    declared = {d.bus_id for d in request.buses}

    #: bus -> [(consumer bus, item on the edge)]
    drawn_by: dict[BusId, list[tuple[BusId, ItemId]]] = {b: [] for b in declared}
    for declaration in request.buses:
        for edge in declaration.sources:
            if edge.source_bus_id is None:
                continue
            if edge.source_bus_id not in declared:
                raise BusNotDeclared(
                    f"{declaration.bus_id} draws {edge.input_item} from "
                    f"{edge.source_bus_id!r}, which is not declared"
                )
            drawn_by[edge.source_bus_id].append((declaration.bus_id, edge.input_item))

    attributed = _attribute(response, data, request, strict=False)
    for producer_id, use in attributed.items():
        for produced, _rate in _recipe(data, use.recipe_id).outputs:
            for consumer in request.buses:
                if consumer.bus_id == producer_id:
                    continue
                consumer_use = attributed.get(consumer.bus_id)
                if consumer_use is None:
                    continue
                if _input_rate(_recipe(data, consumer_use.recipe_id), produced) <= 0.0:
                    continue
                if any(e.input_item == produced for e in consumer.sources):
                    continue
                drawn_by[producer_id].append((consumer.bus_id, produced))

    #: 0 unvisited, 1 on the stack, 2 settled. The stack carries the item each
    #: edge was taken on, so the refusal names the item and not only the buses.
    mark: dict[BusId, int] = {}

    def visit(bus_id: BusId, path: list[str]) -> None:
        state = mark.get(bus_id, 0)
        if state == 2:
            return
        if state == 1:
            raise CreditedFlowCycle(
                "the credited flow graph has a cycle: "
                + " ".join(path + [bus_id])
                + ". A byproduct feeds a bus that transitively produces it. The "
                "demand pass is a single traversal and is not iterated toward a "
                "fixed point, so this is refused rather than approximated."
            )
        mark[bus_id] = 1
        for consumer_id, item_id in drawn_by[bus_id]:
            visit(consumer_id, path + [f"{bus_id} --{item_id}-->"])
        mark[bus_id] = 2
        order.append(bus_id)

    for declaration in request.buses:
        visit(declaration.bus_id, [])
    return tuple(order)


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
    reported at its unslooped figure. NO SITE: nothing in `Lane` expresses a
    somersloop, so there is nothing here to detect. The refusal is owed once the
    reference layer carries the multiplier.

    RATE IS GROSS — the lanes' output at their clocks, summed over every bus of
    the item. For a terminal goal item, which is what §6 is about, gross is what
    reaches the goal. For an item with in-scope automated consumers it
    OVERSTATES what reaches the goal, and the figure that does not is the bus
    residual. `ProjectedGoal` carries goal-completion time and has no field for
    storage-coverage time `T_i = bill_i / R_i`; that is respec §6 work and the
    handoff's next action 4.

    A goal on an item no declared bus produces gets rate 0.0 and `inf` minutes.
    That is the truthful report — the build as declared never completes it — and
    not a refusal, because a goal the declaration does not yet build is an
    ordinary state of a plan in progress.
    """
    projections: list[ProjectedGoal] = []
    for goal_id, item_id, total_required in totals:
        rate = sum(
            lane.output_rate_per_min
            for bus in buses
            if bus.item_id == item_id
            for lane in bus.lanes
        )
        projections.append(
            ProjectedGoal(
                goal_id=goal_id,
                item_id=item_id,
                total_required=total_required,
                rate_per_min=rate,
                minutes_to_complete=(
                    total_required / rate if rate > EPS else math.inf
                ),
            )
        )
    return tuple(projections)


def _invalidating_unlocks(
    data: ReferenceData,
    buses: tuple[Bus, ...],
) -> tuple[RecipeId, ...]:
    """The unlocks that would RE-WIRE this report, not merely cheapen it.

    An alternate is a re-wiring event: Stitched Iron Plate removes Reinforced
    Iron Plate from the screw bus entirely, 199/min -> 124/min. So the
    invalidating set is, for each consumer on each bus, every alternate recipe
    that makes what the consumer makes WITHOUT drawing on that bus's item.

    Derived from the consumer sets, declaration-shaped rather than an
    optimisation. NOT SORTED and not scored — the standing guardrail is that
    alternates are never ordered, so this is discovery order with duplicates
    dropped at first sight, and every entry is a peer.
    """
    seen: dict[RecipeId, None] = {}
    for bus in buses:
        for consumer in bus.consumers:
            if consumer.is_withdrawal:
                continue
            made = {item for item, _ in _recipe(data, consumer.recipe_id).outputs}
            for recipe_id, recipe in data.recipes.items():
                if not recipe.is_alternate:
                    continue
                if not made & {item for item, _ in recipe.outputs}:
                    continue
                if _input_rate(recipe, bus.item_id) > 0.0:
                    continue
                seen.setdefault(recipe_id, None)
    return tuple(seen)
