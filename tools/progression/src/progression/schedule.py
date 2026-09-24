"""The scheduler's first piece: a horizon, and a bill over it as a rate. A13 (D2).

    horizon_from_anchor   T = an anchor goal's total / its target rate
    storage_rates         rate_i = bill_i / T, per item
    rates_of              rate_i = owed_i / T, over a netted bill (D3)
    carry_estimate        units_i = prior rate_i x gap, REPORT ONLY (D3)

`stock` owns quantities and "never a rate, a horizon". Realization keeps §9, so
no player time enters it. The division has to happen somewhere, and this module
is where it happens: the plan's Project Assembly scheduler (section 10) is the
layer that "converts the user's target into required item/min rates".

**It divides, and that is the guardrail.** No machine count, no recipe, no
partition, no ordering. It holds a bill and a horizon and returns their quotient,
so it cannot decide what to build. Asserted by inspection in
`tests/test_progression_schedule.py`: the only arithmetic is addition (bootstrap
plus remainder), division, and — since D3 — the one multiplication in
`carry_estimate`, and there is no min, max or sort. The multiplication converts
a rate back to a quantity for a report; nothing it returns can be netted.

It imports no layer. The bills are read by attribute (`bootstrap_units`,
`remainder_units`), so this module does not need `realization.contracts` on the
path. `stock` stays the only module here that touches that package, which
`tests/test_progression_import_boundary.py` asserts.

**The horizon is a parameter.** `horizon_from_anchor` is the default
derivation. Greg's time-to-completion override (not built, 2026-09-23) is a
different number passed to the same place, so no second path is needed.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from production_adapter.contracts import ItemId


class ScheduleError(ValueError):
    """A horizon or rate that cannot be stated."""


def horizon_from_anchor(total_required: float, anchor_rate_per_min: float) -> float:
    """T in minutes: the anchor goal's total at its target rate.

    50 Smart Plating at 1/min is 50 minutes. The rate is the solve's target for
    the anchor item, so T follows from what the caller asked for and not from
    anything the build produced. The build's own rate is GROSS (project_goals)
    and would make T depend on the clock the horizon is about to set.
    """
    if total_required <= 0:
        raise ScheduleError(f"an anchor total must be positive, got {total_required}")
    if anchor_rate_per_min <= 0:
        raise ScheduleError(
            f"an anchor rate must be positive, got {anchor_rate_per_min}. A goal "
            "nothing is asked to make has no horizon."
        )
    return total_required / anchor_rate_per_min


def storage_rates(bills: Mapping[ItemId, object], horizon_min: float) -> dict[ItemId, float]:
    """Each item's whole bill, bootstrap plus remainder, over T. Bill order kept.

    Which terms the bill holds is decided before it gets here (P1, 2026-09-23):
    this build's machines, the next tier's bootstrap, and the unlocks DECLARED
    for this stage, with the Project Assembly delivery excluded. This function
    divides whatever it is given; that division is all it does.
    """
    if horizon_min <= 0:
        raise ScheduleError(f"a horizon must be positive, got {horizon_min}")
    return {
        item_id: (bill.bootstrap_units + bill.remainder_units) / horizon_min
        for item_id, bill in bills.items()
    }


# --------------------------------------------------------------------------
# D3, 2026-09-23: a netted bill over T, and a carry estimate that never nets
# --------------------------------------------------------------------------

def rates_of(quantities: Mapping[ItemId, float], horizon_min: float) -> dict[ItemId, float]:
    """Each quantity over T, order kept. The sibling of `storage_rates` (D3 P4).

    Takes plain quantities, which is what `stock.NetStock.owed` holds, so
    `storage_rates` keeps its signature and its tests. A negative quantity is
    refused: `owed` never holds one, and a negative storage rate is refused
    downstream anyway.
    """
    if horizon_min <= 0:
        raise ScheduleError(f"a horizon must be positive, got {horizon_min}")
    for item_id, units in quantities.items():
        if units < 0:
            raise ScheduleError(f"{item_id}: a quantity to pace cannot be negative, got {units}")
    return {item_id: units / horizon_min for item_id, units in quantities.items()}


class CarryEstimate:
    """What the prior stage's paced lines would store during a gap. REPORT ONLY.

    D3 P1 (Greg, 2026-09-23): shown beside the declared inventory, never
    netted — not even when nothing is declared. `stock.net_of` refuses this
    type, so that is structural and not a convention.

    It is a modelled figure and UNDERSTATES whenever lines ran faster than
    paced, which is how the pre-Smart-Plating window is played. It also
    ignores container capacity (A7.3): a gap long enough to saturate a
    container caps real carry below this. A paced stage finishes its bill at
    its own T by construction (A13.5's round trip), so the gap is the only
    source this estimate has.

    A plain class, not a dataclass, so it has no `units` pairs a caller could
    mistake for a `DeclaredOnHand`.
    """

    __slots__ = ("gap_min", "prior_rates", "estimated_units")

    def __init__(
        self,
        gap_min: float,
        prior_rates: dict[ItemId, float],
        estimated_units: dict[ItemId, float],
    ) -> None:
        self.gap_min = gap_min
        self.prior_rates = prior_rates
        self.estimated_units = estimated_units


def carry_estimate(prior_rates: Mapping[ItemId, float], gap_min: float) -> CarryEstimate:
    """rate_i x gap, per item, for the report. The inverse of this module's job.

    `prior_rates` is the previous stage's `PacedRunReport.storage_rates`;
    `gap_min` is the build/expedition time before this stage's lines start.
    Both are handed in: this function does not know what a stage is.
    """
    if gap_min < 0:
        raise ScheduleError(f"a gap cannot be negative, got {gap_min}")
    rates = dict(prior_rates)
    return CarryEstimate(
        gap_min=gap_min,
        prior_rates=rates,
        estimated_units={item_id: rate * gap_min for item_id, rate in rates.items()},
    )


# --------------------------------------------------------------------------
# P6 (D4), 2026-09-24: several goals on one horizon over a phase span
# --------------------------------------------------------------------------
#
# Crossover record amendment 15. A stage is the Project Assembly phase span
# (D4 (e)): phase 2's Smart Plating, Versatile Framework and Automated Wiring
# share one T. Greg's call: T is ANCHORED on a goal the caller NAMES, and
# every goal's target rate is its total over that T. Not a max over goals —
# that would pick a binding goal, which the comparator guard forbids (O3).
# Which goal anchors is the caller's declaration; nothing here compares them.


@dataclass(frozen=True)
class PhaseRates:
    """One horizon and a target rate per goal, in caller order.

    `rates` is (goal_id, item_id, rate/min) — the shape a caller turns into
    `OutputTarget`s. Building them is the caller's (G1): this module builds
    no request.
    """

    horizon_min: float
    anchor_goal_id: str
    rates: tuple[tuple[str, ItemId, float], ...]


def phase_rates(
    goals: tuple[tuple[str, ItemId, float], ...],
    *,
    anchor_goal_id: str,
    anchor_rate_per_min: float,
) -> PhaseRates:
    """T = the named goal's total / its rate; each goal's rate = total / T.

    The anchor's own rate comes back as total / T, which is its declared rate
    up to float division. REFUSED: an anchor that names no goal, a goal id
    twice, an item twice (its targets would add), a non-positive total.
    """
    ids = [g for g, _, _ in goals]
    items = [i for _, i, _ in goals]
    if len(ids) != len(set(ids)):
        raise ScheduleError("a goal id appears twice; state each goal once")
    if len(items) != len(set(items)):
        raise ScheduleError(
            "two goals name one item, so its target rates would add. State one "
            "goal per item for a phase."
        )
    for goal_id, _item_id, total in goals:
        if total <= 0:
            raise ScheduleError(f"{goal_id}: a goal total must be positive, got {total}")
    anchor = [total for goal_id, _, total in goals if goal_id == anchor_goal_id]
    if not anchor:
        raise ScheduleError(
            f"the anchor {anchor_goal_id!r} names no goal. The horizon is set by a "
            "goal the caller names; it is not chosen here."
        )
    horizon = horizon_from_anchor(anchor[0], anchor_rate_per_min)
    return PhaseRates(
        horizon_min=horizon,
        anchor_goal_id=anchor_goal_id,
        rates=tuple((goal_id, item_id, total / horizon) for goal_id, item_id, total in goals),
    )
