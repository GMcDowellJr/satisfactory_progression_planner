#!/usr/bin/env python3
"""Command line over the production adapter and the progression layer.

Three subcommands, because there are only three questions this stack can answer:

    tiers     what recipes does tier N give me, and what is it not accounting for
    solve     what does producing X cost
    compare   how do two or more solve configurations differ

`solve` and `compare` are adapter operations; `--tier` is a progression concept.
That is why this lives at `tools/` root rather than inside either package — an
entry point inside `production_adapter` would have to import `progression`, which
inverts the dependency direction the adapter boundary exists to protect. It follows
the convention of the other runnable things here, `check_game_docs_provenance.py`
and `regenerate_manifests.py`: a standalone script that sets up `sys.path` itself,
so nothing needs installing.

**What it refuses.** A command line answering production questions will be asked
progression questions, and the honest failure is to decline by name rather than
answer approximately. `--by`, `--deadline`, `--inventory` and `--what-next` all
exist as arguments purely so they can be rejected with the phase that owns them.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _src in ("production_adapter", "progression"):
    sys.path.insert(0, str(REPO / "tools" / _src / "src"))

from production_adapter import (  # noqa: E402
    CHALLENGE_1_25X_2X, OutputTarget, ResourceCap, Scenario, SolveRequest, Weights, load,
)
from production_adapter.analysis import Variant, compare  # noqa: E402
from production_adapter.lp_backend import (  # noqa: E402
    Infeasible, LpBackend, PowerStatistic, SolverFailure,
)
from progression import at_tier  # noqa: E402

#: Named weightings for `compare --vary weights:...`. Arbitrary tuples belong in a
#: script, not in an argument parser.
WEIGHT_PRESETS = {
    "balanced": Weights(),
    "resources": Weights(resources=1.0, power=0.0, buildings=0.0),
    "power": Weights(resources=0.0, power=1.0, buildings=0.0),
    "buildings": Weights(resources=0.0, power=0.0, buildings=1.0),
}

SCENARIO_PRESETS = {"canonical": Scenario(), "challenge": CHALLENGE_1_25X_2X}

#: Arguments that exist only to be refused, and the phase that owns each.
REFUSALS = {
    "by": "scheduling is Phase 2 — nothing in this model knows what time is",
    "deadline": "scheduling is Phase 2 — nothing in this model knows what time is",
    "inventory": "existing stock is Phase 4; SolveRequest.existing_inventory raises",
    "what_next": "'what should I build next' is Phase 4 — it needs run state",
}


class Refused(SystemExit):
    """A question this model cannot represent, declined by name."""


def _refuse(args) -> None:
    for name, reason in REFUSALS.items():
        if getattr(args, name, None):
            raise Refused(f"error: --{name.replace('_', '-')} is not supported: {reason}")


# --- shared plumbing -----------------------------------------------------

def _pairs(values, what):
    out = {}
    for item in values or ():
        if "=" not in item:
            raise SystemExit(f"error: --{what} expects ID=VALUE, got {item!r}")
        key, _, raw = item.partition("=")
        try:
            out[key.strip()] = float(raw)
        except ValueError:
            raise SystemExit(f"error: --{what} value is not a number: {raw!r}") from None
    return out


def _declared(args) -> tuple[str, ...]:
    ids = list(args.declared or ())
    if args.declared_file:
        for line in pathlib.Path(args.declared_file).read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                ids.append(line)
    return tuple(dict.fromkeys(ids))


def _unlocks(args):
    return at_tier(REPO, args.tier, declared=_declared(args), include_pool=args.pool)


def _request(args, allowed, weights=None):
    targets = _pairs(args.target, "target")
    if not targets:
        raise SystemExit("error: at least one --target ITEM=RATE is required")
    caps = tuple(
        ResourceCap(item, rate) for item, rate in sorted(_pairs(args.cap, "cap").items())
    )
    return SolveRequest(
        outputs=tuple(OutputTarget(i, r) for i, r in sorted(targets.items())),
        allowed_recipes=allowed,
        resource_caps=caps,
        weights=weights or WEIGHT_PRESETS[args.weights],
    )


def _data(args):
    data = load(REPO)
    return data if args.scenario == "canonical" else data.with_scenario(SCENARIO_PRESETS[args.scenario])


def _backend(args, statistic=None):
    return LpBackend(power_statistic=PowerStatistic(statistic or args.power_statistic))


# --- tiers ---------------------------------------------------------------

def cmd_tiers(args) -> int:
    if args.find:
        import csv

        needle = args.find.lower()
        path = REPO / "planning_data" / "game" / "reference" / "recipes.csv"
        with open(path, encoding="utf-8") as f:
            hits = [r for r in csv.DictReader(f) if needle in r["display_name"].lower()]
        for row in sorted(hits, key=lambda r: r["display_name"]):
            print(f"{row['recipe_id']:46s} {row['display_name']}")
        if not hits:
            print(f"no recipe display name contains {args.find!r}")
        return 0

    unlocks = _unlocks(args)
    if args.json:
        print(json.dumps({
            "tier": unlocks.tier,
            "recipe_ids": list(unlocks.recipe_ids),
            "declared": list(unlocks.declared),
            "withheld_research": list(unlocks.withheld_research),
            "withheld_alternates": list(unlocks.withheld_alternates),
            "uncertain": list(unlocks.uncertain),
            "pool": list(unlocks.pool.recipe_ids) if unlocks.pool else None,
        }, indent=2))
        return 0

    print(unlocks.report())
    print()
    for recipe_id in unlocks.recipe_ids:
        print(f"  {recipe_id}")
    return 0


# --- solve ---------------------------------------------------------------

def _print_response(response, data) -> None:
    print(f"{'recipe':46s} {'machines':>9} {'producer':>26}")
    for use in response.recipes:
        print(f"  {use.recipe_id:44s} {use.machine_equivalents:9.4f} {use.producer_class:>26}")
    print()
    print("machines")
    for machine in response.machines:
        print(f"  {machine.producer_class:44s} {machine.effective_count:9.4f}"
              f"   build {machine.physical_count_if_rounded}")
    print()
    print("raw inputs")
    for raw in response.raw_inputs:
        print(f"  {raw.item_id:44s} {raw.rate_per_min:9.4f}/min")
    print()
    p = response.power
    print(f"power   scenario {p.scenario_mw:.4f} MW   canonical {p.canonical_mw:.4f} MW"
          f"   range {p.min_mw:.4f}–{p.max_mw:.4f}")
    print()
    for warning in response.warnings:
        print(f"! {warning}")


def cmd_solve(args) -> int:
    unlocks = _unlocks(args)
    data = _data(args)
    try:
        response = _backend(args).solve(_request(args, unlocks.allowed_recipes), data)
    except Infeasible as exc:
        raise SystemExit(f"infeasible: {exc}") from None
    except SolverFailure as exc:
        raise SystemExit(f"solver failure: {exc}") from None

    if args.json:
        print(json.dumps({
            "recipes": [{"recipe_id": u.recipe_id, "producer_class": u.producer_class,
                         "machine_equivalents": u.machine_equivalents,
                         "cycles_per_min": u.cycles_per_min} for u in response.recipes],
            "raw_inputs": [{"item_id": r.item_id, "rate_per_min": r.rate_per_min}
                           for r in response.raw_inputs],
            "machines": [{"producer_class": m.producer_class,
                          "effective_count": m.effective_count,
                          "physical_count_if_rounded": m.physical_count_if_rounded}
                         for m in response.machines],
            "power": {"scenario_mw": response.power.scenario_mw,
                      "canonical_mw": response.power.canonical_mw,
                      "min_mw": response.power.min_mw, "max_mw": response.power.max_mw},
            "warnings": list(response.warnings),
        }, indent=2))
        return 0

    print(unlocks.report())
    print()
    _print_response(response, data)
    return 0


# --- compare -------------------------------------------------------------

def _variants(args):
    axis, _, raw = args.vary.partition(":")
    values = [v.strip() for v in raw.split(",") if v.strip()]
    if len(values) < 2:
        raise SystemExit(f"error: --vary needs at least two values, got {raw!r}")

    out = []
    for value in values:
        if axis == "power-statistic":
            unlocks, data = _unlocks(args), _data(args)
            out.append(Variant(value, _request(args, unlocks.allowed_recipes), data,
                               _backend(args, value)))
        elif axis == "weights":
            if value not in WEIGHT_PRESETS:
                raise SystemExit(f"error: unknown weights preset {value!r}; "
                                 f"try {sorted(WEIGHT_PRESETS)}")
            unlocks, data = _unlocks(args), _data(args)
            out.append(Variant(value, _request(args, unlocks.allowed_recipes,
                                               WEIGHT_PRESETS[value]), data, _backend(args)))
        elif axis == "pool":
            wide = value in ("on", "true", "yes")
            unlocks = at_tier(REPO, args.tier, declared=_declared(args), include_pool=wide)
            out.append(Variant(value, _request(args, unlocks.allowed_recipes), _data(args),
                               _backend(args)))
        elif axis == "tier":
            unlocks = at_tier(REPO, int(value), declared=_declared(args), include_pool=args.pool)
            out.append(Variant(f"tier{value}", _request(args, unlocks.allowed_recipes),
                               _data(args), _backend(args)))
        elif axis == "scenario":
            if value not in SCENARIO_PRESETS:
                raise SystemExit(f"error: unknown scenario {value!r}; "
                                 f"try {sorted(SCENARIO_PRESETS)}")
            data = load(REPO).with_scenario(SCENARIO_PRESETS[value])
            unlocks = _unlocks(args)
            out.append(Variant(value, _request(args, unlocks.allowed_recipes), data,
                               _backend(args)))
        else:
            raise SystemExit(
                f"error: unknown axis {axis!r}; try power-statistic, weights, pool, "
                "tier, scenario"
            )
    return out


def cmd_compare(args) -> int:
    comparison = compare(_variants(args))
    if args.json:
        print(json.dumps({
            "variants": [{"label": v.label, "objective": v.objective,
                          "power_stat_mw": v.power_stat_mw,
                          "raw_total_per_min": v.raw_total_per_min,
                          "machine_total": v.machine_total,
                          "recipe_ids": sorted(v.recipe_ids)} for v in comparison.variants],
            "regret": {f"{a}|{b}": v for (a, b), v in comparison.regret.items()},
            "incomparable": {f"{a}|{b}": v for (a, b), v in comparison.incomparable.items()},
        }, indent=2))
        return 0

    print(comparison.format_table())
    print()
    for (a, b), (only_a, only_b) in sorted(comparison.recipe_differences.items()):
        if only_a or only_b:
            print(f"{a} only: {list(only_a)}")
            print(f"{b} only: {list(only_b)}")
    return 0


# --- parser --------------------------------------------------------------

def _add_common(parser, *, targets: bool) -> None:
    parser.add_argument("--tier", type=int, required=True, help="tech tier reached")
    parser.add_argument("--pool", action="store_true",
                        help="also allow alternates obtainable at this tier without research")
    parser.add_argument("--declared", action="append", metavar="RECIPE_ID",
                        help="a recipe you hold that the tier does not grant; repeatable")
    parser.add_argument("--declared-file", metavar="PATH",
                        help="file of recipe ids, one per line, # comments allowed")
    parser.add_argument("--json", action="store_true")
    if targets:
        parser.add_argument("--target", action="append", metavar="ITEM=RATE", required=True)
        parser.add_argument("--cap", action="append", metavar="ITEM=RATE",
                            help="upper bound on a raw resource; repeatable")
        parser.add_argument("--scenario", choices=sorted(SCENARIO_PRESETS), default="canonical")
        parser.add_argument("--power-statistic", choices=[s.value for s in PowerStatistic],
                            default="mean", help="D2 is deferred; this is not a default anyone chose")
    for name in REFUSALS:
        parser.add_argument(f"--{name.replace('_', '-')}", help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="production_cli",
        description="Cost a production target, or compare configurations. "
                    "Answers nothing about time, inventory or geography.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    tiers = sub.add_parser("tiers", help="what a tech tier grants, and what it withholds")
    _add_common(tiers, targets=False)
    tiers.add_argument("--find", metavar="TEXT",
                       help="look up recipe ids whose display name contains TEXT")
    tiers.set_defaults(func=cmd_tiers)

    solve = sub.add_parser("solve", help="plan a target")
    _add_common(solve, targets=True)
    solve.add_argument("--weights", choices=sorted(WEIGHT_PRESETS), default="balanced")
    solve.set_defaults(func=cmd_solve)

    comp = sub.add_parser("compare", help="two or more configurations, side by side")
    _add_common(comp, targets=True)
    comp.add_argument("--weights", choices=sorted(WEIGHT_PRESETS), default="balanced")
    comp.add_argument("--vary", required=True, metavar="AXIS:A,B[,C]",
                      help="power-statistic:min,mean,max | weights:balanced,resources | "
                           "pool:off,on | tier:2,4 | scenario:canonical,challenge")
    comp.set_defaults(func=cmd_compare)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "tier", 0) < 0:
        raise SystemExit("error: --tier must be non-negative")
    _refuse(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
