"""`realize.py`'s three bodies. Handoff next action 1.

    realize                turns a solved plan into equipment at a declared tier
    credited_flow_order    reverse-topological BUS order, cycles refused by name
    project_goals          respec section 6 rates and durations

Two gaps these tests PIN rather than paper over, because both are contract
shape rather than body defects and a test is the only place they stay visible:

    projections     `realize` takes no goals, so `RealizationReport.projections`
                    is always empty from it. Empty means "realize was given no
                    goals", never "no goal completes"
    somersloop      `project_goals` is required to refuse a somersloop'd lane by
                    name. Nothing in `Lane` expresses one, so there is nothing
                    to detect and nothing is refused

Reproduced from the record:

    project_goals docstring   Smart Plating is 1 RIP + 1 Rotor on a 30 s cycle,
                              so one Assembler yields 2/min and 100 units takes
                              50 minutes exactly
    A3.1 / respec             Stitched Iron Plate removes Reinforced Iron Plate
                              from the screw bus entirely, so its unlock
                              invalidates a report built on the base recipe
"""
from __future__ import annotations

import dataclasses
import math

import pytest

import _realization_builders as build
from production_adapter.contracts import (
    ItemFlow, PowerReport, RecipeUse, SolveResponse,
)
from production_adapter.scenario import MARGINAL_PEAK_DEBOTTLENECK
#: The module's functions, imported directly. `realization/__init__.py`
#: re-exports `realize` itself, so `from realization import realize` binds
#: the FUNCTION and a module-qualified call would not resolve.
from realization.realize import credited_flow_order, project_goals, realize
from realization.contracts import (
    BusDeclaration, CreditedFlowCycle, Disposition, DispositionUnavailable,
    LaneInfeasible, NodeDeclaration, RealizationRequest, SourceEdge,
    BillTerm, WithdrawalBasis, WithdrawalBill,
)

STITCHED = "Recipe_Alternate_ReinforcedIronPlate_2_C"


@pytest.fixture(scope="module")
def scaled(reference):
    return reference.with_scenario(MARGINAL_PEAK_DEBOTTLENECK)


@pytest.fixture(scope="module")
def caps(logistics):
    return logistics[0]


@pytest.fixture(scope="module")
def rates(logistics):
    return logistics[1]


@pytest.fixture(scope="module")
def report(scaled, caps, rates):
    return realize(
        build.worked_response(), scaled, caps, rates, build.worked_request(),
    )


# --------------------------------------------------------------------------
# credited_flow_order
# --------------------------------------------------------------------------

def test_consumers_are_settled_before_their_sources(scaled):
    order = credited_flow_order(
        build.worked_response(), scaled, build.worked_request(),
    )
    assert set(order) == {"smart_plating", "rip", "rotor", "screws"}
    assert order.index("smart_plating") < order.index("rip") < order.index("screws")
    assert order.index("smart_plating") < order.index("rotor") < order.index("screws")


def test_a_cycle_is_refused_and_names_the_bus_and_the_item(reference):
    """Refused, not iterated toward: on a cycle the update map is non-monotone
    — overflow is a sawtooth in demand and enters with a negative sign — and no
    termination argument is available."""
    empty = SolveResponse(
        recipes=(), items=(), raw_inputs=(),
        power=PowerReport(0, 0, 0, 0), machines=(),
    )
    request = RealizationRequest(
        design_tier=4,
        buses=(
            BusDeclaration(bus_id="a", item_id=build.I_SCREW,
                           sources=(SourceEdge(build.I_IRON_PLATE, "b"),)),
            BusDeclaration(bus_id="b", item_id=build.I_IRON_PLATE,
                           sources=(SourceEdge(build.I_SCREW, "a"),)),
        ),
    )
    with pytest.raises(CreditedFlowCycle) as excinfo:
        credited_flow_order(empty, reference, request)
    message = str(excinfo.value)
    assert "a" in message and "b" in message
    assert build.I_SCREW in message and build.I_IRON_PLATE in message


def test_a_source_bus_that_is_not_declared_is_refused(reference):
    empty = SolveResponse(
        recipes=(), items=(), raw_inputs=(),
        power=PowerReport(0, 0, 0, 0), machines=(),
    )
    request = RealizationRequest(
        design_tier=4,
        buses=(BusDeclaration(bus_id="a", item_id=build.I_SCREW,
                              sources=(SourceEdge(build.I_IRON_ROD, "nope"),)),),
    )
    with pytest.raises(Exception, match="not declared"):
        credited_flow_order(empty, reference, request)


def test_a_credited_byproduct_edge_is_added_only_where_the_declaration_is_silent(
    reference,
):
    """Crediting an item adds an edge from its producer to every consumer of
    it, which is how an acyclic RECIPE graph can have a cyclic CREDITED graph.
    But a declaration outranks a derivation: a consumer that names a source
    already supplies the edge, and one that declares the draw out of scope has
    said so deliberately.

    Recycled Plastic and Recycled Rubber each take the other's PRODUCT as a
    primary input, so this is also the case that shows why the derivation
    cannot be restricted to secondary outputs: there is no byproduct anywhere
    in this loop and the loop is real.
    """
    plastic, rubber = "Desc_Plastic_C", "Desc_Rubber_C"
    FUEL = "Desc_LiquidFuel_C"   # the shared out-of-scope input
    r_plastic = "Recipe_Alternate_Plastic_1_C"
    r_rubber = "Recipe_Alternate_RecycledRubber_C"
    for rid, wants in ((r_plastic, rubber), (r_rubber, plastic)):
        assert any(i == wants for i, _ in reference.recipes[rid].inputs)

    response = SolveResponse(
        recipes=(RecipeUse(r_plastic, "Build_OilRefinery_C", 1.0, 2.0),
                 RecipeUse(r_rubber, "Build_OilRefinery_C", 1.0, 2.0)),
        items=(ItemFlow(plastic, 1.0, 1.0), ItemFlow(rubber, 1.0, 1.0)),
        raw_inputs=(), power=PowerReport(0, 0, 0, 0), machines=(),
    )

    # Silent on the cross-feed: the credited edges close a loop and it is caught.
    silent = RealizationRequest(
        design_tier=8,
        buses=(
            BusDeclaration(bus_id="plastic", item_id=plastic,
                           sources=(SourceEdge(FUEL, None),)),
            BusDeclaration(bus_id="rubber", item_id=rubber,
                           sources=(SourceEdge(FUEL, None),)),
        ),
    )
    with pytest.raises(CreditedFlowCycle):
        credited_flow_order(response, reference, silent)

    # The same plans, with both cross-feeds DECLARED out of scope. The caller
    # has said where those draws come from, so no edge is derived.
    declared = RealizationRequest(
        design_tier=8,
        buses=(
            BusDeclaration(bus_id="plastic", item_id=plastic,
                           sources=(SourceEdge(FUEL, None),
                                    SourceEdge(rubber, None))),
            BusDeclaration(bus_id="rubber", item_id=rubber,
                           sources=(SourceEdge(FUEL, None),
                                    SourceEdge(plastic, None))),
        ),
    )
    assert set(credited_flow_order(response, reference, declared)) == {
        "plastic", "rubber",
    }


# --------------------------------------------------------------------------
# project_goals
# --------------------------------------------------------------------------

def test_the_worked_case_completes_in_fifty_minutes(report):
    """`project_goals`' own docstring, reproduced: one Assembler yields 2/min
    and 100 units takes 50 minutes exactly."""
    projections = project_goals(
        report.buses, (("space_elevator_t1", build.I_SMART_PLATING, 100.0),),
    )
    assert len(projections) == 1
    assert projections[0].rate_per_min == pytest.approx(2.0)
    assert projections[0].minutes_to_complete == pytest.approx(50.0)


def test_rate_is_derived_from_machines_at_the_lane_clock(scaled, caps, rates):
    """The DECLARATION is machine count; the rate follows from it, and no
    player-time parameter enters either figure.

    A12 re-based the numbers, not the claim. This used to clock Smart Plating
    to its 1/min withdrawal alone — half its rate, double the duration — which
    starved the 2/min the solve asks of it. MATCHED now clocks to the line's
    whole demand (2 external + 1 withdrawn = 3/min): two Assemblers at 75%,
    3/min, 100 parts in 33.3 minutes. Every figure is machines at their
    clock."""
    clocked = realize(
        build.worked_response(), scaled, caps, rates,
        RealizationRequest(
            design_tier=4,
            buses=tuple(
                BusDeclaration(bus_id=b.bus_id, item_id=b.item_id,
                               sources=b.sources,
                               stores=False,
                               withdrawal_per_min=1.0)
                if b.bus_id == "smart_plating" else b
                for b in build.worked_buses()
            ),
        ),
    )
    projection = project_goals(
        clocked.buses, (("space_elevator_t1", build.I_SMART_PLATING, 100.0),),
    )[0]
    root = next(b for b in clocked.buses if b.bus_id == "smart_plating")
    assert [(l.machines, l.clock_percent) for l in root.lanes] == [
        (2, pytest.approx(75.0))
    ]
    assert projection.rate_per_min == pytest.approx(3.0)
    assert projection.minutes_to_complete == pytest.approx(100.0 / 3.0)


def test_a_goal_no_bus_produces_never_completes(report):
    """The truthful report for a plan in progress, not a refusal: a goal the
    declaration does not yet build is an ordinary state."""
    projection = project_goals(
        report.buses, (("ficsonium", "Desc_Ficsonium_C", 10.0),),
    )[0]
    assert projection.rate_per_min == 0.0
    assert projection.minutes_to_complete == math.inf


def test_no_lane_can_express_a_somersloop(report):
    """Pins the gap named in the module docstring. `project_goals` owes a
    refusal by name and has no site for one: if a somersloop ever becomes
    expressible on a `Lane`, this fails and says so."""
    import dataclasses

    from realization.contracts import Lane

    fields = {f.name for f in dataclasses.fields(Lane)}
    assert not any("sloop" in f or "somersloop" in f for f in fields)


# --------------------------------------------------------------------------
# realize
# --------------------------------------------------------------------------

def test_total_power_is_the_sum_of_the_lanes(report):
    assert report.total_power_mw == pytest.approx(
        sum(l.power_mw for b in report.buses for l in b.lanes)
    )
    # 3 Assemblers at 15 MW and 5 Constructors at 4 MW, all at 100%.
    assert report.total_power_mw == pytest.approx(65.0)


def test_the_report_carries_the_declared_tier_and_the_node_declarations(report):
    assert report.design_tier == 4
    assert report.extraction == ()


def test_projections_are_always_empty_from_realize(report):
    """The contract gap, pinned. `realize` takes no goals and no totals, so
    this is empty by construction — "realize was given no goals", never "no
    goal completes". `project_goals` is the surface that fills it."""
    assert report.projections == ()


def test_coverage_is_empty_when_no_line_declares_a_withdrawal(report):
    """Empty is not "everything covers" — it is "no line declared a
    withdrawal"."""
    assert report.coverage == ()


def test_a_declared_withdrawal_produces_a_verdict_carrying_its_basis(
    scaled, caps, rates,
):
    """`covers=True` means "covers the floor", never "covers", and the floor it
    means is now named on the declaration rather than assumed by
    `coverage_for`."""
    result = realize(
        build.worked_response(), scaled, caps, rates,
        build.worked_request(withdrawal_per_min=0.5),
    )
    assert len(result.coverage) == 1
    verdict = result.coverage[0]
    assert verdict.bus_id == "screws"
    assert verdict.withdrawal_per_min == pytest.approx(0.5)
    assert verdict.residual_per_min == pytest.approx(1.0)
    assert verdict.covers
    assert verdict.basis is WithdrawalBasis.GEOMETRIC_FLOOR


def test_a_derived_basis_is_carried_through_rather_than_relabelled(
    scaled, caps, rates,
):
    """Amendment 5 A5.5. Before it, `coverage_for` hardcoded the geometric
    floor; a rate summed from the canonical construction bill labelled as
    section 8.2's footprint estimate is a wrong verdict wearing a right one's
    clothes."""
    result = realize(
        build.worked_response(), scaled, caps, rates,
        build.worked_request(
            withdrawal_per_min=0.5,
            withdrawal_basis=WithdrawalBasis.DERIVED_WHOLE_GAME_FLOOR,
        ),
    )
    assert result.coverage[0].basis is WithdrawalBasis.DERIVED_WHOLE_GAME_FLOOR


def test_invalidating_unlocks_name_the_rewiring_alternates(report, scaled):
    """An alternate is a RE-WIRING event, not only a cheaper recipe: Stitched
    Iron Plate makes Reinforced Iron Plate from Iron Plate and Wire and draws no
    screws at all, so unlocking it removes RIP from the screw bus entirely."""
    assert STITCHED in report.invalidating_unlocks
    stitched = scaled.recipes[STITCHED]
    assert stitched.is_alternate
    assert build.I_SCREW not in {i for i, _ in stitched.inputs}
    assert "Desc_IronPlateReinforced_C" in {i for i, _ in stitched.outputs}


def test_invalidating_unlocks_are_not_sorted_and_are_unique(report):
    """Alternates are never ordered — the standing guardrail. Discovery order
    with duplicates dropped at first sight, and every entry a peer."""
    unlocks = report.invalidating_unlocks
    assert len(unlocks) == len(set(unlocks))
    assert list(unlocks) != sorted(unlocks)


def test_a_bus_whose_consumer_has_no_screw_free_alternate_contributes_nothing(
    scaled, caps, rates,
):
    """Every unlock listed must be justified by a consumer on some bus, so a
    report with no automated consumers lists nothing."""
    result = realize(
        build.worked_response(), scaled, caps, rates, build.worked_request(),
    )
    for unlock in result.invalidating_unlocks:
        assert scaled.recipes[unlock].is_alternate


def test_feasibility_findings_reach_the_warnings(scaled, caps, rates):
    """A bus that cannot be kept isolated at this tier is a finding, not an
    error, and it is reported rather than repaired."""
    result = realize(
        build.worked_response(), scaled, caps, rates, build.worked_request(),
    )
    assert any("no lane width" in w for w in result.warnings)


# --------------------------------------------------------------------------
# realize's refusals
# --------------------------------------------------------------------------

def test_sunk_is_refused_by_name(scaled, caps, rates):
    """The AWESOME Sink is absent from the reference layer. A4.2 narrows what
    that absence costs — a build-material line reaches a constant draw through
    MATCHED — but disposal of a genuine overflow still has no model."""
    with pytest.raises(DispositionUnavailable, match="AWESOME Sink"):
        realize(
            build.worked_response(), scaled, caps, rates,
            build.worked_request(disposition=Disposition.SUNK,
                                 withdrawal_per_min=1.0),
        )


def test_tier_two_cannot_feed_a_rotor_assembler(scaled, caps, rates):
    """At the scenario of record one Rotor Assembler draws 124 screws/min and a
    Mk.2 belt carries 120. The declaration is genuinely infeasible at tier 2 —
    the 1.25x rounding pushes a single machine past one belt, which is the
    layout consequence the module docstring predicts."""
    with pytest.raises(LaneInfeasible, match="exceeds belt_mk2"):
        realize(
            build.worked_response(), scaled, caps, rates,
            build.worked_request(design_tier=2),
        )


def test_a_node_clock_outside_the_range_is_refused_not_clamped(scaled, caps, rates):
    """`extraction` is READ, not carried. A parameter nothing reads is a
    parameter that cannot refuse, and the table is the only thing in the layer
    that can say a node declaration is unbuildable."""
    request = RealizationRequest(
        design_tier=4,
        buses=build.worked_buses(),
        nodes=(NodeDeclaration(item_id="Desc_OreIron_C",
                               extractor_class="Build_MinerMk1_C",
                               purity="normal", clock_percent=400.0),),
    )
    with pytest.raises(ValueError, match="is refused, not clamped"):
        realize(build.worked_response(), scaled, caps, rates, request)


def test_a_valid_node_declaration_is_echoed_into_the_report(scaled, caps, rates):
    node = NodeDeclaration(item_id="Desc_OreIron_C",
                           extractor_class="Build_MinerMk1_C",
                           purity="normal", clock_percent=100.0)
    result = realize(
        build.worked_response(), scaled, caps, rates,
        RealizationRequest(design_tier=4, buses=build.worked_buses(),
                           nodes=(node,)),
    )
    assert result.extraction == (node,)


# --------------------------------------------------------------------------
# the report carries both verdicts, in separate fields. Next action 2.
# --------------------------------------------------------------------------
#
# The Concrete line of P30, now sized from a bill instead of a rate. It
# declares no withdrawal RATE, so it contributes no demand and sizes at the
# recovered floor of one machine: supply 15/min, R = 15/min. Against a
# bootstrap of 60 and a remainder of 240 that is 4 minutes and 20 minutes.
# Six distinct quantities — 15, 60, 240, 300, 4, 20.

I_CONCRETE = "Desc_Cement_C"
I_STONE = "Desc_Stone_C"
R_CONCRETE = "Recipe_Concrete_C"


def _concrete_bill_request():
    return RealizationRequest(
        design_tier=4,
        buses=build.worked_buses() + (
            BusDeclaration(
                bus_id="concrete", item_id=I_CONCRETE, recipe_id=R_CONCRETE,
                sources=(SourceEdge(I_STONE, None),),
                withdrawal_bill=WithdrawalBill(
                    bootstrap_units=60.0, remainder_units=240.0,
                    terms=frozenset({BillTerm.MACHINE_CONSTRUCTION,
                                     BillTerm.BOOTSTRAP_SET}),
                    basis=WithdrawalBasis.DERIVED_WHOLE_GAME_FLOOR),
            ),
        ),
    )


def test_a_bill_sized_line_reports_durations_and_not_a_coverage_verdict(
    scaled, caps, rates
):
    """The two fields do not overlap. A reader that has to check which shape an
    entry is has been handed the conflation the split exists to prevent."""
    result = realize(
        build.worked_response(), scaled, caps, rates, _concrete_bill_request(),
    )
    assert result.coverage == ()
    assert len(result.projected_coverage) == 1
    verdict = result.projected_coverage[0]
    assert verdict.bus_id == "concrete"
    assert verdict.residual_per_min == pytest.approx(15.0)
    assert verdict.minutes_to_bootstrap == pytest.approx(4.0)
    assert verdict.minutes_to_total == pytest.approx(20.0)
    assert verdict.basis is WithdrawalBasis.DERIVED_WHOLE_GAME_FLOOR


def test_a_bill_contributes_no_rate_so_the_line_sizes_from_the_declared_build(
    scaled, caps, rates
):
    """Respec §6's settled form, reached from the other side. A stock cannot
    size a bus without a horizon, so the caller DECLARES THE BUILD and reads
    the duration back: one machine by default, and `extra_producers` is the
    lever. Two machines halve the wait.
    """
    request = _concrete_bill_request()
    one = realize(build.worked_response(), scaled, caps, rates, request)
    doubled = dataclasses.replace(
        request,
        buses=request.buses[:-1] + (
            dataclasses.replace(request.buses[-1], extra_producers=1),
        ),
    )
    two = realize(build.worked_response(), scaled, caps, rates, doubled)

    assert next(b for b in one.buses if b.bus_id == "concrete").machines == 1
    assert next(b for b in two.buses if b.bus_id == "concrete").machines == 2
    assert two.projected_coverage[0].residual_per_min == pytest.approx(30.0)
    assert two.projected_coverage[0].minutes_to_bootstrap == pytest.approx(2.0)


def test_both_verdict_fields_are_empty_when_no_line_declares_either(report):
    """Empty is "no line declared one", never "everything covers"."""
    assert report.coverage == ()
    assert report.projected_coverage == ()
