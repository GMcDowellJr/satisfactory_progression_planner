"""Design tier applied to logistics selection (output-contract respec §3).

Two bounds, both DERIVED from the declared tier. Neither is a new default
policy and neither ranks anything:

    ceiling   the highest Mk unlocked at the declared tier
    floor     the lowest Mk that carries the lane's binding rate

"Revert to Mk.1 if throughput works" is the floor. It is admissible under
§8.1 because minimum-sufficient-Mk is a threshold on a rate — single-valued,
with no trade-off priced.

Bodies written 2026-09-21.
"""
from __future__ import annotations

from .contracts import (
    Capability, CapabilityId, DesignTier, ExtractionRate, Mark, NodeDeclaration,
    RealizationError, TierUnavailable,
)

# `unlock_tier` arrives already parsed. logistics_capabilities.csv carries tier
# only as free text in `unlock` ("Tier 4 - Logistics Mk.3"), and that parse is
# `gamedata.load_logistics`'s job — the one place that reads the column. This
# module selects; it does not read CSV text.

#: Mk order is taken from CAPACITY, not from parsing "Mk.3" to 3.
#:
#: The mark is free text and its numeral carries no guarantee; capacity is the
#: property every caller here actually wants — the floor is a threshold on a
#: rate, and the ceiling is only meaningful because a higher Mk carries more.
#: That the two orders coincide on the reference layer is an assumption about
#: the DATA, so it is asserted in `tests/test_capabilities.py` rather than
#: relied on silently. If a future Mk ever carries less than its predecessor,
#: that test fails and names it instead of this module quietly picking wrong.
_ORDER = "capacity_per_min"

#: Extractor clock range. The game admits 1% to 250%; a declared clock outside
#: it is refused rather than clamped, because a clamp answers a question the
#: caller did not ask and hides a declaration that cannot be built.
MIN_CLOCK_PERCENT = 1.0
MAX_CLOCK_PERCENT = 250.0


def _unlocked(
    capabilities: tuple[Capability, ...],
    capability_type: str,
    tier: DesignTier,
) -> list[Capability]:
    """Every capability of `capability_type` unlocked at or below `tier`, ascending."""
    return sorted(
        (c for c in capabilities if c.capability_type == capability_type
         and c.unlock_tier <= tier),
        key=lambda c: (c.capacity_per_min, c.mark),
    )


def highest_at_tier(
    capabilities: tuple[Capability, ...],
    capability_type: str,
    tier: DesignTier,
) -> Capability:
    """The ceiling. Raises `TierUnavailable` when nothing of that type is unlocked."""
    unlocked = _unlocked(capabilities, capability_type, tier)
    if not unlocked:
        raise TierUnavailable(
            f"no {capability_type} is unlocked at tier {tier}"
        )
    return unlocked[-1]


def minimum_sufficient(
    capabilities: tuple[Capability, ...],
    capability_type: str,
    tier: DesignTier,
    rate_per_min: float,
) -> Capability:
    """The floor: lowest Mk at or below `tier` whose capacity carries `rate_per_min`.

    Falls back to the ceiling when no unlocked Mk carries the rate — the lane is
    then wider than one belt and lane decomposition splits it (§5), so this
    returning the ceiling is the correct input to that split, not a failure.
    """
    unlocked = _unlocked(capabilities, capability_type, tier)
    if not unlocked:
        raise TierUnavailable(f"no {capability_type} is unlocked at tier {tier}")
    for capability in unlocked:
        if capability.capacity_per_min >= rate_per_min:
            return capability
    return unlocked[-1]


def extraction_rate(
    rates: tuple[ExtractionRate, ...],
    node: NodeDeclaration,
) -> float:
    """Rate for one declared node at its declared clock.

    Interpolation between `nominal_rate_min` (100%) and `max_250_rate_min`
    (250%) is LINEAR in clock for extractors — extraction is not subject to the
    producer power exponent, which acts on power draw and not on throughput.
    A declared clock outside [1, 250] is refused rather than clamped.

    `NodeDeclaration.count` IS applied: the declaration describes `count`
    identical extractors on one node type at one clock, and nothing else in the
    layer would apply it. Read as "the rate this declaration yields", not "the
    rate of a single machine" — the two differ only when `count != 1`, and the
    reading is stated here because the docstring above admits both.

    The interpolation is written as the two-point form the record specifies
    rather than as `nominal * clock/100`. On the reference layer the two agree
    everywhere, because `max_250 == nominal * 2.5` on all sixteen rows — which
    is a fact about the DATA and is asserted in the tests, not assumed here.
    """
    clock = node.clock_percent
    if not MIN_CLOCK_PERCENT <= clock <= MAX_CLOCK_PERCENT:
        raise ValueError(
            f"{node.extractor_class}: clock {clock}% is outside "
            f"[{MIN_CLOCK_PERCENT}, {MAX_CLOCK_PERCENT}] and is refused, not clamped"
        )
    if node.count < 0:
        raise ValueError(f"{node.extractor_class}: count must be >= 0, got {node.count}")

    for row in rates:
        if row.extractor_class == node.extractor_class and row.purity == node.purity:
            span = row.max_250_rate_min - row.nominal_rate_min
            per_machine = row.nominal_rate_min + span * (clock - 100.0) / 150.0
            return per_machine * node.count
    raise RealizationError(
        f"no extraction rate for {node.extractor_class} at purity {node.purity!r}"
    )


def by_id(capabilities: tuple[Capability, ...], capability_id: CapabilityId) -> Capability:
    """Look up an explicit `trunk_capability` override. Raises when absent.

    Raised rather than returning `None`: an override the caller named and the
    layer could not find is a declaration error, and silently falling back to a
    derived trunk would report a plan built on equipment nobody asked for.
    """
    for capability in capabilities:
        if capability.capability_id == capability_id:
            return capability
    raise RealizationError(f"no capability with id {capability_id!r}")


def marks_at_tier(
    capabilities: tuple[Capability, ...],
    capability_type: str,
    tier: DesignTier,
) -> tuple[Mark, ...]:
    """Every Mk unlocked at `tier`, ascending. Reported, never ordered by preference."""
    return tuple(c.mark for c in _unlocked(capabilities, capability_type, tier))
