"""The power tables (what remains of the D4 P5 ledger; the ledger itself was
retired, decided by Greg 2026-11-17, site-planner reframe A19.4).

Figures are read from the reference tables through `load_power_tables` and
checked against the arithmetic: Coal-Powered Generator 75 MW, 15 coal + 45 m3
water per minute; Biomass Burner 30 MW; Miner Mk.1 5 MW; Water Extractor 20 MW.
"""
from __future__ import annotations

import pathlib

import pytest

from progression import power

REPO = pathlib.Path(__file__).resolve().parents[1]
MINER, COAL, WATER, BURNER = (
    "Build_MinerMk1_C", "Build_GeneratorCoal_C", "Build_WaterPump_C",
    "Build_GeneratorBiomass_Automated_C",
)


@pytest.fixture(scope="module")
def tables():
    return power.load_power_tables(REPO)


def test_the_tables_carry_the_game_figures(tables):
    assert tables.generators[COAL].nameplate_mw == 75.0
    assert tables.generators[BURNER].nameplate_mw == 30.0
    assert (tables.extractors[MINER], tables.extractors[WATER]) == (5.0, 20.0)
    coal = tables.fuels[(COAL, "Desc_Coal_C")]
    assert (coal.burn_per_min, coal.supplemental, coal.supplemental_per_min) == (
        15.0, "Desc_Water_C", 45.0)
    assert "Build_GeneratorGeoThermal_C" in tables.variable


def test_the_ledger_is_retired():
    """A19.4: the report side is progression.power_stack."""
    for name in ("ledger", "PowerLedger", "GeneratorReading", "Role", "SupplyLine",
                 "DemandLine", "FuelDraw"):
        assert not hasattr(power, name), name
