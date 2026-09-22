"""`buses.py`'s six bodies. Handoff next action 1.

Every figure asserted here is either read from the reference CSVs or quoted
from a record, and each test says which. Nothing is restated from the bodies
themselves — a test that agrees with the code because it copied the code
asserts nothing.

**The basis these tests assert is PEAK, and that is deliberate.** A consumer's
draw here is `machines x per-machine input rate` — installed capacity, not
steady draw. Amendment 5 A5.2 establishes that average draw is USAGE in every
state and that nameplate is the peak, so the record's published figures (199,
75, 124) are peak figures: the screw bus's own consumers sit at 40% and 50%
utilisation in this case. Asserting them as peak is correct and survives the
basis change; the usage-basis figures are new and not yet on any record. Each
test that depends on the distinction names it.

Reproduced from the record:

    bus record 1 / 4   screw bus 199/min, RIP 75 (37.7%), Rotor 124 (62.3%),
                       R = 1.0/min at 5 machines
    buses.py docstring at 1.25x a lane of w smelters feeds 0.75w constructors,
                       integral only when w is a multiple of 4
"""
from __future__ import annotations

import dataclasses

import pytest

import _realization_builders as build
from production_adapter.contracts import (
    ItemFlow, PowerReport, RecipeUse, SolveResponse,
)
from production_adapter.scenario import MARGINAL_PEAK_DEBOTTLENECK
from realization import buses as B
from realization.contracts import (
    BusDeclaration, ClockCause, ClockDistribution, ClockMode, Disposition,
    LaneInfeasible, PartitionIncomplete, RealizationError, RealizationRequest,
    RecipeProvenance, SourceEdge,
)

I_IRON_INGOT = "Desc_IronIngot_C"
I_IRON_ORE = "Desc_OreIron_C"
R_IRON_INGOT = "Recipe_IngotIron_C"
R_IRON_PLATE = "Recipe_IronPlate_C"
R_RECYCLED_PLASTIC = "Recipe_Alternate_Plastic_1_C"
#: Alternate: Iron Wire. The id carries no "Iron" — matched by id, never
#: by display name (storage review 6.3: a display-name lookup raises on
#: `Turbo Rifle Ammo`, which is duplicated in the shipped data).
R_IRON_WIRE = "Recipe_Alternate_Wire_1_C"
R_COPPER_WIRE = "Recipe_Wire_C"
#: The Concrete build-material line of P30. 60 Stone -> 15 Concrete/min at the
#: scenario of record, read from recipe_io.csv.
I_CONCRETE = "Desc_Cement_C"
I_STONE = "Desc_Stone_C"
R_CONCRETE = "Recipe_Concrete_C"


@pytest.fixture(scope="module")
def scaled(reference):
    """Reference data at the scenario of record (1.25x recipe inputs).

    `with_scenario` rather than a second `gamedata.load`: the multiplier is
    applied to per-cycle amounts and the rates re-derived, which is the same
    path `load(root, scenario)` takes.
    """
    return reference.with_scenario(MARGINAL_PEAK_DEBOTTLENECK)


@pytest.fixture(scope="module")
def caps(logistics):
    return logistics[0]


def _cap(caps, capability_id):
    return next(c for c in caps if c.capability_id == capability_id)


def _equivalents(response, recipe_id, value):
    """The same response with one recipe's `machine_equivalents` changed.

    The worked case runs one machine on every bus but the screws, which makes
    several distinct quantities numerically equal — `machines * rate` and
    `rate`, a floor of one and a ceil of one. Tests that must tell them apart
    move a bus off 1.0 here rather than asserting on a coincidence.
    """
    return dataclasses.replace(response, recipes=tuple(
        dataclasses.replace(u, machine_equivalents=value)
        if u.recipe_id == recipe_id else u
        for u in response.recipes
    ))


# --------------------------------------------------------------------------
# the carrier map is DATA about two CSVs, so it is asserted against them
# --------------------------------------------------------------------------

def test_every_item_form_has_a_carrier_type(reference):
    """`CARRIER_TYPE` must cover every form `items.csv` actually uses, or a
    trunk cannot be picked for some declared bus and the failure arrives as a
    refusal deep in a traversal rather than here."""
    forms = {i.form for i in reference.items.values()}
    assert forms == {"solid", "liquid", "gas"}
    assert forms <= set(B.CARRIER_TYPE)


def test_every_lane_carrier_type_is_mapped_and_miner_is_not(caps):
    """`miner` is a capability type and is deliberately absent from
    `CARRIED_FORMS`: an extractor is not a lane carrier, and a trunk that is one
    must be refused rather than silently sized."""
    types = {c.capability_type for c in caps}
    assert types == {"belt", "conveyor_lift", "pipeline", "miner"}
    assert set(B.CARRIED_FORMS) == types - {"miner"}


def test_the_two_maps_agree(reference):
    """`CARRIED_FORMS` and `CARRIER_TYPE` are inverses. Written separately
    because each is read in a different direction; asserted together because a
    drift between them is silent."""
    for form, carrier in B.CARRIER_TYPE.items():
        assert form in B.CARRIED_FORMS[carrier]


def test_a_miner_trunk_is_refused(scaled, caps):
    with pytest.raises(RealizationError, match="CARRIED_FORMS"):
        B.machines_per_lane(scaled, build.R_SCREWS, _cap(caps, "miner_mk1"))


# --------------------------------------------------------------------------
# machines_per_lane
# --------------------------------------------------------------------------

def test_the_binding_side_is_the_larger_of_input_and_output(scaled):
    """Screws at 1.25x: 10 rod/min in, 40 screw/min out. The output binds, and
    the figures come from the CSVs rather than from this test."""
    recipe = scaled.recipes[build.R_SCREWS]
    assert dict(recipe.inputs)[build.I_IRON_ROD] == pytest.approx(10.0)
    assert dict(recipe.outputs)[build.I_SCREW] == pytest.approx(40.0)


@pytest.mark.parametrize("capability_id,expected", [
    ("belt_mk1", 1),    # 60 / 40
    ("belt_mk2", 3),    # 120 / 40
    ("belt_mk3", 6),    # 270 / 40
])
def test_machines_per_lane_is_the_floor_of_trunk_over_binding(
    scaled, caps, capability_id, expected
):
    assert B.machines_per_lane(
        scaled, build.R_SCREWS, _cap(caps, capability_id)
    ) == expected


def test_one_machine_past_the_trunk_returns_zero(scaled, caps):
    """One Rotor Assembler draws 124 screws/min at the scenario of record and a
    Mk.2 belt carries 120. Zero, and `decompose` is what turns that into
    `LaneInfeasible` — this function does not raise."""
    assert dict(scaled.recipes[build.R_ROTOR].inputs)[build.I_SCREW] == pytest.approx(124.0)
    assert B.machines_per_lane(scaled, build.R_ROTOR, _cap(caps, "belt_mk2")) == 0


def test_a_fluid_does_not_bind_a_belt(reference, caps):
    """Each item rides its own carrier, so a fluid input is compared against a
    pipeline and not against the conveyor the solids ride.

    Recycled Plastic is the reference layer's own mixed-form case: 30 Rubber
    and 30 Liquid Fuel in, 60 Plastic out. On a belt the Liquid Fuel is not a
    candidate at all and the output binds at 60; on a pipeline only the Liquid
    Fuel is, and it binds at 30.
    """
    recipe = reference.recipes[R_RECYCLED_PLASTIC]
    forms = {i: reference.items[i].form for i, _ in
             list(recipe.inputs) + list(recipe.outputs)}
    assert forms == {"Desc_Rubber_C": "solid", "Desc_LiquidFuel_C": "liquid",
                     "Desc_Plastic_C": "solid"}

    assert B._binding(reference, recipe, _cap(caps, "belt_mk3")) == (
        pytest.approx(60.0), "output",
    )
    assert B._binding(reference, recipe, _cap(caps, "pipeline_mk1")) == (
        pytest.approx(30.0), "input",
    )


def test_an_item_the_reference_layer_does_not_carry_is_refused(reference, caps):
    """A recipe may name an item `items.csv` does not list — 28 of them on
    build docs_a81d250e96aa, measured 2026-09-21, mostly ammunition and
    fireworks projectiles. There is no form for such an item, so no carrier can
    be chosen, and the layer refuses by name rather than guessing "solid".

    A data gap with a consumer, recorded here because this is where it bites.
    """
    unlisted = {
        i for r in reference.recipes.values()
        for i, _ in list(r.inputs) + list(r.outputs)
        if i not in reference.items
    }
    assert unlisted, "items.csv now covers every recipe item — delete this test"
    affected = next(
        r for r in reference.recipes.values()
        if any(i in unlisted for i, _ in list(r.inputs) + list(r.outputs))
    )
    with pytest.raises(RealizationError, match="reference layer"):
        B.machines_per_lane(reference, affected.recipe_id, _cap(caps, "belt_mk3"))


# --------------------------------------------------------------------------
# integral_lane_widths — the 4:3 divisibility result
# --------------------------------------------------------------------------

def _ingot_consumers(data):
    """One Iron Plate Constructor drawing on the ingot bus."""
    return (
        B.consumer_shares(
            SolveResponse(
                recipes=(
                    RecipeUse(R_IRON_PLATE, "Build_ConstructorMk1_C", 1.0, 20.0),
                    RecipeUse(R_IRON_INGOT, "Build_SmelterMk1_C", 1.0, 20.0),
                ),
                items=(ItemFlow(I_IRON_INGOT, 1.0, 1.0),
                       ItemFlow(build.I_IRON_PLATE, 1.0, 0.0)),
                raw_inputs=(), power=PowerReport(0, 0, 0, 0), machines=(),
            ),
            data,
            RealizationRequest(
                design_tier=2,
                buses=(
                    BusDeclaration(bus_id="iron_ingot", item_id=I_IRON_INGOT,
                                   sources=(SourceEdge(I_IRON_ORE, None),),
                                   disposition=Disposition.WITHDRAWN),
                    BusDeclaration(bus_id="iron_plate", item_id=build.I_IRON_PLATE,
                                   sources=(SourceEdge(I_IRON_INGOT, "iron_ingot"),),
                                   disposition=Disposition.WITHDRAWN),
                ),
            ),
            "iron_ingot",
        )
    )


def test_the_multiplier_moves_divisibility_not_only_cost(reference, scaled, caps):
    """`buses.py`'s own module docstring, reproduced from the CSVs.

    At 1x a Smelter's 30 ingot/min feeds one Plate Constructor exactly, so every
    width is integral. At 1.25x the Constructor draws 40 (3 ingot/cycle rounds
    to 4), the ratio is 4 : 3, and a lane of w smelters feeds 0.75w constructors
    — integral only when w is a multiple of 4. On a Mk.2 trunk the cap is
    120/30 = 4, so 4 is the only width that both fits and divides.
    """
    mk2 = _cap(caps, "belt_mk2")
    assert dict(reference.recipes[R_IRON_PLATE].inputs)[I_IRON_INGOT] == pytest.approx(30.0)
    assert dict(scaled.recipes[R_IRON_PLATE].inputs)[I_IRON_INGOT] == pytest.approx(40.0)

    assert B.machines_per_lane(reference, R_IRON_INGOT, mk2) == 4
    assert B.integral_lane_widths(
        reference, R_IRON_INGOT, _ingot_consumers(reference), mk2
    ) == (1, 2, 3, 4)
    assert B.integral_lane_widths(
        scaled, R_IRON_INGOT, _ingot_consumers(scaled), mk2
    ) == (4,)


def test_no_integral_width_is_a_finding_not_an_error(scaled, caps):
    """The screw bus feeds RIP at 75/min and Rotor at 124/min. No width of
    40/min producers lands both on whole machines, so the bus cannot be kept
    isolated at this tier and must merge. Empty, not raised."""
    shares = B.consumer_shares(
        build.worked_response(), scaled, build.worked_request(), "screws",
    )
    assert B.integral_lane_widths(
        scaled, build.R_SCREWS, shares, _cap(caps, "belt_mk3")
    ) == ()


def test_a_withdrawal_consumer_is_skipped(scaled, caps):
    """A player drawing from a container is not a machine and has no whole
    number to land on, so it cannot make a width non-integral."""
    mk2 = _cap(caps, "belt_mk2")
    with_player = _ingot_consumers(scaled) + (
        build.ConsumerShare(recipe_id=None, draw_per_min=7.0, share=None),
    )
    assert B.integral_lane_widths(scaled, R_IRON_INGOT, with_player, mk2) == (4,)


# --------------------------------------------------------------------------
# consumer_shares — bus record section 1's measured row
# --------------------------------------------------------------------------

def test_the_measured_screw_bus(scaled):
    """Bus record sections 1 and 4, at the scenario of record:

        screw bus 199/min  ->  RIP 75 (37.7%)   Rotor 124 (62.3%)

    PEAK basis (A5.2): these are one Assembler each at installed capacity. The
    same two consumers sit at 40% and 50% utilisation, so their USAGE draws are
    30 and 62 and the bus would be 3 machines rather than 5. That figure is not
    on any record and is not asserted here.
    """
    shares = B.consumer_shares(
        build.worked_response(), scaled, build.worked_request(), "screws",
    )
    assert [s.recipe_id for s in shares] == [build.R_RIP, build.R_ROTOR]
    assert [s.draw_per_min for s in shares] == [
        pytest.approx(75.0), pytest.approx(124.0),
    ]
    assert sum(s.draw_per_min for s in shares) == pytest.approx(199.0)
    assert [round(s.share, 4) for s in shares] == [0.3769, 0.6231]


def test_consumers_come_out_in_declaration_order(scaled):
    """Caller order preserved — the standing guardrail against this layer
    ranking anything. Reversing the declarations reverses the report."""
    request = build.worked_request()
    reversed_buses = (request.buses[0],) + tuple(reversed(request.buses[1:]))
    shares = B.consumer_shares(
        build.worked_response(), scaled,
        RealizationRequest(design_tier=4, buses=reversed_buses), "screws",
    )
    assert [s.recipe_id for s in shares] == [build.R_ROTOR, build.R_RIP]


def test_withdrawal_carries_share_none_and_stays_out_of_the_denominator(scaled):
    """`share=None`, not 0.0. Withdrawal is covered by the residual rather than
    sized into the bus, which is what makes A3.5's `R >= withdraw` verdict mean
    anything."""
    shares = B.consumer_shares(
        build.worked_response(), scaled,
        build.worked_request(withdrawal_per_min=5.0), "screws",
    )
    player = [s for s in shares if s.is_withdrawal]
    assert len(player) == 1
    assert player[0].share is None
    assert player[0].draw_per_min == pytest.approx(5.0)
    automated = [s for s in shares if not s.is_withdrawal]
    assert sum(s.share for s in automated) == pytest.approx(1.0)


# --------------------------------------------------------------------------
# recipe attribution — the BusDeclaration-has-no-recipe_id gap
# --------------------------------------------------------------------------

def test_a_bus_the_solve_did_not_run_and_names_no_recipe_is_refused_by_name(scaled):
    """Every build-material line outside the solve lands here: Concrete, Cable,
    the Iron Plate build stock.

    P30 gives `BusDeclaration` a `recipe_id`; it does not make one optional at
    the point of use. A line that names NEITHER a solved candidate nor a recipe
    still cannot be sized, and is still refused rather than guessed, with the
    message naming the store checked.
    """
    request = RealizationRequest(
        design_tier=4,
        buses=build.worked_buses() + (
            BusDeclaration(bus_id="concrete", item_id="Desc_Cement_C",
                           sources=(SourceEdge("Desc_Stone_C", None),),
                           withdrawal_per_min=15.0),
        ),
    )
    with pytest.raises(RealizationError, match="no recipe that outputs"):
        B.buses_from_response(build.worked_response(), scaled, request, ())


def test_sources_discriminate_two_buses_of_one_item(reference):
    """A3.1: wire_iron and wire_copper are told apart by the INPUT items their
    sources name, because nothing in a solve says which is which. Attribution,
    not selection."""
    wire = "Desc_Wire_C"
    iron_wire, copper_wire = R_IRON_WIRE, R_COPPER_WIRE
    assert {i for i, _ in reference.recipes[iron_wire].inputs} == {"Desc_IronIngot_C"}
    assert {i for i, _ in reference.recipes[copper_wire].inputs} == {"Desc_CopperIngot_C"}

    request = RealizationRequest(
        design_tier=4,
        buses=(
            BusDeclaration(bus_id="wire_iron", item_id=wire,
                           sources=(SourceEdge("Desc_IronIngot_C", None),)),
            BusDeclaration(bus_id="wire_copper", item_id=wire,
                           sources=(SourceEdge("Desc_CopperIngot_C", None),)),
        ),
    )
    response = SolveResponse(
        recipes=(RecipeUse(iron_wire, "Build_ConstructorMk1_C", 1.0, 4.0),
                 RecipeUse(copper_wire, "Build_ConstructorMk1_C", 1.0, 4.0)),
        items=(ItemFlow(wire, 1.0, 0.0),),
        raw_inputs=(), power=PowerReport(0, 0, 0, 0), machines=(),
    )
    attributed = B._attribute(response, reference, request)
    assert attributed["wire_iron"].recipe_id == iron_wire
    assert attributed["wire_copper"].recipe_id == copper_wire


def test_a_declaration_that_does_not_discriminate_is_refused(reference):
    """Same two Wire recipes, but neither bus names an input. Two candidates,
    and picking one would be choosing a recipe."""
    wire = "Desc_Wire_C"
    request = RealizationRequest(
        design_tier=4,
        buses=(BusDeclaration(bus_id="wire_a", item_id=wire),),
    )
    response = SolveResponse(
        recipes=(RecipeUse(R_IRON_WIRE, "Build_ConstructorMk1_C", 1.0, 4.0),
                 RecipeUse(R_COPPER_WIRE, "Build_ConstructorMk1_C", 1.0, 4.0)),
        items=(ItemFlow(wire, 1.0, 0.0),),
        raw_inputs=(), power=PowerReport(0, 0, 0, 0), machines=(),
    )
    with pytest.raises(RealizationError, match="does not discriminate"):
        B._attribute(response, reference, request)


def test_lenient_attribution_skips_what_it_cannot_resolve(reference):
    """`credited_flow_order` must produce an order for a declaration it cannot
    fully attribute, or the refusal arrives from the wrong function."""
    wire = "Desc_Wire_C"
    request = RealizationRequest(
        design_tier=4,
        buses=(BusDeclaration(bus_id="wire_a", item_id=wire),),
    )
    response = SolveResponse(
        recipes=(RecipeUse(R_IRON_WIRE, "Build_ConstructorMk1_C", 1.0, 4.0),
                 RecipeUse(R_COPPER_WIRE, "Build_ConstructorMk1_C", 1.0, 4.0)),
        items=(ItemFlow(wire, 1.0, 0.0),),
        raw_inputs=(), power=PowerReport(0, 0, 0, 0), machines=(),
    )
    assert B._attribute(response, reference, request, strict=False) == {}


# --------------------------------------------------------------------------
# P30 — BusDeclaration carries a recipe_id, so a bus outside the solve is
# attributable. Every figure below is read from the CSVs at the scenario of
# record: Recipe_Concrete_C is 60 Stone -> 15 Concrete/min at 1.25x.
# --------------------------------------------------------------------------

def _concrete(withdrawal_per_min=20.0, **kwargs):
    """A Concrete build-material line. The solver does not model it.

    20/min, not 15: at 15 the rate, the supply, the residual and the withdrawal
    are all one number and a test asserting any of them asserts nothing. At 20
    the bus is 2 machines, supply 30, residual 30, withdrawal 20 — four
    distinct quantities.
    """
    kwargs.setdefault("recipe_id", R_CONCRETE)
    return BusDeclaration(
        bus_id="concrete", item_id=I_CONCRETE,
        sources=(SourceEdge(I_STONE, None),),
        withdrawal_per_min=withdrawal_per_min,
        **kwargs,
    )


def _with_concrete(*, response=None, **kwargs):
    request = RealizationRequest(
        design_tier=4, buses=build.worked_buses() + (_concrete(**kwargs),),
    )
    return (response if response is not None else build.worked_response()), request


def test_a_declared_recipe_sizes_a_bus_the_solve_did_not_run(scaled, caps):
    """The unblocking case. Concrete is outside the solve, the declaration names
    its recipe, and the line sizes from its withdrawal alone.

    ceil(20 / 15) = 2 machines at 15/min, so supply 30/min. Read from
    recipe_io.csv at 1.25x, not restated from the body.
    """
    response, request = _with_concrete()
    buses = B.buses_from_response(response, scaled, request, caps)
    concrete = next(b for b in buses if b.bus_id == "concrete")
    assert concrete.recipe_id == R_CONCRETE
    assert concrete.machines == 2
    assert concrete.supply_per_min == pytest.approx(30.0)
    assert concrete.automated_demand_per_min == pytest.approx(0.0)
    assert concrete.withdrawal_per_min == pytest.approx(20.0)
    assert concrete.residual.rate_per_min == pytest.approx(30.0)


def test_a_declared_bus_carries_no_machine_equivalents(scaled):
    """`None`, never 0.0. The solve has no account of this bus, and an absence
    and a measured zero must not share a number — `BusRecipe.__post_init__`
    enforces the pairing, and this is the path that produces it."""
    response, request = _with_concrete()
    attributed = B._attribute(response, scaled, request)
    assert attributed["concrete"].provenance is RecipeProvenance.DECLARED
    assert attributed["concrete"].machine_equivalents is None
    assert attributed["screws"].provenance is RecipeProvenance.SOLVED
    assert attributed["screws"].machine_equivalents == pytest.approx(
        build.SCREW_EQUIVALENTS
    )


def test_a_declared_line_is_sized_by_its_withdrawal(scaled, caps):
    """Two withdrawals, one bus: 20/min gives 2 machines, 50/min gives 4. The
    line tracks its declaration and nothing in the response.

    This pins the SIZING, not the provenance. `_demand`'s external term is
    absent rather than zero on a DECLARED bus, and the two are numerically
    identical here — no arithmetic test can separate them. What separates them
    is `BusRecipe.__post_init__` and the test above.
    """
    small_response, small_request = _with_concrete(withdrawal_per_min=20.0)
    small = B.buses_from_response(small_response, scaled, small_request, caps)
    large_response, large_request = _with_concrete(withdrawal_per_min=50.0)
    large = B.buses_from_response(large_response, scaled, large_request, caps)
    assert next(b for b in small if b.bus_id == "concrete").machines == 2
    assert next(b for b in large if b.bus_id == "concrete").machines == 4


def test_a_declared_bus_needs_no_itemflow(scaled, caps):
    """The reconciliation reads the SOLVE'S account of an item. A bus the solve
    did not run has none, and requiring one moved the refusal one step later —
    which blocked exactly the lines `recipe_id` exists to unblock."""
    response, request = _with_concrete()
    assert all(f.item_id != I_CONCRETE for f in response.items)
    buses = B.buses_from_response(response, scaled, request, caps)
    assert any(b.bus_id == "concrete" for b in buses)


def test_a_declared_recipe_the_solve_did_run_is_still_attributed_from_the_solve(scaled):
    """The declaration disambiguates; it does not replace. Where the named
    recipe IS in the response, the solve's `machine_equivalents` is what the
    bus carries — otherwise naming a recipe would silently discard the sizing
    the solve did."""
    request = RealizationRequest(
        design_tier=4,
        buses=build.worked_buses(recipe_id=build.R_SCREWS),
    )
    attributed = B._attribute(build.worked_response(), scaled, request)
    assert attributed["screws"].provenance is RecipeProvenance.SOLVED
    assert attributed["screws"].machine_equivalents == pytest.approx(
        build.SCREW_EQUIVALENTS
    )


def test_a_declared_recipe_discriminates_where_sources_cannot(reference):
    """The ambiguity refusal has a second escape hatch now. Naming the recipe is
    the CALLER choosing, which is the same authority `sources` already carries —
    this layer still picks nothing."""
    wire = "Desc_Wire_C"
    request = RealizationRequest(
        design_tier=4,
        buses=(BusDeclaration(bus_id="wire_a", item_id=wire,
                              recipe_id=R_COPPER_WIRE),),
    )
    response = SolveResponse(
        recipes=(RecipeUse(R_IRON_WIRE, "Build_ConstructorMk1_C", 1.0, 4.0),
                 RecipeUse(R_COPPER_WIRE, "Build_ConstructorMk1_C", 2.0, 4.0)),
        items=(ItemFlow(wire, 1.0, 0.0),),
        raw_inputs=(), power=PowerReport(0, 0, 0, 0), machines=(),
    )
    attributed = B._attribute(response, reference, request)
    assert attributed["wire_a"].recipe_id == R_COPPER_WIRE
    assert attributed["wire_a"].provenance is RecipeProvenance.SOLVED
    assert attributed["wire_a"].machine_equivalents == pytest.approx(2.0)


def test_a_declared_recipe_that_does_not_output_the_bus_item_is_refused(scaled):
    """The declaration is authoritative and is therefore CHECKED against the
    reference layer before it is believed."""
    response, request = _with_concrete(recipe_id=build.R_SCREWS)
    with pytest.raises(RealizationError, match="does not output"):
        B._attribute(response, scaled, request)


def test_a_declared_recipe_that_does_not_consume_a_declared_source_is_refused(scaled):
    """A bus naming a source for an input its own recipe does not take is a
    contradiction between two halves of one declaration, not a gap in the
    solve."""
    request = RealizationRequest(
        design_tier=4,
        buses=build.worked_buses() + (
            BusDeclaration(bus_id="concrete", item_id=I_CONCRETE,
                           recipe_id=R_CONCRETE,
                           sources=(SourceEdge(I_STONE, None),
                                    SourceEdge(I_IRON_INGOT, None)),
                           withdrawal_per_min=20.0),
        ),
    )
    with pytest.raises(RealizationError, match="does not consume"):
        B._attribute(build.worked_response(), scaled, request)


def test_an_unknown_declared_recipe_is_refused_naming_the_store(scaled):
    """`_recipe`'s refusal, reached through the declaration rather than through
    the response. It names the store and the build."""
    response, request = _with_concrete(recipe_id="Recipe_NotAThing_C")
    with pytest.raises(RealizationError, match="no recipe .* in the reference layer"):
        B._attribute(response, scaled, request)


def test_lenient_attribution_skips_a_contradictory_declaration(scaled):
    """`strict=False` refuses NOTHING, declared recipes included. A refusal from
    `credited_flow_order` is the refusal arriving from the wrong function, which
    is the failure the lenient pass was added to prevent."""
    response, request = _with_concrete(recipe_id="Recipe_NotAThing_C")
    assert "concrete" not in B._attribute(response, scaled, request, strict=False)


def test_a_declared_line_on_a_recipe_the_solve_also_runs_is_refused(scaled):
    """KNOWN LIMITATION, asserted so it cannot become a silent hole.

    Two buses on one recipe collapse `_check_partition`'s recipe -> bus map,
    whatever their provenance. A build-material line for an item the solve also
    produces on the same recipe therefore cannot yet be declared alongside it.
    P30 does not close this; closing it needs bus identity beyond
    (item, sources, recipe).
    """
    request = RealizationRequest(
        design_tier=4,
        buses=build.worked_buses() + (
            BusDeclaration(bus_id="screw_build_stock", item_id=build.I_SCREW,
                           recipe_id=build.R_SCREWS,
                           sources=(SourceEdge(build.I_IRON_ROD, None),),
                           withdrawal_per_min=20.0),
        ),
    )
    with pytest.raises(PartitionIncomplete, match="known limitation"):
        B._attribute(build.worked_response(), scaled, request)


# --------------------------------------------------------------------------
# the partition-coverage tripwire — the fourth candidate finally gets a site
# --------------------------------------------------------------------------

def test_a_consumer_claimed_by_no_declared_bus_is_refused(scaled):
    """`PartitionIncomplete` had no site until now: the exception existed and
    nothing raised it. Drop the RIP bus and its screw draw is real and nothing
    is sized for it."""
    request = RealizationRequest(
        design_tier=4,
        buses=tuple(b for b in build.worked_buses() if b.bus_id != "rip"),
    )
    with pytest.raises(PartitionIncomplete, match="consumes"):
        B.buses_from_response(build.worked_response(), scaled, request, ())


def test_a_declared_consumer_that_names_no_source_is_refused(scaled):
    """The partition is not derived from the consumer set, but it is CHECKED
    against it. A bus that runs a recipe consuming a declared item and says
    nothing about where that item comes from is a gap, not a default."""
    buses = tuple(
        BusDeclaration(bus_id=b.bus_id, item_id=b.item_id,
                       sources=tuple(e for e in b.sources
                                     if e.input_item != build.I_SCREW),
                       disposition=b.disposition)
        if b.bus_id == "rotor" else b
        for b in build.worked_buses()
    )
    with pytest.raises(PartitionIncomplete, match="names no source bus"):
        B.buses_from_response(
            build.worked_response(), scaled,
            RealizationRequest(design_tier=4, buses=buses), (),
        )


# --------------------------------------------------------------------------
# decompose
# --------------------------------------------------------------------------

def test_lanes_partition_the_bus_total_and_are_balanced(scaled, caps):
    """5 machines on a Mk.2 trunk that carries 3: two lanes, 3 and 2. Balanced
    rather than fill-then-spill, which is dominated — equal machines, equal
    residual, worse power, two clock settings instead of one."""
    lanes = B.decompose(
        scaled, build.R_SCREWS, 199.0, (), _cap(caps, "belt_mk2"),
        caps, build.worked_request(), "screws",
    )
    assert [l.machines for l in lanes] == [3, 2]
    assert sum(l.machines for l in lanes) == 5
    assert all(l.machines <= 3 for l in lanes)


def test_a_wider_trunk_needs_one_lane(scaled, caps):
    lanes = B.decompose(
        scaled, build.R_SCREWS, 199.0, (), _cap(caps, "belt_mk3"),
        caps, build.worked_request(), "screws",
    )
    assert [l.machines for l in lanes] == [5]


def test_extra_producers_are_added_to_the_ceil(scaled, caps):
    """R(k) = ceil_residual + k * producer_rate. Storage rate is a MACHINE
    COUNT, and on this bus the quantum is a full 40/min."""
    for k, expected in ((0, 5), (1, 6), (2, 7)):
        lanes = B.decompose(
            scaled, build.R_SCREWS, 199.0, (), _cap(caps, "belt_mk3"), caps,
            build.worked_request(extra_producers=k), "screws",
        )
        assert sum(l.machines for l in lanes) == expected


def test_one_machine_past_the_trunk_is_lane_infeasible(scaled, caps):
    with pytest.raises(LaneInfeasible, match="exceeds belt_mk2"):
        B.decompose(
            scaled, build.R_ROTOR, 4.0, (), _cap(caps, "belt_mk2"), caps,
            RealizationRequest(
                design_tier=2,
                buses=(BusDeclaration(bus_id="rotor", item_id=build.I_ROTOR,
                                      disposition=Disposition.WITHDRAWN),),
            ),
            "rotor",
        )


def test_a_split_clock_puts_each_run_in_its_own_lanes(scaled, caps):
    """Under SPLIT the machines do not share a clock, and one Lane carries one
    clock. 199/min against 5 machines of 40: four at 100% and one at 97.5%.
    """
    lanes = B.decompose(
        scaled, build.R_SCREWS, 199.0, (), _cap(caps, "belt_mk3"), caps,
        build.worked_request(disposition=Disposition.BACK_UP,
                             clock_mode=ClockMode.EXPLICIT,
                             clock_distribution=ClockDistribution.SPLIT),
        "screws",
    )
    assert [(l.machines, round(l.clock_percent, 2)) for l in lanes] == [
        (4, 100.0), (1, 97.5),
    ]
    assert all(l.clock_cause is ClockCause.DECLARED for l in lanes)


def test_a_lane_reports_its_rate_at_its_clock(scaled, caps):
    """`output_rate_per_min` is at the lane's clock — that is what
    `project_goals` reads. `Bus.supply_per_min` is nameplate, and the two are
    different numbers on a clocked bus by design."""
    lanes = B.decompose(
        scaled, build.R_SCREWS, 199.0, (), _cap(caps, "belt_mk3"), caps,
        build.worked_request(disposition=Disposition.BACK_UP), "screws",
    )
    assert len(lanes) == 1
    assert lanes[0].clock_percent == pytest.approx(99.5)
    assert lanes[0].output_rate_per_min == pytest.approx(199.0)


def test_a_lane_input_carries_the_minimum_sufficient_mk_not_the_trunk(scaled, caps):
    """The trunk is the ceiling at the declared tier; an input's carrier is the
    floor for its own rate. 5 screw machines draw 50 rod/min, which a Mk.1 belt
    carries at 60."""
    lanes = B.decompose(
        scaled, build.R_SCREWS, 199.0, (), _cap(caps, "belt_mk3"), caps,
        build.worked_request(), "screws",
    )
    rod = next(i for i in lanes[0].inputs if i.item_id == build.I_IRON_ROD)
    assert rod.rate_per_min == pytest.approx(50.0)
    assert rod.carrier.capability_id == "belt_mk1"
    assert lanes[0].trunk.capability_id == "belt_mk3"


def test_an_input_absent_from_sources_is_out_of_scope(scaled, caps):
    """`BusDeclaration` says an input absent from `sources` is out of scope, so
    the lane input carries `source_bus_id=None` rather than inventing a bus."""
    lanes = B.decompose(
        scaled, build.R_SCREWS, 199.0, (), _cap(caps, "belt_mk3"), caps,
        build.worked_request(), "screws",
    )
    assert lanes[0].inputs[0].source_bus_id is None


def test_lane_power_is_linear_backing_up_and_convex_when_clocked(scaled, caps):
    """The nine-cell table's 99.5% row, through `decompose` rather than through
    `residual` directly: 19.90 MW as a duty cycle, 19.87 MW as a clock."""
    def total(**kw):
        lanes = B.decompose(
            scaled, build.R_SCREWS, 199.0, (), _cap(caps, "belt_mk3"), caps,
            build.worked_request(disposition=Disposition.BACK_UP, **kw), "screws",
        )
        return sum(l.power_mw for l in lanes)

    assert total() == pytest.approx(19.90, abs=0.005)
    assert total(clock_mode=ClockMode.EXPLICIT) == pytest.approx(19.87, abs=0.005)


# --------------------------------------------------------------------------
# buses_from_response
# --------------------------------------------------------------------------

def test_the_screw_bus_whole(scaled, caps):
    """Bus record sections 1 and 4: 5 machines, supply 200, R = 1.0/min."""
    result = B.buses_from_response(
        build.worked_response(), scaled, build.worked_request(), caps,
    )
    screws = next(b for b in result if b.bus_id == "screws")
    assert screws.machines == 5
    assert screws.supply_per_min == pytest.approx(200.0)
    assert screws.automated_demand_per_min == pytest.approx(199.0)
    assert screws.residual.rate_per_min == pytest.approx(1.0)
    assert screws.recipe_id == build.R_SCREWS
    assert not screws.in_deficit


def test_supply_is_nameplate_not_the_sum_of_the_clocked_lanes(scaled, caps):
    """`residual_for` derives utilisation from `supply_per_min`, so it has to be
    the 100% figure. Under BACK_UP the lanes sum to the demand and the supply
    does not — that difference IS the residual."""
    result = B.buses_from_response(
        build.worked_response(), scaled,
        build.worked_request(disposition=Disposition.BACK_UP), caps,
    )
    screws = next(b for b in result if b.bus_id == "screws")
    assert screws.supply_per_min == pytest.approx(200.0)
    assert sum(l.output_rate_per_min for l in screws.lanes) == pytest.approx(199.0)
    assert screws.residual.rate_per_min == pytest.approx(1.0)


def test_a_root_bus_takes_its_demand_from_the_solve(scaled, caps):
    """Smart Plating has no declared consumer, so in-scope demand is zero and
    `machine_equivalents * rate` supplies the out-of-scope draw — the analog of
    `busmodel.Declaration.external_per_min`, which `RealizationRequest` has no
    field for. One Assembler, 2/min."""
    result = B.buses_from_response(
        build.worked_response(), scaled, build.worked_request(), caps,
    )
    root = next(b for b in result if b.bus_id == "smart_plating")
    assert root.machines == 1
    assert root.supply_per_min == pytest.approx(2.0)
    assert root.automated_demand_per_min == pytest.approx(0.0)
    assert root.residual.rate_per_min == pytest.approx(2.0)


def test_buses_come_out_in_reverse_topological_order(scaled, caps):
    """Consumers before their sources: a bus is settled only after everything
    that draws on it."""
    result = B.buses_from_response(
        build.worked_response(), scaled, build.worked_request(), caps,
    )
    order = [b.bus_id for b in result]
    assert order.index("smart_plating") < order.index("rip")
    assert order.index("rip") < order.index("screws")
    assert order.index("rotor") < order.index("screws")


def test_two_buses_on_one_recipe_are_refused(scaled, caps):
    """One `machine_equivalents` figure cannot be split between two buses, and
    how to split it is a design decision the response does not carry."""
    buses = build.worked_buses() + (
        BusDeclaration(bus_id="screws_two", item_id=build.I_SCREW,
                       sources=(SourceEdge(build.I_IRON_ROD, None),),
                       disposition=Disposition.WITHDRAWN),
    )
    with pytest.raises(PartitionIncomplete, match="attributed to both"):
        B.buses_from_response(
            build.worked_response(), scaled,
            RealizationRequest(design_tier=4, buses=buses), caps,
        )


# --------------------------------------------------------------------------
# feasibility
# --------------------------------------------------------------------------

def test_a_sound_bus_reports_nothing(scaled, caps):
    result = B.buses_from_response(
        build.worked_response(), scaled, build.worked_request(), caps,
    )
    assert B.feasibility(next(b for b in result if b.bus_id == "screws")) == ()


def test_a_deficit_is_reported_and_not_repaired(scaled, caps):
    """The repair is one more producer and choosing to build it is the
    caller's. Supply below demand is also the ONLY case where splitter geometry
    decides outcomes, because nobody backs up."""
    result = B.buses_from_response(
        build.worked_response(), scaled, build.worked_request(), caps,
    )
    screws = next(b for b in result if b.bus_id == "screws")
    starved = dataclasses.replace(screws, supply_per_min=160.0)
    assert starved.in_deficit
    assert any("below automated demand" in f for f in B.feasibility(starved))


def test_a_branch_that_cannot_carry_its_draw_is_reported():
    """Rotor draws 124/min. One Mk.2 branch carries 120, so it starves
    regardless of backpressure — backpressure allocates surplus, it does not
    widen a belt. Built from `_realization_builders.bus()`, whose trunk is
    Mk.2, rather than through a trunk override: an override applies to every
    bus and the Rotor bus itself is `LaneInfeasible` at Mk.2, which is a
    different finding."""
    failures = B.feasibility(build.bus())
    assert len(failures) == 1
    assert "exceeds one branch" in failures[0]
    assert "Recipe_Rotor_C" in failures[0]


def test_a_consumer_that_draws_nothing_is_not_connected():
    """No topology is emitted, so reachability cannot be walked. What can be
    said is that a listed consumer drawing nothing is not connected to anything
    the bus carries."""
    ghost = dataclasses.replace(
        build.bus(),
        consumers=(build.ConsumerShare(recipe_id="Recipe_Rotor_C",
                                       draw_per_min=0.0, share=0.0),),
    )
    assert any("draws nothing" in f for f in B.feasibility(ghost))


def test_a_bus_with_no_producers_reaches_nobody():
    assert any(
        "no producers" in f
        for f in B.feasibility(dataclasses.replace(build.bus(), lanes=()))
    )


# --------------------------------------------------------------------------
# quantities the worked case's one-machine buses would otherwise hide
# --------------------------------------------------------------------------

def test_out_of_scope_demand_sizes_a_root_bus_beyond_one_machine(scaled, caps):
    """`test_a_root_bus_takes_its_demand_from_the_solve` cannot tell the
    external term from the machine floor, because both answer 1. At three
    machine-equivalents they separate: the solve sized this recipe for demand
    the declaration does not model, and dropping the term would leave the root
    at the floor."""
    result = B.buses_from_response(
        _equivalents(build.worked_response(), build.R_SMART_PLATING, 3.0),
        scaled, build.worked_request(), caps,
    )
    root = next(b for b in result if b.bus_id == "smart_plating")
    assert root.machines == 3
    assert root.supply_per_min == pytest.approx(6.0)


def test_a_consumer_drawing_on_two_machines_draws_twice(scaled):
    """PEAK basis, asserted where it is visible: every consumer in the worked
    case runs one machine, so `machines * per-machine rate` and the per-machine
    rate alone are the same number. Two Rotor Assemblers draw 248/min."""
    response = _equivalents(build.worked_response(), build.R_ROTOR, 2.0)
    shares = B.consumer_shares(response, scaled, build.worked_request(), "screws")
    draws = {s.recipe_id: s.draw_per_min for s in shares}
    assert draws[build.R_ROTOR] == pytest.approx(248.0)
    assert draws[build.R_RIP] == pytest.approx(75.0)


def test_a_declared_bus_the_solve_sized_at_nothing_still_gets_one_machine(
    scaled, caps,
):
    """The machine floor recovered in `tools/busmodel`, and what gives the
    records Cable 30.00/min and Concrete 15.00/min of overflow against zero
    automated demand. Without it a declared bus disappears from its own
    report."""
    result = B.buses_from_response(
        _equivalents(build.worked_response(), build.R_SMART_PLATING, 0.0),
        scaled, build.worked_request(), caps,
    )
    root = next(b for b in result if b.bus_id == "smart_plating")
    assert root.machines == 1
    assert root.supply_per_min == pytest.approx(2.0)
    assert root.residual.rate_per_min == pytest.approx(2.0)


def test_extra_producers_reach_the_bus_and_not_only_the_lanes(scaled, caps):
    """`decompose` and `_machines` each compute the bus total, and
    `Bus.supply_per_min` comes from one while `Bus.machines` sums the other.
    Asserting both here is what keeps the two copies from drifting apart
    silently."""
    result = B.buses_from_response(
        build.worked_response(), scaled, build.worked_request(extra_producers=1), caps,
    )
    screws = next(b for b in result if b.bus_id == "screws")
    assert screws.machines == 6
    assert screws.supply_per_min == pytest.approx(240.0)
    assert screws.residual.rate_per_min == pytest.approx(41.0)


def test_balanced_is_not_fill_then_spill(scaled, caps):
    """7 machines on a trunk that carries 3. Balanced is 3/2/2; fill-then-spill
    is 3/3/1, and at 5 machines the two agree — which is why the 5-machine case
    cannot tell them apart. Fill-then-spill is dominated: equal machines, equal
    residual, worse power, two clock settings rather than one."""
    lanes = B.decompose(
        scaled, build.R_SCREWS, 199.0, (), _cap(caps, "belt_mk2"), caps,
        build.worked_request(extra_producers=2), "screws",
    )
    assert [l.machines for l in lanes] == [3, 2, 2]
