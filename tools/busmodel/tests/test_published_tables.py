"""The five published tables, as regression tests. This is the point of the package.

Every figure asserted below is QUOTED from a document, with the section named,
and none of it is recomputed from another figure plus a delta. Until now these
tables were reproduced once, by a scratch model with no driver that is
gitignored and cannot be run from the repo; a figure that cannot be reproduced
without guessing its rules cannot be carried forward by anyone else.

Two recovered rules are load-bearing and neither document states them
(crossover record section 1): external demand is 0, and every declared line gets
a one-machine floor. They are options on `solve`, so a failure here names which
rule moved rather than presenting as arithmetic drift.

WHAT IS NOT ASSERTED, and why. A3.5's 27-machine table is NOT a target, and did
not become one on 2026-09-22. Its withdrawal column sits inside the demand sum
on Concrete and Wire_copper and outside it on four other rows under one verdict
column, so `supply - draw = R` reconciles on nine of its eleven rows and fails
on two. `worked_case_A4` is the same topology with that defect removed, and
section 7 pins it under BOTH sizing bases — which is the recompute A5.3 asked
for, not a correction of A3.5.

Section 6 was RE-BASED on 2026-09-22 and its docstring records what it stopped
asserting. Amendment 6 is the record; do not read the change out of this file.

EVERY REPRODUCTION NAMES ITS BASIS, as of 2026-09-23 (amendment 10). `solve`
now defaults to `USAGE`, the model; the tables were computed on `AVERAGE`, so
each call below passes `sizing_basis=RECORD` rather than inheriting a default
that no longer means the record.
"""
from __future__ import annotations

import pytest

from busmodel import SizingBasis, balance_check, solve
from busmodel import declarations as decls
from busmodel.report import out_of_scope_draw

#: The basis every published table was computed on. Named once so a call site
#: reads as a reproduction, and so the default moving cannot move a table.
RECORD = SizingBasis.AVERAGE

TOL = 0.01


def _installed_capacity(decl, data, machines, capacity):
    """The config's capacity column: an explicit rate where it states one, and
    `machines * rate` where it states a machine count instead. Both fields
    appear in one file, which is the config's own convention."""
    out = dict(capacity)
    for b in decl.buses:
        if b.bus_id in machines:
            rate = next(r for i, r in data.recipes[b.recipe_id].outputs if i == b.item_id)
            out[b.bus_id] = machines[b.bus_id] * rate
    return out


# --------------------------------------------------------------------------
# 1. storage review section 5 -- 10 of 10 cells, at 1x and at 1.25x
# --------------------------------------------------------------------------

#: `storage-model-bundle-review-2026-09-21.md` section 5, phase 1, solved to a
#: fixed point with per-input nearest-integer rounding, external demand held
#: constant. bus_id -> (machines, overflow/min).
SECTION_5_1X = {
    decls.I_RIP: (1, 2.62),
    decls.I_IRON_PLATE: (1, 1.25),
    decls.I_IRON_ROD: (3, 13.00),
    decls.I_WIRE: (4, 22.50),
    decls.I_SCREW: (2, 0.00),
}
SECTION_5_1_25X = {
    decls.I_RIP: (1, 1.62),
    decls.I_IRON_PLATE: (2, 15.62),
    decls.I_IRON_ROD: (3, 6.00),
    decls.I_WIRE: (5, 13.12),
    decls.I_SCREW: (3, 26.00),
}
#: "Rotor / Modular Frame / Cable / Concrete  unchanged" -- section 5's own row.
SECTION_5_UNCHANGED = (decls.I_ROTOR, decls.I_MODULAR_FRAME, decls.I_CABLE, decls.I_CONCRETE)


@pytest.mark.parametrize("scenario_name,expected", [
    ("canonical", SECTION_5_1X),
    ("scenario_of_record", SECTION_5_1_25X),
])
def test_storage_review_section_5(request, scenario_name, expected):
    data = request.getfixturevalue(scenario_name)
    solution = solve(decls.storage_review_t1_2(data), data, sizing_basis=RECORD)
    for bus_id, (machines, overflow) in expected.items():
        bus = solution[bus_id]
        assert bus.machines == machines, bus_id
        assert bus.residual_per_min == pytest.approx(overflow, abs=TOL), bus_id


def test_storage_review_section_5_unchanged_rows(canonical, scenario_of_record):
    """Four lines section 5 records as unchanged across the notch.

    Asserted because it is where the min-one-machine floor is visible: these
    rows have zero automated demand, and their overflow is a whole machine's
    output. Without the floor they would be zero at both scenarios and would
    also be "unchanged", which is the wrong reason for the right answer.
    """
    at_1x = solve(decls.storage_review_t1_2(canonical), canonical, sizing_basis=RECORD)
    at_125 = solve(decls.storage_review_t1_2(scenario_of_record), scenario_of_record,
                   sizing_basis=RECORD)
    for bus_id in SECTION_5_UNCHANGED:
        assert at_1x[bus_id].machines == at_125[bus_id].machines == 1, bus_id
        assert at_1x[bus_id].residual_per_min == pytest.approx(
            at_125[bus_id].residual_per_min, abs=TOL
        ), bus_id
        assert at_1x[bus_id].residual_per_min > 0, bus_id


# --------------------------------------------------------------------------
# 2. storage review section 6.1 -- the balance deltas, both phases
# --------------------------------------------------------------------------

#: Section 6.1, at 1x. Positive deltas are legitimate (consumers outside the
#: modelled set); negative ones are not, because the consumer is inside the same
#: file. Only the negative rows are published, so only they are asserted.
SECTION_6_1_NEGATIVES_1X = {
    "T1-2": {decls.I_SCREW: -50.0, decls.I_WIRE: -18.5, decls.I_IRON_ROD: -3.0},
    "T3-4": {decls.I_SCREW: -50.0, decls.I_WIRE: -37.3, decls.I_IRON_ROD: -6.0},
}

#: `bus_level_recompute_and_alternate_crossover.md` section 2. The same check at
#: the scenario of record: the three deltas are LARGER, and in each phase there
#: is a FOURTH. The cardinality is the finding, so it is asserted too.
SECTION_2_NEGATIVES_1_25X = {
    "T1-2": {
        decls.I_SCREW: -74.0, decls.I_WIRE: -30.9, decls.I_IRON_ROD: -8.5,
        decls.I_IRON_PLATE: -5.6,
    },
    "T3-4": {
        decls.I_SCREW: -74.0, decls.I_WIRE: -53.7, decls.I_IRON_ROD: -13.0,
        decls.I_RIP: -0.5,
    },
}


def _negative_deltas(phase, data):
    if phase == "T1-2":
        decl = decls.storage_review_t1_2(data)
        machines, capacity = decls.STORAGE_REVIEW_T1_2_MACHINES, decls.STORAGE_REVIEW_T1_2_CAPACITY
        declared = decls.STORAGE_REVIEW_T1_2_DECLARED_DEMAND
    else:
        decl = decls.storage_review_t3_4(data)
        machines, capacity = decls.STORAGE_REVIEW_T3_4_MACHINES, decls.STORAGE_REVIEW_T3_4_CAPACITY
        declared = decls.STORAGE_REVIEW_T3_4_DECLARED_DEMAND
    rows = balance_check(
        decl, data, _installed_capacity(decl, data, machines, capacity), declared
    )
    return {r.bus_id: r.delta_per_min for r in rows if r.delta_per_min < -1e-9}


@pytest.mark.parametrize("phase", ["T1-2", "T3-4"])
def test_storage_review_section_6_1_deltas(canonical, phase):
    actual = _negative_deltas(phase, canonical)
    expected = SECTION_6_1_NEGATIVES_1X[phase]
    assert set(actual) == set(expected), phase
    for bus_id, delta in expected.items():
        assert actual[bus_id] == pytest.approx(delta, abs=0.05), (phase, bus_id)


@pytest.mark.parametrize("phase", ["T1-2", "T3-4"])
def test_crossover_record_section_2_deltas(scenario_of_record, phase):
    """The same check at 1.25x: four negatives per phase, not three.

    The fourth in phase 1 is Iron Plate, which section 3 of the review names as
    the binding item of the phase.
    """
    actual = _negative_deltas(phase, scenario_of_record)
    expected = SECTION_2_NEGATIVES_1_25X[phase]
    assert set(actual) == set(expected), phase
    for bus_id, delta in expected.items():
        assert actual[bus_id] == pytest.approx(delta, abs=0.05), (phase, bus_id)


# --------------------------------------------------------------------------
# 3. storage review section 7 -- the alternate table, 8 rows, both regimes
# --------------------------------------------------------------------------

SECTION_7 = {
    "stitched": {
        "total_machines": 15,
        decls.I_SCREW: (2, 0.00),
        decls.I_WIRE: (4, 22.50),
        decls.I_IRON_PLATE: (1, 1.25),
        "screw_draw": 100.0,
        "wire_draw": 97.5,
        "iron_ingot": 100.0,
        "copper_ingot": 60.0,
    },
    "base_rip": {
        "total_machines": 16,
        decls.I_SCREW: (4, 40.00),
        decls.I_WIRE: (2, 0.00),
        decls.I_IRON_PLATE: (2, 10.00),
        "screw_draw": 160.0,
        "wire_draw": 60.0,
        "iron_ingot": 155.0,
        "copper_ingot": 30.0,
    },
}


@pytest.mark.parametrize("regime", ["stitched", "base_rip"])
def test_storage_review_section_7_alternate_table(canonical, regime):
    """An alternate is a RE-WIRING event, not only a cheaper recipe.

    Stated as deltas, no ordering: Stitched cuts the screw line from four
    machines to two and iron ingot draw by 35%, at the cost of doubling copper
    ingot draw and adding two wire machines. Nothing here is ranked, which is
    what makes the report admissible under section 8.1.
    """
    decl = (decls.storage_review_t1_2(canonical) if regime == "stitched"
            else decls.storage_review_t1_2_base_rip(canonical))
    solution = solve(decl, canonical, sizing_basis=RECORD)
    expected = SECTION_7[regime]

    assert solution.total_machines == expected["total_machines"]
    for bus_id in (decls.I_SCREW, decls.I_WIRE, decls.I_IRON_PLATE):
        machines, overflow = expected[bus_id]
        assert solution[bus_id].machines == machines, bus_id
        assert solution[bus_id].residual_per_min == pytest.approx(overflow, abs=TOL), bus_id

    assert solution[decls.I_SCREW].demand_per_min == pytest.approx(expected["screw_draw"], abs=TOL)
    assert solution[decls.I_WIRE].demand_per_min == pytest.approx(expected["wire_draw"], abs=TOL)

    out_of_scope = out_of_scope_draw(decl, canonical, solution)
    assert out_of_scope[decls.I_IRON_INGOT] == pytest.approx(expected["iron_ingot"], abs=TOL)
    assert out_of_scope[decls.I_COPPER_INGOT] == pytest.approx(expected["copper_ingot"], abs=TOL)


# --------------------------------------------------------------------------
# 4. bus record section 1 / section 4 -- the screw bus
# --------------------------------------------------------------------------

def test_bus_record_screw_bus(scenario_of_record):
    """`bus_allocation_backpressure_and_residual.md` sections 1 and 4.

        screw bus   199/min      RIP 75 (37.7%)     Rotor 124 (62.3%)
        at the ceil (5 machines, 200/min supply)    R = 1.0/min

    The partition is emitted as RATIOS and never as a splitter tree: a single
    returned topology reproduces the set-valued defect, because splitter trees
    tie constantly.
    """
    data = scenario_of_record
    decl = decls.crossover_regime(data, stitched=False)
    solution = solve(decl, data, sizing_basis=RECORD)
    screws = solution["screws"]

    assert screws.rate_per_min == pytest.approx(40.0, abs=TOL)
    assert screws.demand_per_min == pytest.approx(199.0, abs=TOL)
    assert screws.machines == 5
    assert screws.supply_per_min == pytest.approx(200.0, abs=TOL)
    assert screws.residual_per_min == pytest.approx(1.0, abs=TOL)

    shares = {s.bus_id: s for s in screws.consumers}
    assert shares["rip"].draw_per_min == pytest.approx(75.0, abs=TOL)
    assert shares["rotor"].draw_per_min == pytest.approx(124.0, abs=TOL)
    assert shares["rip"].share == pytest.approx(0.377, abs=0.001)
    assert shares["rotor"].share == pytest.approx(0.623, abs=0.001)


def test_storage_rate_is_a_machine_count(scenario_of_record):
    """Section 4: R(k) = ceil_residual + k * producer_rate.

    At the ceil the screw bus yields 1/min. Meaningful storage costs a machine
    and arrives 40/min at a time, which is what the old per-item boolean could
    not express.
    """
    data = scenario_of_record
    base = decls.crossover_regime(data, stitched=False)
    for k, expected in ((0, 1.0), (1, 41.0), (2, 81.0)):
        decl = decls.Declaration(
            name=f"screws+{k}",
            buses=tuple(
                decls.BusSpec(
                    bus_id=b.bus_id, item_id=b.item_id, recipe_id=b.recipe_id,
                    sources=b.sources, disposition=b.disposition,
                    extra_producers=k if b.bus_id == "screws" else 0,
                    withdrawal_per_min=b.withdrawal_per_min,
                )
                for b in base.buses
            ),
            external_per_min=dict(base.external_per_min),
        )
        residual = solve(decl, data, sizing_basis=RECORD)["screws"].residual_per_min
        assert residual == pytest.approx(expected, abs=TOL)


# --------------------------------------------------------------------------
# 5. bus record section 8 -- the regime comparison, and the crossover sweep
# --------------------------------------------------------------------------

def test_bus_record_section_8_regime_comparison(scenario_of_record):
    """Section 8, targets held at 5 RIP/min and 4 Rotor/min.

        base RIP               screw bus 199/min    19.02 -> 20
        Stitched + Iron Wire   screw bus 124/min    15.79 -> 19

    The bus sheds 37.7%; screw and rod each drop a producer; a two-machine Iron
    Wire lane appears on the ingot bus.
    """
    data = scenario_of_record
    a = solve(decls.crossover_regime(data, stitched=False), data, sizing_basis=RECORD)
    b = solve(decls.crossover_regime(data, stitched=True), data, sizing_basis=RECORD)

    assert a.total_continuous_machines == pytest.approx(19.02, abs=TOL)
    assert a.total_machines == 20
    assert b.total_continuous_machines == pytest.approx(15.79, abs=TOL)
    assert b.total_machines == 19

    assert a["screws"].demand_per_min == pytest.approx(199.0, abs=TOL)
    assert b["screws"].demand_per_min == pytest.approx(124.0, abs=TOL)
    assert b["screws"].machines == a["screws"].machines - 1
    assert b["iron_rod"].machines == a["iron_rod"].machines - 1
    assert b[decls.BUS_WIRE_IRON].machines == 2


#: Crossover record section 6, the full sweep.
#: s -> (A continuous, A ceil, B continuous, B ceil)
SECTION_6_SWEEP = {
    0.1: (1.90, 6, 1.58, 7),
    0.2: (3.80, 7, 3.16, 7),
    0.5: (9.51, 12, 7.90, 11),
    0.9: (17.12, 19, 14.21, 16),
    1.0: (19.02, 20, 15.79, 19),
    1.1: (20.92, 25, 17.37, 22),
    1.6: (30.43, 33, 25.27, 27),
    2.0: (38.03, 39, 31.59, 35),
    5.0: (95.08, 96, 78.97, 83),
    10.0: (190.17, 192, 157.94, 160),
    30.0: (570.50, 572, 473.83, 476),
    100.0: (1901.67, 1903, 1579.44, 1582),
}


@pytest.mark.parametrize("scale", sorted(SECTION_6_SWEEP))
def test_crossover_sweep(scenario_of_record, scale):
    data = scenario_of_record
    a_cont, a_ceil, b_cont, b_ceil = SECTION_6_SWEEP[scale]
    a = solve(decls.crossover_regime(data, stitched=False, scale=scale), data, sizing_basis=RECORD)
    b = solve(decls.crossover_regime(data, stitched=True, scale=scale), data, sizing_basis=RECORD)
    assert a.total_continuous_machines == pytest.approx(a_cont, abs=0.02)
    assert a.total_machines == a_ceil
    assert b.total_continuous_machines == pytest.approx(b_cont, abs=0.02)
    assert b.total_machines == b_ceil


def test_integrality_tax_is_bounded_by_the_bus_count(scenario_of_record):
    """Section 6's structural argument, over the published sweep.

    The tax is a sum of fractional parts over a FIXED number of buses -- seven
    in regime B, six in regime A -- so it is bounded by the bus count and is
    O(1) in scale, while the continuous advantage is O(s). This is why "the
    crossover scale" does not exist as posed.
    """
    data = scenario_of_record
    for scale in SECTION_6_SWEEP:
        for stitched, bus_count in ((False, 6), (True, 7)):
            solution = solve(decls.crossover_regime(data, stitched=stitched, scale=scale), data,
                             sizing_basis=RECORD)
            assert len(solution.buses) == bus_count
            assert 0.0 <= solution.integrality_tax < bus_count


def test_section_6_1_local_minimum(scenario_of_record):
    """s = 1.0 is a local minimum of the saving, not a property of small scale.

    Any single-point measurement of an alternate's machine saving is a sample of
    a sawtooth, and a tool that reports one scale reports noise.
    """
    data = scenario_of_record

    def saved(scale):
        a = solve(decls.crossover_regime(data, stitched=False, scale=scale), data,
                  sizing_basis=RECORD)
        b = solve(decls.crossover_regime(data, stitched=True, scale=scale), data,
                  sizing_basis=RECORD)
        return a.total_machines - b.total_machines

    assert saved(0.9) == 3
    assert saved(1.0) == 1
    assert saved(1.1) == 3
    assert saved(1.0) < saved(0.9) and saved(1.0) < saved(1.1)


# --------------------------------------------------------------------------
# 6. amendment 4's central comparison -- computed, not hand-derived
# --------------------------------------------------------------------------

def test_amendment_4_iron_plate_build_line(scenario_of_record):
    """A4.1 and A4.2, against Iron Ingot's headroom. **RE-BASED 2026-09-22.**

    The comparison is unchanged in substance and has MOVED COLUMNS. A5.2
    settles that the two states do not differ in what a line costs its source
    bus on average — only in power and in peak duration — so the 36/min is a
    PEAK figure and always was. It is asserted here where it belongs.

        MATCHED build line, 10% clock   +4/min ingot avg, +4/min peak
        full Constructor, 100%          +4/min ingot avg, +40/min PEAK

    What this test asserted before, and no longer does: `ingot_full.machines
    == 8, "the full-rate line costs a smelter"`. Under a usage basis both runs
    size 7 smelters, because both draw 204/min on average. The smelter was
    never an average cost.

    **It is not a null result.** The full-rate line asks the ingot bus for
    240/min against a supply of 210 while it refills — 30/min it cannot have —
    and splitters round-robin rather than prioritise, so that shortfall is paid
    by Wire, Iron Plate and Iron Rod, which hold 98% of the bus between them.
    A4.2's finding survives with its provenance corrected: the full-rate line
    does not cost a smelter, it starves its neighbours for the duration of a
    refill. The DURATION is capacity/slack and is still not modelled — no
    container capacity reaches this layer — so how much that costs is not
    answered here, and is not guessed.

    The two runs differ in exactly one declared field, the build line's
    disposition. Everything else is held.
    """
    data = scenario_of_record
    from realization.contracts import Disposition

    matched = solve(decls.worked_case_a4(data), data, sizing_basis=RECORD)
    full = solve(
        decls.worked_case_a4(data, build_plate_disposition=Disposition.BACK_UP), data,
        sizing_basis=RECORD,
    )

    plate = matched[decls.BUS_IRON_PLATE_BUILD]
    assert plate.disposition is Disposition.MATCHED
    assert plate.machines == 1
    assert plate.clock_percent == pytest.approx(10.0, abs=TOL)
    assert plate.supply_per_min == pytest.approx(2.0, abs=TOL)
    assert plate.residual_per_min == pytest.approx(0.0, abs=TOL)

    assert full[decls.BUS_IRON_PLATE_BUILD].machines == 1
    assert full[decls.BUS_IRON_PLATE_BUILD].clock_percent == pytest.approx(100.0, abs=TOL)
    assert full[decls.BUS_IRON_PLATE_BUILD].supply_per_min == pytest.approx(20.0, abs=TOL)

    ingot_matched, ingot_full = matched["iron_ingot"], full["iron_ingot"]

    # The average is the same bus, twice. This is A5.2's claim, computed.
    assert ingot_full.demand_per_min == pytest.approx(
        ingot_matched.demand_per_min, abs=TOL
    )
    assert ingot_matched.machines == 7
    assert ingot_full.machines == 7
    assert ingot_matched.residual_per_min == pytest.approx(6.0, abs=TOL)

    # The 36/min, where it belongs. Same number, different column.
    assert ingot_full.peak_demand_per_min - ingot_matched.peak_demand_per_min == (
        pytest.approx(36.0, abs=TOL)
    )
    assert ingot_matched.peak_demand_per_min == pytest.approx(204.0, abs=TOL)
    assert ingot_full.peak_demand_per_min == pytest.approx(240.0, abs=TOL)

    # MATCHED has no transient at all: supply equals demand by construction.
    assert ingot_matched.peak_shortfall_per_min == pytest.approx(0.0, abs=TOL)
    assert ingot_full.peak_shortfall_per_min == pytest.approx(30.0, abs=TOL)

    # And the shortfall lands on the neighbours, not on the line causing it.
    build_share = next(
        s for s in ingot_full.consumers if s.bus_id == decls.BUS_IRON_PLATE_BUILD
    )
    assert build_share.draw_per_min == pytest.approx(4.0, abs=TOL)
    assert build_share.peak_per_min == pytest.approx(40.0, abs=TOL)
    assert build_share.share < 0.03


def test_worked_case_reproduces_a3_5_rows_unaffected_by_the_basis_defect(scenario_of_record):
    """A3.5's rows that do not depend on the withdrawal-basis defect.

    Nine of A3.5's eleven rows reconcile under `supply - draw = R`; Concrete and
    SmartPlating do not, because a withdrawal sits inside the demand sum on some
    rows and outside it on others. The reconciling rows are asserted; the two
    that do not are left to next action 4.

    Iron Plate's residual is asserted at 15.62 for the PRODUCTION bus alone,
    which A4.1 establishes was never the build supply.
    """
    data = scenario_of_record
    solution = solve(decls.worked_case_a4(data), data, sizing_basis=RECORD)
    for bus_id, machines, residual in (
        ("screws", 4, 36.00),
        (decls.BUS_WIRE_IRON, 3, 20.62),
        (decls.BUS_WIRE_COPPER, 1, 16.00),
        (decls.BUS_IRON_PLATE, 2, 15.62),
        ("copper_ingot", 1, 15.00),
        ("iron_rod", 5, 11.00),
    ):
        assert solution[bus_id].machines == machines, bus_id
        assert solution[bus_id].residual_per_min == pytest.approx(residual, abs=TOL), bus_id


def test_split_wire_buses_do_not_pool(scenario_of_record):
    """A3.1: two buses of one item are DIFFERENT OBJECTS.

    Grouping by item re-merges what the caller declared apart. The merged figure
    is not wrong arithmetic; it describes a factory nobody built.
    """
    data = scenario_of_record
    decl = decls.worked_case_a4(data)
    solution = solve(decl, data, sizing_basis=RECORD)

    wire_buses = decl.buses_of_item(decls.I_WIRE)
    assert {b.bus_id for b in wire_buses} == {decls.BUS_WIRE_IRON, decls.BUS_WIRE_COPPER}
    assert solution[decls.BUS_WIRE_IRON].recipe_id != solution[decls.BUS_WIRE_COPPER].recipe_id
    assert solution[decls.BUS_WIRE_IRON].residual_per_min == pytest.approx(20.62, abs=TOL)
    assert solution[decls.BUS_WIRE_COPPER].residual_per_min == pytest.approx(16.00, abs=TOL)


# --------------------------------------------------------------------------
# 7. the usage recompute, 2026-09-22. Amendment 6
# --------------------------------------------------------------------------
#
# A5.3 predicted the cascade from two rows of arithmetic and did not compute it:
# "size-for-usage does not merely trim the build lines, it shrinks the
# PRODUCTION CHAIN." This is that computation. It is a NEW table rather than a
# correction of A3.5 — A3.5 stands as written and is still not a target.

#: `worked_case_A4` under `SizingBasis.USAGE`, scenario of record, computed
#: 2026-09-22 in a container. Quoted here as the table amendment 6 publishes,
#: which is what makes it a regression target rather than a one-off run.
A3_5_UNDER_USAGE = (
    # bus                       machines  demand    residual
    ("smart_plating",                  1,    2.00,     0.00),
    ("rip",                            1,    4.00,     1.62),
    ("rotor",                          1,    4.00,     0.00),
    ("screws",                         4,  124.00,    36.00),
    (decls.BUS_WIRE_IRON,              2,   33.33,    11.67),
    (decls.BUS_WIRE_COPPER,            1,   14.00,    16.00),
    ("cable",                          1,    3.00,    27.00),
    ("concrete",                       1,    6.00,     9.00),
    (decls.BUS_IRON_PLATE,             1,   17.33,     2.67),
    (decls.BUS_IRON_PLATE_BUILD,       1,    2.00,     0.00),
    ("iron_rod",                       4,   55.00,     5.00),
    ("iron_ingot",                     4,  115.89,     4.11),
    ("copper_ingot",                   1,    7.00,    23.00),
)


def test_worked_case_under_a_usage_basis(scenario_of_record):
    """A5.3's cascade, computed rather than predicted.

    Every row is the same declaration as the AVERAGE run. The only thing that
    changed is that a WITHDRAWN consumer draws its usage instead of its
    nameplate, which is A5.2's single claim.
    """
    data = scenario_of_record
    solution = solve(decls.worked_case_a4(data), data, sizing_basis=SizingBasis.USAGE)
    for bus_id, machines, demand, residual in A3_5_UNDER_USAGE:
        assert solution[bus_id].machines == machines, bus_id
        assert solution[bus_id].demand_per_min == pytest.approx(demand, abs=TOL), bus_id
        assert solution[bus_id].residual_per_min == pytest.approx(residual, abs=TOL), bus_id


def test_the_usage_basis_shrinks_the_production_chain_not_only_the_build_lines(
    scenario_of_record
):
    """A5.3's CONSEQUENCE, asserted as the claim it makes.

        AVERAGE   29 machines, 21.747 continuous
        USAGE     23 machines, 16.989 continuous

    Six machines, and NONE of them is a build line: Cable, Concrete and the
    Iron Plate build line are one machine on both bases — the machine floor
    holds them there. Every machine the usage basis removes comes off Iron
    Ingot (7 -> 4), Iron Rod (5 -> 4), Iron Plate (2 -> 1) and Wire_iron
    (3 -> 2), which are production buses.

    This is why A5.3 says A3.5's figure is a TRANSIENT one: what the factory
    draws before its containers saturate, not what it settles at.
    """
    data = scenario_of_record
    decl = decls.worked_case_a4(data)
    average = solve(decl, data, sizing_basis=RECORD)
    usage = solve(decl, data, sizing_basis=SizingBasis.USAGE)

    assert average.total_machines == 29
    assert usage.total_machines == 23
    assert average.total_continuous_machines == pytest.approx(21.747, abs=0.001)
    assert usage.total_continuous_machines == pytest.approx(16.989, abs=0.001)

    for build_line in ("cable", "concrete", decls.BUS_IRON_PLATE_BUILD):
        assert average[build_line].machines == 1, build_line
        assert usage[build_line].machines == 1, build_line

    for production, before, after in (
        ("iron_ingot", 7, 4),
        ("iron_rod", 5, 4),
        (decls.BUS_IRON_PLATE, 2, 1),
        (decls.BUS_WIRE_IRON, 3, 2),
    ):
        assert average[production].machines == before, production
        assert usage[production].machines == after, production


def test_the_out_of_scope_draw_follows_the_basis_it_was_solved_on(
    scenario_of_record
):
    """An out-of-scope figure on a different basis from the in-scope ones is
    the section 6.1 defect in a new place, so the roll-up reads the solution's
    basis rather than assuming one.

    Iron Ore is the visible case: 210/min under AVERAGE, which is seven
    smelters at nameplate, against 115.89/min under USAGE, which is what the
    ingot bus actually consumes.
    """
    data = scenario_of_record
    decl = decls.worked_case_a4(data)
    average = out_of_scope_draw(decl, data, solve(decl, data, sizing_basis=RECORD))
    usage = out_of_scope_draw(
        decl, data, solve(decl, data, sizing_basis=SizingBasis.USAGE)
    )
    assert average["Desc_OreIron_C"] == pytest.approx(210.00, abs=TOL)
    assert usage["Desc_OreIron_C"] == pytest.approx(115.89, abs=TOL)
    # Limestone is Concrete's, and Concrete is a BACK_UP build line: it drew
    # its usage on both bases already, so this row does not move.
    assert average["Desc_Stone_C"] == pytest.approx(usage["Desc_Stone_C"], abs=TOL)


def test_the_peak_is_reported_on_both_bases_and_sizes_neither(scenario_of_record):
    """The demotion, from the published-table side.

    Wire_copper is the sharpest row: Cable draws 3/min on average and 90/min at
    nameplate, so its peak asks 95/min of a bus supplying 30. Under the OLD
    peak basis that sized Wire_copper at four Constructors. It now sizes at one
    on both bases, and the 65/min is reported as a shortfall the production
    consumers sharing that bus absorb.
    """
    data = scenario_of_record
    decl = decls.worked_case_a4(data)
    average = solve(decl, data, sizing_basis=RECORD)
    usage = solve(decl, data, sizing_basis=SizingBasis.USAGE)
    for solution in (average, usage):
        bus = solution[decls.BUS_WIRE_COPPER]
        assert bus.machines == 1
        assert bus.demand_per_min == pytest.approx(14.00, abs=TOL)
        assert bus.peak_demand_per_min == pytest.approx(95.00, abs=TOL)
        assert bus.peak_shortfall_per_min == pytest.approx(65.00, abs=TOL)


# --------------------------------------------------------------------------
# 8. the storage review under USAGE, 2026-09-23. Amendment 11
# --------------------------------------------------------------------------
#
# Sections 1-3 above reproduce the review on `RECORD` and are unchanged. These
# are NEW tables — what the same declarations say on the model's basis — and
# they are pinned for the reason section 7 is: a recompute nobody can repeat is
# not a finding.

def _storage_review_declarations(canonical, scenario_of_record):
    return (
        ("T1-2 @1x", decls.storage_review_t1_2(canonical), canonical),
        ("T1-2 @1.25x", decls.storage_review_t1_2(scenario_of_record), scenario_of_record),
        ("base RIP @1x", decls.storage_review_t1_2_base_rip(canonical), canonical),
    )


def test_the_storage_review_declares_no_demand(canonical, scenario_of_record):
    """A11.1. External demand is zero (the recovered rule), no line declares a
    withdrawal, and every line is WITHDRAWN — so on USAGE nothing in the
    declaration is demanded, and every bus sits at the one-machine floor with
    its whole output as residual.

    Sections 5 and 7 therefore measured the review's own stated assumption
    (§9: "every modelled line runs at 100% clock") propagated upstream through
    the floor machines. Their record totals are 15, 18 and 16; every machine
    above 9 in each is a floor machine's nameplate draw."""
    for label, decl, data in _storage_review_declarations(canonical, scenario_of_record):
        assert decl.external_per_min == {}, label
        assert all(b.withdrawal_per_min is None for b in decl.buses), label
        usage = solve(decl, data, sizing_basis=SizingBasis.USAGE)
        assert usage.total_continuous_machines == pytest.approx(0.0), label
        assert usage.total_machines == len(decl.buses) == 9, label
        for bus in usage.buses:
            assert bus.machines == 1, (label, bus.bus_id)
            assert bus.residual_per_min == pytest.approx(bus.supply_per_min), (label, bus.bus_id)


def test_section_7s_regimes_are_indistinguishable_on_usage(canonical):
    """A11.2. Stitched against base RIP differs by 15 against 16 machines and
    a 35% iron-ingot delta on RECORD. On USAGE both are 9 floor machines with
    no out-of-scope draw at all: RIP has no demand, so its recipe moves
    nothing. The record's delta is the upstream footprint of ONE RIP machine at
    full rate under each recipe — a real figure, but a per-machine one."""
    stitched = solve(decls.storage_review_t1_2(canonical), canonical,
                     sizing_basis=SizingBasis.USAGE)
    base = solve(decls.storage_review_t1_2_base_rip(canonical), canonical,
                 sizing_basis=SizingBasis.USAGE)
    assert stitched.total_machines == base.total_machines == 9
    for bus in stitched.buses:
        assert base[bus.bus_id].machines == bus.machines, bus.bus_id
        assert base[bus.bus_id].demand_per_min == pytest.approx(bus.demand_per_min), bus.bus_id
    for solution, decl in ((stitched, decls.storage_review_t1_2(canonical)),
                           (base, decls.storage_review_t1_2_base_rip(canonical))):
        assert all(v == pytest.approx(0.0)
                   for v in out_of_scope_draw(decl, canonical, solution).values())


#: A11.3. Section 6.1 with every consumer at the config's OWN declared demand
#: rather than at 100% of its installed capacity. Negative rows only, as in
#: section 2 above. Computed in an agent container 2026-09-23.
SECTION_6_1_AT_DECLARED_DEMAND = {
    ("canonical", "T1-2"): {},
    ("canonical", "T3-4"): {decls.I_WIRE: -17.10},
    ("scenario_of_record", "T1-2"): {decls.I_SCREW: -12.00},
    ("scenario_of_record", "T3-4"): {decls.I_SCREW: -12.00, decls.I_WIRE: -26.98},
}


@pytest.mark.parametrize("scenario_name,phase", sorted(SECTION_6_1_AT_DECLARED_DEMAND))
def test_section_6_1_at_declared_demand(request, scenario_name, phase):
    """Section 6.1 has no sizing basis: its draw is the config's installed
    capacity at 100%, which is nameplate by construction, and it reproduces
    unchanged. Its USAGE analogue draws each consumer at the config's own
    declared demand — a consistency check of the demand column against
    itself. At 1x T1-2 all three negatives vanish (Screws -50 -> 0: Rotor is
    declared at 2/min, half its machine). What survives is T3-4 Wire at 1x, and
    at 1.25x Screws in both phases, where the multiplier raises Rotor's screw
    draw above the 50 the config declares."""
    data = request.getfixturevalue(scenario_name)
    if phase == "T1-2":
        decl, declared = decls.storage_review_t1_2(data), decls.STORAGE_REVIEW_T1_2_DECLARED_DEMAND
    else:
        decl, declared = decls.storage_review_t3_4(data), decls.STORAGE_REVIEW_T3_4_DECLARED_DEMAND
    rows = balance_check(decl, data, declared, declared)
    actual = {r.bus_id: r.delta_per_min for r in rows if r.delta_per_min < -1e-9}
    expected = SECTION_6_1_AT_DECLARED_DEMAND[(scenario_name, phase)]
    assert set(actual) == set(expected), (scenario_name, phase)
    for bus_id, delta in expected.items():
        assert actual[bus_id] == pytest.approx(delta, abs=0.05), (scenario_name, phase, bus_id)
