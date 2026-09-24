"""The storage-fill view (P7; crossover amendment 15, against A7.3). Sizes nothing.

Figures on A13.5's case (first-50 partition, 1x/1x/1x, tier 2, T = 50,
nothing declared), whose paced rates test_goal_run.py pins: plate 22.5,
screws 20.0, rod 14.4, RIP 1.6, rotor 1.24 /min. The partition is re-declared
here rather than imported: a test module importing another is an ordering
dependency.
"""
from __future__ import annotations

import ast
import dataclasses
import importlib.util
import math
import pathlib
import sys
import typing

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
storage_view = _load("storage_view")
Containers = storage_view.Containers
SOURCE = (REPO / "tools" / "storage_view.py").read_text(encoding="utf-8")

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
ONE_BOX = Containers(storage_view.STORAGE_CONTAINER_SLOTS, 1)


@pytest.fixture(scope="module")
def paced():
    data = load(REPO)
    return goal_run.paced_run(
        data=data,
        backend=LpBackend(power_statistic=PowerStatistic.MEAN),
        solve=SolveRequest(outputs=(OutputTarget(SP, 1.0),),
                           allowed_recipes=at_tier(REPO, TIER).allowed_recipes),
        logistics=load_logistics(REPO),
        realization=RealizationRequest(design_tier=TIER, buses=DECLARED),
        goals=goal_run.goals_for_phases(data, stock.load_project_assembly(REPO, data), (1,)),
        construction=load_construction(REPO),
        declared_stock=goal_run.StockDeclaration(
            bootstrap=stock.BootstrapSet(
                tier=TIER,
                buildings=(("Build_MinerMk1_C", 1), ("Build_GeneratorBiomass_Automated_C", 1)),
            ),
            unlocks=unlocks.schematics_in_tiers(REPO, (TIER,)),
            unlock_costs=unlocks.schematic_costs(REPO),
        ),
        horizon_min=schedule.horizon_from_anchor(50.0, 1.0),
    )


def _row(v, bus_id):
    (r,) = [r for r in v.rows if r.bus.bus_id == bus_id]
    return r


def test_fill_is_rate_times_t_and_equals_the_bill_it_paces(paced):
    v = storage_view.view(paced.paced.realization, paced.horizon_min)
    assert [r.bus.bus_id for r in v.rows] == [b.bus_id for b in paced.paced.realization.buses]
    for item_id, bill in paced.floor.stock.bills.items():
        rows = [r for r in v.rows if r.bus.item_id == item_id]
        for r in rows:
            assert r.fill_units == pytest.approx(bill.bootstrap_units + bill.remainder_units)
    assert _row(v, "screws").fill_units == pytest.approx(1000.0)
    assert _row(v, "iron_plate").fill_units == pytest.approx(1125.0)


def test_capacity_is_slots_times_stack_a73(paced):
    v = storage_view.view(paced.paced.realization, paced.horizon_min,
                          containers={"screws": ONE_BOX, "iron_plate": ONE_BOX})
    screws, plate = _row(v, "screws"), _row(v, "iron_plate")
    assert (screws.stack_size, screws.capacity_units) == (500, 12000.0)
    assert screws.minutes_to_fill == pytest.approx(600.0)
    assert screws.fill_of_capacity == pytest.approx(1000.0 / 12000.0)
    assert (plate.stack_size, plate.capacity_units) == (200, 4800.0)
    assert plate.minutes_to_fill == pytest.approx(4800.0 / 22.5)


def test_at_a_phase_span_the_same_rates_overfill_one_container(paced):
    """The standing observation that storage fills quickly, as a number: the
    plate rate over T = 1000 is 22,500 units, 4.69 containers. Reported, not
    refused."""
    v = storage_view.view(paced.paced.realization, 1000.0, containers={"iron_plate": ONE_BOX})
    assert _row(v, "iron_plate").fill_of_capacity == pytest.approx(22500.0 / 4800.0)


def test_a_line_storing_nothing_never_fills(paced):
    v = storage_view.view(paced.paced.realization, paced.horizon_min,
                          containers={"iron_ingot": ONE_BOX})
    ingot = _row(v, "iron_ingot")
    assert ingot.fill_units == 0.0 and math.isinf(ingot.minutes_to_fill)
    assert _row(v, "rip").capacity_units is None


def test_bad_declarations_are_refused(paced):
    with pytest.raises(storage_view.StorageViewError, match="not in the report"):
        storage_view.view(paced.paced.realization, 50.0, containers={"nope": ONE_BOX})
    with pytest.raises(storage_view.StorageViewError, match="positive"):
        storage_view.view(paced.paced.realization, 0.0)
    with pytest.raises(ValueError):
        Containers(24, 0)


# --------------------------------------------------------------------------
# cannot — S1-S3, from the source and by identity
# --------------------------------------------------------------------------

TREE = ast.parse(SOURCE)


def _called() -> set[str]:
    return {
        (n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", ""))
        for n in ast.walk(TREE) if isinstance(n, ast.Call)
    }


def test_s1_calls_no_layer_and_imports_none():
    assert {"realize", "solve", "run", "paced_run", "bill_for", "replace"}.isdisjoint(_called())
    imported = {n.module for n in ast.walk(TREE) if isinstance(n, ast.ImportFrom)}
    for forbidden in ("goal_run", "progression", "production_adapter.lp_backend",
                      "production_adapter.backend", "realization.realize"):
        assert not [m for m in imported if m and m.startswith(forbidden)], forbidden


def test_s2_ranks_and_rounds_nothing():
    assert {"min", "max", "sorted", "sort", "round"}.isdisjoint(_called())


def test_s3_rows_carry_the_reports_buses_and_no_verdict(paced):
    v = storage_view.view(paced.paced.realization, 50.0)
    for row, bus in zip(v.rows, paced.paced.realization.buses):
        assert row.bus is bus
    hints = typing.get_type_hints(storage_view.StorageFill)
    assert bool not in hints.values()
    assert not [f for f in dataclasses.fields(storage_view.StorageFill) if f.name.startswith("is_")]
