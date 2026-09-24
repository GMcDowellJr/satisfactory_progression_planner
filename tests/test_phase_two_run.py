"""Phase 2 (tiers 3-4) in one bucket, per crossover A18. Figures pinned.

    partition   one bus per item, all storing, plus the build-material lines
                and an Encased Industrial Beam line. Confirmed as-is by Greg,
                2026-09-24
    goals       phase 2 (Construction Dock), anchored on Smart Plating at
                1/min: T = 1000; SP 1.0, VF 1.0, AW 0.1 (A15.1)
    recipes     at_tier(4), standard recipes only
    unlocks     every schematic with tech_tier 3 or 4, billed in this phase
                (A18: timing collapses to "bought inside the phase"). That
                set comes from schematics.csv and includes Schematic_5-3_C
                (Logistics Mk.3, tech_tier 4) and the optional 4-2
    bootstrap   DERIVED by the A19 minimum rule (Greg, 2026-09-24): one
                producer per recipe new this phase, one Miner Mk.1 per raw
                resource those recipes use -> 2 miners (iron, coal), 1
                foundry, 2 constructors (beam, pipe), 3 assemblers (VF,
                stator, AW). Power is outside the rule: no coal step here
    standing    none declared; on hand none declared

Measured in the agent container 2026-09-24, 1x scenario, LpBackend MEAN.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

from production_adapter import OutputTarget, SolveRequest, load
from production_adapter.gamedata import load_construction, load_logistics
from production_adapter.lp_backend import LpBackend, PowerStatistic
from progression import at_tier, lag, schedule, stock, unlocks
from realization import BusDeclaration, RealizationRequest, SourceEdge

REPO = pathlib.Path(__file__).resolve().parents[1]
GOAL_RUN_PATH = REPO / "tools" / "goal_run.py"
_spec = importlib.util.spec_from_file_location("goal_run", GOAL_RUN_PATH)
goal_run = importlib.util.module_from_spec(_spec)
sys.modules["goal_run"] = goal_run
_spec.loader.exec_module(goal_run)

B, S = BusDeclaration, SourceEdge
#: item ids
I = dict(SP="Desc_SpaceElevatorPart_1_C", VF="Desc_SpaceElevatorPart_2_C", AW="Desc_SpaceElevatorPart_3_C",
 MF="Desc_ModularFrame_C", STA="Desc_Stator_C", BEAM="Desc_SteelPlate_C", PIPE="Desc_SteelPipe_C",
 STI="Desc_SteelIngot_C", RIP="Desc_IronPlateReinforced_C", ROT="Desc_Rotor_C", SCR="Desc_IronScrew_C",
 PLT="Desc_IronPlate_C", ROD="Desc_IronRod_C", ING="Desc_IronIngot_C", ORE="Desc_OreIron_C", COAL="Desc_Coal_C",
 CU="Desc_CopperIngot_C", CUO="Desc_OreCopper_C", WIRE="Desc_Wire_C", CABLE="Desc_Cable_C", SHEET="Desc_CopperSheet_C",
 STONE="Desc_Stone_C", CON="Desc_Cement_C", EIB="Desc_SteelPlateReinforced_C")
#: the phase-2 partition (see module docstring)
BUSES = (
 B(bus_id="smart_plating", item_id=I["SP"], sources=(S(I["RIP"],"rip"), S(I["ROT"],"rotor"))),
 B(bus_id="versatile_framework", item_id=I["VF"], sources=(S(I["MF"],"modular_frame"), S(I["BEAM"],"steel_beam"))),
 B(bus_id="automated_wiring", item_id=I["AW"], sources=(S(I["STA"],"stator"), S(I["CABLE"],"cable"))),
 B(bus_id="modular_frame", item_id=I["MF"], sources=(S(I["RIP"],"rip"), S(I["ROD"],"iron_rod"))),
 B(bus_id="stator", item_id=I["STA"], sources=(S(I["PIPE"],"steel_pipe"), S(I["WIRE"],"wire"))),
 B(bus_id="steel_beam", item_id=I["BEAM"], sources=(S(I["STI"],"steel_ingot"),)),
 B(bus_id="steel_pipe", item_id=I["PIPE"], sources=(S(I["STI"],"steel_ingot"),)),
 B(bus_id="steel_ingot", item_id=I["STI"], sources=(S(I["ORE"],None), S(I["COAL"],None))),
 B(bus_id="rip", item_id=I["RIP"], sources=(S(I["PLT"],"iron_plate"), S(I["SCR"],"screws"))),
 B(bus_id="rotor", item_id=I["ROT"], sources=(S(I["ROD"],"iron_rod"), S(I["SCR"],"screws"))),
 B(bus_id="screws", item_id=I["SCR"], sources=(S(I["ROD"],"iron_rod"),)),
 B(bus_id="iron_plate", item_id=I["PLT"], sources=(S(I["ING"],"iron_ingot"),)),
 B(bus_id="iron_rod", item_id=I["ROD"], sources=(S(I["ING"],"iron_ingot"),)),
 B(bus_id="iron_ingot", item_id=I["ING"], sources=(S(I["ORE"],None),)),
 B(bus_id="copper_ingot", item_id=I["CU"], sources=(S(I["CUO"],None),)),
 B(bus_id="wire", item_id=I["WIRE"], sources=(S(I["CU"],"copper_ingot"),)),
 B(bus_id="cable", item_id=I["CABLE"], sources=(S(I["WIRE"],"wire"),)),
 B(bus_id="copper_sheet", item_id=I["SHEET"], recipe_id="Recipe_CopperSheet_C", sources=(S(I["CU"],"copper_ingot"),)),
 B(bus_id="concrete", item_id=I["CON"], recipe_id="Recipe_Concrete_C", sources=(S(I["STONE"],None),)),
 B(bus_id="encased_industrial_beam", item_id=I["EIB"], recipe_id="Recipe_EncasedIndustrialBeam_C",
   sources=(S(I["BEAM"],"steel_beam"), S(I["CON"],"concrete"))),
)



@pytest.fixture(scope="module")
def phase2():
    data = load(REPO)
    pa = stock.load_project_assembly(REPO, data)
    goals = goal_run.goals_for_phases(data, pa, (2,))
    rates = schedule.phase_rates(goals, anchor_goal_id=goals[0][0], anchor_rate_per_min=1.0)
    backend = LpBackend(power_statistic=PowerStatistic.MEAN)
    solve = SolveRequest(
        outputs=tuple(OutputTarget(i, r) for _, i, r in rates.rates),
        allowed_recipes=at_tier(REPO, 4).allowed_recipes,
    )
    derived = stock.derive_bootstrap(
        data, tuple(u.recipe_id for u in backend.solve(solve, data).recipes),
        open_before=at_tier(REPO, 2).recipe_ids,
        extractors_open=unlocks.extractors_open_at_tier(REPO, 2),
        tier=4,
    )
    kw = dict(
        data=data,
        backend=backend,
        solve=solve,
        logistics=load_logistics(REPO),
        realization=RealizationRequest(design_tier=4, buses=BUSES),
        goals=goals,
        construction=load_construction(REPO),
        declared_stock=goal_run.StockDeclaration(
            bootstrap=derived.bootstrap,
            unlocks=unlocks.schematics_in_tiers(REPO, (3, 4)),
            unlock_costs=unlocks.schematic_costs(REPO),
        ),
        horizon_min=rates.horizon_min,
    )
    return rates, derived, goal_run.paced_run(**kw)


def _ore(report, bus_id, ore):
    return sum(i.rate_per_min for b in report.realization.buses if b.bus_id == bus_id
               for lane in b.lanes for i in lane.inputs if i.item_id == ore)


ASM, CON_, FDY, SML = ("Build_AssemblerMk1_C", "Build_ConstructorMk1_C",
                       "Build_FoundryMk1_C", "Build_SmelterMk1_C")


def test_phase2_floor_is_23_machines(phase2):
    _, _, r = phase2
    assert r.horizon_min == 1000.0
    assert r.floor.machines == ((ASM, 8), (CON_, 11), (FDY, 1), (SML, 3))
    assert r.floor.realization.total_power_mw == pytest.approx(52.33, abs=5e-3)


def test_phase2_paced_is_25_machines(phase2):
    _, _, r = phase2
    assert r.paced.machines == ((ASM, 8), (CON_, 12), (FDY, 1), (SML, 4))
    assert r.paced.realization.total_power_mw == pytest.approx(67.3555, abs=5e-5)
    assert _ore(r.paced, "iron_ingot", I["ORE"]) == pytest.approx(63.888)
    assert _ore(r.paced, "steel_ingot", I["ORE"]) == pytest.approx(28.55)
    assert _ore(r.paced, "steel_ingot", I["COAL"]) == pytest.approx(28.55)
    assert _ore(r.paced, "copper_ingot", I["CUO"]) == pytest.approx(7.076)
    assert _ore(r.paced, "concrete", I["STONE"]) == pytest.approx(7.98)


def test_phase2_goals_run_at_their_ratio_rates(phase2):
    _, _, r = phase2
    assert [g.rate_per_min for g in r.paced.goals] == pytest.approx([1.0, 1.0, 0.1])


def test_phase2_floor_bill(phase2):
    _, _, r = phase2
    whole = {i: b.total_units for i, b in r.floor.stock.bills.items()}
    assert whole == pytest.approx({
        I["CABLE"]: 1414.0, I["CON"]: 2060.0, I["SHEET"]: 500.0, I["RIP"]: 764.0,
        I["PLT"]: 420.0, I["ROD"]: 615.0, I["MF"]: 495.0, I["ROT"]: 564.0,
        I["PIPE"]: 600.0, I["EIB"]: 100.0, I["BEAM"]: 500.0, I["WIRE"]: 4524.0,
    })
    assert r.floor.stock.unresolved == (("Build_MinerMk1_C", "BP_ItemDescriptorPortableMiner_C"),)


def test_phase2_eib_line_paces_to_its_bill(phase2):
    _, _, r = phase2
    assert r.storage_rates[I["EIB"]] == pytest.approx(0.1)
    (eib,) = [b for b in r.paced.realization.buses if b.bus_id == "encased_industrial_beam"]
    assert not eib.stores_nothing


def test_phase2_lag_table_beside_the_run(phase2):
    rates, _, _ = phase2
    t = lag.lag_table(rates, (0.25,))
    assert [(row.item_id, row.late_by_min, row.catch_up_rate_per_min) for row in t.rows] == (
        pytest.approx([(I["VF"], 250.0, 4 / 3), (I["AW"], 250.0, 0.4 / 3)]))


def test_phase2_bootstrap_is_the_a19_minimum(phase2):
    _, derived, _ = phase2
    assert derived.bootstrap.buildings == (
        ("Build_MinerMk1_C", 2), (FDY, 1), (ASM, 3), (CON_, 2))
    assert [r for r, _ in derived.new_recipes] == [
        "Recipe_IngotSteel_C", "Recipe_SpaceElevatorPart_2_C", "Recipe_SpaceElevatorPart_3_C",
        "Recipe_Stator_C", "Recipe_SteelBeam_C", "Recipe_SteelPipe_C"]
    assert derived.extractors == ((I["ORE"], "Build_MinerMk1_C"), (I["COAL"], "Build_MinerMk1_C"))

