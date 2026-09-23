"""Residual, disposition, clock and power.

Respec §4, corrected by docs/decisions/bus_allocation_backpressure_and_residual.md.

The residual belongs to the BUS:

    R = supply - TOTAL bus demand

Per-lane overflow is not a physical quantity, because backpressure moves
surplus between a bus's consumers before anything can be stored. `classify()`
— respec §4.6's consumed-downstream / dead report — is gone: consumed-
downstream surplus is consumed automatically, so the distinction is already
inside the demand sum and what remains is dead by construction.

R is quantised. At the ceil it is whatever rounding left, and it rises only by
whole producers:

    R(k) = ceil_residual + k * producer_rate

Screw bus, 199/min demand against 40/min producers:

    machines  supply   R          at 100%     backing up   underclocked
      5          200    1.0/min    20.00 MW    19.90 MW     19.87 MW
      6 (+1)     240   41.0/min    24.00 MW    19.90 MW     18.74 MW
      7 (+2)     280   81.0/min    28.00 MW    19.90 MW     17.83 MW

Backing up is FLAT in machine count — with no drain, power is a function of
throughput alone. Underclocking FALLS in machine count (convex power). Only
running at 100% scales up, and it is a transient unless something drains R.

Bodies written 2026-09-21. All nine rows of that table are reproduced by
`tests/test_residual.py`, which is what the table was carried on the record for.
"""
from __future__ import annotations

import math

from production_adapter.gamedata import Producer, ReferenceData

from .contracts import (
    Bus, BusDeclaration, BusResidual, ClockCause, ClockDistribution, ClockMode,
    Coverage, Disposition, DispositionUnavailable, ProjectedCoverage,
    RealizationError, WithdrawalBasis,
)

#: Satisfactory's producer power curve, P = P_base * (clock/100) ** exponent.
#: The exponent is DATA — `Producer.power_exponent`, 1.321929 on all eleven
#: producers — and is read from the producer, never hardcoded.
POWER_IS_CONVEX_IN_CLOCK = True

#: Comparison tolerance. A coverage verdict decided by float noise at the
#: fifteenth decimal is not a verdict.
EPS = 1e-9


def power_at_clock(producer: Producer, clock_percent: float, machines: int) -> float:
    """Power for `machines` of `producer` at `clock_percent`.

    PATCH SITE for the standing defect. `production_buildings.csv` carries
    `power_exponent` on all eleven producers and NOTHING in
    `production_adapter` reads it — grepped across all seven modules; the only
    clock reference there is the comment "fractional, at 100% clock".
    `PowerReport` is therefore linear in machine equivalents, correct at 100%
    and wrong at any other clock. Patched here, where clock first enters.

    REFUSES on a variable-power producer, and the refusal is a finding rather
    than a limitation of this function. Converter, Particle Accelerator and
    Quantum Encoder carry `base_power_mw = 0` in `production_buildings.csv`;
    their real draw is a per-RECIPE range on `Recipe.power`, which this
    signature cannot reach. Returning 0.0 would be a confident wrong answer —
    silently free machines — so the figure is declined and the signature gap is
    named. Widening the signature is a patch, not a body, and is not taken here.
    """
    if machines < 0:
        raise ValueError(f"machines must be >= 0, got {machines}")
    if clock_percent < 0:
        raise ValueError(f"clock must be >= 0, got {clock_percent}")
    if producer.is_variable_power:
        raise RealizationError(
            f"{producer.producer_class} is variable-power: its draw is a range on "
            "the RECIPE (Recipe.power), not base_power_mw, which the reference "
            "layer carries as 0 for this producer. power_at_clock cannot reach it "
            "from a Producer alone and declines rather than reporting 0.0 MW."
        )
    return producer.base_power_mw * (clock_percent / 100.0) ** producer.power_exponent * machines


def power_backing_up(producer: Producer, machines: int, utilisation: float) -> float:
    """Power when belts idle the machines rather than a clock slowing them.

    LINEAR in utilisation — it is a duty cycle, not a clock. That is the whole
    difference from `power_at_clock`, and it is what an explicit clock buys:

        utilisation   explicit clock   backing up   penalty
            99.5%        19.87 MW       19.90 MW     +0.2%
            90.0%        17.40 MW       18.00 MW     +3.5%
            80.0%        14.89 MW       16.00 MW     +7.4%
            50.0%         8.00 MW       10.00 MW    +25.0%

    Assumes an idle producer draws ~0. NOT verified against the reference
    layer; a non-zero idle draw shrinks every gap above.
    """
    if machines < 0:
        raise ValueError(f"machines must be >= 0, got {machines}")
    if not 0.0 <= utilisation <= 1.0 + EPS:
        raise ValueError(f"utilisation must be in [0, 1], got {utilisation}")
    if producer.is_variable_power:
        raise RealizationError(
            f"{producer.producer_class} is variable-power; see power_at_clock"
        )
    return producer.base_power_mw * machines * min(1.0, utilisation)


def residual_of(bus_supply: float, bus_demand: float) -> float:
    """R = supply - demand, at the bus. Never per lane."""
    return bus_supply - bus_demand


def clock_for(
    declaration: BusDeclaration,
    demand_per_min: float,
    supply_per_min: float,
    machines: int,
) -> tuple[tuple[float, ClockCause], ...]:
    """Per-machine (clock, cause). One entry per machine.

        SUNK / WITHDRAWN                every machine 100%, cause FULL
        MATCHED                         demand / nameplate, cause MATCHED
        BACK_UP + BACKPRESSURE          demand/supply, cause BACKPRESSURE
        BACK_UP + EXPLICIT, AVERAGED    demand/supply, cause DECLARED
        BACK_UP + EXPLICIT, SPLIT       n at 100% + remainder, cause DECLARED

    MATCHED takes its clock from `declaration.withdrawal_per_min`, not from the
    bus demand: the point of the state is that the line's output IS the declared
    average draw. A MATCHED declaration without a withdrawal rate has nothing to
    match and is refused.

    AMENDED 2026-09-23, amendment 12. The paragraph above holds only for a line
    with NO in-scope consumers — A4.1's Iron Plate build line, the one MATCHED
    line any case declared. Since A12 MATCHED is also what storage OFF derives
    for a line with a withdrawal AND consumers (D1: "the line clocks down to
    what its consumers need"), and a clock read from the withdrawal alone
    starves those consumers: RIP with storage off, 2/min to Smart Plating and
    2/min withdrawn, ran at 2/min. The clock is now `demand_per_min` over
    nameplate, where `demand_per_min` is what `buses.decompose` passes —
    automated + withdrawal + external — which is `busmodel.solve`'s MATCHED
    rule (supply = demand). For a line with no consumers the two rules are the
    same number. The withdrawal is still REQUIRED: without it the state has
    nothing to match.

    The cause is not decoration. A lane at 96.8% because a splitter ratio
    starved it (RATIO_LIMITED), because the caller set that percentage
    (DECLARED), and because the caller declared a rate that works out to 96.8%
    here (MATCHED) are three different facts, and only the second and third
    survive a change of scenario multiplier unchanged in kind. Respec §4.2's
    "the toggle never touches geometry" holds for DECLARED and MATCHED.

    Backpressure already makes a lane exact, so under BACK_UP an explicit clock
    buys the convex power saving and nothing else — correcting respec §4.5,
    which holds that underclocking is the only lever that makes a lane exact.
    A4.2 narrows §4.5 from the other side: underclocking is also the ORDINARY
    way a build-material line is sized, and on the Iron Plate line it is a 20x
    power reduction rather than a marginal one.

    The branch table above is followed exactly, including where it is odd: a
    BACK_UP bus whose demand equals its supply gets (100.0, BACKPRESSURE) rather
    than (100.0, FULL), even though `ClockCause.FULL` is commented "at 100%".
    Overriding it looked tidier and was not taken — the table is the contract
    P24 wrote deliberately, and a body is not the place to amend one.
    """
    if machines < 1:
        raise ValueError(f"{declaration.bus_id}: machines must be >= 1, got {machines}")
    if supply_per_min <= 0:
        raise ValueError(
            f"{declaration.bus_id}: supply must be positive to derive a clock, "
            f"got {supply_per_min}"
        )

    disposition = declaration.disposition
    if disposition in (Disposition.SUNK, Disposition.WITHDRAWN):
        return tuple((100.0, ClockCause.FULL) for _ in range(machines))

    if disposition is Disposition.MATCHED:
        withdrawal = declaration.withdrawal_per_min
        if withdrawal is None:
            # Unreachable through `BusDeclaration.__post_init__` (P29), and kept
            # so that a declaration built by other means still refuses here
            # rather than dividing by None.
            raise RealizationError(
                f"{declaration.bus_id}: MATCHED without withdrawal_per_min has "
                "nothing to match"
            )
        clock = 100.0 * demand_per_min / supply_per_min
        if clock > 100.0 + EPS:
            raise RealizationError(
                f"{declaration.bus_id}: demand {demand_per_min}/min (declared "
                f"withdrawal {withdrawal}/min included) exceeds nameplate "
                f"{supply_per_min}/min on {machines} machine(s), so the line "
                "cannot be MATCHED at this machine count. Size it first."
            )
        return tuple((min(clock, 100.0), ClockCause.MATCHED) for _ in range(machines))

    # BACK_UP from here.
    fraction = min(1.0, demand_per_min / supply_per_min)
    if declaration.clock_mode is ClockMode.BACKPRESSURE:
        return tuple((fraction * 100.0, ClockCause.BACKPRESSURE) for _ in range(machines))

    if declaration.clock_distribution is ClockDistribution.AVERAGED:
        return tuple((fraction * 100.0, ClockCause.DECLARED) for _ in range(machines))

    # SPLIT: n machines at 100% and one at the remainder. Power-suboptimal and
    # reportable, which is the whole reason it is offered alongside AVERAGED.
    #
    # Machines past the ceil get 0.0, and that is the truthful report rather
    # than a gap in the branch: §4 measures that building past the ceil under
    # BACK_UP "costs build cost and footprint and nothing in power, and buys
    # nothing", and under a declared SPLIT the surplus is exactly the machine
    # that has nothing to do. A 0% clock is not buildable in game; that is the
    # finding, not an evasion of it.
    nameplate = supply_per_min / machines
    equivalents = demand_per_min / nameplate
    whole = min(machines, int(math.floor(equivalents + EPS)))
    remainder = equivalents - whole
    clocks = [100.0] * whole
    if whole < machines:
        clocks.append(min(100.0, remainder * 100.0))
    clocks.extend([0.0] * (machines - len(clocks)))
    return tuple((c, ClockCause.DECLARED) for c in clocks)


def residual_for(
    data: ReferenceData,
    bus: Bus,
    declaration: BusDeclaration,
) -> BusResidual:
    """The bus residual with its disposition and what that disposition costs.

    Raises `DispositionUnavailable` for SUNK: the AWESOME Sink is absent from
    the reference layer (handoff open item 8). Refused rather than silently
    downgraded to BACK_UP, which would misreport both the residual's fate and
    whether the draw is stable.

    R is `supply - automated_demand`. The declared withdrawal is NOT inside that
    sum — `Bus` says so in as many words — because it does not size the bus; it
    is what the residual has to cover, and `coverage_for` is where the two meet.
    Folding it in here would make every coverage verdict compare a number
    against itself.
    """
    if declaration.disposition is Disposition.SUNK:
        raise DispositionUnavailable(
            f"{bus.bus_id}: SUNK routes the overflow to an AWESOME Sink, which is "
            "absent from the reference layer. A4.2 narrows what that absence costs "
            "— a build-material line reaches a constant draw through MATCHED — but "
            "disposal of a genuine overflow still has no model."
        )

    residual = residual_of(bus.supply_per_min, bus.automated_demand_per_min)

    # What the disposition costs against the cheapest alternative. Only one
    # state has a cost to report, and computing power on the others would also
    # drag variable-power producers into a refusal they have no reason to hit.
    power_cost = 0.0
    if (
        declaration.disposition is Disposition.BACK_UP
        and declaration.clock_mode is ClockMode.BACKPRESSURE
        and bus.machines > 0
        and bus.supply_per_min > 0
    ):
        recipe = data.recipes[bus.recipe_id]
        producer = data.producers[recipe.producer_class]
        utilisation = min(1.0, bus.automated_demand_per_min / bus.supply_per_min)
        power_cost = power_backing_up(producer, bus.machines, utilisation) - power_at_clock(
            producer, utilisation * 100.0, bus.machines
        )

    return BusResidual(
        bus_id=bus.bus_id,
        item_id=bus.item_id,
        rate_per_min=residual,
        disposition=declaration.disposition,
        power_cost_mw=power_cost,
    )


def coverage_for(
    bus: Bus,
    declaration: BusDeclaration,
) -> Coverage | None:
    """Whether this bus's residual covers its declared withdrawal.

    `None` on a residual item — a bus with no declared withdrawal has nothing to
    cover, which is different from covering zero.

    The verdict carries its basis because it has to, and the basis is READ from
    the declaration rather than assumed here. Before amendment 5 this function
    hardcoded `GEOMETRIC_FLOOR`, which was true of every rate the repo could
    produce and stopped being true the moment a second basis existed: a rate
    summed from the canonical construction bill is a different floor with
    different error characteristics, and labelling it as §8.2's footprint
    estimate would be a wrong verdict wearing a right one's clothes.

    `Coverage` still has no DEFAULT basis. `BusDeclaration` has one, and the
    asymmetry is deliberate — see the field's comment there.
    """
    withdrawal = declaration.withdrawal_per_min
    if withdrawal is None:
        return None
    residual = bus.residual.rate_per_min
    return Coverage(
        bus_id=bus.bus_id,
        item_id=bus.item_id,
        residual_per_min=residual,
        withdrawal_per_min=withdrawal,
        basis=declaration.withdrawal_basis,
        covers=residual >= withdrawal - EPS,
    )


def projected_coverage_for(
    bus: Bus,
    declaration: BusDeclaration,
) -> ProjectedCoverage | None:
    """The stock-basis verdict: how long this bus's residual takes to cover a
    declared BILL, bootstrap half first.

    `None` on a line that declares no bill — including one sized from a RATE,
    which `coverage_for` answers instead. The two are mutually exclusive at the
    declaration, so exactly one of the pair returns a verdict for any line and
    neither has to know about the other.

        T_bootstrap = bootstrap / R
        T_total     = (bootstrap + remainder) / R

    Both DERIVED durations reported out, never a horizon assumed in, which is
    what keeps §9 intact — structurally the same move as
    `ProjectedGoal.minutes_to_complete`. The horizon objection applied to a
    per-tier bill converted to a rate; it does not apply here, because nothing
    is converted.

    NO BOOLEAN, deliberately. `T` is finite whenever `R > 0`, so a `covers`
    field would be trivially true, and making it mean something needs a tier
    horizon this layer may not hold. The duration is the verdict.

    R is the BUS RESIDUAL — what is left after the in-scope automated
    consumers, which is the only rate a player can actually withdraw. It may be
    zero or negative on a bus in deficit; both give `inf`, which is the
    truthful report that the build as declared never covers the bill.

    The basis is READ from the bill, not from `declaration.withdrawal_basis`.
    That field carries the basis of the RATE, and on a bill-sized line it is
    the untouched default — labelling a canonical bill as §8.2's footprint
    estimate is exactly the wrong verdict wearing a right one's clothes that
    amendment 5 named.
    """
    bill = declaration.withdrawal_bill
    if bill is None:
        return None
    residual = bus.residual.rate_per_min
    if residual > EPS:
        to_bootstrap = bill.bootstrap_units / residual
        to_total = bill.total_units / residual
    else:
        to_bootstrap = math.inf
        to_total = math.inf
    return ProjectedCoverage(
        bus_id=bus.bus_id,
        item_id=bus.item_id,
        residual_per_min=residual,
        bootstrap_units=bill.bootstrap_units,
        remainder_units=bill.remainder_units,
        terms=bill.terms,
        basis=bill.basis,
        minutes_to_bootstrap=to_bootstrap,
        minutes_to_total=to_total,
    )


def draw_is_stable(declaration: BusDeclaration) -> bool:
    """Whether this bus presents a constant power draw.

    SUNK and MATCHED. Under BACK_UP the producers oscillate between running and
    paused as belts fill and drain, so the draw fluctuates and has to be sized
    against its peak; SUNK never stops and MATCHED never needs to.

    A4.2 is what makes this two branches instead of one, and the consequence
    runs the other way too: constant power for a BUILD-MATERIAL line no longer
    depends on the AWESOME Sink, which is absent from the reference layer. The
    Sink still gates constant power for a line with a genuine overflow to
    dispose of. That is a real cost against the generator surface (respec
    §10.5) and it is now the only remaining one of the Sink's two reasons to
    matter, the other being disposal mode itself.

    WITHDRAWN is deliberately NOT stable. Its producers run at 100% only while
    the player is drawing the container down; §9 keeps player time out of the
    model, so the tool cannot claim a duration for that and does not report the
    draw as constant.
    """
    return declaration.disposition in (Disposition.SUNK, Disposition.MATCHED)
