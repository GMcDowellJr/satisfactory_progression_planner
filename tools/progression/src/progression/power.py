"""The power tables: fixed-output generators, their fuels, extractor base power.

What is left of the D4 P5 power ledger (goal_run_driver.md amendments 4 and
5, 2026-09-24). The ledger itself (`ledger`, `PowerLedger`, `GeneratorReading`,
`Role` and their lines) was used by tests only and was RETIRED, decided by
Greg 2026-11-17 (site-planner reframe A19.4); its job, which generators carry
a need and what they burn, is `progression.power_stack`'s (A18, A19). The
tables stay: portfolio_run, district_run, site_card, factory_run and the
extraction-draw arithmetic read `extractors` from them.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

from production_adapter.contracts import ItemId, ProducerClass
from production_adapter.gamedata import (
    load_extraction_building_rows, load_generator_fuel_rows, load_power_building_rows,
)


class PowerLedgerError(ValueError):
    """The tables decline rather than picking between two figures. (The name
    is kept from the retired ledger: callers catch it.)"""


@dataclass(frozen=True)
class GeneratorSpec:
    producer_class: ProducerClass
    nameplate_mw: float


@dataclass(frozen=True)
class FuelSpec:
    producer_class: ProducerClass
    fuel: ItemId
    burn_per_min: float
    supplemental: ItemId | None
    supplemental_per_min: float


@dataclass(frozen=True)
class PowerTables:
    """Fixed-output generators, their fuels, and extractor base power. Game docs."""

    generators: dict[ProducerClass, GeneratorSpec]
    fuels: dict[tuple[ProducerClass, ItemId], FuelSpec]
    extractors: dict[ProducerClass, float]
    #: Generator classes whose output is not a constant (geothermal). Named so
    #: a reading of one is refused with a reason, not reported as unknown power
    variable: frozenset[ProducerClass]


def load_power_tables(repo_root: str | pathlib.Path) -> PowerTables:
    """power_buildings.csv, generator_fuels.csv, extraction_buildings.csv.

    An extractor class listed twice with different base power is refused
    rather than picked. Rows come from `gamedata` (R1, 2026-11-17); a missing
    table raises `gamedata.ReferenceDataError` there.
    """
    generators: dict[ProducerClass, GeneratorSpec] = {}
    variable: set[ProducerClass] = set()
    for r in load_power_building_rows(repo_root):
        if r.power_production_mw is not None:
            generators[r.generator_class] = GeneratorSpec(r.generator_class, r.power_production_mw)
        else:
            variable.add(r.generator_class)

    fuels: dict[tuple[ProducerClass, ItemId], FuelSpec] = {}
    for r in load_generator_fuel_rows(repo_root):
        fuels[(r.generator_class, r.fuel_item_id)] = FuelSpec(
            producer_class=r.generator_class,
            fuel=r.fuel_item_id,
            burn_per_min=r.burn_rate_per_min,
            supplemental=r.supplemental_item_id,
            supplemental_per_min=r.supplemental_rate_per_min,
        )

    extractors: dict[ProducerClass, float] = {}
    for r in load_extraction_building_rows(repo_root):
        mw = r.base_power_mw
        if extractors.get(r.extractor_class, mw) != mw:
            raise PowerLedgerError(
                f"{r.extractor_class}: two base power figures in "
                "extraction_buildings.csv; refused rather than picked"
            )
        extractors[r.extractor_class] = mw

    return PowerTables(generators, fuels, extractors, frozenset(variable))
