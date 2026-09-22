"""`residual.py`'s seven bodies. Handoff next action 3, residual.py first.

The module's own docstring carries a nine-cell power table that the record has
been quoting since 2026-09-21 and that no code in the repo produced. It is
reproduced here, cell for cell, which is what the table was carried for.

    machines  supply   R          at 100%     backing up   underclocked
      5          200    1.0/min    20.00 MW    19.90 MW     19.87 MW
      6 (+1)     240   41.0/min    24.00 MW    19.90 MW     18.74 MW
      7 (+2)     280   81.0/min    28.00 MW    19.90 MW     17.83 MW
"""
from __future__ import annotations

import dataclasses
import math

import pytest

import _realization_builders as build
from realization import residual as R
from realization.contracts import (
    ClockCause, ClockDistribution, ClockMode, Disposition, DispositionUnavailable,
    BillTerm, RealizationError, WithdrawalBasis, WithdrawalBill,
)

SCREW_DEMAND = 199.0
PRODUCER_RATE = 40.0


# --------------------------------------------------------------------------
# the section 4 table
# --------------------------------------------------------------------------

@pytest.mark.parametrize("machines,supply,residual,at_100,backing_up,underclocked", [
    (5, 200.0, 1.0, 20.00, 19.90, 19.87),
    (6, 240.0, 41.0, 24.00, 19.90, 18.74),
    (7, 280.0, 81.0, 28.00, 19.90, 17.83),
])
def test_section_4_power_table(machines, supply, residual, at_100, backing_up, underclocked):
    utilisation = SCREW_DEMAND / supply
    assert R.residual_of(supply, SCREW_DEMAND) == pytest.approx(residual, abs=0.005)
    assert R.power_at_clock(build.CONSTRUCTOR, 100.0, machines) == pytest.approx(at_100, abs=0.005)
    assert R.power_backing_up(build.CONSTRUCTOR, machines, utilisation) == pytest.approx(
        backing_up, abs=0.005
    )
    assert R.power_at_clock(
        build.CONSTRUCTOR, utilisation * 100.0, machines
    ) == pytest.approx(underclocked, abs=0.005)


def test_backing_up_is_flat_in_machine_count():
    """With no drain, power is a function of THROUGHPUT alone and extra
    producers merely idle more. Building past the ceil costs build cost and
    footprint and nothing in power, and buys nothing."""
    figures = [
        R.power_backing_up(build.CONSTRUCTOR, m, SCREW_DEMAND / (m * PRODUCER_RATE))
        for m in (5, 6, 7)
    ]
    assert figures[0] == pytest.approx(figures[1]) == pytest.approx(figures[2])
    assert figures[0] == pytest.approx(19.90, abs=0.005)


def test_underclocking_falls_in_machine_count():
    """Power is convex in clock, so spreading a fixed output over more machines
    is strictly cheaper. This is the only column where extra producers pay for
    themselves."""
    figures = [
        R.power_at_clock(build.CONSTRUCTOR, 100.0 * SCREW_DEMAND / (m * PRODUCER_RATE), m)
        for m in (5, 6, 7)
    ]
    assert figures[0] > figures[1] > figures[2]


def test_only_running_at_100_percent_scales_up():
    figures = [R.power_at_clock(build.CONSTRUCTOR, 100.0, m) for m in (5, 6, 7)]
    assert figures == pytest.approx([20.0, 24.0, 28.0])


@pytest.mark.parametrize("utilisation,explicit,backing_up", [
    (0.995, 19.87, 19.90),
    (0.900, 17.40, 18.00),
    (0.800, 14.89, 16.00),
    (0.500, 8.00, 10.00),
])
def test_the_convex_saving_an_explicit_clock_buys(utilisation, explicit, backing_up):
    """`power_backing_up`'s own docstring table. The saving grows with slack:
    +0.2% at 99.5% utilisation, +25% at 50%."""
    assert R.power_at_clock(build.CONSTRUCTOR, utilisation * 100.0, 5) == pytest.approx(
        explicit, abs=0.005
    )
    assert R.power_backing_up(build.CONSTRUCTOR, 5, utilisation) == pytest.approx(
        backing_up, abs=0.005
    )


def test_the_exponent_is_read_from_the_producer_not_hardcoded():
    """`power_exponent` is DATA. A producer with a linear curve must come back
    linear, which a hardcoded 1.321929 would not."""
    linear = dataclasses.replace(build.CONSTRUCTOR, power_exponent=1.0)
    assert R.power_at_clock(linear, 50.0, 5) == pytest.approx(10.0)
    assert R.power_at_clock(build.CONSTRUCTOR, 50.0, 5) == pytest.approx(8.0, abs=0.005)


def test_a_variable_power_producer_is_refused_rather_than_reported_as_free():
    """The signature gap, named rather than papered over.

    Converter, Particle Accelerator and Quantum Encoder carry
    `base_power_mw = 0` in `production_buildings.csv`; their real draw is a
    per-RECIPE range this signature cannot reach. Returning 0.0 would report
    silently free machines.
    """
    with pytest.raises(RealizationError, match="variable-power"):
        R.power_at_clock(build.CONVERTER, 100.0, 1)
    with pytest.raises(RealizationError, match="variable-power"):
        R.power_backing_up(build.CONVERTER, 1, 0.5)


def test_every_reference_producer_carries_the_same_exponent(reference):
    """Eleven producers, one exponent. The docstrings say so; this measures it,
    so a future extract that changes one is a failure rather than a surprise."""
    exponents = {p.power_exponent for p in reference.producers.values()}
    assert exponents == {1.321929}
    assert len(reference.producers) == 11


def test_variable_power_producers_carry_zero_base_power(reference):
    """The reason `power_at_clock` refuses them, asserted against the data
    rather than assumed from three names."""
    variable = {k for k, p in reference.producers.items() if p.is_variable_power}
    assert variable == {
        "Build_Converter_C", "Build_HadronCollider_C", "Build_QuantumEncoder_C",
    }
    assert all(reference.producers[k].base_power_mw == 0.0 for k in variable)


# --------------------------------------------------------------------------
# clock_for — the five-branch table
# --------------------------------------------------------------------------

@pytest.mark.parametrize("disposition", [Disposition.WITHDRAWN, Disposition.SUNK])
def test_withdrawn_and_sunk_run_every_machine_at_100(disposition):
    declaration = build.declaration(
        disposition=disposition,
        withdrawal_per_min=2.0 if disposition is Disposition.SUNK else None,
    )
    clocks = R.clock_for(declaration, SCREW_DEMAND, 200.0, 5)
    assert clocks == tuple((100.0, ClockCause.FULL) for _ in range(5))


def test_matched_takes_its_clock_from_the_declared_rate_not_the_demand():
    """A4.1's Iron Plate build line: one Constructor makes 20 plate/min against
    a geometric withdrawal estimate of 2.00/min, so the clock is 10%.

    The clock comes from `withdrawal_per_min`, not from bus demand — the point
    of the state is that the line's output IS the declared average draw.
    """
    declaration = build.declaration(
        bus_id="iron_plate_build", item_id=build.I_IRON_PLATE,
        disposition=Disposition.MATCHED, withdrawal_per_min=2.0,
    )
    clocks = R.clock_for(declaration, 0.0, 20.0, 1)
    assert clocks == ((pytest.approx(10.0), ClockCause.MATCHED),)


def test_matched_is_distinct_from_declared():
    """The caller stated a DRAW, not a percentage, and the percentage moves when
    the scenario multiplier does. A cause of DECLARED would lose that."""
    declaration = build.declaration(
        disposition=Disposition.MATCHED, withdrawal_per_min=2.0
    )
    assert R.clock_for(declaration, 0.0, 20.0, 1)[0][1] is ClockCause.MATCHED
    assert ClockCause.MATCHED is not ClockCause.DECLARED


def test_matched_above_nameplate_is_refused():
    """A withdrawal the machine set cannot make is a sizing error, not a clock
    above 100%. Refused rather than clamped."""
    declaration = build.declaration(
        disposition=Disposition.MATCHED, withdrawal_per_min=50.0
    )
    with pytest.raises(RealizationError, match="cannot be MATCHED"):
        R.clock_for(declaration, 0.0, 20.0, 1)


def test_back_up_under_backpressure_is_demand_over_supply():
    declaration = build.declaration(disposition=Disposition.BACK_UP)
    clocks = R.clock_for(declaration, SCREW_DEMAND, 200.0, 5)
    assert clocks == tuple((pytest.approx(99.5), ClockCause.BACKPRESSURE) for _ in range(5))


def test_back_up_explicit_averaged_is_the_same_clock_with_a_different_cause():
    """Backpressure already makes the lane exact. What an explicit clock buys is
    the POWER CURVE, not the exactness — which is why the number is identical
    and only the cause moves."""
    declaration = build.declaration(
        disposition=Disposition.BACK_UP, clock_mode=ClockMode.EXPLICIT,
        clock_distribution=ClockDistribution.AVERAGED,
    )
    clocks = R.clock_for(declaration, SCREW_DEMAND, 200.0, 5)
    assert clocks == tuple((pytest.approx(99.5), ClockCause.DECLARED) for _ in range(5))


def test_back_up_explicit_split_is_n_at_100_plus_a_remainder():
    declaration = build.declaration(
        disposition=Disposition.BACK_UP, clock_mode=ClockMode.EXPLICIT,
        clock_distribution=ClockDistribution.SPLIT,
    )
    clocks = R.clock_for(declaration, SCREW_DEMAND, 200.0, 5)
    assert [c for c, _ in clocks] == pytest.approx([100.0, 100.0, 100.0, 100.0, 97.5])
    assert {cause for _, cause in clocks} == {ClockCause.DECLARED}


def test_split_is_power_suboptimal_against_averaged():
    """Power is convex in clock, so the averaged distribution is power-optimal
    for a fixed machine set and SPLIT is the reportable one."""
    declaration = build.declaration(
        disposition=Disposition.BACK_UP, clock_mode=ClockMode.EXPLICIT
    )
    averaged = R.clock_for(
        dataclasses.replace(declaration, clock_distribution=ClockDistribution.AVERAGED),
        SCREW_DEMAND, 200.0, 5,
    )
    split = R.clock_for(
        dataclasses.replace(declaration, clock_distribution=ClockDistribution.SPLIT),
        SCREW_DEMAND, 200.0, 5,
    )
    power = lambda cs: sum(R.power_at_clock(build.CONSTRUCTOR, c, 1) for c, _ in cs)
    assert power(split) > power(averaged)


def test_split_past_the_ceil_reports_a_machine_with_nothing_to_do():
    """Section 4 measures that building past the ceil under BACK_UP buys
    nothing. Under a declared SPLIT the surplus is exactly the machine at 0%,
    which is not buildable in game — that is the finding, reported rather than
    smoothed away."""
    declaration = build.declaration(
        disposition=Disposition.BACK_UP, clock_mode=ClockMode.EXPLICIT,
        clock_distribution=ClockDistribution.SPLIT, extra_producers=1,
    )
    clocks = R.clock_for(declaration, SCREW_DEMAND, 240.0, 6)
    assert [c for c, _ in clocks] == pytest.approx([100.0, 100.0, 100.0, 100.0, 97.5, 0.0])


def test_clock_for_emits_one_entry_per_machine():
    declaration = build.declaration(disposition=Disposition.BACK_UP)
    for machines in (1, 3, 7):
        assert len(R.clock_for(declaration, SCREW_DEMAND, machines * 40.0, machines)) == machines


def test_clock_for_refuses_a_degenerate_bus():
    declaration = build.declaration(disposition=Disposition.BACK_UP)
    with pytest.raises(ValueError):
        R.clock_for(declaration, SCREW_DEMAND, 200.0, 0)
    with pytest.raises(ValueError):
        R.clock_for(declaration, SCREW_DEMAND, 0.0, 5)


# --------------------------------------------------------------------------
# residual_for
# --------------------------------------------------------------------------

def test_residual_for_carries_the_declared_steady_state(reference):
    """The "no stateless residual" tripwire at the emitting site rather than at
    the type. A residual without its bus's state is meaningless."""
    bus = build.bus()
    declaration = build.declaration(disposition=Disposition.WITHDRAWN)
    result = R.residual_for(reference, bus, declaration)
    assert result.disposition is Disposition.WITHDRAWN
    assert result.rate_per_min == pytest.approx(1.0)
    assert result.bus_id == "screws"
    assert result.power_cost_mw == pytest.approx(0.0)


def test_sunk_is_refused_by_name(reference):
    """Refused rather than silently downgraded to BACK_UP, which would
    misreport both the residual's fate and the power draw's stability."""
    with pytest.raises(DispositionUnavailable, match="AWESOME Sink"):
        R.residual_for(
            reference, build.bus(),
            build.declaration(disposition=Disposition.SUNK, withdrawal_per_min=0.0),
        )


def test_back_up_reports_the_convex_saving_it_leaves_on_the_table(reference):
    """Under BACKPRESSURE the belts idle the machines, so the bus pays the
    linear duty-cycle figure where an explicit clock would pay the convex one.
    On the screw bus at the ceil that is 19.90 against 19.87."""
    result = R.residual_for(
        reference, build.bus(), build.declaration(disposition=Disposition.BACK_UP)
    )
    assert result.power_cost_mw == pytest.approx(19.90 - 19.868, abs=0.005)
    assert result.power_cost_mw > 0


def test_an_explicit_clock_has_already_taken_the_saving(reference):
    result = R.residual_for(
        reference, build.bus(),
        build.declaration(disposition=Disposition.BACK_UP, clock_mode=ClockMode.EXPLICIT),
    )
    assert result.power_cost_mw == pytest.approx(0.0)


def test_the_residual_excludes_the_declared_withdrawal(reference):
    """R is supply minus AUTOMATED demand. The withdrawal is what the residual
    has to cover, so folding it in would make every coverage verdict compare a
    number against itself."""
    bus = build.bus(withdrawal_per_min=5.0)
    result = R.residual_for(reference, bus, build.declaration(withdrawal_per_min=5.0))
    assert result.rate_per_min == pytest.approx(1.0)


# --------------------------------------------------------------------------
# coverage_for and draw_is_stable
# --------------------------------------------------------------------------

def test_a_residual_item_has_no_coverage_verdict():
    """`None`, not `covers=True`. A bus with no declared withdrawal has nothing
    to cover, which is different from covering zero."""
    assert R.coverage_for(build.bus(), build.declaration()) is None


def test_a_coverage_verdict_always_names_the_geometric_floor():
    """A3.3: the withdrawal rate is section 8.2's estimate and its author
    declares it a FLOOR, so `covers=True` means "covers the floor"."""
    bus = build.bus(bus_id="concrete", item_id="Desc_Cement_C",
                    recipe_id="Recipe_Concrete_C",
                    supply_per_min=15.0, automated_demand_per_min=6.0, machines=1)
    verdict = R.coverage_for(
        bus, build.declaration(bus_id="concrete", item_id="Desc_Cement_C",
                               withdrawal_per_min=6.0)
    )
    assert verdict is not None
    assert verdict.basis is WithdrawalBasis.GEOMETRIC_FLOOR
    assert verdict.residual_per_min == pytest.approx(9.0)
    assert verdict.covers


def test_coverage_fails_when_the_residual_is_short():
    bus = build.bus(supply_per_min=200.0, automated_demand_per_min=199.0)
    verdict = R.coverage_for(bus, build.declaration(withdrawal_per_min=5.0))
    assert verdict is not None and not verdict.covers


def test_coverage_at_exact_equality_covers():
    """A dedicated intermediate landing exactly on its withdrawal is the design
    working, not a near miss decided by float noise."""
    bus = build.bus(supply_per_min=200.0, automated_demand_per_min=199.0)
    verdict = R.coverage_for(bus, build.declaration(withdrawal_per_min=1.0))
    assert verdict is not None and verdict.covers


@pytest.mark.parametrize("disposition,stable", [
    (Disposition.SUNK, True),
    (Disposition.MATCHED, True),
    (Disposition.BACK_UP, False),
    (Disposition.WITHDRAWN, False),
])
def test_draw_is_stable(disposition, stable):
    """A4.2 is what makes this two branches instead of one: constant power for a
    build-material line no longer depends on the AWESOME Sink.

    WITHDRAWN is deliberately not stable — its producers run at 100% only while
    the player is drawing the container down, and section 9 keeps player time
    out of the model.
    """
    needs_rate = disposition in (Disposition.MATCHED, Disposition.SUNK)
    declaration = build.declaration(
        disposition=disposition,
        withdrawal_per_min=2.0 if needs_rate else None,
    )
    assert R.draw_is_stable(declaration) is stable


# --------------------------------------------------------------------------
# projected_coverage_for — the stock basis. Next action 2.
# --------------------------------------------------------------------------
#
# Every quantity below is distinct on purpose. R = 50, bootstrap = 120,
# remainder = 380, total = 500, T_bootstrap = 2.4, T_total = 10.0 — no two of
# them coincide, so an assertion on any one of them is an assertion.

BOOTSTRAP = 120.0
REMAINDER = 380.0


#: The terms a stock pass can actually sum today: the canonical machine
#: halves. UNLOCK_COST, PROJECT_ASSEMBLY and SPATIAL are each blocked on
#: something named, and their absence is what keeps the bill a floor.
CANONICAL_TERMS = frozenset({
    BillTerm.MACHINE_CONSTRUCTION, BillTerm.BOOTSTRAP_SET,
})


def _bill(bootstrap=BOOTSTRAP, remainder=REMAINDER, terms=CANONICAL_TERMS):
    return WithdrawalBill(
        bootstrap_units=bootstrap, remainder_units=remainder, terms=terms,
        basis=WithdrawalBasis.DERIVED_WHOLE_GAME_FLOOR,
    )


def _bus_with_residual_50():
    """Supply 200, automated demand 150, so R = 50/min."""
    return build.bus(supply_per_min=200.0, automated_demand_per_min=150.0)


def test_a_line_without_a_bill_has_no_projected_verdict():
    """`None`, not a zero-unit projection. A line sized from a rate is
    `coverage_for`'s, and a residual item is neither's."""
    assert R.projected_coverage_for(build.bus(), build.declaration()) is None
    assert R.projected_coverage_for(
        build.bus(), build.declaration(withdrawal_per_min=5.0)
    ) is None


def test_the_two_verdicts_are_mutually_exclusive_per_line():
    """The declaration refuses both, so exactly one of the pair answers for any
    line and neither function has to know about the other."""
    rate_line = build.declaration(withdrawal_per_min=5.0)
    bill_line = build.declaration(withdrawal_bill=_bill())
    bus = _bus_with_residual_50()
    assert R.coverage_for(bus, rate_line) is not None
    assert R.projected_coverage_for(bus, rate_line) is None
    assert R.coverage_for(bus, bill_line) is None
    assert R.projected_coverage_for(bus, bill_line) is not None


def test_both_durations_are_derived_from_the_residual():
    """T = bill / R, twice. 120/50 = 2.4 and 500/50 = 10.0."""
    verdict = R.projected_coverage_for(
        _bus_with_residual_50(), build.declaration(withdrawal_bill=_bill())
    )
    assert verdict.residual_per_min == pytest.approx(50.0)
    assert verdict.minutes_to_bootstrap == pytest.approx(2.4)
    assert verdict.minutes_to_total == pytest.approx(10.0)
    assert verdict.total_units == pytest.approx(500.0)


def test_the_bootstrap_duration_is_the_shorter_one():
    """The split's whole point: the bootstrap gates when the NEXT TIER CAN
    START, and reporting only the total answers a different question."""
    verdict = R.projected_coverage_for(
        _bus_with_residual_50(), build.declaration(withdrawal_bill=_bill())
    )
    assert verdict.minutes_to_bootstrap < verdict.minutes_to_total


def test_a_bootstrap_only_bill_has_equal_durations():
    """The boundary case, asserted because it is the one place the two figures
    SHOULD coincide — a remainder of zero, not a fixture accident."""
    verdict = R.projected_coverage_for(
        _bus_with_residual_50(),
        build.declaration(withdrawal_bill=_bill(remainder=0.0)),
    )
    assert verdict.minutes_to_bootstrap == pytest.approx(2.4)
    assert verdict.minutes_to_total == pytest.approx(2.4)


@pytest.mark.parametrize("supply,demand", [
    (200.0, 200.0),   # R = 0, the ceil landed exactly
    (150.0, 200.0),   # R < 0, the bus is in deficit
])
def test_a_residual_that_cannot_cover_reports_inf_rather_than_refusing(supply, demand):
    """The truthful report — the build as declared never covers the bill — and
    not a refusal, matching `project_goals` on a goal no declared bus produces.
    A plan in progress is an ordinary state."""
    verdict = R.projected_coverage_for(
        build.bus(supply_per_min=supply, automated_demand_per_min=demand),
        build.declaration(withdrawal_bill=_bill()),
    )
    assert verdict.minutes_to_bootstrap == math.inf
    assert verdict.minutes_to_total == math.inf


def test_the_basis_is_read_from_the_bill_and_not_from_the_rate_field():
    """`BusDeclaration.withdrawal_basis` carries the basis of the RATE and is
    left at its GEOMETRIC_FLOOR default on a bill-sized line. Reading it here
    would label a canonical bill as §8.2's footprint estimate."""
    line = build.declaration(withdrawal_bill=_bill())
    assert line.withdrawal_basis is WithdrawalBasis.GEOMETRIC_FLOOR
    verdict = R.projected_coverage_for(_bus_with_residual_50(), line)
    assert verdict.basis is WithdrawalBasis.DERIVED_WHOLE_GAME_FLOOR


def test_the_projected_verdict_carries_no_boolean():
    """No `covers`. T is finite whenever R > 0, so a boolean would be trivially
    true; making it mean something needs a tier horizon this layer may not
    hold. §8.1 — of two constructions, take the one without an opinion."""
    verdict = R.projected_coverage_for(
        _bus_with_residual_50(), build.declaration(withdrawal_bill=_bill())
    )
    assert not hasattr(verdict, "covers")


def test_the_verdict_carries_the_bill_terms_out():
    """A bill of the canonical machine terms and a bill of all six are
    different floors at the same basis. The verdict says which it had, or
    "covers the floor" changes meaning while every field still reads the
    same."""
    verdict = R.projected_coverage_for(
        _bus_with_residual_50(), build.declaration(withdrawal_bill=_bill())
    )
    assert verdict.terms == CANONICAL_TERMS
    assert BillTerm.SPATIAL not in verdict.terms
