"""Behavioural coverage for the realization types. Handoff next action 2.

Before this file the layer's tests were an AST import scan, a dependency scan
and a module-set assertion — and **nothing anywhere constructed a `Bus`, a
`BusDeclaration` or a `BusResidual`**. That is why 23 type edits on 2026-09-21,
including three renames chosen to break loudly, broke nothing. A rename that
lands on nobody is not a signal.

Three of the four candidate tripwires now have a site and are asserted here:

    no stateless residual   `BusResidual.disposition` is required and
                            undefaulted, so the property holds by construction.
                            Nothing asserted it stayed that way
    matched needs a rate    P29. `Disposition.MATCHED` without
                            `withdrawal_per_min` has nothing to match
    coverage names a basis  `Coverage.basis` has no default, so a verdict cannot
                            be constructed without saying what it was measured
                            against

The fourth — "no single-scale delta" — still has no site: Phase 3 has not
started and there is no ranking surface to attach it to.

`partition coverage` (`PartitionIncomplete`) is NOT asserted here. Its site is
`buses_from_response`, which is still `NotImplementedError`; a test that
constructs the exception without the code that raises it asserts the class
statement and nothing else.
"""
from __future__ import annotations

import dataclasses

import pytest

import _realization_builders as build
from realization.contracts import (
    Bus, BusDeclaration, BusNotDeclared, BusResidual, ConsumerShare, Coverage,
    Disposition, RealizationRequest, SourceEdge, WithdrawalBasis,
)


# --------------------------------------------------------------------------
# tripwire: no stateless residual
# --------------------------------------------------------------------------

def test_bus_residual_requires_a_disposition():
    """The "no stateless residual" tripwire, in type form.

    A residual without its own bus's steady state is meaningless, which is how
    two documents computed R under different states and mistook the difference
    for an error. The field is required and undefaulted; this asserts it stays
    that way.
    """
    with pytest.raises(TypeError):
        BusResidual(                                  # type: ignore[call-arg]
            bus_id="screws",
            item_id=build.I_SCREW,
            rate_per_min=1.0,
            power_cost_mw=0.0,
        )


def test_bus_residual_disposition_has_no_default():
    """Asserted on the field rather than only through a failed call.

    A defaulted `disposition` would make the constructor above succeed and this
    whole class of error silent, so the absence of a default is the property —
    not the `TypeError` that happens to follow from it today.
    """
    field = {f.name: f for f in dataclasses.fields(BusResidual)}["disposition"]
    assert field.default is dataclasses.MISSING
    assert field.default_factory is dataclasses.MISSING


# --------------------------------------------------------------------------
# tripwire: MATCHED needs a rate (P29)
# --------------------------------------------------------------------------

def test_matched_without_a_withdrawal_rate_is_refused():
    """P29. MATCHED is "underclocked to the AVERAGE WITHDRAWAL RATE".

    Without a rate there is nothing to match and no clock to derive. Refused at
    construction, where the declaration is, rather than three calls later inside
    `clock_for` as an arithmetic fault on a `None`.
    """
    with pytest.raises(ValueError, match="requires withdrawal_per_min"):
        build.declaration(disposition=Disposition.MATCHED)


def test_a_withdrawal_without_matched_is_legal():
    """The converse, asserted so the refusal is not widened by a later edit.

    BACK_UP is the OTHER build-material sizing: whole machines, fills and
    pauses. A4.2 names two ways to run the line and this refusal must bite on
    neither of them.
    """
    declaration = build.declaration(
        disposition=Disposition.BACK_UP, withdrawal_per_min=2.0
    )
    assert declaration.is_build_material_line


def test_matched_with_a_withdrawal_rate_constructs():
    declaration = build.declaration(
        disposition=Disposition.MATCHED, withdrawal_per_min=2.0
    )
    assert declaration.disposition is Disposition.MATCHED
    assert declaration.is_build_material_line


# --------------------------------------------------------------------------
# tripwire: a coverage verdict names its basis
# --------------------------------------------------------------------------

def test_coverage_cannot_be_constructed_without_a_basis():
    """A3.3 makes the floor caveat a labelling requirement.

    A labelling requirement routed through `RealizationReport.warnings` is free
    text that nothing can assert. Here the verdict cannot exist without stating
    what it was measured against, which is the repo's standing rule that a
    structural guardrail beats a policy.
    """
    with pytest.raises(TypeError):
        Coverage(                                     # type: ignore[call-arg]
            bus_id="concrete",
            item_id="Desc_Cement_C",
            residual_per_min=9.0,
            withdrawal_per_min=6.0,
            covers=True,
        )
    field = {f.name: f for f in dataclasses.fields(Coverage)}["basis"]
    assert field.default is dataclasses.MISSING


def test_the_only_withdrawal_basis_is_the_geometric_floor():
    """There is currently one, and `covers=True` therefore means "covers the
    floor", never "covers"."""
    assert tuple(WithdrawalBasis) == (WithdrawalBasis.GEOMETRIC_FLOOR,)


# --------------------------------------------------------------------------
# the declared partition
# --------------------------------------------------------------------------

def test_two_buses_of_one_item_are_different_objects():
    """A3.1, and the reason `BusDeclaration` is keyed by `bus_id`.

    Item-keying was the one-bus-per-item assumption in type form: two Wire
    declarations under it were accepted and the second was silently unreachable.
    """
    wire = "Desc_Wire_C"
    request = RealizationRequest(
        design_tier=4,
        buses=(
            BusDeclaration(bus_id="wire_iron", item_id=wire,
                           sources=(SourceEdge(build.I_IRON_INGOT, "iron_ingot"),)),
            BusDeclaration(bus_id="wire_copper", item_id=wire,
                           sources=(SourceEdge("Desc_CopperIngot_C", "copper_ingot"),)),
        ),
    )
    both = request.declarations_for_item(wire)
    assert len(both) == 2
    assert {d.bus_id for d in both} == {"wire_iron", "wire_copper"}
    assert request.declaration_for("wire_iron") is not request.declaration_for("wire_copper")


def test_a_duplicate_bus_id_is_refused():
    declaration = build.declaration()
    with pytest.raises(ValueError, match="duplicate bus_id"):
        RealizationRequest(design_tier=4, buses=(declaration, declaration))


def test_an_undeclared_bus_raises_rather_than_defaulting():
    """Under a declared partition a default is not a sensible fallback: which
    bus an item runs on is precisely what the caller states, and inventing one
    re-merges the buses the caller split."""
    request = RealizationRequest(design_tier=4, buses=(build.declaration(),))
    with pytest.raises(BusNotDeclared):
        request.declaration_for("wire_iron")


def test_an_input_may_name_at_most_one_source_bus():
    with pytest.raises(ValueError, match="at most one source bus"):
        BusDeclaration(
            bus_id="rip",
            item_id="Desc_IronPlateReinforced_C",
            sources=(
                SourceEdge("Desc_Wire_C", "wire_iron"),
                SourceEdge("Desc_Wire_C", "wire_copper"),
            ),
        )


def test_extra_producers_must_be_non_negative():
    with pytest.raises(ValueError, match="extra_producers"):
        build.declaration(extra_producers=-1)


def test_a_negative_withdrawal_is_refused():
    with pytest.raises(ValueError, match="withdrawal_per_min"):
        build.declaration(withdrawal_per_min=-1.0)


# --------------------------------------------------------------------------
# Bus, constructed whole
# --------------------------------------------------------------------------

def test_a_whole_bus_constructs_and_its_derived_properties_hold():
    """The screw bus of bus record sections 1 and 4, built as an object.

        199/min demand    RIP 75 (37.7%)   Rotor 124 (62.3%)
        5 machines, 200/min supply, R = 1.0/min
    """
    screws = build.bus()
    assert screws.machines == 5
    assert screws.supply_per_min == pytest.approx(200.0)
    assert screws.residual.rate_per_min == pytest.approx(1.0)
    assert not screws.in_deficit
    shares = {c.recipe_id: c for c in screws.consumers}
    assert shares["Recipe_IronPlateReinforced_C"].share == pytest.approx(0.377, abs=0.001)
    assert shares["Recipe_Rotor_C"].share == pytest.approx(0.623, abs=0.001)
    assert sum(c.draw_per_min for c in screws.consumers) == pytest.approx(199.0)


def test_in_deficit_is_the_only_case_where_geometry_decides():
    """Supply below automated demand. Nobody backs up, so the nominal ratio
    picks who starves. Adding one producer removes the problem rather than
    solving it."""
    assert build.bus(supply_per_min=160.0).in_deficit
    assert not build.bus(supply_per_min=200.0).in_deficit
    #: Exactly balanced is not a deficit — backpressure has nothing to allocate
    #: but nobody starves either.
    assert not build.bus(supply_per_min=199.0).in_deficit


def test_machines_sums_the_lanes_and_never_the_ceil():
    """`Bus.machines` is the lanes' total. A lane is a parallel producer line
    INSIDE a bus, and the ceil happens once per bus, not once per lane."""
    screws = dataclasses.replace(
        build.bus(), lanes=(build.lane(machines=3), build.lane(machines=2))
    )
    assert screws.machines == 5


def test_withdrawal_is_not_inside_automated_demand():
    """`Bus` says so in as many words, and it is what makes a coverage verdict
    mean anything: the withdrawal does not size the bus, it is what the residual
    has to cover. Folding it in would compare a number against itself."""
    screws = build.bus(withdrawal_per_min=5.0)
    assert screws.automated_demand_per_min == pytest.approx(199.0)
    assert screws.withdrawal_per_min == pytest.approx(5.0)
    assert screws.residual.rate_per_min == pytest.approx(1.0)


def test_player_withdrawal_is_a_consumer_with_no_recipe():
    """A3.1 names it as the third consumer on the Wire bus. It carries
    `share=None`: withdrawal is not in the denominator, because it is covered by
    the residual rather than sized into the bus."""
    withdrawal = ConsumerShare(recipe_id=None, draw_per_min=5.0, share=None)
    assert withdrawal.is_withdrawal
    assert not ConsumerShare(recipe_id="Recipe_Cable_C", draw_per_min=9.0,
                             share=0.5).is_withdrawal


def test_the_four_steady_states_are_the_whole_enum():
    """A4.2 adds a fourth and the enum is NOT split: the drain is a derived
    property of one declared state. If a fifth arrives, this names it."""
    assert {d.value for d in Disposition} == {"back_up", "sunk", "withdrawn", "matched"}


def test_the_types_are_frozen():
    """A report that can be mutated after it is emitted is not a report."""
    screws = build.bus()
    for obj, field, value in (
        (screws, "supply_per_min", 1.0),
        (screws.residual, "rate_per_min", 1.0),
        (build.declaration(), "disposition", Disposition.BACK_UP),
    ):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, field, value)
