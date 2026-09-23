"""The joint: a bill the stock pass COMPUTED, sized against a declared build.

Handoff 2026-09-22 10:00, next action 1. Until this file existed,
`progression.stock.bill_for` emitted `WithdrawalBill`s and
`BusDeclaration.withdrawal_bill` accepted them and NOTHING JOINED THEM — every
`ProjectedCoverage` on the record came from a hand-built fixture, so the whole
stock-basis chain was asserted end to end in types and had never run on a solve.

**The caller is the joint, and this file is the caller.** Neither package may
reach the other: `stock` imports `realization.contracts` for the bill TYPES and
nothing further, and `realization` imports `progression` not at all. Both
directions are asserted by `tests/test_progression_import_boundary.py` and
`tools/realization/tests/test_import_boundary.py`; nothing here weakens them,
because a test directory is above both packages rather than inside either.

It lives in `tests/` because `tests/conftest.py` is the only conftest in the
repo that puts all three src trees on `sys.path`. It deliberately does NOT
import `tools/realization/tests/_realization_builders.py`: the joint would then
be asserted through another package's private test fixtures, and the builders
are not on this directory's path anyway.

**Scenario.** One `ReferenceData` feeds both halves. A bill summed at 1x against
a bus sized at 1.25x is two answers to one question with nothing saying which
governs — the failure `Coverage.basis` exists to prevent, arriving as a
scenario mismatch instead of a basis mismatch. Building construction costs do
not move with the recipe multiplier (`load_construction` takes no scenario);
the Project Assembly term moves with its OWN multiplier, which is 2.0 here.

**The worked line is Concrete**, chosen because it is the term the
decomposition note calls the loosest floor: dominated by the spatial term,
which is absent until phase 5. A duration read off it is a floor by a wide and
unmeasured margin, and that is the point — the chain reports the floor it has,
labelled.
"""
from __future__ import annotations


import pathlib

import pytest

from production_adapter import load
from production_adapter.contracts import (
    ItemFlow, MachineCount, PowerReport, RecipeUse, SolveResponse,
)
from production_adapter.gamedata import load_construction, load_logistics
from production_adapter.scenario import MARGINAL_PEAK_DEBOTTLENECK
from progression import stock, unlocks
from realization.contracts import (
    BillTerm, BusDeclaration, PartitionIncomplete, RealizationRequest,
    SourceEdge, WithdrawalBasis,
)
from realization.realize import realize

REPO = pathlib.Path(__file__).resolve().parents[1]

I_CONCRETE = "Desc_Cement_C"
I_STONE = "Desc_Stone_C"
R_CONCRETE = "Recipe_Concrete_C"
CONSTRUCTOR = "Build_ConstructorMk1_C"

I_PORTABLE_MINER = "BP_ItemDescriptorPortableMiner_C"
I_SINK_COUPON = "Desc_ResourceSinkCoupon_C"

#: Greg's stated coal-power minimum. It is the bootstrap set that exercises the
#: Portable Miner gap, which is why it is the one used here as well as in
#: `test_progression_stock.py` — the gap has to survive the crossing.
BOOTSTRAP = (
    ("Build_GeneratorCoal_C", 1),
    ("Build_WaterPump_C", 1),
    ("Build_MinerMk1_C", 1),
)

#: Settled counts, handed in. NOT one of each, so `count` is visible in every
#: sum. The two Foundries are here for a reason: they are the only buildings in
#: the set that consume Concrete in the REMAINDER half, so without them the
#: worked line's remainder is zero and `minutes_to_total` collapses onto
#: `minutes_to_bootstrap` — one duration asserted twice.
SETTLED = (
    (CONSTRUCTOR, 5),
    ("Build_AssemblerMk1_C", 2),
    ("Build_FoundryMk1_C", 2),
)

TIER = 3
PHASES = (1,)


@pytest.fixture(scope="module")
def data():
    """The scenario of record. ONE instance, read by both halves."""
    return load(REPO).with_scenario(MARGINAL_PEAK_DEBOTTLENECK)


@pytest.fixture(scope="module")
def construction():
    return load_construction(REPO)


@pytest.fixture(scope="module")
def logistics():
    return load_logistics(REPO)


@pytest.fixture(scope="module")
def stock_pass(data, construction):
    """A REAL bill. Four terms, from four reference tables, over real counts."""
    return stock.bill_for(
        data,
        construction,
        bootstrap=stock.BootstrapSet(tier=TIER, buildings=BOOTSTRAP),
        machines=SETTLED,
        unlocks=unlocks.schematics_at_tier(REPO, TIER),
        unlock_costs=unlocks.schematic_costs(REPO),
        project_assembly=stock.load_project_assembly(REPO, data),
        phases=PHASES,
    )


def _empty_solve() -> SolveResponse:
    """A solve that runs nothing.

    The Concrete line is a bus the SOLVE DOES NOT RUN — that is the definition
    of a build-material line — so it needs no `RecipeUse` to be attributed
    from, and `recipe_id` on the declaration is where the caller supplies it
    (P30). An empty response is therefore the HONEST input here, not a stub:
    anything else would put a recipe in the solve that the declaration then
    collides with, which is the refusal pinned at the foot of this file.
    """
    return SolveResponse(
        recipes=(), items=(), raw_inputs=(),
        power=PowerReport(0.0, 0.0, 0.0, 0.0), machines=(), backend="test",
    )


def _concrete_line(bill) -> BusDeclaration:
    """One machine at the recovered floor. `extra_producers` is the lever.

    `withdrawal_basis` is LEFT AT ITS DEFAULT on purpose — see
    `test_the_bills_basis_governs_and_the_declarations_is_left_untouched`.
    """
    return BusDeclaration(
        bus_id="concrete",
        item_id=I_CONCRETE,
        recipe_id=R_CONCRETE,
        sources=(SourceEdge(I_STONE, None),),
        withdrawal_bill=bill,
    )


@pytest.fixture(scope="module")
def joined(data, logistics, stock_pass):
    """The whole chain, once: bill_for -> BusDeclaration -> realize."""
    capabilities, rates = logistics
    bill = stock_pass.bills[I_CONCRETE]
    request = RealizationRequest(
        design_tier=4, buses=(_concrete_line(bill),),
    )
    return bill, realize(_empty_solve(), data, capabilities, rates, request)


# --------------------------------------------------------------------------
# the crossing
# --------------------------------------------------------------------------

def test_a_computed_bill_produces_exactly_one_projected_verdict(joined):
    """One bill-sized line in, one stock-basis verdict out."""
    _bill, report = joined
    assert len(report.projected_coverage) == 1
    assert report.projected_coverage[0].bus_id == "concrete"
    assert report.projected_coverage[0].item_id == I_CONCRETE


def test_the_rate_shaped_verdict_stays_empty(joined):
    """`coverage` is empty because no line declared a withdrawal RATE, which is
    a different statement from "nothing covers". The two fields do not overlap
    and a reader never has to ask which shape an entry is."""
    _bill, report = joined
    assert report.coverage == ()


def test_the_quantities_cross_unaltered(joined):
    """The verdict's quantities ARE the bill's. Asserted against the bill
    object the pass emitted, never against a restated figure — a constant here
    would pass just as well if the two halves had been joined by coincidence.
    """
    bill, report = joined
    verdict = report.projected_coverage[0]
    assert verdict.bootstrap_units == bill.bootstrap_units
    assert verdict.remainder_units == bill.remainder_units
    assert verdict.total_units == bill.total_units


def test_the_terms_the_pass_summed_are_the_terms_the_verdict_reports(joined):
    """The floor can move underneath a basis that still reads the same, which
    is why `BillTerm` exists at all. This asserts the term set survives the
    crossing — the one thing that could drift silently and change what a
    duration means while every field still reads correctly.

    Four terms, and the two the caller supplied are named: a bill summed with
    UNLOCK_COST and PROJECT_ASSEMBLY that arrived reporting only the two base
    terms would be a floor understating itself.
    """
    bill, report = joined
    verdict = report.projected_coverage[0]
    assert verdict.terms == bill.terms
    assert verdict.terms == frozenset({
        BillTerm.MACHINE_CONSTRUCTION, BillTerm.BOOTSTRAP_SET,
        BillTerm.UNLOCK_COST, BillTerm.PROJECT_ASSEMBLY,
    })
    assert BillTerm.SPATIAL not in verdict.terms


def test_the_bills_basis_governs_and_the_declarations_is_left_untouched(joined):
    """The exact relabelling amendment 5 named, now exercised across the real
    join rather than across a fixture.

    `BusDeclaration.withdrawal_basis` carries the basis of the RATE and
    defaults to `GEOMETRIC_FLOOR`. On a bill-sized line it is never set, so it
    sits at that default while the bill carries a canonical basis. A verdict
    that read the declaration's field would label a four-term canonical bill as
    §8.2's footprint estimate — a wrong verdict wearing a right one's clothes.
    """
    bill, report = joined
    declaration = _concrete_line(bill)
    assert declaration.withdrawal_basis is WithdrawalBasis.GEOMETRIC_FLOOR
    assert report.projected_coverage[0].basis is (
        WithdrawalBasis.DERIVED_WHOLE_GAME_FLOOR
    )


# --------------------------------------------------------------------------
# the first real T_bootstrap
# --------------------------------------------------------------------------

def test_the_durations_are_the_bill_over_the_residual(joined):
    """T = bill / R, twice, derived from the report's OWN residual.

    Not a restated constant: the residual is read back off the verdict, so the
    assertion holds if the sizing changes and fails if the arithmetic does.
    """
    bill, report = joined
    verdict = report.projected_coverage[0]
    assert verdict.residual_per_min > 0.0
    assert verdict.minutes_to_bootstrap == pytest.approx(
        bill.bootstrap_units / verdict.residual_per_min
    )
    assert verdict.minutes_to_total == pytest.approx(
        bill.total_units / verdict.residual_per_min
    )
    assert verdict.minutes_to_bootstrap <= verdict.minutes_to_total


def test_the_worked_line_at_the_recovered_floor(joined):
    """The figures, pinned. Container, 2026-09-22, scenario of record.

        1 machine on Recipe_Concrete_C   15/min nameplate, R = 15/min
        bootstrap                        10 Concrete — the Miner Mk.1's 10,
                                         and nothing else in the coal set
                                         consumes Concrete
        remainder                        1520 — two Foundries at 20 each, plus
                                         the tier-3 unlock costs
        T_bootstrap                      40 seconds
        T_total                          102 minutes

    These are pinned SEPARATELY from the arithmetic test above so a change to
    the reference data fails here, by name, rather than silently moving a
    number the arithmetic test would still accept.
    """
    _bill, report = joined
    verdict = report.projected_coverage[0]
    assert verdict.residual_per_min == pytest.approx(15.0)
    assert verdict.bootstrap_units == pytest.approx(10.0)
    assert verdict.remainder_units == pytest.approx(1520.0)
    assert verdict.minutes_to_bootstrap == pytest.approx(2.0 / 3.0)
    assert verdict.minutes_to_total == pytest.approx(102.0)


def test_a_second_machine_halves_the_wait_and_nothing_else_moves(
    data, logistics, stock_pass
):
    """Respec §6's settled form, reached through the real bill. A stock cannot
    size a bus, so the caller DECLARES THE BUILD and reads the duration back.
    `extra_producers` is the lever; the bill does not move when it is pulled.
    """
    capabilities, rates = logistics
    bill = stock_pass.bills[I_CONCRETE]
    doubled = RealizationRequest(
        design_tier=4,
        buses=(
            BusDeclaration(
                bus_id="concrete", item_id=I_CONCRETE, recipe_id=R_CONCRETE,
                sources=(SourceEdge(I_STONE, None),),
                withdrawal_bill=bill, extra_producers=1,
            ),
        ),
    )
    report = realize(_empty_solve(), data, capabilities, rates, doubled)
    verdict = report.projected_coverage[0]

    assert next(b for b in report.buses if b.bus_id == "concrete").machines == 2
    assert verdict.residual_per_min == pytest.approx(30.0)
    assert verdict.total_units == bill.total_units
    assert verdict.minutes_to_total == pytest.approx(51.0)


#: THE `inf` PATH IS NOT REACHABLE FROM HERE, and that is a property of the
#: sizing rather than a gap in this file. A bill-sized line declares no
#: withdrawal rate, so its bus is sized `max(1, ceil(demand / rate)) +
#: extra_producers` and supply is nameplate — which means `residual >= 0`
#: always, and `residual <= EPS` only where in-scope demand lands exactly on
#: the nameplate. Every duration reachable through the real join is therefore
#: finite. `inf` is exercised in `tools/realization/tests/test_residual.py`
#: against a constructed zero-residual bus, which is the only way to reach it.


# --------------------------------------------------------------------------
# what the crossing does NOT carry
# --------------------------------------------------------------------------

def test_the_unresolved_cost_inputs_are_named_and_reach_no_verdict(stock_pass):
    """The floor's known gaps survive as a REPORT, not as a zero.

    The Portable Miner is a build cost for the Miner Mk.1 and is equipment
    rather than a part, so it is absent from items.csv by construction; two
    Custom schematics are priced in Sink Coupons for the same reason. All three
    are named in `unresolved` and none of them gets a bill — so no declaration
    can be made against them at all, which is the point. A bill emitted for an
    item the reference layer does not carry would put a quantity of something
    with no form on a bus that has no carrier.
    """
    named = {item for _source, item in stock_pass.unresolved}
    assert I_PORTABLE_MINER in named
    assert I_SINK_COUPON in named
    for item in named:
        assert item not in stock_pass.bills


def test_the_spatial_term_is_absent_and_that_is_what_keeps_it_a_floor(joined):
    """Restated at the joint because this is where a reader meets the number.

    Concrete is the item the decomposition note measures as dominated by the
    spatial term — 371 of the 544 io-carrying building recipes consume it,
    almost all structural. A T_total of 102 minutes is therefore a floor by a
    wide and unmeasured margin, and the verdict says so by naming its terms
    rather than by carrying prose.
    """
    _bill, report = joined
    assert BillTerm.SPATIAL not in report.projected_coverage[0].terms


# --------------------------------------------------------------------------
# limitations, pinned at the joint
# --------------------------------------------------------------------------

def test_a_build_material_line_on_a_recipe_the_solve_runs_is_refused(
    data, logistics, stock_pass
):
    """P30's live limitation, now with a consumer.

    A build-material line for an item the solve ALSO produces on the same
    recipe cannot be declared alongside it: two buses running one recipe share
    one `machine_equivalents` figure and splitting it is a design decision the
    response does not carry. Concrete and Cable are the likely first casualties
    in real use.

    Refused BY NAME rather than silently collapsing, and pinned here so that
    widening bus identity beyond (item, sources, recipe) fails this test
    instead of quietly changing what a declaration means.
    """
    capabilities, rates = logistics
    bill = stock_pass.bills[I_CONCRETE]
    response = SolveResponse(
        recipes=(RecipeUse(R_CONCRETE, CONSTRUCTOR, 1.0, 4.0),),
        items=(ItemFlow(I_CONCRETE, 15.0, 0.0),),
        raw_inputs=(),
        power=PowerReport(0.0, 0.0, 0.0, 0.0),
        machines=(MachineCount(CONSTRUCTOR, 1.0, 1),),
        backend="test",
    )
    request = RealizationRequest(
        design_tier=4,
        buses=(
            BusDeclaration(
                bus_id="concrete_production", item_id=I_CONCRETE,
                recipe_id=R_CONCRETE, sources=(SourceEdge(I_STONE, None),),
            ),
            _concrete_line(bill),
        ),
    )
    with pytest.raises(PartitionIncomplete, match=R_CONCRETE):
        realize(response, data, capabilities, rates, request)


def test_the_zero_clock_warning_fires_on_every_bill_sized_line(joined):
    """A CONTRADICTION in one report, pinned rather than patched.

    A bill contributes no rate, so a bill-sized line has zero in-scope demand,
    so `clock_for` returns 0% under BACKPRESSURE and the lane produces 0/min.
    `realize` warns on any 0% lane, and its text reads "Building past the ceil
    costs build cost and footprint and buys nothing" — while
    `projected_coverage` on the SAME line divides a bill by the 15/min that
    machine's nameplate supplies.

    Both figures are defensible on their own: 0% is the steady state with
    nobody withdrawing, and 15/min is the maximum sustained draw the declared
    build supports. The warning is wrong about the CAUSE — the machine is the
    recovered floor of one, not a machine past the ceil — and it is the cause,
    not the clock, that makes it read as advice to delete the machine the
    duration depends on.

    The warning's trigger checks `clock_percent` and does not check whether the
    line declares a bill. Pinned here rather than patched: it changes no
    emitted number, and the fix is a realization-layer decision about what a
    0% clock means on a line the solve does not run.
    """
    _bill, report = joined
    assert any(
        w.startswith("concrete:") and "0% clock" in w for w in report.warnings
    ), report.warnings
    assert report.projected_coverage[0].residual_per_min == pytest.approx(15.0)
    lane_output = sum(
        lane.output_rate_per_min
        for bus in report.buses if bus.bus_id == "concrete"
        for lane in bus.lanes
    )
    assert lane_output == pytest.approx(0.0)
