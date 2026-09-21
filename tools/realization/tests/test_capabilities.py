"""`capabilities.py`'s five bodies, and the two data assumptions they rest on.

Two bounds, both DERIVED from the declared tier, neither a policy:

    ceiling   the highest Mk unlocked at the declared tier
    floor     the lowest Mk that carries the lane's binding rate

The module orders marks by CAPACITY rather than by parsing "Mk.3" to 3. That
the two orders coincide is a claim about the reference layer, so it is measured
here rather than assumed there.
"""
from __future__ import annotations

import dataclasses

import pytest

from realization import capabilities as C
from realization.contracts import (
    Capability, NodeDeclaration, RealizationError, TierUnavailable,
)


@pytest.fixture(scope="module")
def caps(logistics):
    return logistics[0]


@pytest.fixture(scope="module")
def rates(logistics):
    return logistics[1]


# --------------------------------------------------------------------------
# the data assumptions the module rests on
# --------------------------------------------------------------------------

def test_mark_order_and_capacity_order_coincide(caps):
    """`capabilities.py` orders by capacity because capacity is what every
    caller wants. If a future Mk ever carries less than its predecessor, this
    fails and names it instead of the module quietly picking wrong."""
    for capability_type in {c.capability_type for c in caps}:
        rows = sorted(
            (c for c in caps if c.capability_type == capability_type),
            key=lambda c: int(c.mark.removeprefix("Mk.")),
        )
        capacities = [c.capacity_per_min for c in rows]
        assert capacities == sorted(capacities), capability_type


def test_belt_mk4_is_tier_5(caps):
    """The respec's section 3.1 correction, which `Capability.unlock_tier`
    exists to make impossible rather than merely unlikely."""
    belt_mk4 = C.by_id(caps, "belt_mk4")
    assert belt_mk4.unlock_tier == 5
    assert belt_mk4.unlock_text.startswith("Tier 5")


def test_max_250_is_exactly_two_and_a_half_times_nominal(rates):
    """The two-point interpolation in `extraction_rate` is written as the record
    specifies it. On this data it agrees everywhere with `nominal * clock/100`,
    and that agreement is a fact about the DATA — measured here, not assumed in
    the module."""
    for row in rates:
        assert row.max_250_rate_min == pytest.approx(row.nominal_rate_min * 2.5), row


# --------------------------------------------------------------------------
# ceiling and floor
# --------------------------------------------------------------------------

@pytest.mark.parametrize("tier,expected", [
    (0, "belt_mk1"),
    (1, "belt_mk1"),
    (2, "belt_mk2"),
    (3, "belt_mk2"),
    (4, "belt_mk3"),
    (5, "belt_mk4"),
    (6, "belt_mk4"),
    (7, "belt_mk5"),
    (9, "belt_mk6"),
])
def test_highest_at_tier(caps, tier, expected):
    assert C.highest_at_tier(caps, "belt", tier).capability_id == expected


def test_highest_at_tier_refuses_when_nothing_is_unlocked(caps):
    """Pipelines arrive at Tier 3. A plan that needs one at Tier 2 is refused by
    name rather than handed the nearest thing."""
    with pytest.raises(TierUnavailable, match="pipeline"):
        C.highest_at_tier(caps, "pipeline", 2)


@pytest.mark.parametrize("rate,expected", [
    (0.0, "belt_mk1"),
    (59.0, "belt_mk1"),
    (60.0, "belt_mk1"),
    (60.1, "belt_mk2"),
    (120.0, "belt_mk2"),
    (121.0, "belt_mk3"),
    (270.0, "belt_mk3"),
])
def test_minimum_sufficient_is_a_threshold_on_a_rate(caps, rate, expected):
    """"Revert to Mk.1 if throughput works" is the floor. Admissible under
    section 8.1 because it is single-valued with no trade-off priced."""
    assert C.minimum_sufficient(caps, "belt", 4, rate).capability_id == expected


def test_minimum_sufficient_never_exceeds_the_declared_tier(caps):
    """A rate only Mk.6 carries, asked at Tier 4, must not answer Mk.6."""
    chosen = C.minimum_sufficient(caps, "belt", 4, 1000.0)
    assert chosen.capability_id == "belt_mk3"
    assert chosen.unlock_tier <= 4


def test_minimum_sufficient_falls_back_to_the_ceiling(caps):
    """The lane is then wider than one belt and lane decomposition splits it, so
    returning the ceiling is the correct input to that split, not a failure."""
    assert C.minimum_sufficient(caps, "belt", 9, 10_000.0).capability_id == "belt_mk6"


def test_marks_at_tier_ascends_and_ranks_nothing(caps):
    assert C.marks_at_tier(caps, "belt", 4) == ("Mk.1", "Mk.2", "Mk.3")
    assert C.marks_at_tier(caps, "pipeline", 2) == ()
    assert C.marks_at_tier(caps, "miner", 4) == ("Mk.1", "Mk.2")


def test_by_id_raises_on_an_override_that_does_not_exist(caps):
    """An override the caller named and the layer could not find is a
    declaration error. Silently falling back to a derived trunk would report a
    plan built on equipment nobody asked for."""
    assert C.by_id(caps, "belt_mk3").mark == "Mk.3"
    with pytest.raises(RealizationError, match="belt_mk9"):
        C.by_id(caps, "belt_mk9")


def test_the_ordering_is_not_a_mark_string_sort(caps):
    """A lexicographic sort of "Mk.1".."Mk.6" happens to be correct and would
    stop being correct at "Mk.10". Asserted against a synthetic row so the
    module's capacity ordering is what is being measured."""
    mk10 = Capability(
        capability_id="belt_mk10", capability_type="belt", mark="Mk.10",
        capacity_per_min=2400.0, unit="items/min", unlock_tier=9,
        unlock_text="Tier 9 - Synthetic",
    )
    assert C.highest_at_tier(caps + (mk10,), "belt", 9).capability_id == "belt_mk10"


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

@pytest.mark.parametrize("extractor,purity,clock,expected", [
    ("Build_MinerMk1_C", "normal", 100.0, 60.0),
    ("Build_MinerMk1_C", "normal", 250.0, 150.0),
    ("Build_MinerMk1_C", "pure", 100.0, 120.0),
    ("Build_MinerMk1_C", "impure", 100.0, 30.0),
    ("Build_MinerMk2_C", "normal", 100.0, 120.0),
    ("Build_MinerMk1_C", "normal", 50.0, 30.0),
    ("Build_WaterPump_C", "none", 100.0, 120.0),
])
def test_extraction_rate_is_linear_in_clock(rates, extractor, purity, clock, expected):
    node = NodeDeclaration(
        item_id="Desc_OreIron_C", extractor_class=extractor,
        purity=purity, clock_percent=clock,
    )
    assert C.extraction_rate(rates, node) == pytest.approx(expected)


def test_extraction_rate_applies_the_declared_count(rates):
    """`NodeDeclaration.count` describes `count` identical extractors, and
    nothing else in the layer applies it."""
    one = NodeDeclaration(item_id="Desc_OreIron_C", extractor_class="Build_MinerMk1_C",
                          purity="normal")
    three = dataclasses.replace(one, count=3)
    assert C.extraction_rate(rates, three) == pytest.approx(
        3 * C.extraction_rate(rates, one)
    )


@pytest.mark.parametrize("clock", [0.0, 0.5, 251.0, -10.0])
def test_a_clock_outside_the_buildable_range_is_refused_not_clamped(rates, clock):
    """A clamp answers a question the caller did not ask and hides a
    declaration that cannot be built."""
    node = NodeDeclaration(item_id="Desc_OreIron_C", extractor_class="Build_MinerMk1_C",
                           purity="normal", clock_percent=clock)
    with pytest.raises(ValueError, match="refused, not clamped"):
        C.extraction_rate(rates, node)


def test_an_unknown_extractor_or_purity_is_refused(rates):
    node = NodeDeclaration(item_id="Desc_Water_C", extractor_class="Build_WaterPump_C",
                           purity="pure")
    with pytest.raises(RealizationError, match="no extraction rate"):
        C.extraction_rate(rates, node)


def test_maximise_each_node_is_a_declared_default_not_an_assumption(rates):
    """The layer never raises a clock on the caller's behalf: the default is
    100%, and 250% has to be declared."""
    node = NodeDeclaration(item_id="Desc_OreIron_C", extractor_class="Build_MinerMk1_C",
                           purity="normal")
    assert node.clock_percent == 100.0
    assert C.extraction_rate(rates, node) == pytest.approx(60.0)
