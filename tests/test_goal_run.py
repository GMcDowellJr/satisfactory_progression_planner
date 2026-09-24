"""The goal run: wiring, the guardrails by inspection, and the figures it re-derives.

`tools/goal_run.py` adds no arithmetic, so these tests check three things and
leave the arithmetic to the layers' own suites:

    carried    every layer's answer reaches the report as the SAME object, each
               layer is called once, and all of them saw one `ReferenceData`
    cannot     the module builds no target, recipe set or partition, ranks
               nothing, and runs no layer in a loop — read from the source,
               because a guardrail left to review is a policy
    figures    the 1 Smart Plating/min case at 1x/1x/1x, storing and with storage
               off. Amendment 12 recorded these as NOT PINNED — they came from a
               scratch driver — and this is the first place they are asserted

Loaded by path, like `test_production_cli.py`, because the module lives at
`tools/` root.
"""
from __future__ import annotations

import ast
import dataclasses
import importlib.util
import math
import pathlib
import sys

import pytest

from production_adapter import OutputTarget, Scenario, SolveRequest, load
from production_adapter.gamedata import load_construction, load_logistics
from production_adapter.lp_backend import LpBackend, PowerStatistic
from progression import at_tier, stock, unlocks
from realization import BusDeclaration, Disposition, RealizationRequest, SourceEdge

REPO = pathlib.Path(__file__).resolve().parents[1]
GOAL_RUN_PATH = REPO / "tools" / "goal_run.py"

_spec = importlib.util.spec_from_file_location("goal_run", GOAL_RUN_PATH)
goal_run = importlib.util.module_from_spec(_spec)
#: Registered before exec: `dataclass` resolves string annotations through
#: `sys.modules[cls.__module__]`, and a module loaded by path is not there yet.
sys.modules["goal_run"] = goal_run
_spec.loader.exec_module(goal_run)

SP, RIP, ROT, SCR, PLT, ROD, ING, ORE = (
    "Desc_SpaceElevatorPart_1_C", "Desc_IronPlateReinforced_C", "Desc_Rotor_C",
    "Desc_IronScrew_C", "Desc_IronPlate_C", "Desc_IronRod_C",
    "Desc_IronIngot_C", "Desc_OreIron_C",
)
ASSEMBLER, CONSTRUCTOR, SMELTER = (
    "Build_AssemblerMk1_C", "Build_ConstructorMk1_C", "Build_SmelterMk1_C",
)
TIER = 2

#: The partition of `first50_run.py`, re-declared after A12: `stores` defaults
#: on, so the storing case declares nothing about storage at all.
DECLARED = (
    BusDeclaration(bus_id="smart_plating", item_id=SP,
                   sources=(SourceEdge(RIP, "rip"), SourceEdge(ROT, "rotor"))),
    BusDeclaration(bus_id="rip", item_id=RIP,
                   sources=(SourceEdge(PLT, "iron_plate"), SourceEdge(SCR, "screws"))),
    BusDeclaration(bus_id="rotor", item_id=ROT,
                   sources=(SourceEdge(ROD, "iron_rod"), SourceEdge(SCR, "screws"))),
    BusDeclaration(bus_id="screws", item_id=SCR, sources=(SourceEdge(ROD, "iron_rod"),)),
    BusDeclaration(bus_id="iron_plate", item_id=PLT, sources=(SourceEdge(ING, "iron_ingot"),)),
    BusDeclaration(bus_id="iron_rod", item_id=ROD, sources=(SourceEdge(ING, "iron_ingot"),)),
    BusDeclaration(bus_id="iron_ingot", item_id=ING, sources=(SourceEdge(ORE, None),)),
)
STORAGE_OFF = tuple(dataclasses.replace(b, stores=False) for b in DECLARED)

#: The bootstrap `first50_run.py` declared: a miner and a biomass burner.
BOOTSTRAP = stock.BootstrapSet(
    tier=TIER,
    buildings=(("Build_MinerMk1_C", 1), ("Build_GeneratorBiomass_Automated_C", 1)),
)


@pytest.fixture(scope="module")
def data():
    """1x recipe, 1x power, 1x Project Assembly: `Scenario()`."""
    return load(REPO)


@pytest.fixture(scope="module")
def project_assembly(data):
    return stock.load_project_assembly(REPO, data)


def _kwargs(data, project_assembly, buses, *, goals=None, backend=None):
    return dict(
        data=data,
        backend=backend or LpBackend(power_statistic=PowerStatistic.MEAN),
        solve=SolveRequest(
            outputs=(OutputTarget(SP, 1.0),),
            allowed_recipes=at_tier(REPO, TIER).allowed_recipes,
        ),
        logistics=load_logistics(REPO),
        realization=RealizationRequest(design_tier=TIER, buses=buses),
        goals=(
            goals if goals is not None
            else goal_run.goals_for_phases(data, project_assembly, (1,))
        ),
        construction=load_construction(REPO),
        declared_stock=goal_run.StockDeclaration(
            bootstrap=BOOTSTRAP,
            unlocks=unlocks.schematics_at_tier(REPO, TIER),
            unlock_costs=unlocks.schematic_costs(REPO),
            project_assembly=project_assembly,
            phases=(1,),
        ),
    )


@pytest.fixture(scope="module")
def storing(data, project_assembly):
    return goal_run.run(**_kwargs(data, project_assembly, DECLARED))


@pytest.fixture(scope="module")
def storage_off(data, project_assembly):
    return goal_run.run(**_kwargs(data, project_assembly, STORAGE_OFF))


def _bus(report, bus_id):
    (bus,) = [b for b in report.realization.buses if b.bus_id == bus_id]
    return bus


def _ore_per_min(report):
    return sum(
        i.rate_per_min
        for lane in _bus(report, "iron_ingot").lanes
        for i in lane.inputs
        if i.item_id == ORE
    )


# --------------------------------------------------------------------------
# figures — A12's "not pinned" list, re-derived here and pinned from this run
# --------------------------------------------------------------------------

def test_storing_the_first_fifty_takes_seventeen_machines_and_120_ore(storing):
    """Every line runs at 100% and draws what it produces (D1, Q2).

    120.0 ore/min is also Greg's in-game figure, which A12 recorded as the
    scratch driver's source of confidence. This run produces it independently.
    """
    assert storing.machines == ((ASSEMBLER, 3), (CONSTRUCTOR, 10), (SMELTER, 4))
    assert sum(n for _, n in storing.machines) == 17
    assert _ore_per_min(storing) == pytest.approx(120.0)


def test_storage_off_takes_seven_machines_and_23_25_ore(storage_off):
    """Every line clocks down to what its consumers need and draws usage."""
    assert storage_off.machines == ((ASSEMBLER, 3), (CONSTRUCTOR, 3), (SMELTER, 1))
    assert sum(n for _, n in storage_off.machines) == 7
    assert _ore_per_min(storage_off) == pytest.approx(23.25)


def test_phase_one_completes_in_25_minutes_storing_and_50_off(storing, storage_off):
    """RATE IS GROSS (project_goals). One Assembler at 100% makes 2/min; clocked
    to the 1/min target it makes 1/min. 50 units at 1x either way."""
    (s,) = storing.goals
    (o,) = storage_off.goals
    assert (s.total_required, s.rate_per_min, s.minutes_to_complete) == (50.0, 2.0, 25.0)
    assert (o.total_required, o.rate_per_min, o.minutes_to_complete) == (50.0, 1.0, 50.0)


# --------------------------------------------------------------------------
# carried — the same objects, each layer once, one ReferenceData
# --------------------------------------------------------------------------

@pytest.fixture
def spied(monkeypatch, data, project_assembly):
    """The run with every layer wrapped to record its arguments and its return."""
    calls: dict[str, list] = {"solve": [], "realize": [], "project_goals": [], "bill_for": []}

    class Backend:
        def __init__(self):
            self._inner = LpBackend(power_statistic=PowerStatistic.MEAN)

        def solve(self, request, d):
            out = self._inner.solve(request, d)
            calls["solve"].append((d, out))
            return out

    def wrap(name, fn, data_of):
        def spy(*args, **kwargs):
            out = fn(*args, **kwargs)
            calls[name].append((data_of(args, kwargs), out))
            return out
        return spy

    monkeypatch.setattr(goal_run, "realize",
                        wrap("realize", goal_run.realize, lambda a, k: a[1]))
    monkeypatch.setattr(goal_run, "project_goals",
                        wrap("project_goals", goal_run.project_goals, lambda a, k: None))
    monkeypatch.setattr(goal_run.stock, "bill_for",
                        wrap("bill_for", stock.bill_for, lambda a, k: a[0]))
    report = goal_run.run(**_kwargs(data, project_assembly, DECLARED, backend=Backend()))
    return report, calls


def test_each_layer_is_called_exactly_once(spied):
    _, calls = spied
    assert {name: len(c) for name, c in calls.items()} == {
        "solve": 1, "realize": 1, "project_goals": 1, "bill_for": 1,
    }


def test_the_report_carries_each_layers_own_object(spied):
    """Identity, not equality: the driver cannot have rebuilt or restated one."""
    report, calls = spied
    assert report.solve is calls["solve"][0][1]
    assert report.realization is calls["realize"][0][1]
    assert report.goals is calls["project_goals"][0][1]
    assert report.stock is calls["bill_for"][0][1]


def test_every_layer_saw_the_one_reference_data(spied, data):
    report, calls = spied
    assert report.data is data
    for name in ("solve", "realize", "bill_for"):
        assert calls[name][0][0] is data, name


def test_the_bill_is_summed_over_the_machines_the_report_names(
    storing, data, project_assembly,
):
    """Remainder = machines named in the report + unlocks + phase 1, and nothing
    else. Re-summed from the three terms rather than re-quoted."""
    expected: dict[str, float] = {}
    for term in (
        stock.cost_of(load_construction(REPO), storing.machines),
        stock.unlock_cost(unlocks.schematics_at_tier(REPO, TIER), unlocks.schematic_costs(REPO)),
        stock.project_assembly_cost(data, project_assembly, (1,)),
    ):
        for item_id, units in term.items():
            expected[item_id] = expected.get(item_id, 0.0) + units
    got = {i: b.remainder_units for i, b in storing.stock.bills.items() if b.remainder_units}
    assert got == pytest.approx({i: u for i, u in expected.items() if i in storing.stock.bills and u})


# --------------------------------------------------------------------------
# goals
# --------------------------------------------------------------------------

def test_a_goal_no_declared_bus_makes_passes_through_as_zero_and_inf(data, project_assembly):
    report = goal_run.run(**_kwargs(
        data, project_assembly, DECLARED, goals=(("vf", "Desc_SpaceElevatorPart_2_C", 1000.0),),
    ))
    (g,) = report.goals
    assert g.rate_per_min == 0.0
    assert math.isinf(g.minutes_to_complete)


def test_goals_keep_caller_order(data, project_assembly):
    handed = (("b", SP, 10.0), ("a", SP, 5.0))
    report = goal_run.run(**_kwargs(data, project_assembly, DECLARED, goals=handed))
    assert [g.goal_id for g in report.goals] == ["b", "a"]


def test_goals_for_phases_scales_by_the_project_assembly_multiplier(project_assembly):
    """The same rule the bill's delivery term uses, so the two cannot disagree."""
    doubled = load(REPO).with_scenario(Scenario(project_assembly_requirement_multiplier=2.0))
    ((_, item, total),) = goal_run.goals_for_phases(doubled, project_assembly, (1,))
    assert (item, total) == (SP, 100.0)
    assert stock.project_assembly_cost(doubled, project_assembly, (1,)) == {SP: total}


def test_goals_for_phases_is_one_goal_per_row_in_table_order(data, project_assembly):
    goals = goal_run.goals_for_phases(data, project_assembly, (2,))
    rows = [r for r in project_assembly if r.phase == 2]
    assert [g[1] for g in goals] == [r.item_id for r in rows]


# --------------------------------------------------------------------------
# cannot — read from the source
# --------------------------------------------------------------------------

TREE = ast.parse(GOAL_RUN_PATH.read_text(encoding="utf-8"))


def _called_names(node) -> list[str]:
    names = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            names.append(f.id if isinstance(f, ast.Name) else getattr(f, "attr", ""))
    return names


def test_the_module_builds_no_target_recipe_set_or_partition():
    """G1. A module that cannot construct these cannot choose them."""
    forbidden = {"SolveRequest", "OutputTarget", "BusDeclaration", "SourceEdge",
                 "RealizationRequest", "AllowedRecipes", "BootstrapSet"}
    assert forbidden.isdisjoint(_called_names(TREE))


def test_nothing_is_ranked():
    """G3. No min, max or sort anywhere in the module."""
    assert {"min", "max", "sorted", "sort"}.isdisjoint(_called_names(TREE))


def test_run_has_no_loop_and_one_call_site_per_layer():
    """G2. The bill is not fed back (O2): no loop can re-run a layer."""
    (fn,) = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "run"]
    loops = (ast.For, ast.While, ast.comprehension, ast.AsyncFor)
    assert not [n for n in ast.walk(fn) if isinstance(n, loops)]
    names = _called_names(fn)
    for layer in ("solve", "realize", "project_goals", "bill_for"):
        assert names.count(layer) == 1, layer


# ==========================================================================
# paced_run — A13 (D2). The floor pass, the rates, the paced pass
# ==========================================================================

import csv  # noqa: E402

from progression import schedule  # noqa: E402

#: P1: the unlocks paced are the ones THIS stage buys, declared by the caller.
#: Here: the milestones the schematics table places at tech tier 2. Filtered in
#: the test, because deciding a stage's set is the caller's and not the run's.
_ROWS = {
    r["schematic_id"]: r
    for r in csv.DictReader(
        (REPO / "planning_data" / "game" / "reference" / "schematics.csv").open(encoding="utf-8")
    )
}
TIER_2_BOUGHT = tuple(
    s for s in unlocks.schematics_at_tier(REPO, TIER) if _ROWS[s]["tech_tier"] == "2"
)


def _paced_kwargs(data, project_assembly, buses=DECLARED, **over):
    kw = _kwargs(data, project_assembly, buses)
    kw["declared_stock"] = goal_run.StockDeclaration(
        bootstrap=BOOTSTRAP,
        unlocks=TIER_2_BOUGHT,
        unlock_costs=unlocks.schematic_costs(REPO),
    )
    kw["horizon_min"] = schedule.horizon_from_anchor(50.0, 1.0)
    kw.update(over)
    return kw


@pytest.fixture(scope="module")
def paced(data, project_assembly):
    return goal_run.paced_run(**_paced_kwargs(data, project_assembly))


def test_the_stage_buys_five_tier_2_milestones():
    """The declared set, pinned so a change in the table shows up here first."""
    assert len(TIER_2_BOUGHT) == 5
    assert {_ROWS[s]["schematic_type"] for s in TIER_2_BOUGHT} == {"EST_Milestone"}


def test_the_floor_pass_is_storage_off(paced, storage_off):
    """Pass 1 is the smallest build that meets usage — the storage-off figures."""
    assert paced.floor.machines == storage_off.machines
    assert _ore_per_min(paced.floor) == pytest.approx(23.25)


def test_the_paced_rates_are_the_floor_bill_over_fifty_minutes(paced):
    """Re-derived from the floor bill here, then pinned."""
    assert paced.horizon_min == 50.0
    for item_id, bill in paced.floor.stock.bills.items():
        assert paced.storage_rates[item_id] == pytest.approx(
            (bill.bootstrap_units + bill.remainder_units) / 50.0)
    assert {i: round(paced.storage_rates[i], 4) for i in (RIP, PLT, ROD, SCR, ROT)} == {
        RIP: 1.6, PLT: 22.5, ROD: 14.4, SCR: 20.0, ROT: 1.24,
    }


def test_the_paced_first_fifty_takes_sixteen_machines_and_109_55_ore(paced):
    """Between storage off (7, 23.25) and running flat out (17, 120.0). The
    first cut of D2's figures, measured in the container on 2026-09-23."""
    assert paced.paced.machines == ((ASSEMBLER, 3), (CONSTRUCTOR, 9), (SMELTER, 4))
    assert _ore_per_min(paced.paced) == pytest.approx(109.55)


def test_every_paced_line_has_at_least_the_floors_machines(paced):
    """The floor argument: pass 2's demand is pass 1's plus a non-negative
    rate, so a bill summed over pass 1 is a floor of pass 2's."""
    floor = {b.bus_id: b.machines for b in paced.floor.realization.buses}
    for b in paced.paced.realization.buses:
        assert b.machines >= floor[b.bus_id], b.bus_id


def test_phase_one_finishes_at_t(paced):
    """The goal line's rate is the solve's target, so the goal completes at the
    horizon it defined. The round trip."""
    (g,) = paced.paced.goals
    assert g.minutes_to_complete == pytest.approx(paced.horizon_min)


def test_lines_with_nothing_to_pace_are_reported(paced):
    """P5. Smart Plating's delivery term is excluded (P1), and no building
    costs Iron Ingot, so both clock to usage and store nothing."""
    empty = {b.bus_id for b in paced.paced.realization.buses if b.stores_nothing}
    assert empty == {"smart_plating", "iron_ingot"}


def test_a_project_assembly_term_is_refused(data, project_assembly):
    kw = _paced_kwargs(data, project_assembly)
    kw["declared_stock"] = dataclasses.replace(
        kw["declared_stock"], project_assembly=project_assembly, phases=(1,))
    with pytest.raises(goal_run.PacedRunError, match="counts it twice"):
        goal_run.paced_run(**kw)


def test_two_storing_buses_of_one_item_are_refused(data, project_assembly):
    doubled = DECLARED + (dataclasses.replace(DECLARED[3], bus_id="screws_2"),)
    with pytest.raises(goal_run.PacedRunError, match="which one stores"):
        goal_run.paced_run(**_paced_kwargs(data, project_assembly, buses=doubled))


def test_a_line_declared_storage_off_is_left_alone(data, project_assembly):
    """Only storing lines are paced; the caller's storage-off lines stay off."""
    mixed = tuple(
        dataclasses.replace(b, stores=False) if b.bus_id == "iron_plate" else b
        for b in DECLARED
    )
    report = goal_run.paced_run(**_paced_kwargs(data, project_assembly, buses=mixed))
    (plate,) = [b for b in report.paced.realization.buses if b.bus_id == "iron_plate"]
    assert plate.residual.disposition is Disposition.BACK_UP
    assert plate.storage_per_min == 0.0


def test_paced_run_calls_run_twice_and_never_in_a_loop():
    """Pass 1 and pass 2, no third. The comprehensions in it build
    declarations; none of them contains a `run` call."""
    (fn,) = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "paced_run"]
    assert _called_names(fn).count("run") == 2
    loops = (ast.For, ast.While, ast.comprehension, ast.AsyncFor,
             ast.ListComp, ast.GeneratorExp, ast.SetComp, ast.DictComp)
    for node in ast.walk(fn):
        if isinstance(node, loops):
            assert "run" not in _called_names(node)


# ==========================================================================
# D3 — a declared inventory nets the floor bill; an estimate rides along
# ==========================================================================

#: 500 plates and every rotor the stage owes, held at stage open. Invented
#: for the test, not a reading of Greg's save.
ON_HAND = stock.DeclaredOnHand(((PLT, 500.0), (ROT, 62.0), ("Desc_Wire_C", 40.0)))


@pytest.fixture(scope="module")
def netted(data, project_assembly):
    return goal_run.paced_run(**_paced_kwargs(data, project_assembly, on_hand=ON_HAND))


def test_with_nothing_declared_nothing_nets(paced):
    """P8: the default reproduces A13.5, and the report says nothing netted."""
    assert paced.net is None
    assert paced.carry_estimate is None


def test_the_helper_names_the_set_the_test_filtered_by_hand():
    """P6: `schematics_in_tiers` and A13's hand filter agree on tier 2."""
    assert unlocks.schematics_in_tiers(REPO, (TIER,)) == TIER_2_BOUGHT


def test_held_stock_lowers_its_rate_by_units_over_t(paced, netted):
    """500 plates held: 22.5 -> 12.5/min. Rotors fully held: 1.24 -> 0."""
    assert netted.storage_rates[PLT] == pytest.approx(paced.storage_rates[PLT] - 500.0 / 50.0)
    assert netted.storage_rates[PLT] == pytest.approx(12.5)
    assert netted.storage_rates[ROT] == 0.0
    for item in (RIP, ROD, SCR):
        assert netted.storage_rates[item] == pytest.approx(paced.storage_rates[item])


def test_the_net_is_the_floor_bill_less_the_declaration(netted):
    assert netted.net.on_hand is ON_HAND
    assert netted.net.owed == pytest.approx(
        stock.net_of(netted.floor.stock.bills, ON_HAND).owed)
    # Wire is billed (tier-2 unlocks) but no declared bus makes it, so the
    # 40 held net against it and pace nothing: no line reads the rate.
    wire = netted.floor.stock.bills["Desc_Wire_C"]
    assert netted.net.owed["Desc_Wire_C"] == pytest.approx(
        wire.bootstrap_units + wire.remainder_units - 40.0)
    assert netted.net.surplus == {}


def test_a_fully_held_item_stores_nothing(netted):
    """P5 again: the rotor line clocks to usage."""
    (rotor,) = [b for b in netted.paced.realization.buses if b.bus_id == "rotor"]
    assert rotor.stores_nothing


def test_netting_keeps_the_floor_argument(netted):
    floor = {b.bus_id: b.machines for b in netted.floor.realization.buses}
    for b in netted.paced.realization.buses:
        assert b.machines >= floor[b.bus_id], b.bus_id


def test_netting_moves_nothing_upstream_of_the_bill(paced, netted):
    """The floor pass does not see the inventory: same build, same bill."""
    assert netted.floor.machines == paced.floor.machines
    assert netted.floor.stock.bills == paced.floor.stock.bills


def test_netted_first_fifty_takes_thirteen_machines_and_80_6_ore(netted):
    """First figures with a declared inventory (the invented ON_HAND above).
    Measured in the container on 2026-09-23 and pinned: 16 -> 13 machines,
    109.55 -> 80.6 ore/min against the un-netted paced build."""
    assert netted.paced.machines == ((ASSEMBLER, 3), (CONSTRUCTOR, 7), (SMELTER, 3))
    assert _ore_per_min(netted.paced) == pytest.approx(80.6)


def test_a_carry_estimate_is_carried_and_moves_nothing(data, project_assembly, paced):
    """P1: shown beside, never nets. With no declaration, the rates are
    exactly A13's however large the estimate."""
    est = schedule.carry_estimate(paced.storage_rates, 1000.0)
    report = goal_run.paced_run(**_paced_kwargs(data, project_assembly, carry_estimate=est))
    assert report.carry_estimate is est
    assert report.net is None
    assert report.storage_rates == paced.storage_rates
    assert report.paced.machines == paced.paced.machines


def test_paced_run_never_reads_the_estimate():
    """By inspection: the parameter is passed to the report and nowhere else."""
    (fn,) = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == "paced_run"]
    uses = [n for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == "carry_estimate"]
    assert len(uses) == 1
    kw = [n for n in ast.walk(fn) if isinstance(n, ast.keyword) and n.arg == "carry_estimate"]
    assert len(kw) == 1 and isinstance(kw[0].value, ast.Name)


# ==========================================================================
# Amendment 4 — the case of record, and machines standing at stage open (D4)
# ==========================================================================
#
# The case of record (Greg, 2026-09-24, "for now"): the first-50 partition
# plus the build-material lines, each carrying its recipe_id (P30); the Mk1
# coal step as the bootstrap TARGET; on hand = 10% of each item's whole floor
# bill, a declared placeholder until a real reading, built HERE by the caller
# from a first run's floor bill. The A12-A14 fixtures above are kept as they
# were: their figures are still true of their declarations.

CU_ORE, CU, WIRE, CABLE, SHEET, STONE, CONCRETE = (
    "Desc_OreCopper_C", "Desc_CopperIngot_C", "Desc_Wire_C", "Desc_Cable_C",
    "Desc_CopperSheet_C", "Desc_Stone_C", "Desc_Cement_C",
)
BUILD_MATERIAL = (
    BusDeclaration(bus_id="copper_ingot", item_id=CU, recipe_id="Recipe_IngotCopper_C",
                   sources=(SourceEdge(CU_ORE, None),)),
    BusDeclaration(bus_id="wire", item_id=WIRE, recipe_id="Recipe_Wire_C",
                   sources=(SourceEdge(CU, "copper_ingot"),)),
    BusDeclaration(bus_id="cable", item_id=CABLE, recipe_id="Recipe_Cable_C",
                   sources=(SourceEdge(WIRE, "wire"),)),
    BusDeclaration(bus_id="copper_sheet", item_id=SHEET, recipe_id="Recipe_CopperSheet_C",
                   sources=(SourceEdge(CU, "copper_ingot"),)),
    BusDeclaration(bus_id="concrete", item_id=CONCRETE, recipe_id="Recipe_Concrete_C",
                   sources=(SourceEdge(STONE, None),)),
)
RECORD = DECLARED + BUILD_MATERIAL
MINER, COAL_GEN, WATER = "Build_MinerMk1_C", "Build_GeneratorCoal_C", "Build_WaterPump_C"
MK1_COAL_STEP = stock.BootstrapSet(tier=TIER, buildings=((MINER, 2), (COAL_GEN, 4), (WATER, 2)))


def _record_kwargs(data, project_assembly, *, standing=None, **over):
    kw = _paced_kwargs(data, project_assembly, buses=RECORD, **over)
    kw["declared_stock"] = goal_run.StockDeclaration(
        bootstrap=MK1_COAL_STEP,
        unlocks=unlocks.schematics_in_tiers(REPO, (TIER,)),
        unlock_costs=unlocks.schematic_costs(REPO),
        standing=standing,
    )
    return kw


def _ten_percent(report):
    """The placeholder: 10% of each billed item's whole floor bill."""
    return stock.DeclaredOnHand(tuple(
        (i, 0.1 * (b.bootstrap_units + b.remainder_units))
        for i, b in report.floor.stock.bills.items()
    ))


def _ore(report, bus_id, ore):
    return sum(i.rate_per_min for lane in _bus(report, bus_id).lanes
               for i in lane.inputs if i.item_id == ore)


@pytest.fixture(scope="module")
def record(data, project_assembly):
    return goal_run.paced_run(**_record_kwargs(data, project_assembly))


@pytest.fixture(scope="module")
def record_ten(data, project_assembly, record):
    return goal_run.paced_run(**_record_kwargs(
        data, project_assembly, on_hand=_ten_percent(record)))


#: The Mk1 coal step already built at stage open.
COAL_STANDING = stock.StandingBuildings(MK1_COAL_STEP.buildings)


@pytest.fixture(scope="module")
def record_coal_standing(data, project_assembly):
    return goal_run.paced_run(**_record_kwargs(
        data, project_assembly, standing=COAL_STANDING))


def test_record_floor_is_twelve_machines_and_its_whole_bill(record):
    """Measured in the container 2026-09-24 (08:35 scratch driver), re-derived
    by this run and pinned."""
    assert record.floor.machines == ((ASSEMBLER, 3), (CONSTRUCTOR, 7), (SMELTER, 2))
    whole = {i: b.bootstrap_units + b.remainder_units
             for i, b in record.floor.stock.bills.items()}
    assert whole == pytest.approx({
        CABLE: 656.0, CONCRETE: 720.0, SHEET: 40.0, RIP: 188.0, PLT: 1120.0,
        ROD: 710.0, SCR: 1000.0, ROT: 122.0, WIRE: 516.0,
    })


def test_record_paced_is_27_machines(record):
    assert record.paced.machines == ((ASSEMBLER, 3), (CONSTRUCTOR, 18), (SMELTER, 6))
    assert _ore(record.paced, "iron_ingot", ORE) == pytest.approx(148.62)
    assert _ore(record.paced, "copper_ingot", CU_ORE) == pytest.approx(19.88)
    assert _ore(record.paced, "concrete", STONE) == pytest.approx(43.20)
    assert record.paced.realization.total_power_mw == pytest.approx(107.8094, abs=5e-5)


def test_record_with_ten_percent_on_hand_is_26_machines(record, record_ten):
    """The floor pass does not see the inventory; the paced pass does. The
    08:35 handoff printed these to two places (136.08, 17.89); pinned here in
    full."""
    assert record_ten.floor.stock.bills == record.floor.stock.bills
    assert record_ten.paced.machines == ((ASSEMBLER, 3), (CONSTRUCTOR, 17), (SMELTER, 6))
    assert _ore(record_ten.paced, "iron_ingot", ORE) == pytest.approx(136.083)
    assert _ore(record_ten.paced, "copper_ingot", CU_ORE) == pytest.approx(17.892)
    assert _ore(record_ten.paced, "concrete", STONE) == pytest.approx(38.88)
    assert record_ten.paced.realization.total_power_mw == pytest.approx(97.9009, abs=5e-5)


def test_no_standing_declared_nets_no_buildings(record, storing, paced):
    """D4 P4: the default reproduces every figure, and says nothing netted."""
    assert goal_run.StockDeclaration(bootstrap=BOOTSTRAP).standing is None
    for report in (storing, paced.floor, paced.paced, record.floor, record.paced):
        assert report.stock.standing_net is None


def test_a_standing_coal_step_zeroes_the_bootstrap_half(record, record_coal_standing):
    """Both passes are netted; the floor BUILD does not move, only its bill."""
    r = record_coal_standing
    assert r.floor.machines == record.floor.machines
    for report in (r.floor, r.paced):
        net = report.stock.standing_net
        assert net.standing is COAL_STANDING
        assert net.owed_bootstrap == {MINER: 0, COAL_GEN: 0, WATER: 0}
        assert net.surplus == {}
        assert all(b.bootstrap_units == 0.0 for b in report.stock.bills.values())
    assert r.floor.stock.bills[RIP].remainder_units == record.floor.stock.bills[RIP].remainder_units


def test_record_with_the_coal_step_standing_is_22_machines(record_coal_standing):
    """First figures with a standing reading. Measured in the container
    2026-09-24 and pinned: 27 -> 22 machines against the record."""
    r = record_coal_standing
    assert r.paced.machines == ((ASSEMBLER, 3), (CONSTRUCTOR, 14), (SMELTER, 5))
    assert _ore(r.paced, "iron_ingot", ORE) == pytest.approx(110.52)
    assert _ore(r.paced, "copper_ingot", CU_ORE) == pytest.approx(15.88)
    assert _ore(r.paced, "concrete", STONE) == pytest.approx(42.00)
    assert r.paced.realization.total_power_mw == pytest.approx(75.6885, abs=5e-5)


def test_copper_sheet_is_billed_only_by_the_water_extractors(record, record_coal_standing):
    """With the extractors standing no bill names Copper Sheet, so its line
    paces to 0.0 and stores nothing (P5)."""
    assert SHEET in record.floor.stock.bills
    assert SHEET not in record_coal_standing.floor.stock.bills
    assert _bus(record_coal_standing.paced, "copper_sheet").stores_nothing


def test_standing_keeps_the_floor_argument(record_coal_standing):
    floor = {b.bus_id: b.machines for b in record_coal_standing.floor.realization.buses}
    for b in record_coal_standing.paced.realization.buses:
        assert b.machines >= floor[b.bus_id], b.bus_id
