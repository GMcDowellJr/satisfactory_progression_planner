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
from realization import BusDeclaration, RealizationRequest, SourceEdge

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
