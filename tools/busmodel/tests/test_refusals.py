"""The model declines rather than emitting a figure it cannot stand behind.

Four refusals, each with a site. They are here rather than in a docstring for
the reason the repo has already demonstrated three times: where the invariant is
testable, make it a test.
"""
from __future__ import annotations

import pytest

from busmodel import (
    BusModelError,
    BusNotDeclared,
    BusSpec,
    CreditedFlowCycle,
    Declaration,
    DispositionUnavailable,
    SizingBasis,
    SourceEdge,
    solve,
)
from busmodel import declarations as decls
from busmodel.model import SOLVE_BASES
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
            # A12: a DERIVED MATCHED always carries its rate, so this refusal
            # is reachable only through the record path.
            stores=False,
            recorded_disposition=Disposition.MATCHED,
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
                # A12: SUNK is not derivable from the toggle; the record path
                # is what keeps this refusal reachable and tested.
                recorded_disposition=Disposition.SUNK,
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


# --------------------------------------------------------------------------
# the peak demotion, 2026-09-22. A5.2
# --------------------------------------------------------------------------

def test_the_peak_basis_is_refused_by_name_and_says_where_the_peak_went(
    scenario_of_record
):
    """`SizingBasis.PEAK` stopped being a solve mode and is refused, not removed.

    Removing the member would answer a caller with an AttributeError, which
    says nothing about why. The refusal names A5.2 and names the three fields
    that carry the peak instead, so the demotion is discoverable at the call
    site rather than only in a decision record.
    """
    data = scenario_of_record
    with pytest.raises(BusModelError, match="not a sizing basis"):
        solve(decls.worked_case_a4(data), data, sizing_basis=SizingBasis.PEAK)


def test_a_bus_spec_no_longer_accepts_presents_peak_draw():
    """The loud break. A caller who still means "size this against nameplate"
    gets a TypeError rather than a field that is quietly never read.

    A declaration nothing reads is worse than no declaration: it lets a caller
    state a preference that silently does not apply.
    """
    with pytest.raises(TypeError, match="presents_peak_draw"):
        BusSpec(
            bus_id="plate_build",
            item_id=decls.I_IRON_PLATE,
            recipe_id=decls.R_IRON_PLATE,
            presents_peak_draw=True,
        )


@pytest.mark.parametrize("basis", sorted(SOLVE_BASES, key=lambda b: b.value))
def test_no_machine_count_anywhere_reads_the_peak(scenario_of_record, basis):
    """The guardrail that keeps the demotion from undoing itself.

    A peak that can move a machine count is `presents_peak_draw` again under a
    new name. Asserted structurally: the sizing reads `demand_per_min`, so
    doubling every peak in the model must leave every machine count, every
    residual and every clock exactly where it was.

    Checked by re-solving a declaration whose peaks differ wildly from its
    averages — the BACK_UP build line's peak is ten times its draw — and
    asserting the two runs agree on everything except the peak columns.

    Over BOTH sizing bases since 2026-09-23. It ran on the default alone, and
    the default moved (amendment 10); a guardrail that silently changes which
    basis it guards is guarding less than it says.
    """
    data = scenario_of_record
    matched = solve(decls.worked_case_a4(data), data, sizing_basis=basis)
    full = solve(
        decls.worked_case_a4(data, build_plate_disposition=Disposition.BACK_UP),
        data,
        sizing_basis=basis,
    )
    for a, b in zip(matched.buses, full.buses):
        assert a.bus_id == b.bus_id
        if a.bus_id == decls.BUS_IRON_PLATE_BUILD:
            continue   # the one bus whose own declaration changed
        assert a.machines == b.machines, a.bus_id
        assert a.demand_per_min == pytest.approx(b.demand_per_min), a.bus_id
        assert a.residual_per_min == pytest.approx(b.residual_per_min), a.bus_id
        assert a.clock_percent == pytest.approx(b.clock_percent), a.bus_id
    # ... and the peak is where the difference went.
    assert matched["iron_ingot"].peak_demand_per_min != (
        full["iron_ingot"].peak_demand_per_min
    )


@pytest.mark.parametrize("basis", sorted(SOLVE_BASES, key=lambda b: b.value))
def test_a_matched_line_has_no_transient_to_report(scenario_of_record, basis):
    """Peak equals average under MATCHED, which is the state's whole point.

    Supply equals demand by construction, so the machine is already clocked to
    the draw. Reporting a nameplate peak for it would invent a transient the
    state is defined to not have. Over both bases, for the reason the guardrail
    above gives.
    """
    data = scenario_of_record
    solution = solve(decls.worked_case_a4(data), data, sizing_basis=basis)
    build = solution[decls.BUS_IRON_PLATE_BUILD]
    assert build.disposition is Disposition.MATCHED
    share = next(
        s for s in solution["iron_ingot"].consumers
        if s.bus_id == decls.BUS_IRON_PLATE_BUILD
    )
    assert share.peak_per_min == pytest.approx(share.draw_per_min)
    assert build.peak_shortfall_per_min == pytest.approx(0.0)


# --------------------------------------------------------------------------
# the default is the model; the record is named (amendment 10, superseded in
# its default by amendment 12)
# --------------------------------------------------------------------------

def test_the_default_basis_is_storage():
    """A12 (D1): the storage toggle sets the basis per line, and a call that
    names no basis gets that. A10 had made the default `USAGE`, which is
    "storage off everywhere" — the opposite of the default toggle."""
    import inspect

    default = inspect.signature(solve).parameters["sizing_basis"].default
    assert default is SizingBasis.STORAGE


def test_the_default_moves_the_worked_case_off_usage(scenario_of_record):
    """29 machines against USAGE's 23 (A6.3). This is what lets the default pin
    fail: a STORAGE rule reverted to usage answers 23 here.

    STORAGE equals AVERAGE on this declaration, and on every declaration today,
    BY CONSTRUCTION — a storing line is WITHDRAWN and a WITHDRAWN line runs at
    100%. Pinned as an equality so that the day D2 gives a storing line a
    target clock, this test is where the two rules are seen to part."""
    data = scenario_of_record
    decl = decls.worked_case_a4(data)
    assert solve(decl, data).total_machines == 29
    assert solve(decl, data, sizing_basis=SizingBasis.USAGE).total_machines == 23
    assert solve(decl, data, sizing_basis=SizingBasis.AVERAGE).total_machines == 29


def test_storage_off_everywhere_is_usage(scenario_of_record):
    """The toggle is the whole of the difference. Every line of the worked case
    with storage OFF (record paths dropped, so each line derives from the
    toggle alone) solves under STORAGE exactly as the whole declaration does
    under USAGE."""
    import dataclasses

    data = scenario_of_record
    decl = decls.worked_case_a4(data)
    off = dataclasses.replace(
        decl,
        buses=tuple(
            dataclasses.replace(b, stores=False, recorded_disposition=None)
            for b in decl.buses
        ),
    )
    a = solve(off, data)
    b = solve(decl, data, sizing_basis=SizingBasis.USAGE)
    assert [x.machines for x in a.buses] == [y.machines for y in b.buses]
    for x, y in zip(a.buses, b.buses):
        assert x.automated_demand_per_min == pytest.approx(y.automated_demand_per_min)


def test_a_storing_line_with_nothing_to_store_is_reported(scenario_of_record):
    """D1's "no residual" report. On `worked_case_A4` Smart Plating and Rotor
    store and have residual 0.00 (A6.3); Screws stores 36.00; the MATCHED
    Iron Plate build line has storage off. The report names the first two and
    picks no remedy."""
    data = scenario_of_record
    solution = solve(decls.worked_case_a4(data), data)
    flagged = {b.bus_id for b in solution.buses if b.stores_nothing}
    assert {"smart_plating", "rotor"} <= flagged
    assert "screws" not in flagged
    assert decls.BUS_IRON_PLATE_BUILD not in flagged


def test_out_of_scope_draw_follows_the_storage_basis(scenario_of_record):
    """The report mirrors `solve`'s branch, or an out-of-scope figure sits on a
    different basis from the in-scope ones — the section 6.1 defect in a new
    place. Iron Ore on `worked_case_A4`: 210.00/min with the record's storing
    lines drawing what they produce, 115.89 with storage off (A6.3)."""
    from busmodel.report import out_of_scope_draw

    data = scenario_of_record
    decl = decls.worked_case_a4(data)
    storage = out_of_scope_draw(decl, data, solve(decl, data))
    usage = out_of_scope_draw(
        decl, data, solve(decl, data, sizing_basis=SizingBasis.USAGE))
    assert storage["Desc_OreIron_C"] == pytest.approx(210.00, abs=0.005)
    assert usage["Desc_OreIron_C"] == pytest.approx(115.89, abs=0.005)


def test_disposition_is_no_longer_a_declaration():
    """Q4: a TypeError, the loud break A6.1 chose for `presents_peak_draw`."""
    with pytest.raises(TypeError, match="disposition"):
        BusSpec(bus_id="x", item_id=decls.I_WIRE, recipe_id=decls.R_WIRE,
                disposition=Disposition.WITHDRAWN)


def test_only_the_record_uses_the_record_path(repo_root):
    """A12, Q5. `recorded_disposition` exists so the published tables still
    reproduce. Anywhere else under `tools/*/src` it would let a caller declare
    a state the toggle deliberately does not offer. Asserted by inspection:
    outside the two contracts that define it and the module that holds the
    record, no source file passes it."""
    import pathlib

    allowed = {
        pathlib.Path("tools/busmodel/src/busmodel/declarations.py"),
        pathlib.Path("tools/busmodel/src/busmodel/model.py"),
        pathlib.Path("tools/realization/src/realization/contracts.py"),
    }
    offenders = [
        path.relative_to(repo_root)
        for path in (repo_root / "tools").glob("*/src/**/*.py")
        if "recorded_disposition" in path.read_text(encoding="utf-8")
        and path.relative_to(repo_root) not in allowed
    ]
    assert offenders == []


def test_the_cli_defaults_to_storage_and_takes_the_others_as_overrides(capsys, repo_root):
    """`python -m busmodel` without `--basis` renders the storage basis;
    `--basis usage` and `--basis average` are the overrides. The rendered table
    names its basis either way — an output must say which it is."""
    from busmodel.cli import main

    main(["worked_case_A4", "--repo", str(repo_root)])
    out = capsys.readouterr().out
    assert "basis storage" in out
    # A12: the "no residual" report reaches the rendered output.
    assert "storing, nothing to store:" in out and "smart_plating" in out
    main(["worked_case_A4", "--repo", str(repo_root), "--basis", "usage"])
    assert "basis usage" in capsys.readouterr().out
    main(["worked_case_A4", "--repo", str(repo_root), "--basis", "average"])
    assert "basis average" in capsys.readouterr().out
