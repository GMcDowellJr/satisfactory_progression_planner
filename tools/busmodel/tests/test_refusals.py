"""The model declines rather than emitting a figure it cannot stand behind.

Four refusals, each with a site. They are here rather than in a docstring for
the reason the repo has already demonstrated three times: where the invariant is
testable, make it a test.
"""
from __future__ import annotations

import pytest

from busmodel import (
    BusNotDeclared,
    BusSpec,
    CreditedFlowCycle,
    Declaration,
    DispositionUnavailable,
    SourceEdge,
    solve,
)
from busmodel import declarations as decls
from realization.contracts import Disposition


def test_matched_without_a_withdrawal_rate_is_refused():
    """MATCHED is defined as "underclocked to the average withdrawal rate".

    Without a rate there is nothing to match and no clock to derive, so the
    declaration is refused at construction rather than solved into a figure
    whose basis does not exist.
    """
    with pytest.raises(ValueError, match="nothing to match"):
        BusSpec(
            bus_id="plate_build",
            item_id=decls.I_IRON_PLATE,
            recipe_id=decls.R_IRON_PLATE,
            disposition=Disposition.MATCHED,
        )


def test_sunk_is_refused_by_name(scenario_of_record):
    """SUNK requires the AWESOME Sink, absent from the reference layer.

    Refused by name rather than silently downgraded to BACK_UP, which would
    misreport both the residual's fate and the power draw's stability. A4.2
    narrows what the absence costs and does not remove it.
    """
    decl = Declaration(
        name="sunk",
        buses=(
            BusSpec(
                bus_id="concrete", item_id=decls.I_CONCRETE, recipe_id=decls.R_CONCRETE,
                sources=(SourceEdge("Desc_Stone_C", None),),
                disposition=Disposition.SUNK,
            ),
        ),
    )
    with pytest.raises(DispositionUnavailable, match="AWESOME Sink"):
        solve(decl, scenario_of_record)


def test_an_undeclared_source_bus_is_refused():
    """Raised rather than defaulted.

    Under a declared partition, defaulting an unknown bus into existence
    re-merges exactly what the caller split.
    """
    with pytest.raises(BusNotDeclared):
        Declaration(
            name="dangling",
            buses=(
                BusSpec(
                    bus_id="rip", item_id=decls.I_RIP, recipe_id=decls.R_STITCHED_RIP,
                    sources=(SourceEdge(decls.I_WIRE, "wire_iron"),),
                ),
            ),
        )


def test_a_credited_flow_cycle_is_refused(scenario_of_record):
    """The demand pass is a single reverse-topological traversal.

    It is not iterated toward a fixed point, so on a cycle the map is
    non-monotone and no termination argument is available.
    """
    decl = Declaration(
        name="cycle",
        buses=(
            BusSpec(
                bus_id="plate", item_id=decls.I_IRON_PLATE, recipe_id=decls.R_IRON_PLATE,
                sources=(SourceEdge(decls.I_IRON_INGOT, "ingot"),),
            ),
            BusSpec(
                bus_id="ingot", item_id=decls.I_IRON_INGOT, recipe_id=decls.R_IRON_INGOT,
                sources=(SourceEdge("Desc_OreIron_C", "plate"),),
            ),
        ),
    )
    with pytest.raises(CreditedFlowCycle):
        solve(decl, scenario_of_record)


def test_a_duplicate_bus_id_is_refused():
    """Two buses of one item are ordinary; two buses with one id are not.

    Item-keying was the one-bus-per-item assumption in type form: two Wire
    declarations under it were accepted and the second was silently unreachable.
    """
    wire = BusSpec(bus_id="wire", item_id=decls.I_WIRE, recipe_id=decls.R_WIRE)
    with pytest.raises(ValueError, match="duplicate bus_id"):
        Declaration(name="dupe", buses=(wire, wire))


def test_two_buses_of_one_item_are_ordinary():
    """The complement of the test above, asserted so the refusal is not widened."""
    decl = Declaration(
        name="split",
        buses=(
            BusSpec(bus_id="wire_iron", item_id=decls.I_WIRE, recipe_id=decls.R_IRON_WIRE),
            BusSpec(bus_id="wire_copper", item_id=decls.I_WIRE, recipe_id=decls.R_WIRE),
        ),
    )
    assert len(decl.buses_of_item(decls.I_WIRE)) == 2
