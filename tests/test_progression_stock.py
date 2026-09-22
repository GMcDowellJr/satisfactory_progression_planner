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
from progression import stock, unlocks
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


# --------------------------------------------------------------------------
# UNLOCK_COST — 3b. The parked tier question turned out to be already answered.
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def costs():
    return unlocks.schematic_costs(REPO)


def test_unlock_cost_sums_over_a_schematic_set(costs):
    """Base Building (200 Concrete, 100 Iron Plate, 100 Iron Rod) plus Basic
    Steel Production (500 Concrete, 1000 Wire, 150 Rotor, 50 Modular Frame).
    Concrete is the only overlap and must add to 700, not replace."""
    total = stock.unlock_cost(("Schematic_1-1_C", "Schematic_3-4_C"), costs)
    assert total["Desc_Cement_C"] == pytest.approx(700.0)
    assert total["Desc_Wire_C"] == pytest.approx(1000.0)
    assert total["Desc_IronRod_C"] == pytest.approx(100.0)


def test_an_uncosted_schematic_contributes_nothing(costs):
    """Absent from the cost table means free. Safe only because every Milestone
    and Tutorial is costed — asserted in test_progression_unlocks.py, and this
    is the consumer that depends on it."""
    free = "Schematic_XMassTree_T1_C"
    assert free not in costs
    assert stock.unlock_cost((free,), costs) == {}


def test_unlock_costs_land_in_the_remainder_not_the_bootstrap(data, construction, costs):
    """The bootstrap half is "the initial machines needed to start the next
    tier" as declared — machines. A milestone purchase is not one, so folding
    it in would widen a definition the caller gave."""
    result = stock.bill_for(
        data, construction,
        bootstrap=stock.BootstrapSet(tier=1, buildings=(("Build_ConstructorMk1_C", 1),)),
        machines=(),
        unlocks=("Schematic_1-1_C",), unlock_costs=costs,
    )
    concrete = result.bills[I_CONCRETE]
    assert concrete.bootstrap_units == pytest.approx(0.0)
    assert concrete.remainder_units == pytest.approx(200.0)
    assert BillTerm.UNLOCK_COST in concrete.terms


def test_the_sink_coupon_rows_are_named_like_any_other_unresolvable(data, construction, costs):
    """Two EST_Custom schematics are priced in Desc_ResourceSinkCoupon_C, which
    is not in items.csv because a coupon is not a part. They reach `unresolved`
    through the SAME rule as the Portable Miner — no special case, because a
    special case is a place for the next one to hide."""
    result = stock.bill_for(
        data, construction,
        bootstrap=stock.BootstrapSet(tier=1, buildings=(("Build_ConstructorMk1_C", 1),)),
        machines=(),
        unlocks=("ResourceSink_PolymerResin_C",), unlock_costs=costs,
    )
    assert result.unresolved == (
        ("ResourceSink_PolymerResin_C", "Desc_ResourceSinkCoupon_C"),
    )
    assert "Desc_ResourceSinkCoupon_C" not in result.bills


# --------------------------------------------------------------------------
# PROJECT_ASSEMBLY — 3c
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def requirements(data):
    return stock.load_project_assembly(REPO, data)


def test_the_delivery_table_resolves_every_name_to_one_item(requirements):
    """The table carries `item_name` and no `item_id`. Measured against
    items.csv, 2026-09-22: no display name is duplicated there at all and all
    fifteen rows resolve to exactly one item. The join is safe by MEASUREMENT,
    not by design, which is why the loader refuses rather than picks."""
    assert len(requirements) == 15
    assert all(r.item_id.startswith("Desc_SpaceElevatorPart_") for r in requirements)
    phase_1 = [r for r in requirements if r.phase == 1]
    assert len(phase_1) == 1
    assert phase_1[0].item_id == "Desc_SpaceElevatorPart_1_C"
    assert phase_1[0].quantity_1x == pytest.approx(50.0)


def test_items_csv_has_no_duplicate_display_names(data):
    """The measured fact the name join rests on. The storage review's warning
    about `Turbo Rifle Ammo` is about the RECIPE table; items.csv has no
    duplicate at all today. If that changes, the join stops being safe and this
    says so before a bill does."""
    import collections

    counts = collections.Counter(item.display_name for item in data.items.values())
    assert [name for name, n in counts.items() if n > 1] == []


@pytest.mark.parametrize("doctor,match", [
    ("collide", "matches 2 items"),
    ("remove", "matches 0 items"),
])
def test_an_unresolvable_delivery_name_is_refused_rather_than_picked(data, doctor, match):
    """The guard is LATENT against the shipped data — every name resolves today,
    so removing it changes no figure and a mutation against it survives. This
    is what makes it load-bearing: the reference layer is doctored so the guard
    is the only thing standing between a wiki-sourced display name and a wrong
    item id.
    """
    import dataclasses

    items = dict(data.items)
    smart_plating = "Desc_SpaceElevatorPart_1_C"
    if doctor == "collide":
        decoy_id, decoy = next(
            (k, v) for k, v in items.items() if k != smart_plating
        )
        items[decoy_id] = dataclasses.replace(decoy, display_name="Smart Plating")
    else:
        del items[smart_plating]
    doctored = dataclasses.replace(data, items=items)

    with pytest.raises(stock.StockPassError, match=match):
        stock.load_project_assembly(REPO, doctored)


def test_phases_are_declared_and_nothing_else_is_counted(data, requirements):
    """`delivery_unlocks` is prose — "Tiers 3 and 4", "Project Assembly launch".
    Parsing English into a tier mapping would be inventing one, so the caller
    names the phases."""
    one = stock.project_assembly_cost(data, requirements, (1,))
    one_and_two = stock.project_assembly_cost(data, requirements, (1, 2))
    assert one == {"Desc_SpaceElevatorPart_1_C": pytest.approx(50.0)}
    assert one_and_two["Desc_SpaceElevatorPart_1_C"] == pytest.approx(1050.0)
    assert set(one_and_two) == {
        "Desc_SpaceElevatorPart_1_C",
        "Desc_SpaceElevatorPart_2_C",
        "Desc_SpaceElevatorPart_3_C",
    }
    assert stock.project_assembly_cost(data, requirements, ()) == {}


def test_the_project_assembly_multiplier_is_applied_and_not_rounded(requirements):
    """UNOBSERVED TIE, recorded rather than guessed.

    `apply_project_assembly_quantity` multiplies and does not round — the
    adapter's existing method, followed rather than improved. At 1.25x phase 1's
    50 Smart Plating lands on 62.5, which is exactly a tie, and the rounding
    rule for THIS multiplier has never been read in game. The recipe-input rule
    (nearest, halves away from zero) was probed before it was locked and this
    one has not been.

    PROBE, one glance, no construction: set the Project Assembly requirement
    multiplier to 1.25 and read phase 1's Smart Plating requirement. 62 or 63
    settles it.
    """
    from production_adapter import load
    from production_adapter.scenario import Scenario

    scaled = load(REPO, Scenario(project_assembly_requirement_multiplier=1.25))
    total = stock.project_assembly_cost(scaled, requirements, (1,))
    assert total["Desc_SpaceElevatorPart_1_C"] == pytest.approx(62.5)


def test_the_recipe_multiplier_does_not_touch_delivery_quantities(requirements):
    """A term scaled by the wrong multiplier is silently wrong. The recipe
    multiplier raises what a recipe COSTS; it does not raise what the Space
    Elevator asks for."""
    from production_adapter import load
    from production_adapter.scenario import Scenario

    scaled = load(REPO, Scenario(recipe_input_multiplier=1.25))
    total = stock.project_assembly_cost(scaled, requirements, (1,))
    assert total["Desc_SpaceElevatorPart_1_C"] == pytest.approx(50.0)


# --------------------------------------------------------------------------
# the term set reports what THIS call consulted
# --------------------------------------------------------------------------

def test_terms_widen_only_when_the_caller_supplies_the_term(
    data, construction, costs, requirements
):
    """`terms` is per call, not per module. A bill that claimed UNLOCK_COST
    because the module can compute it would be reporting a capability as a
    measurement."""
    kwargs = dict(
        bootstrap=stock.BootstrapSet(tier=1, buildings=(("Build_ConstructorMk1_C", 1),)),
        machines=(),
    )
    bare = stock.bill_for(data, construction, **kwargs)
    with_unlocks = stock.bill_for(
        data, construction, unlocks=("Schematic_1-1_C",), unlock_costs=costs, **kwargs
    )
    with_both = stock.bill_for(
        data, construction, unlocks=("Schematic_1-1_C",), unlock_costs=costs,
        project_assembly=requirements, phases=(1,), **kwargs
    )
    assert next(iter(bare.bills.values())).terms == stock.BASE_TERMS
    assert next(iter(with_unlocks.bills.values())).terms == (
        stock.BASE_TERMS | {BillTerm.UNLOCK_COST}
    )
    assert with_both.bills["Desc_SpaceElevatorPart_1_C"].terms == (
        stock.BASE_TERMS | {BillTerm.UNLOCK_COST, BillTerm.PROJECT_ASSEMBLY}
    )
    for result in (bare, with_unlocks, with_both):
        for bill in result.bills.values():
            assert BillTerm.SPATIAL not in bill.terms


@pytest.mark.parametrize("kwargs,match", [
    ({"unlocks": ("Schematic_1-1_C",)}, "together or not at all"),
    ({"unlock_costs": {}}, "together or not at all"),
    ({"phases": (1,)}, "together or not at all"),
])
def test_a_half_supplied_term_is_refused(data, construction, kwargs, match):
    """A schematic set with no cost table sums to zero, and a requirement table
    with no phases selects nothing — either would be reported as the term
    COUNTED. That is the term set lying, which is the one thing it exists to
    prevent."""
    with pytest.raises(stock.StockPassError, match=match):
        stock.bill_for(
            data, construction,
            bootstrap=stock.BootstrapSet(tier=1, buildings=(("Build_ConstructorMk1_C", 1),)),
            machines=(), **kwargs,
        )
