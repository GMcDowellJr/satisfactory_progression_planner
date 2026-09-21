"""Independent verification that a SolveResponse is internally consistent.

`_demand_oracle` answers "what does this target require" by propagating demand.
That is the right reference for a chain where nothing feeds back — and the wrong
one for a chain where an enabled recipe's byproduct satisfies another demand,
because the oracle credits no byproducts and a production solver credits them all.
Neither is wrong; they answer different questions. Discovered 2026-09-18 on Nuclear
Pasta, where `Recipe_AluminaSolution_C` runs 4.1000 in the oracle and 3.0750 in the
LP because the LP nets the Silica byproduct against Silica demand.

So plan section 11's late-game case needs a reference the oracle cannot be. This is
it: rather than recomputing what the answer should be, it checks that the answer the
solver gave actually balances, meets the request, and draws only raw resources.

Deliberately crippled in the same way as its two siblings, and it must stay that way.

    It does not solve. It takes a response and returns violations. It has no notion
    of what a better answer would look like and cannot produce one.

    It reads the reference CSVs directly rather than going through
    `production_adapter.gamedata`, so it stays an independent check of the adapter
    rather than a restatement of it.

    It has no CLI, no __main__, no entry point, and lives under tests/ with a
    leading underscore.

Scope: item balance, target satisfaction, raw-input legitimacy, and agreement
between the recipe activities and the reported `ItemFlow` tuple. Power and machine
counts are `_fixed_recipe_expectations`' job and are not duplicated here.
"""
from __future__ import annotations

import collections
import csv
import pathlib
from decimal import Decimal, ROUND_HALF_UP

REF = pathlib.Path(__file__).resolve().parents[1] / "planning_data" / "game" / "reference"


def _rows(name: str) -> list[dict[str, str]]:
    with open(REF / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _scaled_input_rate(amount_per_cycle: float, unit: str, cycles_per_min: float,
                       multiplier: float) -> float:
    """The game's scaled input rate: round the per-cycle amount, then rate it.

    Reimplemented rather than imported, for the same reason this module reads the
    CSVs directly. Record 3.2.5: nearest integer, halves away from zero, per
    input. A scalar multiplier applied to a rate — what this module did until
    2026-09-21 — cannot express it.
    """
    if multiplier == 1.0:
        return amount_per_cycle * cycles_per_min
    if multiplier < 1.0:
        raise ValueError(
            "sub-1x multipliers need a declared floor rule (record 3.2.3); this "
            "check does not carry one"
        )
    scaled = (Decimal(repr(amount_per_cycle)) * Decimal(repr(multiplier))).quantize(
        Decimal(1), rounding=ROUND_HALF_UP
    )
    return float(scaled) * cycles_per_min


def _io(input_multiplier: float):
    cycles = {
        r["recipe_id"]: 60.0 / float(r["manufacturing_duration_sec"])
        for r in _rows("recipes.csv")
    }
    inputs = collections.defaultdict(list)
    outputs = collections.defaultdict(list)
    for r in _rows("recipe_io.csv"):
        rid = r["recipe_id"]
        if r["direction"] == "output":
            outputs[rid].append((r["item_id"], float(r["rate_per_min"])))
        else:
            inputs[rid].append((r["item_id"], _scaled_input_rate(
                float(r["amount_per_cycle"]), r.get("unit") or "items",
                cycles[rid], input_multiplier,
            )))
    resources = {r["item_id"] for r in _rows("items.csv") if r["category"] == "resource"}
    return inputs, outputs, resources


def violations(
    response,
    targets: dict[str, float],
    input_multiplier: float = 1.0,
    tolerance: float = 1e-4,
) -> list[str]:
    """Every way this response fails to be a consistent answer to that request.

    An empty list is the assertion. `input_multiplier` must match the scenario the
    response was solved under, because the LP consumed already-scaled inputs and
    these CSVs are canonical. It is applied to per-cycle amounts and rounded, per
    record 3.2.5 — not multiplied into the rate.
    """
    inputs, outputs, resources = _io(input_multiplier)
    activities = {u.recipe_id: u.machine_equivalents for u in response.recipes}
    raw = {r.item_id: r.rate_per_min for r in response.raw_inputs}
    problems: list[str] = []

    produced: dict[str, float] = collections.defaultdict(float)
    consumed: dict[str, float] = collections.defaultdict(float)
    for recipe_id, count in activities.items():
        if count < 0:
            problems.append(f"{recipe_id}: negative activity {count}")
        for item, rate in outputs.get(recipe_id, ()):
            produced[item] += rate * count
        for item, rate in inputs.get(recipe_id, ()):
            consumed[item] += rate * count

    for item, rate in raw.items():
        if item not in resources:
            problems.append(f"{item} is drawn as a raw input but is not a resource in items.csv")
        if rate < -tolerance:
            problems.append(f"{item}: negative raw draw {rate}")

    for item in set(produced) | set(consumed) | set(raw) | set(targets):
        net = produced[item] + raw.get(item, 0.0) - consumed[item]
        wanted = targets.get(item, 0.0)
        if net < wanted - tolerance:
            problems.append(
                f"{item}: net {net:.6f}/min does not meet {wanted:.6f}/min "
                f"(produced {produced[item]:.6f}, raw {raw.get(item, 0.0):.6f}, "
                f"consumed {consumed[item]:.6f})"
            )
        if item not in resources and item not in produced and net > tolerance:
            problems.append(f"{item}: appears from nowhere at {net:.6f}/min")

    reported = {f.item_id: f for f in response.items}
    for item in set(produced) | set(consumed):
        flow = reported.get(item)
        if flow is None:
            if produced[item] > tolerance or consumed[item] > tolerance:
                problems.append(f"{item}: flows but is absent from SolveResponse.items")
            continue
        # The adapter counts raw draw as production so that net_per_min means
        # leftover; this check has to add it on the same side.
        expected_production = produced[item] + raw.get(item, 0.0)
        if abs(flow.produced_per_min - expected_production) > tolerance:
            problems.append(
                f"{item}: reported produced {flow.produced_per_min:.6f} != "
                f"{expected_production:.6f} from the activities"
            )
        if abs(flow.consumed_per_min - consumed[item]) > tolerance:
            problems.append(
                f"{item}: reported consumed {flow.consumed_per_min:.6f} != "
                f"{consumed[item]:.6f} from the activities"
            )

    return problems
