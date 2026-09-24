"""Phase 2 (tiers 3-4) in one bucket, per crossover A18. Figures pinned.

AMENDED 2026-09-24 (crossover A22): the declaration below now lives in
tools/phases/phase2.py and the run in tools/phase_run.py; this file pins
their figures. The description stands.

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
                AMENDED (A20, Greg 2026-09-24 12:30): plus the DECLARED Mk1
                coal step (2 miners, 4 coal generators, 2 water extractors)
                by addition per class -> 4 miners. The power ledger is
                reported over the paced pass
    standing    none declared; on hand none declared

Measured in the agent container 2026-09-24, 1x scenario, LpBackend MEAN.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

from progression import lag, power

REPO = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("phase_run", REPO / "tools" / "phase_run.py")
phase_run = sys.modules.get("phase_run") or importlib.util.module_from_spec(_spec)
if "phase_run" not in sys.modules:
    sys.modules["phase_run"] = phase_run
    _spec.loader.exec_module(phase_run)
rate_sheet = phase_run.rate_sheet

#: The declaration (tools/phases/phase2.py) — moved out of this file 2026-09-24
DECL = phase_run.declaration(2)
I = DECL.I
MINER, COAL_GEN, WATER = "Build_MinerMk1_C", "Build_GeneratorCoal_C", "Build_WaterPump_C"


@pytest.fixture(scope="module")
def phase2():
    pr = phase_run.run(DECL)
    return pr.rates, pr.derived, pr.bootstrap, pr.report


def _ore(report, bus_id, ore):
    return sum(i.rate_per_min for b in report.realization.buses if b.bus_id == bus_id
               for lane in b.lanes for i in lane.inputs if i.item_id == ore)


ASM, CON_, FDY, SML = ("Build_AssemblerMk1_C", "Build_ConstructorMk1_C",
                       "Build_FoundryMk1_C", "Build_SmelterMk1_C")


def test_phase2_floor_is_23_machines(phase2):
    _, _, _, r = phase2
    assert r.horizon_min == 1000.0
    assert r.floor.machines == ((ASM, 8), (CON_, 11), (FDY, 1), (SML, 3))
    assert r.floor.realization.total_power_mw == pytest.approx(52.33, abs=5e-3)


def test_phase2_paced_is_27_machines(phase2):
    """A20: 25 -> 27 with the coal step billed (screws 2 -> 3, plate 1 -> 2).
    Power FALLS 0.04 MW: the two split lines run at lower clocks, and power at
    clock is superlinear, so they save more than the other lines add."""
    _, _, _, r = phase2
    assert r.paced.machines == ((ASM, 8), (CON_, 14), (FDY, 1), (SML, 4))
    assert r.paced.realization.total_power_mw == pytest.approx(67.3149, abs=5e-5)
    assert _ore(r.paced, "iron_ingot", I["ORE"]) == pytest.approx(65.793)
    assert _ore(r.paced, "steel_ingot", I["ORE"]) == pytest.approx(28.55)
    assert _ore(r.paced, "steel_ingot", I["COAL"]) == pytest.approx(28.55)
    assert _ore(r.paced, "copper_ingot", I["CUO"]) == pytest.approx(7.276)
    assert _ore(r.paced, "concrete", I["STONE"]) == pytest.approx(8.04)


def test_phase2_goals_run_at_their_ratio_rates(phase2):
    _, _, _, r = phase2
    assert [g.rate_per_min for g in r.paced.goals] == pytest.approx([1.0, 1.0, 0.1])


def test_phase2_floor_bill(phase2):
    _, _, _, r = phase2
    whole = {i: b.total_units for i, b in r.floor.stock.bills.items()}
    assert whole == pytest.approx({
        I["CABLE"]: 1534.0, I["CON"]: 2080.0, I["SHEET"]: 540.0, I["RIP"]: 864.0,
        I["PLT"]: 440.0, I["ROD"]: 615.0, I["MF"]: 495.0, I["ROT"]: 624.0,
        I["PIPE"]: 600.0, I["EIB"]: 100.0, I["BEAM"]: 500.0, I["WIRE"]: 4524.0,
    })
    assert r.floor.stock.unresolved == (("Build_MinerMk1_C", "BP_ItemDescriptorPortableMiner_C"),)


def test_phase2_eib_line_paces_to_its_bill(phase2):
    _, _, _, r = phase2
    assert r.storage_rates[I["EIB"]] == pytest.approx(0.1)
    (eib,) = [b for b in r.paced.realization.buses if b.bus_id == "encased_industrial_beam"]
    assert not eib.stores_nothing


def test_phase2_lag_table_beside_the_run(phase2):
    rates, _, _, _ = phase2
    t = lag.lag_table(rates, (0.25,))
    assert [(row.item_id, row.late_by_min, row.catch_up_rate_per_min) for row in t.rows] == (
        pytest.approx([(I["VF"], 250.0, 4 / 3), (I["AW"], 250.0, 0.4 / 3)]))


def test_phase2_bootstrap_is_the_a19_minimum(phase2):
    _, derived, _, _ = phase2
    assert derived.bootstrap.buildings == (
        ("Build_MinerMk1_C", 2), (FDY, 1), (ASM, 3), (CON_, 2))
    assert [r for r, _ in derived.new_recipes] == [
        "Recipe_IngotSteel_C", "Recipe_SpaceElevatorPart_2_C", "Recipe_SpaceElevatorPart_3_C",
        "Recipe_Stator_C", "Recipe_SteelBeam_C", "Recipe_SteelPipe_C"]
    assert derived.extractors == ((I["ORE"], "Build_MinerMk1_C"), (I["COAL"], "Build_MinerMk1_C"))



def test_phase2_bootstrap_adds_the_coal_step(phase2):
    """P1 / A20: derived minimum + declared power step, by addition per class
    (`stock.add_bootstrap`; the declaration's POWER_STEP)."""
    _, _, bootstrap, _ = phase2
    assert bootstrap.buildings == (
        (MINER, 4), (FDY, 1), (ASM, 3), (CON_, 2), (COAL_GEN, 4), (WATER, 2))


def test_phase2_ledger_plans_the_coal_step(phase2):
    """Nothing standing: base 0, the step is 300 MW PLANNED. Known demand is
    the paced lines plus the bootstrap's extractors at nameplate: all 4 miners
    (2 derived for steel, 2 for coal) x 5 + 2 water extractors x 20 = 60."""
    _, _, bootstrap, r = phase2
    led = power.ledger(
        power.load_power_tables(REPO), production_mw=r.paced.realization.total_power_mw,
        bootstrap=bootstrap, standing_net=r.paced.stock.standing_net, generators=(),
    )
    assert (led.base_mw, led.planned_mw) == (0.0, 300.0)
    assert [(p.producer_class, p.count) for p in led.planned] == [(COAL_GEN, 4)]
    assert led.known_demand_mw == pytest.approx(127.3149, abs=5e-5)
    assert led.base_and_planned_less_demand_mw == pytest.approx(172.6851, abs=5e-5)
    assert led.ore_extraction_mw is None


# --------------------------------------------------------------------------
# The per-phase rate sheet over this run (tools/rate_sheet.py). A view only
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sheet2(phase2):
    rates, derived, bootstrap, r = phase2
    return phase_run.sheet_of(phase_run.PhaseRun(DECL, rates, derived, bootstrap, r))


def test_rate_sheet_is_the_paced_build_row_for_row(phase2, sheet2):
    _, _, _, r = phase2
    assert [row.bus for row in sheet2.rows] == list(r.paced.realization.buses)
    for row, bus in zip(sheet2.rows, r.paced.realization.buses):
        assert row.bus is bus
    assert sheet2.anchor_rate_per_min == pytest.approx(1.0)
    assert sheet2.total_power_mw == r.paced.realization.total_power_mw


def test_rate_sheet_phase2_figures(sheet2):
    """Measured in the container 2026-09-24 against d309971; A20.3's run."""
    got = {row.bus.bus_id: (row.flow_per_min, row.downstream_per_min,
                            row.storage_per_min, row.other_per_min) for row in sheet2.rows}
    assert got["smart_plating"] == pytest.approx((1.0, 0.0, 0.0, 1.0))
    assert got["versatile_framework"] == pytest.approx((1.0, 0.0, 0.0, 1.0))
    assert got["automated_wiring"] == pytest.approx((0.1, 0.0, 0.0, 0.1))
    assert got["wire"] == pytest.approx((12.392, 7.868, 4.524, 0.0))
    assert got["iron_ingot"] == pytest.approx((65.793, 65.793, 0.0, 0.0))
    assert got["concrete"] == pytest.approx((2.68, 0.6, 2.08, 0.0))
    for bus_id, (_f, _d, _s, other) in got.items():
        if bus_id not in ("smart_plating", "versatile_framework", "automated_wiring"):
            assert other == pytest.approx(0.0, abs=1e-9), bus_id


def test_rate_sheet_raw_inputs_match_the_ore_pins(phase2, sheet2):
    _, _, _, r = phase2
    raw = {row.bus.bus_id: dict(row.raw) for row in sheet2.rows}
    assert raw["steel_ingot"] == pytest.approx({I["ORE"]: 28.55, I["COAL"]: 28.55})
    assert raw["iron_ingot"] == pytest.approx({I["ORE"]: _ore(r.paced, "iron_ingot", I["ORE"])})
    assert raw["rip"] == {}


def test_rate_sheet_refuses_an_anchor_the_run_lacks(phase2):
    _, _, _, r = phase2
    with pytest.raises(rate_sheet.RateSheetError):
        rate_sheet.sheet(r.paced.realization, r.paced.goals, phase="x",
                         anchor_goal_id="no such goal", horizon_min=r.horizon_min)


def test_rate_sheet_renders_display_names(phase2, sheet2):
    """Names come from items.csv / producers when data is passed; no figure moves."""
    _, _, _, r = phase2
    text = rate_sheet.render(sheet2, r.paced.data)
    assert "at Smart Plating = 1.000/min" in text
    for name in ("Versatile Framework", "Automated Wiring", "Concrete", "Assembler", "Iron Ore"):
        assert name in text, name
    assert "Desc_" not in text and "Build_" not in text
    assert rate_sheet.render(sheet2).count("\n") == text.count("\n")


def test_phase_run_at_another_anchor_rate_is_another_run():
    """A21 in practice: 2 SP/min is a run, not the 1/min sheet doubled."""
    pr = phase_run.run(DECL, anchor_rate_per_min=2.0)
    assert pr.report.horizon_min == 500.0
    assert [g.rate_per_min for g in pr.report.paced.goals] == pytest.approx([2.0, 2.0, 0.2])
    (ingot,) = [b for b in pr.report.paced.realization.buses if b.bus_id == "iron_ingot"]
    flow = sum(l.output_rate_per_min for l in ingot.lanes)
    assert flow == pytest.approx(132.445)
    assert flow > 2 * 65.793


def test_phase_run_cli_prints_the_sheet(capsys):
    assert phase_run.main(["--phase", "2"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("RATE SHEET  phase 2 (tiers 3-4)")
    assert "at Smart Plating = 1.000/min" in out


def test_phase_run_refuses_an_undeclared_phase():
    with pytest.raises(phase_run.PhaseRunError):
        phase_run.declaration(99)
