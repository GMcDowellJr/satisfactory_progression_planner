"""The per-chain view: figures on the first-50 case, refusals, and the guardrails.

`tools/chain_view.py` regroups a realized build by caller-declared chains. It
sizes nothing, so these tests check that it cannot (V1-V3, from the source and
by identity) and that its regrouping reconciles with the report it read.

The chains are Greg's, 2026-09-23, mapped onto the first-50 partition as read
by this session — the mapping is an inference, recorded as one:

    smelting               iron_ingot
    plate_rip              iron_plate, rip           (ingot is the feed, not a member)
    rod_rotor_screws_rip   iron_rod, rotor, screws, rip
    smart_plating          smart_plating

RIP sits in two chains, so the chain totals over-count the build by one.

Loaded by path, like `test_goal_run.py`, because both modules live at `tools/`
root. The partition and stock declaration are re-declared here rather than
imported from `test_goal_run.py`: a test module importing another is an
ordering dependency.
"""
from __future__ import annotations

import ast
import dataclasses
import importlib.util
import pathlib
import sys

import pytest

from production_adapter import OutputTarget, SolveRequest, load
from production_adapter.gamedata import load_construction, load_logistics
from production_adapter.lp_backend import LpBackend, PowerStatistic
from progression import at_tier, schedule, stock, unlocks
from realization import BusDeclaration, RealizationRequest, SourceEdge

REPO = pathlib.Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


goal_run = sys.modules.get("goal_run") or _load("goal_run")
chain_view = _load("chain_view")
Chain, ChainViewError = chain_view.Chain, chain_view.ChainViewError
CHAIN_VIEW_SOURCE = (REPO / "tools" / "chain_view.py").read_text(encoding="utf-8")

SP, RIP, ROT, SCR, PLT, ROD, ING, ORE = (
    "Desc_SpaceElevatorPart_1_C", "Desc_IronPlateReinforced_C", "Desc_Rotor_C",
    "Desc_IronScrew_C", "Desc_IronPlate_C", "Desc_IronRod_C",
    "Desc_IronIngot_C", "Desc_OreIron_C",
)
TIER = 2

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

CHAINS = (
    Chain("smelting", ("iron_ingot",)),
    Chain("plate_rip", ("iron_plate", "rip")),
    Chain("rod_rotor_screws_rip", ("iron_rod", "rotor", "screws", "rip")),
    Chain("smart_plating", ("smart_plating",)),
)


@pytest.fixture(scope="module")
def data():
    return load(REPO)


@pytest.fixture(scope="module")
def paced(data):
    """A13.5's case: tier-2 bought milestones, T = 50, nothing declared."""
    bought = unlocks.schematics_in_tiers(REPO, (TIER,))
    return goal_run.paced_run(
        data=data,
        backend=LpBackend(power_statistic=PowerStatistic.MEAN),
        solve=SolveRequest(
            outputs=(OutputTarget(SP, 1.0),),
            allowed_recipes=at_tier(REPO, TIER).allowed_recipes,
        ),
        logistics=load_logistics(REPO),
        realization=RealizationRequest(design_tier=TIER, buses=DECLARED),
        goals=goal_run.goals_for_phases(data, stock.load_project_assembly(REPO, data), (1,)),
        construction=load_construction(REPO),
        declared_stock=goal_run.StockDeclaration(
            bootstrap=stock.BootstrapSet(
                tier=TIER,
                buildings=(("Build_MinerMk1_C", 1), ("Build_GeneratorBiomass_Automated_C", 1)),
            ),
            unlocks=bought,
            unlock_costs=unlocks.schematic_costs(REPO),
        ),
        horizon_min=schedule.horizon_from_anchor(50.0, 1.0),
    )


@pytest.fixture(scope="module")
def floor_view(paced):
    return chain_view.view(paced.floor.realization, CHAINS)


@pytest.fixture(scope="module")
def paced_view(paced):
    return chain_view.view(paced.paced.realization, CHAINS)


def _chain(v, chain_id):
    (c,) = [c for c in v.chains if c.chain_id == chain_id]
    return c


def _draw(c, item_id, source):
    (d,) = [d for d in c.boundary if (d.item_id, d.source_bus_id) == (item_id, source)]
    return d.rate_per_min


# --------------------------------------------------------------------------
# figures
# --------------------------------------------------------------------------

def test_chain_machine_totals_floor_and_paced(floor_view, paced_view):
    """The pacing grows the smelting and rod chains most (1 -> 4, 4 -> 9)."""
    got = [(c.chain_id, f.total_machines, c.total_machines)
           for f, c in zip(floor_view.chains, paced_view.chains)]
    assert got == [
        ("smelting", 1, 4),
        ("plate_rip", 2, 3),
        ("rod_rotor_screws_rip", 4, 9),
        ("smart_plating", 1, 1),
    ]


def test_build_total_is_the_reports_and_not_the_chains_sum(paced, floor_view, paced_view):
    """RIP is in two chains, so the chains over-count the build by its machines."""
    for v, run in ((floor_view, paced.floor), (paced_view, paced.paced)):
        assert v.build_machines == sum(n for _, n in run.machines)
        assert v.shared == ("rip",)
        rip = run.realization.buses[[b.bus_id for b in run.realization.buses].index("rip")]
        assert sum(c.total_machines for c in v.chains) == v.build_machines + rip.machines
    assert (floor_view.build_machines, paced_view.build_machines) == (7, 16)


def test_smelting_draws_what_the_ingot_line_makes(floor_view, paced_view):
    """Boundary draw and flow are both lane figures at the lanes' clocks."""
    for v, ore in ((floor_view, 23.25), (paced_view, 109.55)):
        c = _chain(v, "smelting")
        assert _draw(c, ORE, None) == pytest.approx(ore)
        assert chain_view.flow_of(c.buses[0]) == pytest.approx(ore)


def test_a_bus_inside_the_chain_is_not_a_boundary_draw(paced_view):
    """plate_rip holds iron_plate, so RIP's plate input is internal; its screws
    come from the rod chain and are drawn across the boundary."""
    c = _chain(paced_view, "plate_rip")
    keys = [(d.item_id, d.source_bus_id) for d in c.boundary]
    assert (PLT, "iron_plate") not in keys
    assert keys == [(ING, "iron_ingot"), (SCR, "screws")]
    assert _draw(c, SCR, "screws") == pytest.approx(31.2)


def test_flow_is_at_the_clock_and_nameplate_is_supply(floor_view):
    """Storage off: the ingot smelter runs at 77.5%, 23.25 of a 30.00 nameplate."""
    (b,) = _chain(floor_view, "smelting").buses
    assert (chain_view.flow_of(b), b.supply_per_min) == (pytest.approx(23.25), 30.0)


def test_both_renders_name_the_build_total_and_the_shared_bus(data, floor_view, paced_view):
    one = chain_view.render(paced_view, data)
    two = chain_view.render_paced(floor_view, paced_view, data)
    assert "build total 16 machines" in one
    assert "build total 7 | 16 machines" in two
    for text in (one, two):
        assert "shared buses" in text and "rip" in text


# --------------------------------------------------------------------------
# unchained, refusals
# --------------------------------------------------------------------------

def test_a_bus_in_no_chain_is_listed_not_dropped(paced):
    v = chain_view.view(paced.paced.realization, (Chain("smelting", ("iron_ingot",)),))
    assert v.unchained is not None
    assert [b.bus_id for b in v.unchained.buses] == [
        b.bus_id for b in paced.paced.realization.buses if b.bus_id != "iron_ingot"
    ]
    assert v.shared == ()
    assert v.chains[0].total_machines + v.unchained.total_machines == v.build_machines


@pytest.mark.parametrize("chains, says", [
    ((Chain("x", (PLT,)),), "not item"),
    ((Chain("x", ("nope",)),), "does not hold"),
    ((Chain("x", ("rip",)), Chain("x", ("rotor",))), "declared twice"),
    ((Chain("x", ("rip", "rip")),), "a bus twice"),
    ((Chain("x", ()),), "names no bus"),
    ((Chain(chain_view.UNCHAINED, ("rip",)),), "own group name"),
])
def test_refusals(paced, chains, says):
    with pytest.raises(ChainViewError, match=says):
        chain_view.view(paced.paced.realization, chains)


def test_render_paced_refuses_views_of_different_shape(data, paced):
    a = chain_view.view(paced.floor.realization, CHAINS)
    b = chain_view.view(paced.paced.realization, CHAINS[:2])
    with pytest.raises(ChainViewError, match="differ"):
        chain_view.render_paced(a, b, data)


# --------------------------------------------------------------------------
# guardrails — from the source and by identity
# --------------------------------------------------------------------------

def _called_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            names.add(f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None))
    return names


def test_v1_calls_no_layer():
    called = _called_names(ast.parse(CHAIN_VIEW_SOURCE))
    forbidden = {"realize", "solve", "run", "paced_run", "bill_for", "replace",
                 "project_goals", "storage_rates", "rates_of", "net_of"}
    assert not called & forbidden


def test_v1_imports_types_only():
    """No `goal_run`, `progression`, backend or `realize` import."""
    tree = ast.parse(CHAIN_VIEW_SOURCE)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module)
            imported.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    assert not {m for m in imported if m and (
        "goal_run" in m or m.startswith("progression") or "backend" in m
        or m.endswith(".realize") or m.endswith("realize")
    )}


def test_v2_ranks_nothing():
    called = _called_names(ast.parse(CHAIN_VIEW_SOURCE))
    assert not called & {"min", "max", "sorted", "sort"}


def test_v3_view_holds_the_reports_bus_objects(paced, paced_view):
    by_id = {b.bus_id: b for b in paced.paced.realization.buses}
    for c in paced_view.chains:
        for b in c.buses:
            assert b is by_id[b.bus_id]


def test_chain_order_is_the_callers(paced):
    reversed_chains = tuple(reversed(CHAINS))
    v = chain_view.view(paced.paced.realization, reversed_chains)
    assert [c.chain_id for c in v.chains] == [c.chain_id for c in reversed_chains]
    assert [b.bus_id for b in v.chains[1].buses] == list(reversed_chains[1].bus_ids)
