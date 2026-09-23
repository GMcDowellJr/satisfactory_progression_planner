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

Bodies written 2026-09-21. Three things the bodies had to settle, all recorded
here rather than resolved quietly:

    RECIPE ATTRIBUTION   a bus's recipe is ATTRIBUTED from the response: the
                         recipes the SOLVE already chose, matched to a
                         declaration by output item and by the input items its
                         `sources` name. That is attribution, not selection:
                         this layer never picks a recipe, and it refuses by name
                         when the declaration does not discriminate.
                         AMENDED 2026-09-22 by P30. `BusDeclaration` now carries
                         an optional `recipe_id`, which `busmodel.BusSpec`
                         always did. A bus the solve did not run — every
                         build-material line — is attributed from the
                         declaration instead and carries
                         `RecipeProvenance.DECLARED`. It is still not selection:
                         the CALLER named the recipe. A bus that names none and
                         has no candidate is refused exactly as before.
                         See `_attribute`
    NAMEPLATE DRAW       a consumer's draw is `machines * per-machine input
                         rate`. That is what the signature admits — the draws of
                         one bus are computed without any partial solution in
                         hand — and it reproduces the record's measured screw
                         bus exactly. It is also A4.2's PEAK basis, not A3.5's
                         AVERAGE, and `BusDeclaration` has no
                         `presents_peak_draw` to say otherwise. Next action 2
                         AMENDED 2026-09-23. A consumer's draw is now its USAGE —
                         `consumer demand * per-machine input / consumer rate` —
                         which A5.2 says is the average draw in every state, and
                         nameplate is REPORTED as `ConsumerShare.peak_per_min`.
                         The signature did not have to change: the consumer's
                         settled demand was already reachable through `_demand`'s
                         cached recursion. Nameplate had also made `_demand`'s
                         `external` term subtract a peak from an average, which
                         hid out-of-scope demand up to the consumers'
                         integrality slack. See `_draw`
                         AMENDED AGAIN 2026-09-23, amendment 12 (D1). A STORING
                         consumer draws what it PRODUCES — nameplate at 100% —
                         because its residual goes to storage instead of idling
                         it. Only a non-storing consumer draws usage. `external`
                         keeps subtracting USAGE, not the draw, so A8.2's repair
                         survives the change. See `_draw`
    SIGNATURE            `decompose` gained `bus_id` and `capabilities`. Without
                         the first it cannot reach the declaration its own
                         docstring sizes from; without the second it cannot fill
                         `LaneInput.carrier`, which is the minimum sufficient Mk
                         and not the trunk. Zero call sites at the time
"""
from __future__ import annotations

import math

from production_adapter.contracts import ItemId, RecipeId, RecipeUse, SolveResponse
from production_adapter.gamedata import Capability, ReferenceData, Recipe

from .capabilities import highest_at_tier, minimum_sufficient, by_id
from .contracts import (
    Bus, BusId, BusRecipe, BusResidual, ClockCause, ConsumerShare,
    CreditedFlowCycle, Disposition, Lane, LaneInfeasible, LaneInput, PartitionIncomplete,
    RealizationError, RealizationRequest, RecipeProvenance,
)
from .residual import EPS, clock_for, power_at_clock, power_backing_up, residual_for

#: Which item forms a carrier of each type can carry. `items.csv` carries three
#: forms — solid, liquid, gas — and `logistics_capabilities.csv` four capability
#: types. The mapping is DATA about those two tables, not a rule, so the tests
#: assert it against the CSVs rather than this module relying on it silently.
#: `miner` is deliberately absent: an extractor is not a lane carrier.
CARRIED_FORMS: dict[str, tuple[str, ...]] = {
    "belt": ("solid",),
    "conveyor_lift": ("solid",),
    "pipeline": ("liquid", "gas"),
}

#: The inverse, for picking a trunk from the item a bus carries.
CARRIER_TYPE: dict[str, str] = {
    "solid": "belt",
    "liquid": "pipeline",
    "gas": "pipeline",
}


# --------------------------------------------------------------------------
# private: reference-layer lookups that refuse rather than default
# --------------------------------------------------------------------------

def _recipe(data: ReferenceData, recipe_id: RecipeId) -> Recipe:
    recipe = data.recipes.get(recipe_id)
    if recipe is None:
        raise RealizationError(
            f"no recipe {recipe_id!r} in the reference layer "
            f"(build {data.game_build_id})"
        )
    return recipe


def _form(data: ReferenceData, item_id: ItemId) -> str:
    item = data.items.get(item_id)
    if item is None:
        raise RealizationError(
            f"no item {item_id!r} in the reference layer "
            f"(build {data.game_build_id})"
        )
    return item.form


def _carrier_type(data: ReferenceData, item_id: ItemId) -> str:
    form = _form(data, item_id)
    carrier = CARRIER_TYPE.get(form)
    if carrier is None:
        raise RealizationError(
            f"{item_id} has form {form!r}, which no carrier type in "
            f"CARRIED_FORMS covers"
        )
    return carrier


def _output_rate(recipe: Recipe, item_id: ItemId) -> float:
    for item, rate in recipe.outputs:
        if item == item_id:
            return rate
    raise RealizationError(f"{recipe.recipe_id} does not output {item_id}")


def _input_rate(recipe: Recipe, item_id: ItemId) -> float:
    for item, rate in recipe.inputs:
        if item == item_id:
            return rate
    return 0.0


def _binding(
    data: ReferenceData,
    recipe: Recipe,
    trunk: Capability,
) -> tuple[float, str]:
    """Per-machine (rate, side) on the side the trunk binds.

    Only items the trunk can CARRY are compared: each item rides its own belt,
    so a fluid input does not bind a lane against a conveyor. An item the trunk
    cannot carry needs a carrier of its own, which is what `LaneInput.carrier`
    is for.

    Ties go to "output". A recipe whose largest input rate equals its output
    rate is bound equally on both sides; naming the output is the bus's own
    side and is reported rather than left to dictionary order.
    """
    forms = CARRIED_FORMS.get(trunk.capability_type)
    if forms is None:
        raise RealizationError(
            f"{trunk.capability_id} is a {trunk.capability_type}, which "
            f"CARRIED_FORMS does not list as a lane carrier"
        )
    best_rate = 0.0
    best_side = "output"
    for item, rate in recipe.outputs:
        if _form(data, item) in forms and rate > best_rate:
            best_rate, best_side = rate, "output"
    for item, rate in recipe.inputs:
        if _form(data, item) in forms and rate > best_rate + EPS:
            best_rate, best_side = rate, "input"
    if best_rate <= 0.0:
        raise RealizationError(
            f"{recipe.recipe_id} moves nothing a {trunk.capability_type} can "
            f"carry, so a {trunk.capability_id} trunk binds no side of it"
        )
    return best_rate, best_side


def _source_of(request: RealizationRequest, bus_id: BusId, item_id: ItemId) -> BusId | None:
    """Which bus a declaration draws `item_id` from. `None` = out of scope.

    An input ABSENT from `sources` is out of scope too — `BusDeclaration` says
    so in as many words — so this cannot distinguish "declared None" from
    "unmentioned", and nothing here needs it to. `credited_flow_order` does, and
    reads `sources` directly for that reason.
    """
    for edge in request.declaration_for(bus_id).sources:
        if edge.input_item == item_id:
            return edge.source_bus_id
    return None


# --------------------------------------------------------------------------
# private: recipe attribution
# --------------------------------------------------------------------------

def _attribute(
    response: SolveResponse,
    data: ReferenceData,
    request: RealizationRequest,
    *,
    strict: bool = True,
) -> dict[BusId, BusRecipe]:
    """Which recipe runs on each declared bus, and on whose word. P30.

    This is attribution, never selection. The solver has already chosen the
    recipe set; the declaration says how that set is partitioned into buses, and
    this reads the two against each other. A bus matches a `RecipeUse` when the
    recipe outputs the bus's item AND consumes every input the bus's `sources`
    name — which is exactly how amendment 3 distinguishes two buses of one item:
    wire_iron declares `SourceEdge(Iron Ingot, ...)` and wire_copper declares
    `SourceEdge(Copper Ingot, ...)`, and nothing in the solve says which is
    which.

    Two provenances since 2026-09-22, and the result carries which:

        SOLVED     matched to a `RecipeUse`. Unchanged behaviour, and the only
                   behaviour for a bus the solve ran
        DECLARED   `BusDeclaration.recipe_id` named a recipe the solve did not
                   run. Every build-material line lands here — Concrete, Cable,
                   the Iron Plate build stock — because the solver does not
                   model them. The solve has NO ACCOUNT of such a bus, which is
                   why `BusRecipe.machine_equivalents` is None rather than 0.0

    A declared `recipe_id` is the CALLER choosing, not this layer: it is the
    same authority `sources` already carries, one step further. It therefore
    also settles the several-candidates case, which is a disambiguation rather
    than a selection.

    The declared recipe is CHECKED against the reference layer before it is
    believed — it must exist, output the bus's item, and consume every input
    `sources` names. A declaration that contradicts the reference layer is
    refused by name rather than carried into the sizing.

    Refuses by name in four cases, none of which this layer may resolve:

        no candidate        the solve ran no recipe that produces the item with
                            the declared inputs, AND the declaration names none
        several candidates  the declaration discriminates by neither `sources`
                            nor `recipe_id`. Choosing would be choosing a recipe
        declared recipe     the named recipe does not output the bus's item, or
        does not fit        does not consume an input `sources` names
        one recipe, two     two declared buses attributed to one recipe would
        buses               double-count `machine_equivalents` and collapse
                            `_check_partition`'s recipe -> bus map. KNOWN
                            LIMITATION with a consumer: a build-material line
                            for an item the solve also produces on the same
                            recipe cannot be declared alongside it. Recorded
                            2026-09-22; P30 does not close it, and closing it
                            needs bus identity beyond (item, sources, recipe).
                            NARROWED 2026-09-23: refused only where the solve
                            RAN the recipe. Two DECLARED buses on one recipe
                            carry no `machine_equivalents` and appear nowhere
                            in `response.recipes`, so neither reason applies —
                            and `worked_case_A4`'s two Iron Plate buses are
                            exactly that case

    `RealizationError` rather than a named subclass: there is no
    `AmbiguousAttribution` in `contracts.py`, and adding one is a patch.

    `strict=False` returns what could be attributed and refuses nothing. It is
    for `credited_flow_order`, which must produce an order for a declaration it
    cannot fully attribute — otherwise a build-material line outside the solve
    would make the ORDER unobtainable as well as the sizing, and the refusal
    would arrive from the wrong function. The gap is not thereby silent:
    `buses_from_response` attributes strictly and refuses by name.
    """
    by_bus: dict[BusId, BusRecipe] = {}
    claimed: dict[RecipeId, BusId] = {}
    for declaration in request.buses:
        declared_inputs = {e.input_item for e in declaration.sources}
        candidates: list[RecipeUse] = []
        for use in response.recipes:
            recipe = _recipe(data, use.recipe_id)
            if not any(item == declaration.item_id for item, _ in recipe.outputs):
                continue
            if not declared_inputs <= {item for item, _ in recipe.inputs}:
                continue
            candidates.append(use)

        named = declaration.recipe_id
        if named is not None:
            # The declaration is authoritative, so it is CHECKED first. An
            # unknown recipe is refused by `_recipe` naming the store and the
            # build.
            #
            # Under `strict=False` a contradictory declaration is SKIPPED, not
            # raised. The lenient pass exists so `credited_flow_order` can order
            # a declaration it cannot fully attribute; a refusal from there is
            # the refusal arriving from the wrong function, which is the exact
            # failure the lenient path was added to prevent.
            declared_recipe = data.recipes.get(named)
            if declared_recipe is None:
                if not strict:
                    continue
                _recipe(data, named)   # refuses by name, naming store and build
            if not any(item == declaration.item_id for item, _ in declared_recipe.outputs):
                if not strict:
                    continue
                raise RealizationError(
                    f"{declaration.bus_id}: declares recipe_id {named!r}, which "
                    f"does not output {declaration.item_id} in the reference "
                    f"layer (build {data.game_build_id}). A bus carries the item "
                    "its recipe produces."
                )
            missing = declared_inputs - {item for item, _ in declared_recipe.inputs}
            if missing:
                if not strict:
                    continue
                raise RealizationError(
                    f"{declaration.bus_id}: declares recipe_id {named!r}, which "
                    f"does not consume {sorted(missing)}. The bus names a source "
                    "for an input its own recipe does not take."
                )
            matched = [use for use in candidates if use.recipe_id == named]
            attribution = (
                BusRecipe(
                    recipe_id=named,
                    provenance=RecipeProvenance.SOLVED,
                    machine_equivalents=matched[0].machine_equivalents,
                )
                if matched
                else BusRecipe(recipe_id=named, provenance=RecipeProvenance.DECLARED)
            )
        else:
            if len(candidates) != 1 and not strict:
                continue
            if not candidates:
                raise RealizationError(
                    f"{declaration.bus_id}: the solve ran no recipe that outputs "
                    f"{declaration.item_id} and consumes "
                    f"{sorted(declared_inputs) or '[]'}. Checked "
                    f"SolveResponse.recipes ({len(response.recipes)} entries) "
                    f"against the reference layer, build {data.game_build_id}. "
                    "The declaration names no recipe_id to fall back on, so a "
                    "bus outside the solve — a build-material line — cannot be "
                    "sized here. Set BusDeclaration.recipe_id (P30)."
                )
            if len(candidates) > 1:
                raise RealizationError(
                    f"{declaration.bus_id}: {len(candidates)} of the solve's recipes "
                    f"output {declaration.item_id} and accept the declared inputs "
                    f"({sorted(c.recipe_id for c in candidates)}). The declaration "
                    "does not discriminate and this layer does not choose a recipe: "
                    "name more of the bus's inputs in `sources`, or state the "
                    "recipe in BusDeclaration.recipe_id."
                )
            use = candidates[0]
            attribution = BusRecipe(
                recipe_id=use.recipe_id,
                provenance=RecipeProvenance.SOLVED,
                machine_equivalents=use.machine_equivalents,
            )

        other = claimed.get(attribution.recipe_id)
        # Two DECLARED buses on one recipe are admitted (2026-09-23). Neither
        # reason for the refusal below applies to them: both carry
        # `machine_equivalents=None`, so there is no figure to double-count,
        # and `_check_partition` walks `response.recipes` alone, which holds
        # neither. The refusal stands wherever the solve ran the recipe.
        if (
            other is not None
            and attribution.provenance is RecipeProvenance.DECLARED
            and by_bus[other].provenance is RecipeProvenance.DECLARED
        ):
            other = None
        if other is not None and not strict:
            continue
        if other is not None:
            raise PartitionIncomplete(
                f"{attribution.recipe_id} is attributed to both {other!r} and "
                f"{declaration.bus_id!r}. Two buses running one recipe share one "
                "machine_equivalents figure, and splitting it is a design "
                "decision the response does not carry. A declared "
                "build-material line on a recipe the solve also runs lands here "
                "and is a known limitation, not a malformed declaration."
            )
        claimed[attribution.recipe_id] = declaration.bus_id
        by_bus[declaration.bus_id] = attribution
    return by_bus


# --------------------------------------------------------------------------
# lanes
# --------------------------------------------------------------------------

def machines_per_lane(
    data: ReferenceData,
    recipe_id: RecipeId,
    trunk: Capability,
) -> int:
    """How many producers of `recipe_id` one trunk belt carries on the binding side.

    Returns 0 when a single machine already exceeds the trunk; the caller
    raises `LaneInfeasible` rather than emitting a fractional lane.

    Measured at 100% CLOCK, deliberately. A clocked lane moves less and would
    admit more machines per belt, but a belt sized against a clock is a belt
    that saturates the moment the clock is raised, and the clock is not in this
    signature to be read anyway.
    """
    recipe = _recipe(data, recipe_id)
    binding_rate, _ = _binding(data, recipe, trunk)
    return int(math.floor((trunk.capacity_per_min + EPS) / binding_rate))


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

    Withdrawal consumers (`recipe_id is None`) are skipped: a player drawing
    from a container is not a machine and has no whole number to land on.
    """
    recipe = _recipe(data, recipe_id)
    produced = tuple(item for item, _ in recipe.outputs)
    if not produced:
        raise RealizationError(f"{recipe_id} has no output to run a bus on")
    rate = _output_rate(recipe, produced[0])

    draws: list[float] = []
    for consumer in consumers:
        if consumer.is_withdrawal:
            continue
        per_machine = _input_rate(_recipe(data, consumer.recipe_id), produced[0])
        if per_machine > 0.0:
            draws.append(per_machine)

    widths: list[int] = []
    for width in range(1, machines_per_lane(data, recipe_id, trunk) + 1):
        supply = width * rate
        if all(
            abs(supply / draw - round(supply / draw)) <= EPS
            for draw in draws
        ):
            widths.append(width)
    return tuple(widths)


def decompose(
    data: ReferenceData,
    recipe_id: RecipeId,
    demand_per_min: float,
    consumers: tuple[ConsumerShare, ...],
    trunk: Capability,
    capabilities: tuple[Capability, ...],
    request: RealizationRequest,
    bus_id: BusId,
) -> tuple[Lane, ...]:
    """Split a bus's producers into whole lanes.

    Machine count is the bus total — `ceil(demand / rate) + extra_producers` —
    and lanes partition it. Distribution across lanes is by minimum total
    machines, balanced, one clock. Fill-then-spill is dominated: equal machines
    and equal residual, worse power, and two clock settings rather than one.

    Power does NOT decide the machine count. P = P_base * (D/r)^e * N^(1-e)
    with e > 1 is strictly decreasing in N without bound, so a power objective
    always answers "more machines" and has no interior optimum.

    SIGNATURE, widened 2026-09-21 against zero call sites. `bus_id` because the
    sizing rule above reads `extra_producers` and the clock reads `disposition`,
    both per-bus declarations this function could not reach through `request`
    alone. `capabilities` because `LaneInput.carrier` is the MINIMUM SUFFICIENT
    Mk for that one input, which is not the trunk and cannot be derived from it.

    `consumers` is carried and not read. The distribution rule above fixes the
    widths, so there is no freedom left for integrality to decide, and re-sizing
    the bus until `integral_lane_widths` is non-empty would add machines the
    demand does not need. Integrality is REPORTED by that function; it is not
    an objective here.

    Under `ClockDistribution.SPLIT` the machines do not share a clock, so a run
    of equal clocks becomes its own group of lanes — including the 0% group,
    which is the machine past the ceil that has nothing to do. A 0% clock is not
    buildable in game; §4 measures that case and it is reported rather than
    smoothed away.
    """
    declaration = request.declaration_for(bus_id)
    recipe = _recipe(data, recipe_id)
    rate = _output_rate(recipe, declaration.item_id)
    if rate <= 0.0:
        raise RealizationError(f"{bus_id}: {recipe_id} outputs {rate}/min")

    per_lane = machines_per_lane(data, recipe_id, trunk)
    if per_lane < 1:
        binding_rate, side = _binding(data, recipe, trunk)
        raise LaneInfeasible(
            f"{bus_id}: one {recipe.producer_class} binds {binding_rate}/min on "
            f"its {side} side, which exceeds {trunk.capability_id} at "
            f"{trunk.capacity_per_min}/min. No whole number of machines fits."
        )

    #: The machine floor is the rule recovered in `tools/busmodel` — every
    #: declared line gets at least one machine. Without it a declared bus whose
    #: demand rounds to nothing disappears from its own report.
    total = max(1, math.ceil(demand_per_min / rate - EPS)) + declaration.extra_producers
    nameplate = total * rate
    clocks = clock_for(declaration, demand_per_min, nameplate, total)

    binding_rate, binding_side = _binding(data, recipe, trunk)
    producer = data.producers[recipe.producer_class]

    lanes: list[Lane] = []
    for clock, cause, count in _runs(clocks):
        groups = max(1, math.ceil(count / per_lane))
        base, extra = divmod(count, groups)
        widths = [base + 1] * extra + [base] * (groups - extra)
        for width in widths:
            if width < 1:
                continue
            scale = width * clock / 100.0
            lanes.append(
                Lane(
                    recipe_id=recipe_id,
                    producer_class=recipe.producer_class,
                    machines=width,
                    clock_percent=clock,
                    clock_cause=cause,
                    output_item=declaration.item_id,
                    output_rate_per_min=rate * scale,
                    binding_side=binding_side,
                    binding_rate_per_min=binding_rate * scale,
                    trunk=trunk,
                    inputs=tuple(
                        LaneInput(
                            item_id=item,
                            rate_per_min=per_min * scale,
                            carrier=minimum_sufficient(
                                capabilities,
                                _carrier_type(data, item),
                                request.design_tier,
                                per_min * scale,
                            ),
                            source_bus_id=_source_of(request, bus_id, item),
                        )
                        for item, per_min in recipe.inputs
                    ),
                    power_mw=_lane_power(producer, width, clock, cause),
                )
            )
    return tuple(lanes)


def _runs(
    clocks: tuple[tuple[float, ClockCause], ...],
) -> tuple[tuple[float, ClockCause, int], ...]:
    """Consecutive equal (clock, cause) entries, as (clock, cause, count).

    One Lane carries one clock, so machines at different clocks cannot share a
    lane. Under AVERAGED and BACKPRESSURE this is a single run and the grouping
    is a no-op; under SPLIT it is what keeps the report truthful.
    """
    runs: list[tuple[float, ClockCause, int]] = []
    for clock, cause in clocks:
        if runs and abs(runs[-1][0] - clock) <= EPS and runs[-1][1] is cause:
            clock_, cause_, count = runs[-1]
            runs[-1] = (clock_, cause_, count + 1)
        else:
            runs.append((clock, cause, 1))
    return tuple(runs)


def _lane_power(producer, machines: int, clock: float, cause: ClockCause) -> float:
    """Convex in a CLOCK, linear in a DUTY CYCLE. The cause picks which.

    `ClockCause.BACKPRESSURE` means belts idle the machines: that is a duty
    cycle and power is linear in it. Every other cause is a clock the machine is
    actually set to, and power follows `power_exponent`. On the record's screw
    bus at 5 machines and 99.5%: 19.90 MW backing up, 19.87 MW clocked.
    """
    if cause is ClockCause.BACKPRESSURE:
        return power_backing_up(producer, machines, clock / 100.0)
    return power_at_clock(producer, clock, machines)


# --------------------------------------------------------------------------
# buses
# --------------------------------------------------------------------------

def _draw(
    response: SolveResponse,
    data: ReferenceData,
    request: RealizationRequest,
    consumer_id: BusId,
    item_id: ItemId,
    attributed: dict[BusId, BusRecipe],
    cache: dict[BusId, int | None],
) -> tuple[float, float, float]:
    """`(draw, peak, usage)` — what one consumer bus draws of `item_id`.

        draw    what SIZES the source bus. Amendment 12 (D1): a STORING
                consumer (`stores=True`) runs at its clock and sends its
                residual to storage, so it draws what it PRODUCES — its supply
                at its clock, which is nameplate while that clock is 100%. A
                non-storing consumer draws its usage. Written as supply rather
                than as `peak` so that a target clock (D2) moves the draw
                without a second rule

        usage   consumer demand * per-machine input / consumer output rate.
                A5.2: the AVERAGE draw once a line's buffer has saturated.
                Sizes a non-storing consumer's source; always what `external`
                subtracts
        peak    consumer machines * per-machine input — nameplate. Equal to usage
                under MATCHED, where the consumer is clocked to its demand and
                has no transient to have. REPORTED, and read by `feasibility`
                for branch capacity and connectivity, which are questions about
                what a belt must carry rather than about how many machines

    Mirrors `busmodel.solve` under `SizingBasis.STORAGE` (A12; `USAGE` until
    then). A peak that can move a
    machine count is `presents_peak_draw` again under a new name, so the sizing
    path reads `draw` and never `peak` and a test re-solves with peaks an order
    of magnitude apart and expects no machine count to move.
    """
    consumer = request.declaration_for(consumer_id)
    use = attributed[consumer_id]
    recipe = _recipe(data, use.recipe_id)
    per_machine = _input_rate(recipe, item_id)
    rate = _output_rate(recipe, consumer.item_id)
    if rate <= 0.0:
        raise RealizationError(f"{consumer_id}: {use.recipe_id} outputs {rate}/min")
    machines = _machines(response, data, request, consumer_id, attributed, cache)
    demand = _demand(response, data, request, consumer_id, attributed, cache)
    usage = demand * per_machine / rate
    peak = usage if consumer.disposition is Disposition.MATCHED else machines * per_machine
    if consumer.stores:
        supply = machines * rate   # every lane at 100%; no target clock yet
        draw = supply * per_machine / rate
    else:
        draw = usage
    return draw, peak, usage


def consumer_shares(
    response: SolveResponse,
    data: ReferenceData,
    request: RealizationRequest,
    bus_id: BusId,
) -> tuple[ConsumerShare, ...]:
    """Every consumer's claim on ONE BUS, as ratios over automated demand.

    Renamed from `partition`, which after amendment 3 means the bus partition —
    a declaration this function does not make. Keyed by bus rather than item,
    because two buses of one item have different consumers by construction.

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

    AMENDED 2026-09-23. `draw_per_min` is the consumer's USAGE and
    `peak_per_min` its nameplate — see `_draw`. The measured example above is a
    PEAK figure: it holds only where the solve runs each Assembler at a whole
    machine, which is what `worked_response()` feeds. On a continuous solve of
    the same chain the usage draws are 30 and 62. The text this replaces said
    the signature admitted only nameplate; it did not — the consumer's settled
    demand was reachable through `_demand` all along.

    Consumers come out in `request.buses` order. Caller order is preserved, per
    the standing guardrail against this layer ranking anything.
    """
    declaration = request.declaration_for(bus_id)
    attributed = _attribute(response, data, request)
    cache: dict[BusId, int | None] = {}

    shares: list[tuple[RecipeId, float]] = []
    for consumer in request.buses:
        if consumer.bus_id == bus_id:
            continue
        if not any(
            edge.input_item == declaration.item_id and edge.source_bus_id == bus_id
            for edge in consumer.sources
        ):
            continue
        use = attributed[consumer.bus_id]
        draw, peak, _usage = _draw(
            response, data, request, consumer.bus_id, declaration.item_id,
            attributed, cache,
        )
        shares.append((use.recipe_id, draw, peak))

    automated = sum(draw for _, draw, _ in shares)
    out = [
        ConsumerShare(
            recipe_id=recipe_id,
            draw_per_min=draw,
            share=(draw / automated) if automated > 0.0 else 0.0,
            peak_per_min=peak,
        )
        for recipe_id, draw, peak in shares
    ]
    if declaration.withdrawal_per_min is not None:
        # `share=None`, not 0.0. Withdrawal is not in the denominator: it is
        # covered by the residual rather than sized into the bus, which is what
        # makes A3.5's `R >= withdraw` verdict mean anything.
        # A player's own draw carries no modelled transient, so its peak is
        # the declared rate — the same rule `busmodel.solve` follows.
        out.append(
            ConsumerShare(
                recipe_id=None,
                draw_per_min=declaration.withdrawal_per_min,
                share=None,
                peak_per_min=declaration.withdrawal_per_min,
            )
        )
    return tuple(out)


def _machines(
    response: SolveResponse,
    data: ReferenceData,
    request: RealizationRequest,
    bus_id: BusId,
    attributed: dict[BusId, BusRecipe],
    cache: dict[BusId, int | None],
) -> int:
    """Whole machines on one bus. This layer is where `effective_count` stops
    being fractional.

    `ceil(demand / rate) + extra_producers`, with the recovered machine floor of
    one. The demand is the bus's own sizing demand — see `_demand` — and never
    a re-derivation of the solve.

    `cache` is what makes the pass a SINGLE traversal rather than one that
    revisits. `_machines` and `_demand` are mutually recursive — a bus's size
    needs its consumers' sizes — so without it the same bus is recomputed once
    per path that reaches it, which is exponential in the chain depth and is a
    different algorithm from the one the demand pass is specified as. A `None`
    in the cache marks a bus whose size is still being computed, which is a
    cycle: refused by name, never iterated toward.
    """
    if bus_id in cache:
        settled = cache[bus_id]
        if settled is None:
            raise CreditedFlowCycle(
                f"{bus_id} transitively draws on itself. The demand pass is a "
                "single traversal and is not iterated toward a fixed point."
            )
        return settled
    cache[bus_id] = None

    declaration = request.declaration_for(bus_id)
    use = attributed[bus_id]
    rate = _output_rate(_recipe(data, use.recipe_id), declaration.item_id)
    if rate <= 0.0:
        raise RealizationError(f"{bus_id}: {use.recipe_id} outputs {rate}/min")
    demand = _demand(response, data, request, bus_id, attributed, cache)
    machines = max(1, math.ceil(demand / rate - EPS)) + declaration.extra_producers
    cache[bus_id] = machines
    return machines


def _demand(
    response: SolveResponse,
    data: ReferenceData,
    request: RealizationRequest,
    bus_id: BusId,
    attributed: dict[BusId, BusRecipe],
    cache: dict[BusId, int | None],
) -> float:
    """The demand that SIZES a bus: in-scope + declared withdrawal + out-of-scope.

        automated   derived from the declared consumers. Never declared — that
                    was A2.1's standing half. Their USAGE since 2026-09-23 (see
                    `_draw`), which is also what makes `external` below
                    coherent: the solve's figure is continuous, and subtracting
                    nameplate from it netted genuine out-of-scope demand against
                    the consumers' integrality slack and reported zero
        withdrawal  DECLARED, on a build-material line
        external    `machine_equivalents * rate` less the in-scope draw, floored
                    at zero. The solve sized this recipe for demand the
                    declaration does not model — the Space Elevator part rate at
                    the root, or a consumer left out of scope — and this is that
                    demand, read from the response rather than re-derived. It is
                    the analog of `busmodel.Declaration.external_per_min`, which
                    `RealizationRequest` has no field for.
                    ZERO on a `RecipeProvenance.DECLARED` bus, and not by
                    arithmetic: the solve has no account of that bus at all, so
                    there is no external demand to read. Absence, not a measured
                    zero — which is why `BusRecipe.machine_equivalents` is
                    `None` there and this branches on the `None` instead of
                    multiplying a 0.0 nobody measured (P30)

    This is NOT `Bus.automated_demand_per_min`, which is the in-scope draw
    alone. The two differ by withdrawal and external, and the difference is
    deliberate: `residual_for` computes `R = supply - automated`, so a root bus
    reports its whole output as residual — which is what it is, since the
    consumer is out of scope — and that is how the records get Cable 30.00/min
    and Concrete 15.00/min of overflow against zero automated demand.
    """
    declaration = request.declaration_for(bus_id)
    use = attributed[bus_id]
    rate = _output_rate(_recipe(data, use.recipe_id), declaration.item_id)

    automated = 0.0
    #: A12. USAGE alone, for `external`. A storing consumer's draw is what it
    #: produces, and subtracting THAT from the solve's continuous figure is
    #: exactly the peak-minus-average A8.2 repaired.
    in_scope_usage = 0.0
    for consumer in request.buses:
        if consumer.bus_id == bus_id:
            continue
        if not any(
            edge.input_item == declaration.item_id and edge.source_bus_id == bus_id
            for edge in consumer.sources
        ):
            continue
        draw, _peak, usage = _draw(
            response, data, request, consumer.bus_id, declaration.item_id,
            attributed, cache,
        )
        automated += draw
        in_scope_usage += usage

    external = (
        0.0
        if use.machine_equivalents is None
        else max(0.0, use.machine_equivalents * rate - in_scope_usage)
    )
    return automated + (declaration.withdrawal_per_min or 0.0) + external


def buses_from_response(
    response: SolveResponse,
    data: ReferenceData,
    request: RealizationRequest,
    capabilities: tuple[Capability, ...],
) -> tuple[Bus, ...]:
    """Every DECLARED bus, in reverse topological order of the credited flow.

    AUTHORITY: `request.buses` enumerates the buses. The response supplies flows
    into them and contains no partition — nothing in a solve says that Wire runs
    as two unconnected buses, because that is a design choice and not a property
    of the recipe set.

    Reads `RecipeUse.machine_equivalents` and `ItemFlow`, and nothing else from
    the response. Does not re-derive the solve.

    Raises `PartitionIncomplete` when a consumer of a declared item is claimed
    by no declared bus or by more than one.

    `supply_per_min` is NAMEPLATE — `machines * rate` at 100% — and not the sum
    of the lanes' clocked output. The record's screw bus is 5 machines, supply
    200, R = 1.0/min under a state in which the lanes may be running at 99.5%,
    and `residual_for` derives its utilisation from that same nameplate. A lane
    reports its own rate AT ITS CLOCK, which is what `project_goals` reads.
    """
    attributed = _attribute(response, data, request)
    _check_partition(response, data, request, attributed)

    # `ItemFlow` is read for the reconciliation warning only. It is the solve's
    # own account of an item and is deliberately not allowed to size anything:
    # it is keyed by ITEM, and an item may run on several buses.
    flows = {flow.item_id: flow for flow in response.items}
    cache: dict[BusId, int | None] = {}

    buses: list[Bus] = []
    for bus_id in _order(response, data, request):
        declaration = request.declaration_for(bus_id)
        use = attributed[bus_id]
        recipe = _recipe(data, use.recipe_id)
        rate = _output_rate(recipe, declaration.item_id)

        consumers = consumer_shares(response, data, request, bus_id)
        automated = sum(c.draw_per_min for c in consumers if not c.is_withdrawal)
        machines = _machines(response, data, request, bus_id, attributed, cache)
        demand = _demand(response, data, request, bus_id, attributed, cache)

        trunk = (
            by_id(capabilities, request.trunk_capability)
            if request.trunk_capability is not None
            else highest_at_tier(
                capabilities,
                _carrier_type(data, declaration.item_id),
                request.design_tier,
            )
        )
        lanes = decompose(
            data, use.recipe_id, demand, consumers, trunk, capabilities, request, bus_id,
        )

        bus = Bus(
            bus_id=bus_id,
            item_id=declaration.item_id,
            recipe_id=use.recipe_id,
            supply_per_min=machines * rate,
            automated_demand_per_min=automated,
            withdrawal_per_min=declaration.withdrawal_per_min or 0.0,
            lanes=lanes,
            consumers=consumers,
            #: Placeholder, replaced immediately below. `Bus` is frozen and
            #: `residual_for` takes a whole `Bus`, so the object is built once
            #: with a zero residual and once with the real one rather than
            #: duplicating `residual_for`'s branch table here.
            residual=BusResidual(
                bus_id=bus_id,
                item_id=declaration.item_id,
                rate_per_min=0.0,
                disposition=declaration.disposition,
                power_cost_mw=0.0,
            ),
        )
        buses.append(
            Bus(
                bus_id=bus.bus_id,
                item_id=bus.item_id,
                recipe_id=bus.recipe_id,
                supply_per_min=bus.supply_per_min,
                automated_demand_per_min=bus.automated_demand_per_min,
                withdrawal_per_min=bus.withdrawal_per_min,
                lanes=bus.lanes,
                consumers=bus.consumers,
                residual=residual_for(data, bus, declaration),
            )
        )
        # P30. The reconciliation is against the SOLVE'S own account of the
        # item, so it can only be required of a bus the solve ran. A DECLARED
        # bus is by definition one the solve has no account of — demanding an
        # `ItemFlow` for it moves the refusal one step later and blocks exactly
        # the build-material lines `recipe_id` exists to unblock.
        if use.provenance is RecipeProvenance.SOLVED and flows.get(declaration.item_id) is None:
            raise RealizationError(
                f"{bus_id}: the response carries no ItemFlow for "
                f"{declaration.item_id}, so the solve's own account of the item "
                "cannot be read back"
            )
    return tuple(buses)


def _check_partition(
    response: SolveResponse,
    data: ReferenceData,
    request: RealizationRequest,
    attributed: dict[BusId, BusRecipe],
) -> None:
    """The partition-coverage tripwire. The last of the four candidates to get a site.

    A declared partition is not DERIVED from the consumer set — amendment 3
    contradicts that — but it is CHECKED against it. For every declared item,
    every recipe in the solve that consumes it must be attributed to exactly one
    declared bus, and that bus must name a source for it. A consumer claimed by
    nobody is a draw nothing is sized for; a consumer claimed twice is a draw
    counted twice.
    """
    declared_items = {d.item_id for d in request.buses}
    bus_of_recipe = {use.recipe_id: bus_id for bus_id, use in attributed.items()}

    for item_id in sorted(declared_items):
        for use in response.recipes:
            recipe = _recipe(data, use.recipe_id)
            if _input_rate(recipe, item_id) <= 0.0:
                continue
            consumer_bus = bus_of_recipe.get(use.recipe_id)
            if consumer_bus is None:
                raise PartitionIncomplete(
                    f"{use.recipe_id} consumes {item_id}, which is declared, but "
                    "no declared bus runs that recipe. The draw is real and "
                    "nothing is sized for it."
                )
            sources = [
                e for e in request.declaration_for(consumer_bus).sources
                if e.input_item == item_id
            ]
            if not sources:
                raise PartitionIncomplete(
                    f"{consumer_bus} runs {use.recipe_id}, which consumes the "
                    f"declared item {item_id}, and names no source bus for it. "
                    "Declare the source, or declare it out of scope with "
                    "source_bus_id=None."
                )
            # `BusDeclaration.__post_init__` already refuses two source edges
            # for one input, so "claimed by more than one" cannot arise from a
            # single declaration; it arises from two buses of one item both
            # attributed to the same recipe, which `_attribute` refuses.


def _order(
    response: SolveResponse,
    data: ReferenceData,
    request: RealizationRequest,
) -> tuple[BusId, ...]:
    """Reverse-topological bus order. Imported by `realize.credited_flow_order`,
    which is the public surface and carries the reasoning."""
    from .realize import credited_flow_order

    return credited_flow_order(response, data, request)


def feasibility(bus: Bus) -> tuple[str, ...]:
    """The three checks that replace emitting a splitter topology.

        supply >= demand        otherwise the bus is in deficit, nobody backs
                                up, and the nominal ratio decides who starves
        branch capacity         every consumer's branch carries its PEAK, or
                                it starves regardless of backpressure. The
                                peak, not the usage: a belt has to carry what
                                the machine draws while it runs, and a
                                consumer at 40% utilisation still draws at
                                nameplate whenever it is not paused
        connectivity            a consumer reachable from the producers

    Returns the failures, empty when the bus is sound. Deficit is reported
    rather than repaired: the repair is one more producer, and choosing to
    build it is the caller's.

    Connectivity is checked STRUCTURALLY, not geometrically: this layer emits no
    topology, so there is no graph to walk. What it can say is that a bus with
    no producers reaches nobody, and that a consumer drawing nothing is not
    connected to anything the bus carries. A real reachability check needs a
    placed layout and belongs to phase 5.
    """
    failures: list[str] = []

    if bus.in_deficit:
        failures.append(
            f"{bus.bus_id}: supply {bus.supply_per_min:g}/min is below automated "
            f"demand {bus.automated_demand_per_min:g}/min. Nobody backs up, so "
            "the nominal splitter ratio decides who starves. One more producer "
            "removes the problem."
        )

    for consumer in bus.consumers:
        branch = max((lane.trunk.capacity_per_min for lane in bus.lanes), default=0.0)
        if branch > 0.0 and consumer.peak_per_min > branch + EPS:
            who = consumer.recipe_id or "player withdrawal"
            failures.append(
                f"{bus.bus_id}: {who} draws {consumer.peak_per_min:g}/min, which "
                f"exceeds one branch at {branch:g}/min. It starves regardless of "
                "backpressure until the branch is split or the Mk raised."
            )

    if not bus.lanes:
        failures.append(
            f"{bus.bus_id}: no producers, so no consumer is reachable from them."
        )
    # The PEAK here too. A consumer held at the machine floor with no demand
    # has a usage of zero and is still connected; what says it is not is a
    # recipe that consumes nothing this bus carries, and that is peak zero.
    for consumer in bus.consumers:
        if consumer.peak_per_min <= EPS:
            who = consumer.recipe_id or "player withdrawal"
            failures.append(
                f"{bus.bus_id}: {who} is listed as a consumer and draws nothing. "
                "It is not connected to anything this bus carries."
            )

    return tuple(failures)
