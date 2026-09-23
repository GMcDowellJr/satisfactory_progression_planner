"""The scheduler's first piece: a horizon, and a bill over it as a rate. A13 (D2).

    horizon_from_anchor   T = an anchor goal's total / its target rate
    storage_rates         rate_i = bill_i / T, per item

`stock` owns quantities and "never a rate, a horizon". Realization keeps §9, so
no player time enters it. The division has to happen somewhere, and this module
is where it happens: the plan's Project Assembly scheduler (section 10) is the
layer that "converts the user's target into required item/min rates".

**It divides, and that is the guardrail.** No machine count, no recipe, no
partition, no ordering. It holds a bill and a horizon and returns their quotient,
so it cannot decide what to build. Asserted by inspection in
`tests/test_progression_schedule.py`: the only arithmetic is addition (bootstrap
plus remainder) and division, and there is no min, max or sort.

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
