"""Design tier applied to logistics selection (output-contract respec §3).

Two bounds, both DERIVED from the declared tier. Neither is a new default
policy and neither ranks anything:

    ceiling   the highest Mk unlocked at the declared tier
    floor     the lowest Mk that carries the lane's binding rate

"Revert to Mk.1 if throughput works" is the floor. It is admissible under
§8.1 because minimum-sufficient-Mk is a threshold on a rate — single-valued,
with no trade-off priced.
"""
from __future__ import annotations

from .contracts import (
    Capability, CapabilityId, DesignTier, ExtractionRate, Mark, NodeDeclaration,
)

# `unlock_tier` arrives already parsed. logistics_capabilities.csv carries tier
# only as free text in `unlock` ("Tier 4 - Logistics Mk.3"), and that parse is
# `gamedata.load_logistics`'s job — the one place that reads the column. This
# module selects; it does not read CSV text.


def highest_at_tier(
    capabilities: tuple[Capability, ...],
    capability_type: str,
    tier: DesignTier,
) -> Capability:
    """The ceiling. Raises `TierUnavailable` when nothing of that type is unlocked."""
    raise NotImplementedError


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
    raise NotImplementedError


def extraction_rate(
    rates: tuple[ExtractionRate, ...],
    node: NodeDeclaration,
) -> float:
    """Rate for one declared node at its declared clock.

    Interpolation between `nominal_rate_min` (100%) and `max_250_rate_min`
    (250%) is LINEAR in clock for extractors — extraction is not subject to the
    producer power exponent, which acts on power draw and not on throughput.
    A declared clock outside [1, 250] is refused rather than clamped.
    """
    raise NotImplementedError


def by_id(capabilities: tuple[Capability, ...], capability_id: CapabilityId) -> Capability:
    """Look up an explicit `trunk_capability` override. Raises when absent."""
    raise NotImplementedError


def marks_at_tier(
    capabilities: tuple[Capability, ...],
    capability_type: str,
    tier: DesignTier,
) -> tuple[Mark, ...]:
    """Every Mk unlocked at `tier`, ascending. Reported, never ordered by preference."""
    raise NotImplementedError
