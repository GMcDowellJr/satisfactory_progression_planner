"""The stock pass. Handoff next action 3, canonical half.

Every figure here is read from building_recipe_io.csv through
`gamedata.load_construction` and asserted against the arithmetic, never
restated from the body. The worked set is Greg's own coal bootstrap — 1 coal
generator, 1 water extractor, 1 miner — because it is the one that exercises
the Portable Miner gap.

    Coal-Powered Generator   30 Cable, 20 Reinforced Iron Plate, 10 Rotor
    Water Extractor          20 Copper Sheet, 10 Reinforced Iron Plate, 10 Rotor
    Miner Mk.1               1 Portable Miner, 10 Concrete, 10 Iron Plate
    Constructor              8 Cable, 2 Reinforced Iron Plate
    Assembler                10 Cable, 8 Reinforced Iron Plate, 4 Rotor
"""
from __future__ import annotations

import pathlib

import pytest

from production_adapter import ReferenceDataError, load
from production_adapter.gamedata import load_construction
from progression import stock
from realization.contracts import BillTerm, WithdrawalBasis

REPO = pathlib.Path(__file__).resolve().parents[1]

I_CABLE = "Desc_Cable_C"
I_RIP = "Desc_IronPlateReinforced_C"
I_ROTOR = "Desc_Rotor_C"
I_CONCRETE = "Desc_Cement_C"
I_COPPER_SHEET = "Desc_CopperSheet_C"
I_PORTABLE_MINER = "BP_ItemDescriptorPortableMiner_C"


@pytest.fixture(scope="module")
def data():
    return load(REPO)


@pytest.fixture(scope="module")
def construction():
    return load_construction(REPO)


@pytest.fixture(scope="module")
def coal_bootstrap():
    """Greg's stated coal-power minimum, 2026-09-22."""
    return stock.BootstrapSet(tier=3, buildings=(
        ("Build_GeneratorCoal_C", 1),
        ("Build_WaterPump_C", 1),
        ("Build_MinerMk1_C", 1),
    ))


#: Deliberately NOT one of each. Five Constructors and two Assemblers make
#: `count` visible in every sum — with one of each, a per-building cost and a
#: total are the same number and an assertion on either asserts nothing.
SETTLED = (("Build_ConstructorMk1_C", 5), ("Build_AssemblerMk1_C", 2))


@pytest.fixture(scope="module")
def result(data, construction, coal_bootstrap):
    return stock.bill_for(
        data, construction, bootstrap=coal_bootstrap, machines=SETTLED,
    )


# --------------------------------------------------------------------------
# the arithmetic
# --------------------------------------------------------------------------

def test_a_machine_set_costs_the_sum_of_its_buildings(construction):
    """5 Constructors at 8 Cable + 2 Assemblers at 10 Cable = 60, not 18."""
    cost = stock.cost_of(construction, SETTLED)
    assert cost[I_CABLE] == pytest.approx(5 * 8.0 + 2 * 10.0)
    assert cost[I_RIP] == pytest.approx(5 * 2.0 + 2 * 8.0)
    assert cost[I_ROTOR] == pytest.approx(2 * 4.0)


def test_the_two_halves_are_summed_separately(result):
    """Rotor: 10 from the generator + 10 from the extractor in the bootstrap,
    8 from two Assemblers in the remainder. Three distinct figures."""
    rotor = result.bills[I_ROTOR]
    assert rotor.bootstrap_units == pytest.approx(20.0)
    assert rotor.remainder_units == pytest.approx(8.0)
    assert rotor.total_units == pytest.approx(28.0)


def test_an_item_only_one_half_needs_still_gets_a_bill(result):
    """Concrete comes only from the miner, Copper Sheet only from the water
    extractor. Both are bootstrap-only, and a zero remainder is a figure rather
    than an absence."""
    for item_id, units in ((I_CONCRETE, 10.0), (I_COPPER_SHEET, 20.0)):
        bill = result.bills[item_id]
        assert bill.bootstrap_units == pytest.approx(units)
        assert bill.remainder_units == pytest.approx(0.0)


# --------------------------------------------------------------------------
# what the bill says about itself
# --------------------------------------------------------------------------

def test_every_bill_names_the_two_summed_terms(result):
    """`terms` states which stores were CONSULTED, not which came out non-zero.
    A bill whose terms shrank on a zero would make "the bootstrap contributes
    nothing" and "the bootstrap was not counted" the same report."""
    assert result.bills
    for bill in result.bills.values():
        assert bill.terms == stock.SUMMED_TERMS
        assert bill.basis is WithdrawalBasis.DERIVED_WHOLE_GAME_FLOOR


def test_a_remainder_only_item_still_names_the_bootstrap_term(data, construction):
    """The case the coal fixture cannot reach: every item in it has a non-zero
    bootstrap, so a bill whose terms shrank on a zero would pass there unnoticed.
    A Smelter is 5 Iron Rod + 8 Wire and the coal bootstrap has neither, so both
    items are remainder-only and their bootstrap half is a measured zero.
    """
    result = stock.bill_for(
        data, construction,
        bootstrap=stock.BootstrapSet(tier=3, buildings=(("Build_GeneratorCoal_C", 1),)),
        machines=(("Build_SmelterMk1_C", 3),),
    )
    for item_id, per_building in (("Desc_IronRod_C", 5.0), ("Desc_Wire_C", 8.0)):
        bill = result.bills[item_id]
        assert bill.bootstrap_units == pytest.approx(0.0)
        assert bill.remainder_units == pytest.approx(3 * per_building)
        assert bill.terms == stock.SUMMED_TERMS, (
            "a zero bootstrap is a figure, not a reason to stop counting the term"
        )


def test_the_three_unsummed_terms_are_absent_and_that_is_what_makes_it_a_floor(result):
    """UNLOCK_COST is blocked on resolving a tier to its schematic ids;
    PROJECT_ASSEMBLY scales by a different multiplier; SPATIAL is phase 5's.
    Their absence is the floor property A5.5 needs, and it is stated rather
    than inferred."""
    for bill in result.bills.values():
        assert BillTerm.UNLOCK_COST not in bill.terms
        assert BillTerm.PROJECT_ASSEMBLY not in bill.terms
        assert BillTerm.SPATIAL not in bill.terms


# --------------------------------------------------------------------------
# what it refuses, and what it reports rather than dropping
# --------------------------------------------------------------------------

def test_the_portable_miner_is_reported_incomplete_and_named(result):
    """Respec §10.4, and §8.1's shape applied to it: report the bill as
    incomplete and NAME the missing item rather than recursing into workshop
    recipes or dropping the row.

    The Portable Miner is equipment rather than a part, so it is absent from
    items.csv by construction — items.csv being the sole resource authority.
    Every miner's construction bill is only partly resolvable, and Greg's coal
    bootstrap contains a miner, so this is the ordinary case and not an edge.
    """
    assert result.unresolved == (("Build_MinerMk1_C", I_PORTABLE_MINER),)
    assert I_PORTABLE_MINER not in result.bills


def test_a_resolvable_set_reports_nothing_unresolved(data, construction):
    """The negative case, so `unresolved` is known to be discriminating rather
    than always populated."""
    result = stock.bill_for(
        data, construction,
        bootstrap=stock.BootstrapSet(tier=3, buildings=(("Build_FoundryMk1_C", 1),)),
        machines=(("Build_ConstructorMk1_C", 1),),
    )
    assert result.unresolved == ()


def test_an_unknown_producer_is_refused_rather_than_costed_at_zero(data, construction):
    with pytest.raises(ReferenceDataError, match="no Build Gun recipe"):
        stock.bill_for(
            data, construction,
            bootstrap=stock.BootstrapSet(tier=3, buildings=(("Build_NotAThing_C", 1),)),
            machines=(),
        )


def test_a_bootstrap_set_refuses_a_zero_count():
    """A building that is not needed is left out, not declared as zero. A zero
    row reads as a considered judgement and costs nothing, which is the worst
    of both."""
    with pytest.raises(ValueError, match="must be positive"):
        stock.BootstrapSet(tier=3, buildings=(("Build_MinerMk1_C", 0),))


def test_a_bootstrap_set_refuses_a_repeated_producer():
    with pytest.raises(ValueError, match="appears twice"):
        stock.BootstrapSet(tier=3, buildings=(
            ("Build_MinerMk1_C", 1), ("Build_MinerMk1_C", 2),
        ))


def test_a_bootstrap_set_refuses_being_empty():
    with pytest.raises(ValueError, match="at least one building"):
        stock.BootstrapSet(tier=3, buildings=())


# --------------------------------------------------------------------------
# the guardrail, in signature form
# --------------------------------------------------------------------------

def test_the_pass_cannot_derive_a_machine_count():
    """`machines` is a PARAMETER. A module that derived its own counts would be
    deciding what to build, which is a broader and more authoritative question
    than "what does this bill come to" — and this module holds enough to drift
    into answering it. The restriction is in the signature, not in a policy."""
    import inspect

    parameters = inspect.signature(stock.bill_for).parameters
    assert "machines" in parameters
    assert "bootstrap" in parameters
    assert parameters["machines"].kind is inspect.Parameter.KEYWORD_ONLY


def test_the_pass_takes_no_scenario():
    """Building construction costs do not scale with the recipe multiplier
    (respec §8, measured twice). A scenario parameter would be either applied
    and wrong, or accepted and ignored."""
    import inspect

    for fn in (stock.bill_for, stock.cost_of):
        assert not any(
            "scenario" in name for name in inspect.signature(fn).parameters
        )


def test_the_pass_emits_quantities_and_never_a_rate(result):
    """Quantities in, quantities out. Converting to a rate needs a time horizon
    §9 keeps out of the model, and the horizon is owned downstream by whoever
    holds the residual."""
    import dataclasses

    fields = {f.name for f in dataclasses.fields(next(iter(result.bills.values())))}
    assert not any("per_min" in name or "rate" in name for name in fields)
