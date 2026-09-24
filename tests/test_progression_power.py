"""The power ledger (D4 P5; goal_run_driver.md amendment 5). Reported, sizes nothing.

Figures are read from the reference tables through `load_power_tables` and
checked against the arithmetic: Coal-Powered Generator 75 MW, 15 coal + 45 m3
water per minute; Biomass Burner 30 MW; Miner Mk.1 5 MW; Water Extractor 20 MW.
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import typing

import pytest

from progression import power, stock

REPO = pathlib.Path(__file__).resolve().parents[1]
MINER, COAL, WATER, BURNER = (
    "Build_MinerMk1_C", "Build_GeneratorCoal_C", "Build_WaterPump_C",
    "Build_GeneratorBiomass_Automated_C",
)
MK1_COAL_STEP = stock.BootstrapSet(tier=2, buildings=((MINER, 2), (COAL, 4), (WATER, 2)))
LINES = (("Build_ConstructorMk1_C", 7),)
BASE, RESERVE = power.Role.BASE, power.Role.RESERVE


@pytest.fixture(scope="module")
def tables():
    return power.load_power_tables(REPO)


def _net(*standing):
    return stock.net_buildings(MK1_COAL_STEP, LINES, stock.StandingBuildings(standing))


def test_the_tables_carry_the_figures_the_ledger_uses(tables):
    assert tables.generators[COAL].nameplate_mw == 75.0
    assert tables.generators[BURNER].nameplate_mw == 30.0
    assert (tables.extractors[MINER], tables.extractors[WATER]) == (5.0, 20.0)
    coal = tables.fuels[(COAL, "Desc_Coal_C")]
    assert (coal.burn_per_min, coal.supplemental, coal.supplemental_per_min) == (
        15.0, "Desc_Water_C", 45.0)
    assert "Build_GeneratorGeoThermal_C" in tables.variable


def test_nothing_standing_plans_the_whole_coal_step(tables):
    """Burners standing and fed as reserve; the coal step not built yet."""
    led = power.ledger(
        tables, production_mw=100.0, bootstrap=MK1_COAL_STEP,
        standing_net=_net((BURNER, 4)),
        generators=(power.GeneratorReading(BURNER, 4, RESERVE, True),),
    )
    assert (led.base_mw, led.reserve_mw, led.planned_mw) == (0.0, 120.0, 300.0)
    assert [(s.producer_class, s.count, s.fed) for s in led.planned] == [(COAL, 4, None)]
    assert led.known_demand_mw == pytest.approx(100.0 + 2 * 5.0 + 2 * 20.0)
    assert led.base_less_demand_mw == pytest.approx(-150.0)
    assert led.base_and_reserve_less_demand_mw == pytest.approx(-30.0)
    assert led.base_and_planned_less_demand_mw == pytest.approx(150.0)


def test_a_standing_coal_step_is_base_and_plans_nothing(tables):
    led = power.ledger(
        tables, production_mw=75.6885, bootstrap=MK1_COAL_STEP,
        standing_net=_net((MINER, 2), (COAL, 4), (WATER, 2), (BURNER, 4)),
        generators=(
            power.GeneratorReading(COAL, 4, BASE, True, fuel="Desc_Coal_C"),
            power.GeneratorReading(BURNER, 4, RESERVE, True),
        ),
    )
    assert led.planned == ()
    assert (led.base_mw, led.reserve_mw) == (300.0, 120.0)
    coal, burner = led.fuel
    assert (coal.fuel_per_min, coal.supplemental, coal.supplemental_per_min) == (
        60.0, "Desc_Water_C", 180.0)
    assert burner.fuel is None and burner.fuel_per_min is None


def test_ore_extraction_is_unknown_never_zero(tables):
    led = power.ledger(tables, production_mw=10.0, bootstrap=MK1_COAL_STEP,
                       standing_net=None, generators=())
    assert led.ore_extraction_mw is None
    (ore,) = [d for d in led.demand if d.source == "ore extraction"]
    assert ore.mw is None and ore.basis.startswith("UNKNOWN")
    assert all(d.basis == "NAMEPLATE" for d in led.demand if d.source.startswith("bootstrap"))


def test_fed_flips_supply_and_nothing_else(tables):
    kw = dict(production_mw=50.0, bootstrap=MK1_COAL_STEP, standing_net=_net((BURNER, 2)))
    fed = power.ledger(tables, generators=(power.GeneratorReading(BURNER, 2, BASE, True),), **kw)
    unfed = power.ledger(tables, generators=(power.GeneratorReading(BURNER, 2, BASE, False),), **kw)
    assert (fed.base_mw, unfed.base_mw) == (60.0, 0.0)
    assert [(s.count, s.mw) for s in unfed.unfed] == [(2, 0.0)]
    for field in ("planned", "demand", "known_demand_mw", "reserve_mw", "planned_mw"):
        assert getattr(fed, field) == getattr(unfed, field), field


def test_reserve_is_never_summed_into_base(tables):
    led = power.ledger(
        tables, production_mw=0.0, bootstrap=MK1_COAL_STEP, standing_net=_net((BURNER, 3)),
        generators=(power.GeneratorReading(BURNER, 1, BASE, True),
                    power.GeneratorReading(BURNER, 2, RESERVE, True)),
    )
    assert (led.base_mw, led.reserve_mw) == (30.0, 60.0)


@pytest.mark.parametrize("standing, readings", [
    (((COAL, 4),), ()),                                              # standing, not read
    ((), (power.GeneratorReading(COAL, 1, BASE, True),)),            # read, not standing
    (((BURNER, 4),), (power.GeneratorReading(BURNER, 3, BASE, True),)),
])
def test_readings_must_match_the_standing_declaration(tables, standing, readings):
    with pytest.raises(power.PowerLedgerError, match="declared standing"):
        power.ledger(tables, production_mw=0.0, bootstrap=MK1_COAL_STEP,
                     standing_net=_net(*standing), generators=readings)


def test_a_variable_output_generator_is_refused(tables):
    with pytest.raises(power.PowerLedgerError, match="variable output"):
        power.ledger(
            tables, production_mw=0.0, bootstrap=MK1_COAL_STEP,
            standing_net=_net(("Build_GeneratorGeoThermal_C", 1)),
            generators=(power.GeneratorReading("Build_GeneratorGeoThermal_C", 1, BASE, True),),
        )


def test_a_fuel_the_class_does_not_burn_is_refused(tables):
    with pytest.raises(power.PowerLedgerError, match="does not burn"):
        power.ledger(
            tables, production_mw=0.0, bootstrap=MK1_COAL_STEP, standing_net=_net((COAL, 1)),
            generators=(power.GeneratorReading(COAL, 1, BASE, True, fuel="Desc_Wood_C"),),
        )


@pytest.mark.parametrize("kw", [
    dict(count=0, role=BASE, fed=True),
    dict(count=1, role="base", fed=True),
    dict(count=1, role=BASE, fed=None),
])
def test_a_reading_must_declare_role_and_fed(kw):
    """Lock (c): no defaults."""
    with pytest.raises(ValueError):
        power.GeneratorReading(BURNER, **kw)


# --------------------------------------------------------------------------
# cannot — read from the source
# --------------------------------------------------------------------------

SOURCE = pathlib.Path(power.__file__).read_text(encoding="utf-8")


def test_the_ledger_has_no_verdict_field():
    """A shortfall is a number, never a bool: no field of the report is one."""
    hints = typing.get_type_hints(power.PowerLedger)
    assert bool not in hints.values()
    assert not [f for f in dataclasses.fields(power.PowerLedger)
                if "sufficient" in f.name or "feasible" in f.name or f.name.startswith("is_")]


def test_the_ledger_ranks_and_rounds_nothing():
    called = {
        (n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", ""))
        for n in ast.walk(ast.parse(SOURCE)) if isinstance(n, ast.Call)
    }
    assert {"min", "max", "sorted", "sort", "round"}.isdisjoint(called)


def test_the_ledger_calls_no_layer():
    """Report only: it cannot re-run a bill, a netting, a solve or a realization."""
    called = {
        (n.func.id if isinstance(n.func, ast.Name) else getattr(n.func, "attr", ""))
        for n in ast.walk(ast.parse(SOURCE)) if isinstance(n, ast.Call)
    }
    assert {"bill_for", "net_buildings", "net_of", "cost_of", "solve", "realize",
            "run", "paced_run"}.isdisjoint(called)
