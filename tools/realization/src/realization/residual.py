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
"""
from __future__ import annotations

from production_adapter.gamedata import Producer, ReferenceData

from .contracts import (
    Bus, BusDeclaration, BusResidual, ClockCause, ClockDistribution, ClockMode,
    Coverage, Disposition,
)

#: Satisfactory's producer power curve, P = P_base * (clock/100) ** exponent.
#: The exponent is DATA — `Producer.power_exponent`, 1.321929 on all eleven
#: producers — and is read from the producer, never hardcoded.
POWER_IS_CONVEX_IN_CLOCK = True


def power_at_clock(producer: Producer, clock_percent: float, machines: int) -> float:
    """Power for `machines` of `producer` at `clock_percent`.

    PATCH SITE for the standing defect. `production_buildings.csv` carries
    `power_exponent` on all eleven producers and NOTHING in
    `production_adapter` reads it — grepped across all seven modules; the only
    clock reference there is the comment "fractional, at 100% clock".
    `PowerReport` is therefore linear in machine equivalents, correct at 100%
    and wrong at any other clock. Patched here, where clock first enters.
    """
    raise NotImplementedError


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
    raise NotImplementedError


def residual_of(bus_supply: float, bus_demand: float) -> float:
    """R = supply - demand, at the bus. Never per lane."""
    raise NotImplementedError


def clock_for(
    declaration: BusDeclaration,
    demand_per_min: float,
    supply_per_min: float,
    machines: int,
) -> tuple[tuple[float, ClockCause], ...]:
    """Per-machine (clock, cause). One entry per machine.

        SUNK / WITHDRAWN                every machine 100%, cause FULL
        MATCHED                         withdrawal / nameplate, cause MATCHED
        BACK_UP + BACKPRESSURE          demand/supply, cause BACKPRESSURE
        BACK_UP + EXPLICIT, AVERAGED    demand/supply, cause DECLARED
        BACK_UP + EXPLICIT, SPLIT       n at 100% + remainder, cause DECLARED

    MATCHED takes its clock from `declaration.withdrawal_per_min`, not from the
    bus demand: the point of the state is that the line's output IS the declared
    average draw. A MATCHED declaration without a withdrawal rate has nothing to
    match and is refused.

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
    """
    raise NotImplementedError


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
    """
    raise NotImplementedError


def coverage_for(
    bus: Bus,
    declaration: BusDeclaration,
) -> Coverage | None:
    """Whether this bus's residual covers its declared withdrawal.

    `None` on a residual item — a bus with no declared withdrawal has nothing to
    cover, which is different from covering zero.

    The verdict carries its basis because it has to: the withdrawal rate is
    §8.2's geometric estimate, declared by its author as a FLOOR, so `covers` is
    optimistic by an unmeasured amount. `Coverage` has no default basis for that
    reason — the caveat cannot be dropped on the way out.
    """
    raise NotImplementedError


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
    """
    raise NotImplementedError
