"""Load the canonical reference layer into the adapter's own shape.

This is the only place that knows the CSV filenames and column names. Backends
receive `ReferenceData`, never a path and never a DictReader.

Everything here is read-only. The reference layer is authoritative (plan
section 1.2) and nothing in this package writes to it.
"""
from __future__ import annotations

import csv
import pathlib
from dataclasses import dataclass, field

from .contracts import ItemId, ProducerClass, RecipeId
from .scenario import ITEM_UNIT, Scenario

REFERENCE_SUBPATH = pathlib.Path("planning_data") / "game" / "reference"


class ReferenceDataError(RuntimeError):
    """The reference layer is missing something the adapter requires."""


@dataclass(frozen=True)
class Producer:
    producer_class: ProducerClass
    display_name: str
    power_model: str          # "fixed" | "variable"
    base_power_mw: float
    power_exponent: float

    @property
    def is_variable_power(self) -> bool:
        return self.power_model == "variable"


@dataclass(frozen=True)
class PowerRange:
    min_mw: float
    max_mw: float

    @property
    def mean_mw(self) -> float:
        return (self.min_mw + self.max_mw) / 2.0

    def scaled(self, factor: float) -> "PowerRange":
        return PowerRange(self.min_mw * factor, self.max_mw * factor)


@dataclass(frozen=True)
class Recipe:
    recipe_id: RecipeId
    display_name: str
    is_alternate: bool
    duration_sec: float
    producer_class: ProducerClass
    inputs: tuple[tuple[ItemId, float], ...]    # (item, per-minute at 100% clock)
    outputs: tuple[tuple[ItemId, float], ...]
    power: PowerRange
    #: (item, per-cycle amount, unit) — what the game states and what the recipe
    #: multiplier acts on. `inputs` is this divided by the cycle; a scenario is
    #: applied here and the rates are re-derived, because rounding to whole parts
    #: is not expressible on a rate (scenario.py, record 3.2.5).
    input_amounts: tuple[tuple[ItemId, float, str], ...] = ()

    @property
    def cycles_per_min(self) -> float:
        return 60.0 / self.duration_sec

    def scaled(self, scenario: Scenario) -> "Recipe":
        """A copy with scenario modifiers applied. Canonical data is untouched."""
        if scenario.is_canonical:
            return self
        if scenario.recipe_input_multiplier == 1.0:
            # No input transform at all, so the canonical rates are carried
            # through unchanged rather than re-derived and re-rounded.
            inputs = self.inputs
            input_amounts = self.input_amounts
        else:
            input_amounts = tuple(
                (i, scenario.apply_input_amount(a, u), u) for i, a, u in self.input_amounts
            )
            per_min = self.cycles_per_min
            inputs = tuple((i, a * per_min) for i, a, _ in input_amounts)
        return Recipe(
            recipe_id=self.recipe_id,
            display_name=self.display_name,
            is_alternate=self.is_alternate,
            duration_sec=self.duration_sec,
            producer_class=self.producer_class,
            inputs=inputs,
            outputs=tuple((i, scenario.apply_output_rate(r)) for i, r in self.outputs),
            power=self.power.scaled(scenario.machine_power_multiplier),
            input_amounts=input_amounts,
        )


@dataclass(frozen=True)
class Item:
    item_id: ItemId
    display_name: str
    form: str
    is_resource: bool


@dataclass(frozen=True)
class Capability:
    """One row of logistics_capabilities.csv, with the tier resolved.

    The CSV carries tier only as free text in `unlock` ("Tier 4 - Logistics
    Mk.3"); `unlock_tier` is that parsed to an integer and `unlock_text` keeps
    the original for reporting. The respec's own section 3.1 correction — belt
    Mk.4 recorded as Tier 4 when it is Tier 5 — is the error this field exists
    to make impossible rather than merely unlikely.
    """

    capability_id: str
    capability_type: str      # belt | conveyor_lift | pipeline | miner
    mark: str                 # "Mk.1" .. "Mk.6"
    capacity_per_min: float
    unit: str
    unlock_tier: int
    unlock_text: str


@dataclass(frozen=True)
class ExtractionRate:
    """One row of extraction_rates.csv: extractor x purity."""

    extractor_class: ProducerClass
    purity: str               # impure | normal | pure | none
    purity_multiplier: float
    nominal_rate_min: float   # at 100% clock
    max_250_rate_min: float   # at 250% clock
    unit: str                 # items/min | m3/min


@dataclass(frozen=True)
class ReferenceData:
    game_build_id: str
    recipes: dict[RecipeId, Recipe]
    producers: dict[ProducerClass, Producer]
    items: dict[ItemId, Item]
    resource_items: frozenset[ItemId]
    scenario: Scenario = field(default_factory=Scenario)

    def with_scenario(self, scenario: Scenario) -> "ReferenceData":
        return ReferenceData(
            game_build_id=self.game_build_id,
            recipes={k: v.scaled(scenario) for k, v in self.recipes.items()},
            producers=self.producers,
            items=self.items,
            resource_items=self.resource_items,
            scenario=scenario,
        )

    def base_recipes(self) -> tuple[RecipeId, ...]:
        return tuple(sorted(k for k, v in self.recipes.items() if not v.is_alternate))


def _rows(path: pathlib.Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ReferenceDataError(f"missing reference table: {path}")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load(repo_root: str | pathlib.Path, scenario: Scenario | None = None) -> ReferenceData:
    """Read the canonical tables. Raises rather than guessing when data is absent."""
    ref = pathlib.Path(repo_root) / REFERENCE_SUBPATH

    producers: dict[ProducerClass, Producer] = {}
    for r in _rows(ref / "production_buildings.csv"):
        producers[r["producer_class"]] = Producer(
            producer_class=r["producer_class"],
            display_name=r["display_name"],
            power_model=r["power_model"],
            base_power_mw=float(r["base_power_mw"]),
            power_exponent=float(r["power_exponent"]),
        )

    variable: dict[RecipeId, PowerRange] = {}
    for r in _rows(ref / "recipe_variable_power.csv"):
        variable[r["recipe_id"]] = PowerRange(float(r["power_min_mw"]), float(r["power_max_mw"]))

    producer_of = {r["recipe_id"]: r["producer_class"] for r in _rows(ref / "recipe_producers.csv")}

    io_in: dict[RecipeId, list[tuple[ItemId, float]]] = {}
    io_out: dict[RecipeId, list[tuple[ItemId, float]]] = {}
    io_in_amounts: dict[RecipeId, list[tuple[ItemId, float, str]]] = {}
    for r in _rows(ref / "recipe_io.csv"):
        if r["direction"] == "input":
            io_in.setdefault(r["recipe_id"], []).append(
                (r["item_id"], float(r["rate_per_min"]))
            )
            io_in_amounts.setdefault(r["recipe_id"], []).append(
                (r["item_id"], float(r["amount_per_cycle"]), r.get("unit") or ITEM_UNIT)
            )
        else:
            io_out.setdefault(r["recipe_id"], []).append(
                (r["item_id"], float(r["rate_per_min"]))
            )

    builds: set[str] = set()
    recipes: dict[RecipeId, Recipe] = {}
    for r in _rows(ref / "recipes.csv"):
        rid = r["recipe_id"]
        builds.add(r["game_build_id"])
        pc = producer_of.get(rid)
        if pc is None:
            raise ReferenceDataError(f"{rid} has no producer in recipe_producers.csv")
        producer = producers.get(pc)
        if producer is None:
            raise ReferenceDataError(
                f"{rid} is produced in {pc}, absent from production_buildings.csv"
            )
        if producer.is_variable_power:
            power = variable.get(rid)
            if power is None:
                raise ReferenceDataError(
                    f"{rid} runs on variable-power {pc} but has no recipe_variable_power row"
                )
        else:
            # Variable-power fields on a fixed-power producer are ignored by the
            # game and must be ignored here. Honouring them overstates Ballistic
            # Warp Drive by roughly 20x.
            power = PowerRange(producer.base_power_mw, producer.base_power_mw)
        recipes[rid] = Recipe(
            recipe_id=rid,
            display_name=r["display_name"],
            is_alternate=r["is_alternate"] == "true",
            duration_sec=float(r["manufacturing_duration_sec"]),
            producer_class=pc,
            inputs=tuple(io_in.get(rid, ())),
            outputs=tuple(io_out.get(rid, ())),
            power=power,
            input_amounts=tuple(io_in_amounts.get(rid, ())),
        )

    items: dict[ItemId, Item] = {}
    resources: set[ItemId] = set()
    for r in _rows(ref / "items.csv"):
        items[r["item_id"]] = Item(
            item_id=r["item_id"],
            display_name=r["display_name"],
            form=r["form"],
            is_resource=r["category"] == "resource",
        )
        if r["category"] == "resource":
            resources.add(r["item_id"])

    if len(builds) != 1:
        raise ReferenceDataError(f"reference layer spans multiple game builds: {sorted(builds)}")

    data = ReferenceData(
        game_build_id=builds.pop(),
        recipes=recipes,
        producers=producers,
        items=items,
        resource_items=frozenset(resources),
    )
    return data if scenario is None else data.with_scenario(scenario)


_TIER_PREFIX = "Tier "


def _unlock_tier(unlock_text: str) -> int:
    """Parse "Tier 4 - Logistics Mk.3" to 4.

    Raises rather than defaulting. A capability whose tier cannot be read is a
    data defect, and a silent 0 would unlock every Mk at every tier — the
    failure would present as a plan that builds Mk.6 belts on a fresh save.
    """
    text = unlock_text.strip()
    if not text.startswith(_TIER_PREFIX):
        raise ReferenceDataError(f"unlock text has no tier: {unlock_text!r}")
    head = text[len(_TIER_PREFIX):].split("-", 1)[0].strip()
    if not head.isdigit():
        raise ReferenceDataError(f"unlock tier is not a number: {unlock_text!r}")
    return int(head)


def load_logistics(
    repo_root: str | pathlib.Path,
) -> tuple[tuple[Capability, ...], tuple[ExtractionRate, ...]]:
    """Read logistics_capabilities.csv and extraction_rates.csv.

    Deliberately NOT part of `ReferenceData`. Neither table is scenario
    dependent — belt throughput and node purity do not move with the recipe
    multiplier — and placing them behind `with_scenario()` would make scaling
    them a one-line mistake later.

    Returned sorted by (capability_type, unlock_tier, mark) and by
    (extractor_class, purity), so callers that iterate are deterministic
    without sorting at each site.
    """
    ref = pathlib.Path(repo_root) / REFERENCE_SUBPATH

    caps = tuple(
        Capability(
            capability_id=r["capability_id"],
            capability_type=r["capability_type"],
            mark=r["mark"],
            capacity_per_min=float(r["capacity_per_min"]),
            unit=r["unit"],
            unlock_tier=_unlock_tier(r["unlock"]),
            unlock_text=r["unlock"],
        )
        for r in _rows(ref / "logistics_capabilities.csv")
    )

    rates = tuple(
        ExtractionRate(
            extractor_class=r["extractor_class"],
            purity=r["purity"],
            purity_multiplier=float(r["purity_multiplier"]),
            nominal_rate_min=float(r["nominal_rate_min"]),
            max_250_rate_min=float(r["max_250_rate_min"]),
            unit=r["unit"],
        )
        for r in _rows(ref / "extraction_rates.csv")
    )

    return (
        tuple(sorted(caps, key=lambda c: (c.capability_type, c.unlock_tier, c.mark))),
        tuple(sorted(rates, key=lambda e: (e.extractor_class, e.purity))),
    )
