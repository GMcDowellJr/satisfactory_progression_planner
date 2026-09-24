"""The power ledger: supply and demand for one stage, REPORTED. It sizes nothing.

D4 P5, goal_run_driver.md amendments 4 and 5. Greg's locks, 2026-09-24:

    (c)  no default for generators: each standing generator is declared base
         or reserve, and fed or not
    (d)  generator fuel and water appear here only, never in the solve
    S2   extractors at NAMEPLATE (100% clock), labelled so. Demand is then
         overstated, which makes base - demand the conservative figure
    A5   bootstrap generators still OWED (not yet standing) are PLANNED
         supply: their own line, never summed into base

**Nothing reads this to size anything, and that is the guardrail.** A peak is
reported and never sizes; the same holds for a shortfall. The ledger has no
verdict field — no "sufficient", no "feasible" — because a boolean here would
be a tier-horizon judgement the model does not hold. A shortfall is a negative
number. Asserted from the source: no min, max, sort or round, and no field of
the report is a bool.

**Ore extraction is UNKNOWN, never 0.0.** Ore miners need node purity, which
is a world-layer fact. `ore_extraction_mw` is None and every balance says it
is taken before ore extraction. A zero would read as "measured, and nothing".

**Separate grids are not modelled.** A generator on another grid is declared
as not supplying (not fed, or left out).

Import direction: downward, like the rest of the package. It takes the
production draw as a number handed in (`RealizationReport.total_power_mw`),
so it needs no realization import — `stock` stays the one module here that
touches `realization.contracts`.
"""
from __future__ import annotations

import csv
import enum
import pathlib
from dataclasses import dataclass

from production_adapter.contracts import ItemId, ProducerClass

from .stock import BootstrapSet, NetBuildings

REFERENCE = ("planning_data", "game", "reference")


class PowerLedgerError(ValueError):
    """The ledger declines rather than reporting a number it cannot stand behind."""


class Role(enum.Enum):
    """What a standing generator is FOR. Declared; there is no default (lock c)."""

    BASE = "base"
    RESERVE = "reserve"


@dataclass(frozen=True)
class GeneratorReading:
    """Some of one class's standing generators, as the player declares them.

    A class may be split across readings (2 burners base and fed, 2 reserve and
    unfed). `fuel` is the item they burn; None reports the fuel draw as
    unknown rather than guessing which of the class's fuels is in use.
    """

    producer_class: ProducerClass
    count: int
    role: Role
    fed: bool
    fuel: ItemId | None = None

    def __post_init__(self) -> None:
        if self.count <= 0:
            raise ValueError(
                f"{self.producer_class}: a generator reading counts at least one. "
                "A generator that is not there is left out, not declared as zero."
            )
        if not isinstance(self.role, Role):
            raise ValueError(f"{self.producer_class}: role must be a Role, got {self.role!r}")
        if not isinstance(self.fed, bool):
            raise ValueError(f"{self.producer_class}: fed must be declared True or False")


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
    rather than picked.
    """
    base = pathlib.Path(repo_root).joinpath(*REFERENCE)

    def rows(name: str) -> list[dict[str, str]]:
        path = base / name
        if not path.is_file():
            raise PowerLedgerError(f"missing reference table: {path}")
        with path.open(encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    generators: dict[ProducerClass, GeneratorSpec] = {}
    variable: set[ProducerClass] = set()
    for r in rows("power_buildings.csv"):
        if r["power_model"] == "fixed":
            generators[r["generator_class"]] = GeneratorSpec(
                r["generator_class"], float(r["power_production_mw"]))
        else:
            variable.add(r["generator_class"])

    fuels: dict[tuple[ProducerClass, ItemId], FuelSpec] = {}
    for r in rows("generator_fuels.csv"):
        fuels[(r["generator_class"], r["fuel_item_id"])] = FuelSpec(
            producer_class=r["generator_class"],
            fuel=r["fuel_item_id"],
            burn_per_min=float(r["burn_rate_per_min"]),
            supplemental=r["supplemental_item_id"] or None,
            supplemental_per_min=float(r["supplemental_rate_per_min"] or 0.0),
        )

    extractors: dict[ProducerClass, float] = {}
    for r in rows("extraction_buildings.csv"):
        mw = float(r["base_power_mw"])
        if extractors.get(r["extractor_class"], mw) != mw:
            raise PowerLedgerError(
                f"{r['extractor_class']}: two base power figures in "
                "extraction_buildings.csv; refused rather than picked"
            )
        extractors[r["extractor_class"]] = mw

    return PowerTables(generators, fuels, extractors, frozenset(variable))


@dataclass(frozen=True)
class SupplyLine:
    """One reading, or one planned class, at nameplate."""

    producer_class: ProducerClass
    count: int
    mw: float
    fed: bool | None  # None on a planned line: not built, so not readable


@dataclass(frozen=True)
class DemandLine:
    """One draw. `basis` names how it was taken; `mw` None means unknown."""

    source: str
    mw: float | None
    basis: str


@dataclass(frozen=True)
class FuelDraw:
    """What a fed generator reading burns per minute. `fuel` None: not declared."""

    producer_class: ProducerClass
    count: int
    fuel: ItemId | None
    fuel_per_min: float | None
    supplemental: ItemId | None
    supplemental_per_min: float | None


@dataclass(frozen=True)
class PowerLedger:
    """Supply and demand, side by side. No verdict; a shortfall is a negative number.

        base        standing generators declared BASE and fed
        reserve     standing generators declared RESERVE and fed. Never in base
        unfed       standing generators declared unfed; supply 0, listed
        planned     bootstrap generators still OWED; nameplate, not yet built.
                    Never in base or reserve
        demand      production lines as handed in; the bootstrap target's
                    extractors at NAMEPLATE; ore extraction UNKNOWN (None)

    The balances are all taken BEFORE ore extraction, which is unknown:

        base_less_demand                  base - demand
        base_and_reserve_less_demand      base + reserve - demand
        base_and_planned_less_demand      base + planned - demand: the stage
                                          once its bootstrap stands, if every
                                          planned generator is fed
    """

    base: tuple[SupplyLine, ...]
    reserve: tuple[SupplyLine, ...]
    unfed: tuple[SupplyLine, ...]
    planned: tuple[SupplyLine, ...]
    demand: tuple[DemandLine, ...]
    fuel: tuple[FuelDraw, ...]
    base_mw: float
    reserve_mw: float
    planned_mw: float
    known_demand_mw: float
    ore_extraction_mw: None
    base_less_demand_mw: float
    base_and_reserve_less_demand_mw: float
    base_and_planned_less_demand_mw: float


def _nameplate(tables: PowerTables, producer_class: ProducerClass) -> float:
    if producer_class in tables.variable:
        raise PowerLedgerError(
            f"{producer_class}: variable output; a nameplate would be invented. "
            "Refused rather than reported."
        )
    if producer_class not in tables.generators:
        raise PowerLedgerError(f"{producer_class}: not a generator in power_buildings.csv")
    return tables.generators[producer_class].nameplate_mw


def ledger(
    tables: PowerTables,
    *,
    production_mw: float,
    bootstrap: BootstrapSet,
    standing_net: NetBuildings | None,
    generators: tuple[GeneratorReading, ...],
) -> PowerLedger:
    """One stage's ledger. Every input is a declaration or a layer's answer.

    `production_mw` is the realization's `total_power_mw` for the build being
    judged (the paced pass, usually). `standing_net` is the bill's
    `StockPass.standing_net`; None means nothing was declared standing, and
    then no generator reading may be given either.

    CONSISTENCY, refused otherwise: for every generator class, the readings'
    counts sum to that class's count in the standing declaration. A coal
    generator read here but not declared standing would supply power without
    netting the bootstrap's coal count, and be planned a second time.
    """
    standing = dict(standing_net.standing.buildings) if standing_net is not None else {}
    read: dict[ProducerClass, int] = {}
    for g in generators:
        _nameplate(tables, g.producer_class)
        read[g.producer_class] = read.get(g.producer_class, 0) + g.count
    for producer_class in list(read) + [pc for pc in standing if pc in tables.generators]:
        if read.get(producer_class, 0) != standing.get(producer_class, 0):
            raise PowerLedgerError(
                f"{producer_class}: {read.get(producer_class, 0)} read as generators, "
                f"{standing.get(producer_class, 0)} declared standing. Declare each "
                "standing generator once in both, with its role and whether it is fed."
            )

    base: list[SupplyLine] = []
    reserve: list[SupplyLine] = []
    unfed: list[SupplyLine] = []
    fuel: list[FuelDraw] = []
    for g in generators:
        mw = _nameplate(tables, g.producer_class) * g.count
        if not g.fed:
            unfed.append(SupplyLine(g.producer_class, g.count, 0.0, False))
            continue
        line = SupplyLine(g.producer_class, g.count, mw, True)
        (base if g.role is Role.BASE else reserve).append(line)
        if g.fuel is None:
            fuel.append(FuelDraw(g.producer_class, g.count, None, None, None, None))
        else:
            spec = tables.fuels.get((g.producer_class, g.fuel))
            if spec is None:
                raise PowerLedgerError(f"{g.producer_class} does not burn {g.fuel}")
            fuel.append(FuelDraw(
                g.producer_class, g.count, g.fuel, spec.burn_per_min * g.count,
                spec.supplemental,
                spec.supplemental_per_min * g.count if spec.supplemental else None,
            ))

    owed = (standing_net.owed_bootstrap if standing_net is not None
            else dict(bootstrap.buildings))
    planned: list[SupplyLine] = []
    for producer_class, count in owed.items():
        if count and producer_class in tables.generators:
            planned.append(SupplyLine(
                producer_class, count, _nameplate(tables, producer_class) * count, None))

    demand: list[DemandLine] = [DemandLine("production lines", production_mw, "realized clocks")]
    for producer_class, count in bootstrap.buildings:
        if producer_class in tables.extractors:
            demand.append(DemandLine(
                f"bootstrap {producer_class} x{count}",
                tables.extractors[producer_class] * count, "NAMEPLATE"))
    demand.append(DemandLine("ore extraction", None, "UNKNOWN: node purity is world layer"))

    base_mw = sum(s.mw for s in base)
    reserve_mw = sum(s.mw for s in reserve)
    planned_mw = sum(s.mw for s in planned)
    known = sum(d.mw for d in demand if d.mw is not None)
    return PowerLedger(
        base=tuple(base), reserve=tuple(reserve), unfed=tuple(unfed),
        planned=tuple(planned), demand=tuple(demand), fuel=tuple(fuel),
        base_mw=base_mw, reserve_mw=reserve_mw, planned_mw=planned_mw,
        known_demand_mw=known, ore_extraction_mw=None,
        base_less_demand_mw=base_mw - known,
        base_and_reserve_less_demand_mw=base_mw + reserve_mw - known,
        base_and_planned_less_demand_mw=base_mw + planned_mw - known,
    )
