"""D6 (crossover A23): phase 1 as a declaration; standing per lane, with provenance.

Project doc d6-phase-defaults-and-lane-standing-design-2026-09-24.md,
Amendments 1-2 (decided by Greg, 2026-09-24). Build step 4's list:

    shared bus ids     phase 1 and phase 2 name every shared item's bus alike
    conservation       per lane, per infrastructure class, per paid item
    provenance         required, and printed for each kind
    Cast Screw         a standing lane of another recipe nets nothing

plus the step 1 pins (phase 1 through phase_run reproduces the case of
record), G2' (surplus machines never pay bootstrap buildings), O4 (only the
declared step nets against infrastructure), and the save / read round trip.

Measured in the agent container 2026-09-24, 1x scenario, LpBackend MEAN,
on origin/master ac8cb89 plus this change.
"""
from __future__ import annotations

import ast
import dataclasses
import importlib.util
import inspect
import pathlib
import sys
import textwrap

import pytest

from production_adapter import load
from production_adapter.gamedata import load_construction
from progression import stock

REPO = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("phase_run", REPO / "tools" / "phase_run.py")
phase_run = sys.modules.get("phase_run") or importlib.util.module_from_spec(_spec)
if "phase_run" not in sys.modules:
    sys.modules["phase_run"] = phase_run
    _spec.loader.exec_module(phase_run)
rate_sheet = phase_run.rate_sheet
goal_run = phase_run.goal_run

P1 = phase_run.declaration(1)
P2 = phase_run.declaration(2)
ASM, CON, FDY, SML = ("Build_AssemblerMk1_C", "Build_ConstructorMk1_C",
                      "Build_FoundryMk1_C", "Build_SmelterMk1_C")
MINER, COAL_GEN, WATER = "Build_MinerMk1_C", "Build_GeneratorCoal_C", "Build_WaterPump_C"
CAST_SCREW = "Recipe_Alternate_Screw_C"
DECLARED_SRC = stock.StandingSource(stock.StandingProvenance.DECLARED, path="standing.toml")


@pytest.fixture(scope="module")
def data():
    return load(REPO)


@pytest.fixture(scope="module")
def phase1():
    return phase_run.run(P1)


@pytest.fixture(scope="module")
def placeholder(tmp_path_factory):
    state = tmp_path_factory.mktemp("state")
    standing = phase_run.resolve_standing(2, state_dir=state)
    return state, standing


@pytest.fixture(scope="module")
def phase2(placeholder):
    _, standing = placeholder
    return phase_run.run(P2, standing=standing)


# --------------------------------------------------------------------------
# Step 1: phase 1 is the case of record, through phase_run
# --------------------------------------------------------------------------

def test_phase1_is_the_case_of_record(phase1):
    """The figures tests/test_goal_run.py pins for the record (amendment 4),
    re-derived through the declaration and phase_run."""
    r = phase1.report
    assert phase1.derived is None
    assert phase1.bootstrap.buildings == P1.BOOTSTRAP
    assert r.horizon_min == 50.0
    assert r.floor.machines == ((ASM, 3), (CON, 7), (SML, 2))
    assert r.paced.machines == ((ASM, 3), (CON, 18), (SML, 6))
    assert r.paced.realization.total_power_mw == pytest.approx(107.8094, abs=5e-5)
    whole = {i: b.bootstrap_units + b.remainder_units for i, b in r.floor.stock.bills.items()}
    assert whole == pytest.approx({
        "Desc_Cable_C": 656.0, "Desc_Cement_C": 720.0, "Desc_CopperSheet_C": 40.0,
        "Desc_IronPlateReinforced_C": 188.0, "Desc_IronPlate_C": 1120.0,
        "Desc_IronRod_C": 710.0, "Desc_IronScrew_C": 1000.0, "Desc_Rotor_C": 122.0,
        "Desc_Wire_C": 516.0,
    })


def test_a_declaration_with_both_bootstrap_shapes_is_refused():
    both = type("Decl", (), dict(vars(P1)))
    both.POWER_STEP = P2.POWER_STEP
    with pytest.raises(phase_run.PhaseRunError, match="either a declared bootstrap"):
        phase_run.run(both)


def test_shared_items_share_bus_ids_across_phases():
    """D6 G3 matches standing by bus_id; a renamed bus would silently net nothing."""
    one = {b.item_id: b.bus_id for b in P1.BUSES}
    two = {b.item_id: b.bus_id for b in P2.BUSES}
    shared = set(one) & set(two)
    assert shared == set(one), "every phase 1 item is carried in phase 2"
    assert {i: one[i] for i in shared} == {i: two[i] for i in shared}


# --------------------------------------------------------------------------
# Provenance (G1): required, and printed
# --------------------------------------------------------------------------

def test_a_standing_list_cannot_be_built_without_provenance():
    with pytest.raises(ValueError, match="provenance"):
        stock.StandingLanes(lanes=(), infrastructure=(), source=None)


@pytest.mark.parametrize("kwargs, match", [
    (dict(kind=stock.StandingProvenance.DECLARED), "names the file"),
    (dict(kind=stock.StandingProvenance.SAVED_PLAN, phase=1, anchor_rate_per_min=1.0),
     "names the file"),
    (dict(kind=stock.StandingProvenance.SAVED_PLAN, path="x.toml"), "phase and rate"),
    (dict(kind=stock.StandingProvenance.PLACEHOLDER, phase=1), "phase and rate"),
    (dict(kind=stock.StandingProvenance.PLACEHOLDER, phase=1, anchor_rate_per_min=1.0,
          path="x.toml"), "nothing was saved"),
    (dict(kind="placeholder", phase=1, anchor_rate_per_min=1.0), "StandingProvenance"),
])
def test_a_source_states_what_its_kind_requires(kwargs, match):
    with pytest.raises(ValueError, match=match):
        stock.StandingSource(**kwargs)


def test_no_standing_field_is_a_bool():
    import typing
    for cls in (stock.StandingSource, stock.StandingLanes, stock.LaneNet, stock.NetLanes,
                stock.NetInfrastructure, stock.SurplusOutput, stock.BootstrapPayment,
                rate_sheet.LaneRow, rate_sheet.StandingTable):
        hints = typing.get_type_hints(cls, vars(stock) | vars(rate_sheet))
        assert bool not in hints.values(), cls


@pytest.mark.parametrize("source, words", [
    (None, "none declared"),
    (DECLARED_SRC, "DECLARED  file standing.toml"),
    (stock.StandingSource(stock.StandingProvenance.SAVED_PLAN, 1, 1.0, "p.toml"),
     "SAVED_PLAN  have-after of phase 1 at 1.000/min"),
    (stock.StandingSource(stock.StandingProvenance.PLACEHOLDER, 1, 1.0),
     "placeholder, revise me"),
])
def test_the_header_prints_every_kind(source, words):
    table = rate_sheet.standing(None, source=source)
    assert words in rate_sheet.render_standing(table)


def test_the_cli_prints_the_placeholder_line(capsys, tmp_path):
    phase_run.main(["--phase", "2", "--state-dir", str(tmp_path)])
    assert "PLACEHOLDER  a run of phase 1 at 1.000/min" in capsys.readouterr().out
    assert not list(tmp_path.iterdir()), "a placeholder saves nothing"


# --------------------------------------------------------------------------
# net_lanes (G3): per lane, conserved, exact keys only
# --------------------------------------------------------------------------

def _lanes(*entries, infra=()):
    return stock.StandingLanes(lanes=tuple(entries), infrastructure=tuple(infra),
                               source=DECLARED_SRC)


def test_net_lanes_two_sign_tests_and_conservation():
    needed = ((("screws", "Recipe_Screw_C", CON), 3), (("iron_plate", "Recipe_IronPlate_C", CON), 2))
    net = stock.net_lanes(needed, _lanes(
        (("screws", "Recipe_Screw_C", CON), 5), (("iron_plate", "Recipe_IronPlate_C", CON), 1)))
    assert [(r.to_build, r.surplus) for r in net.rows] == [(0, 2), (1, 0)]
    for r in net.rows + net.not_in_run:
        assert r.to_build + r.standing == r.needed + r.surplus
    assert net.owed_machines() == ((CON, 1),)


def test_a_cast_screw_lane_does_not_meet_a_standard_screw_lane():
    """D6 G3: the recipe is part of the key. Listed, nets nothing."""
    needed = ((("screws", "Recipe_Screw_C", CON), 3),)
    net = stock.net_lanes(needed, _lanes((("screws", CAST_SCREW, CON), 4)))
    (row,) = net.rows
    assert (row.standing, row.to_build) == (0, 3)
    (other,) = net.not_in_run
    assert (other.key, other.needed, other.surplus) == (("screws", CAST_SCREW, CON), 0, 4)
    table = rate_sheet.standing(net, source=DECLARED_SRC)
    assert "standing, not in this run" in rate_sheet.render_standing(table)


def test_nothing_moves_across_lanes():
    """A surplus constructor on screws does not build iron plate."""
    needed = ((("screws", "Recipe_Screw_C", CON), 1), (("iron_plate", "Recipe_IronPlate_C", CON), 2))
    net = stock.net_lanes(needed, _lanes((("screws", "Recipe_Screw_C", CON), 3)))
    assert net.owed_machines() == ((CON, 2),)


@pytest.mark.parametrize("lanes, match", [
    ((((("a", "r", CON), 1)), (("a", "r", CON), 2)), "twice"),
    (((("a", "r", CON), -1),), "negative"),
    (((("a", "r"), 1),), "three non-empty strings"),
    (((("a", "r", CON, "belt_3"), 1),), "three non-empty strings"),
])
def test_a_bad_lane_list_is_refused(lanes, match):
    with pytest.raises(ValueError, match=match):
        stock.StandingLanes(lanes=lanes, infrastructure=(), source=DECLARED_SRC)


def test_the_lane_entry_holds_no_layout():
    """D6: bus, recipe, class, count and nothing else."""
    fields = {f.name for f in dataclasses.fields(stock.StandingLanes)}
    assert fields == {"lanes", "infrastructure", "source"}
    assert {f.name for f in dataclasses.fields(stock.LaneNet)} == {
        "key", "needed", "standing", "to_build", "surplus"}


# --------------------------------------------------------------------------
# bill_for: the pairing rules, and G2' on buildings
# --------------------------------------------------------------------------

def test_bill_for_refuses_half_a_pair_and_two_readings(data):
    c = load_construction(REPO)
    boot = stock.BootstrapSet(tier=4, buildings=((CON, 1),))
    lanes = ((("screws", "Recipe_Screw_C", CON), 2),)
    base = dict(bootstrap=boot, machines=((CON, 2),))
    with pytest.raises(stock.StockPassError, match="together or not at all"):
        stock.bill_for(data, c, lanes=lanes, **base)
    with pytest.raises(stock.StockPassError, match="two readings"):
        stock.bill_for(data, c, lanes=lanes, standing_lanes=_lanes(),
                       standing=stock.StandingBuildings(()), **base)
    with pytest.raises(stock.StockPassError, match="do not regroup"):
        stock.bill_for(data, c, bootstrap=boot, machines=((CON, 3),),
                       lanes=lanes, standing_lanes=_lanes())


def test_surplus_machines_never_pay_bootstrap_buildings(data):
    """G2': five standing constructors against two needed leave three
    surplus, and the bootstrap's constructor is still costed whole."""
    c = load_construction(REPO)
    boot = stock.BootstrapSet(tier=4, buildings=((CON, 1),))
    lanes = ((("screws", "Recipe_Screw_C", CON), 2),)
    got = stock.bill_for(data, c, bootstrap=boot, machines=((CON, 2),), lanes=lanes,
                         standing_lanes=_lanes((("screws", "Recipe_Screw_C", CON), 5)))
    whole = stock.cost_of(c, boot.buildings)
    assert {i: b.bootstrap_units for i, b in got.bills.items()} == pytest.approx(whole)
    assert all(b.remainder_units == 0.0 for b in got.bills.values())
    assert got.lane_net.rows[0].surplus == 3


# --------------------------------------------------------------------------
# Surplus output (O1' (a)) pays the bootstrap bill, and only that half
# --------------------------------------------------------------------------

def test_surplus_output_is_machines_times_nameplate_times_t(data):
    net = stock.net_lanes(((("iron_plate", "Recipe_IronPlate_C", CON), 1),),
                          _lanes((("iron_plate", "Recipe_IronPlate_C", CON), 3)))
    out = stock.surplus_output(data, net, 50.0)
    (rate,) = [r for i, r in data.recipes["Recipe_IronPlate_C"].outputs]
    assert out.units == pytest.approx({"Desc_IronPlate_C": 2 * rate * 50.0})
    assert out.source is DECLARED_SRC
    assert "UPPER BOUND" in out.basis


def test_pay_bootstrap_conserves_and_leaves_the_remainder(phase2):
    pay = phase2.report.bootstrap_payment
    floor = phase2.report.floor.stock.bills
    for item_id, bill in floor.items():
        after = pay.bills[item_id]
        assert after.remainder_units == bill.remainder_units
        assert after.bootstrap_units + pay.paid[item_id] == pytest.approx(bill.bootstrap_units)
        assert after.basis is bill.basis and after.terms == bill.terms
    for item_id, units in pay.surplus.units.items():
        assert pay.paid.get(item_id, 0.0) + pay.left.get(item_id, 0.0) == pytest.approx(units)


def test_pay_bootstrap_refuses_a_plain_inventory(phase2):
    with pytest.raises(stock.StockPassError, match="SurplusOutput"):
        stock.pay_bootstrap(phase2.report.floor.stock.bills, stock.DeclaredOnHand(()))


def test_the_netting_functions_rank_and_round_nothing():
    for fn in (stock.net_lanes, stock.net_infrastructure, stock.surplus_output,
               stock.pay_bootstrap, stock.NetLanes.owed_machines, stock.NetLanes.have_after):
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        names = {n.func.id for n in ast.walk(tree)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert {"min", "max", "sorted", "round", "abs"}.isdisjoint(names), fn.__name__


# --------------------------------------------------------------------------
# O4: infrastructure nets the declared step only
# --------------------------------------------------------------------------

def test_infrastructure_nets_the_power_step_and_conserves():
    step = ((MINER, 2), (COAL_GEN, 4), (WATER, 2))
    net = stock.net_infrastructure(step, _lanes(infra=((COAL_GEN, 5), (MINER, 1), (SML, 2))))
    assert net.owed == {MINER: 1, COAL_GEN: 0, WATER: 2}
    assert net.surplus == {COAL_GEN: 1, SML: 2}
    held = {MINER: 1, COAL_GEN: 5, SML: 2}
    for pc in set(net.owed) | set(net.surplus):
        assert net.owed.get(pc, 0) + held.get(pc, 0) == dict(step).get(pc, 0) + net.surplus.get(pc, 0)


def test_phase2_on_the_placeholder_nets_the_coal_step_not_the_a19_minimum(phase2):
    """Phase 1 bootstraps the Mk1 coal step; phase 2's POWER_STEP is the same
    step, and meets it whole. The A19 miners (iron, coal) are still owed."""
    assert phase2.infrastructure.owed == {MINER: 0, COAL_GEN: 0, WATER: 0}
    assert phase2.bootstrap == phase2.derived.bootstrap
    assert dict(phase2.bootstrap.buildings)[MINER] == 2


# --------------------------------------------------------------------------
# Phase 2 on the placeholder phase 1: figures
# --------------------------------------------------------------------------

def test_phase2_on_the_placeholder_figures(phase2):
    """Measured in the container 2026-09-24. The floor is unchanged by
    standing (D4, D6): only what is owed moves."""
    r = phase2.report
    assert phase2.standing.source.kind is stock.StandingProvenance.PLACEHOLDER
    assert r.floor.machines == ((ASM, 8), (CON, 11), (FDY, 1), (SML, 3))
    assert r.paced.machines == ((ASM, 8), (CON, 12), (FDY, 1), (SML, 4))
    assert r.paced.realization.total_power_mw == pytest.approx(66.7418, abs=5e-5)
    assert r.paced.stock.lane_net.owed_machines() == ((ASM, 5), (CON, 2), (FDY, 1))
    assert {i: u for i, u in r.bootstrap_payment.paid.items() if u} == {"Desc_IronPlate_C": 20.0}


def test_phase2_lanes_conserve(phase2):
    for r in phase2.report.paced.stock.lane_net.rows:
        assert r.to_build + r.standing == r.needed + r.surplus


# --------------------------------------------------------------------------
# Resolution order and the saved plan
# --------------------------------------------------------------------------

def test_phase1_resolves_to_nothing_standing(tmp_path):
    assert phase_run.resolve_standing(1, state_dir=tmp_path) is None


def test_a_standing_file_is_declared_and_wins(tmp_path, phase1):
    path = phase_run.write_plan(phase1, tmp_path / "mine.toml")
    phase_run.write_plan(phase1, tmp_path / "phase1.toml")
    got = phase_run.resolve_standing(2, standing_path=path, state_dir=tmp_path)
    assert got.source.kind is stock.StandingProvenance.DECLARED
    assert got.source.path == str(path)


def test_a_saved_plan_reads_back_as_the_placeholder_lists(tmp_path, phase1, placeholder):
    """Save phase 1 at 1/min, read it as phase 2's SAVED_PLAN: the lists are
    the placeholder's, only the provenance differs."""
    _, made = placeholder
    phase_run.write_plan(phase1, tmp_path / "phase1.toml")
    saved = phase_run.resolve_standing(2, state_dir=tmp_path)
    assert saved.source.kind is stock.StandingProvenance.SAVED_PLAN
    assert (saved.source.phase, saved.source.anchor_rate_per_min) == (1, 1.0)
    assert (saved.lanes, saved.infrastructure) == (made.lanes, made.infrastructure)


def test_have_after_is_standing_plus_to_build(phase2):
    lanes, infra = phase_run.have_after(phase2)
    rows = phase2.report.paced.stock.lane_net
    assert lanes == tuple((r.key, r.standing + r.to_build) for r in rows.rows + rows.not_in_run)
    assert dict(infra) == {MINER: 2, COAL_GEN: 4, WATER: 2}
