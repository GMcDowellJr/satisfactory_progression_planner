"""Shadow prices in plain language (decided by Greg, 2026-10-19: "per unit,
marginal"). Report wording only; nothing here solves or sizes.

A shadow price is the LP's dual: what ONE more unit of a limit would buy,
read at the solved point. It holds for small changes only (a bigger step can
reach another limit), so every phrase ends "at the margin" and every report
that prints one also prints MARGIN_NOTE once.

    per_unit   +1/min Iron Ore -> +0.667 Iron Plate/min at the margin
    per_mw     +10 MW -> +0.05 Iron Plate/min at the margin
    horizon    +10 MW -> horizon 265.2 -> 258.6 min at the margin
               (a bill scale: the minutes to cover the declared bill)

A dual of zero at a cap the plan sits on (a degenerate optimum) reads "no
gain at the margin": the cap is drawn fully but one more unit buys nothing.
The step for power is a declared constant, not chosen per report.
"""
from __future__ import annotations

#: the power step the phrases quote; 1 MW reads as noise on most sites
MW_STEP = 10.0
#: below this a dual is zero (HiGHS returns -1e-13 for nothing)
ZERO = 1.0e-12
MARGIN_NOTE = ("'at the margin': what one more unit of that limit buys at this plan; "
               "a bigger step can run into another limit")


def per_unit(shadow: float | None, limit: str, gain: str, high: float | None = None) -> str:
    """`gain` names the output, e.g. "Iron Plate/min" or "weighted output".
    `high`: the top of a per-socket range (A4: each socket kind brings its
    own MW when power binds), `shadow` then its bottom."""
    if shadow is None:
        return f"+1/min {limit} -> not priced"
    if high is not None:
        return (f"+1/min {limit} -> +{shadow + 0.0:.4g} to +{high:.4g} {gain} at the margin, "
                "by which socket gives it")
    if shadow <= ZERO:
        return f"+1/min {limit} -> no gain at the margin"
    return f"+1/min {limit} -> +{shadow:.4g} {gain} at the margin"


def per_mw(shadow: float, gain: str, step: float = MW_STEP) -> str:
    if shadow <= ZERO:
        return f"+{step:g} MW -> no gain at the margin"
    return f"+{step:g} MW -> +{shadow * step:.4g} {gain} at the margin"


def horizon(shadow: float, scale: float, step: float, what: str, high: float | None = None) -> str:
    """A bill-scale dual as minutes to cover the bill. `what` is the step
    as a phrase ("+10 MW", "+1/min Coal"); `step` its size in the dual's
    unit; `high` the top of a per-socket range. Scale 0 has no horizon, so
    the new scale is given instead."""
    if shadow <= ZERO and high is None:
        return f"{what} -> no gain at the margin"
    after = scale + shadow * step
    if scale <= ZERO:
        return f"{what} -> bill scale 0 -> {after:.4g}/min (horizon {1.0 / after:.1f} min) at the margin"
    if high is not None:
        best = scale + high * step
        return (f"{what} -> horizon {1.0 / scale:.1f} -> {1.0 / after:.1f} to {1.0 / best:.1f} min "
                "at the margin, by which socket gives it")
    return f"{what} -> horizon {1.0 / scale:.1f} -> {1.0 / after:.1f} min at the margin"
