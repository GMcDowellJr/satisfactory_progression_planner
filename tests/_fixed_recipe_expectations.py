"""Expected power and machine counts for a GIVEN set of recipe multipliers.

The companion to `_demand_oracle`. The oracle propagates demand and deliberately
reports neither power nor machine counts (`test_reports_no_power_or_machine_counts`
enforces that). This module supplies exactly that missing layer, and nothing else,
so that a production backend has something independent to be checked against.

Deliberately crippled in the same way, and it must stay that way.

    It does not choose. `expectations()` takes a multiplier map as input and never
    computes one. Recipe selection is the solver's job; this module inherits the
    oracle's `AmbiguousDemand` guard by never being in a position to select.

    It reads the reference CSVs directly rather than going through
    `production_adapter.gamedata`, so that it remains an independent check of the
    adapter rather than a restatement of it.

    It has no CLI, no __main__, no entry point, and lives under tests/ with a
    leading underscore.

Scope, per docs/decisions/production_lp_formulation.md:

    D5   extraction is outside the LP, so power here EXCLUDES extraction.
    D2   undecided. Power is reported as a (min, mean, max) triple and the caller
         picks. For every producer in the current fixed-recipe cases the three
         coincide, because all of them are fixed-power — which is why these cases
         are safe to write while D2 is open.
"""
from __future__ import annotations

import csv
import pathlib
from dataclasses import dataclass

REF = pathlib.Path(__file__).resolve().parents[1] / "planning_data" / "game" / "reference"


@dataclass(frozen=True)
class PowerTriple:
    min_mw: float
    mean_mw: float
    max_mw: float

    @property
    def is_degenerate(self) -> bool:
        """True when every contributing producer is fixed-power."""
        return self.min_mw == self.mean_mw == self.max_mw


@dataclass(frozen=True)
class ExpectedFactory:
    power: PowerTriple
    machines_by_producer_class: dict[str, float]
    machines_by_display_name: dict[str, float]


def _rows(name: str) -> list[dict[str, str]]:
    with open(REF / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _tables():
    producer_of = {r["recipe_id"]: r["producer_class"] for r in _rows("recipe_producers.csv")}
    producers = {
        r["producer_class"]: (r["power_model"], float(r["base_power_mw"]), r["display_name"])
        for r in _rows("production_buildings.csv")
    }
    variable = {
        r["recipe_id"]: (float(r["power_min_mw"]), float(r["power_max_mw"]))
        for r in _rows("recipe_variable_power.csv")
    }
    return producer_of, producers, variable


def expectations(recipe_multipliers: dict[str, float]) -> ExpectedFactory:
    """Power and machine counts for a multiplier map the caller already has.

    `recipe_multipliers` is `OracleResult.recipe_multipliers`, or any fixed set of
    machine equivalents. This function never decides which recipes to run.
    """
    producer_of, producers, variable = _tables()

    lo = mean = hi = 0.0
    by_class: dict[str, float] = {}
    by_name: dict[str, float] = {}

    for recipe_id, multiplier in sorted(recipe_multipliers.items()):
        producer_class = producer_of.get(recipe_id)
        if producer_class is None:
            raise KeyError(f"{recipe_id} has no producer in recipe_producers.csv")
        entry = producers.get(producer_class)
        if entry is None:
            raise KeyError(f"{recipe_id} runs in {producer_class}, absent from production_buildings.csv")
        model, base_mw, display_name = entry

        if model == "variable":
            rng = variable.get(recipe_id)
            if rng is None:
                raise KeyError(f"{recipe_id} runs on variable-power {producer_class} with no range row")
            r_lo, r_hi = rng
        else:
            # Variable-power fields on a fixed-power producer are ignored by the game
            # and must be ignored here. See docs/decisions/production_building_power_model.md.
            r_lo = r_hi = base_mw

        lo += r_lo * multiplier
        hi += r_hi * multiplier
        mean += ((r_lo + r_hi) / 2.0) * multiplier
        by_class[producer_class] = by_class.get(producer_class, 0.0) + multiplier
        by_name[display_name] = by_name.get(display_name, 0.0) + multiplier

    return ExpectedFactory(
        power=PowerTriple(lo, mean, hi),
        machines_by_producer_class=by_class,
        machines_by_display_name=by_name,
    )
