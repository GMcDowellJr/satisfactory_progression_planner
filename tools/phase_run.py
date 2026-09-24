#!/usr/bin/env python3
"""Run one declared phase at a player's anchor rate, and print its rate sheet.

Greg, 2026-09-24 ("Python module + CLI"). The declaration lives in
`tools/phases/phase<N>.py`; this module composes it with the layers exactly as
tests/test_phase_two_run.py did, and nothing more:

    goals      goal_run.goals_for_phases(PHASE); anchor = the goal on ANCHOR_ITEM
    rates      schedule.phase_rates at the anchor rate the caller passes
    solve      those rates as targets, recipes at_tier(RECIPE_TIER)
    bootstrap  stock.derive_bootstrap (A19) + POWER_STEP (A20), by addition
    run        goal_run.paced_run; unlocks = every schematic in TIERS

**Another rate is another run** (A21). The anchor rate is an input to the run,
never a factor applied to a sheet. Nothing here chooses a recipe, a partition
or a bootstrap: each comes from the declaration or a layer.

    uv run python tools/phase_run.py --phase 2 --anchor-rate 3
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
from dataclasses import dataclass

REPO = pathlib.Path(__file__).resolve().parents[1]
for _src in ("production_adapter", "progression", "realization"):
    _path = str(REPO / "tools" / _src / "src")
    if _path not in sys.path:
        sys.path.insert(0, _path)

from production_adapter import OutputTarget, SolveRequest, load  # noqa: E402
from production_adapter.gamedata import load_construction, load_logistics  # noqa: E402
from production_adapter.lp_backend import LpBackend, PowerStatistic  # noqa: E402
from progression import at_tier, schedule, stock, unlocks  # noqa: E402
from realization import RealizationRequest  # noqa: E402


def _load(name: str, path: pathlib.Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


goal_run = _load("goal_run", REPO / "tools" / "goal_run.py")
rate_sheet = _load("rate_sheet", REPO / "tools" / "rate_sheet.py")


class PhaseRunError(ValueError):
    """A phase with no declaration, or a declaration the run cannot use."""


def declaration(phase: int):
    path = REPO / "tools" / "phases" / f"phase{phase}.py"
    if not path.exists():
        raise PhaseRunError(f"no declaration for phase {phase}: {path} does not exist")
    return _load(f"phases_phase{phase}", path)


@dataclass(frozen=True)
class PhaseRun:
    decl: object
    rates: schedule.PhaseRates
    derived: stock.DerivedBootstrap
    bootstrap: stock.BootstrapSet
    report: object  # goal_run.PacedRunReport


def run(decl, *, anchor_rate_per_min: float = 1.0, repo: pathlib.Path = REPO) -> PhaseRun:
    data = load(repo)
    pa = stock.load_project_assembly(repo, data)
    goals = goal_run.goals_for_phases(data, pa, (decl.PHASE,))
    anchor = [g for g, i, _ in goals if i == decl.ANCHOR_ITEM]
    if len(anchor) != 1:
        raise PhaseRunError(
            f"phase {decl.PHASE}: ANCHOR_ITEM {decl.ANCHOR_ITEM} names "
            f"{len(anchor)} goals; it must name exactly one"
        )
    rates = schedule.phase_rates(goals, anchor_goal_id=anchor[0],
                                 anchor_rate_per_min=anchor_rate_per_min)
    backend = LpBackend(power_statistic=PowerStatistic.MEAN)
    solve = SolveRequest(
        outputs=tuple(OutputTarget(i, r) for _, i, r in rates.rates),
        allowed_recipes=at_tier(repo, decl.RECIPE_TIER).allowed_recipes,
    )
    derived = stock.derive_bootstrap(
        data, tuple(u.recipe_id for u in backend.solve(solve, data).recipes),
        open_before=at_tier(repo, decl.PREVIOUS_TIER).recipe_ids,
        extractors_open=unlocks.extractors_open_at_tier(repo, decl.PREVIOUS_TIER),
        tier=decl.RECIPE_TIER,
    )
    bootstrap = stock.add_bootstrap(
        derived.bootstrap,
        stock.BootstrapSet(tier=decl.RECIPE_TIER, buildings=decl.POWER_STEP),
    )
    report = goal_run.paced_run(
        data=data,
        backend=backend,
        solve=solve,
        logistics=load_logistics(repo),
        realization=RealizationRequest(design_tier=decl.DESIGN_TIER, buses=decl.BUSES),
        goals=goals,
        construction=load_construction(repo),
        declared_stock=goal_run.StockDeclaration(
            bootstrap=bootstrap,
            unlocks=unlocks.schematics_in_tiers(repo, decl.TIERS),
            unlock_costs=unlocks.schematic_costs(repo),
        ),
        horizon_min=rates.horizon_min,
    )
    return PhaseRun(decl=decl, rates=rates, derived=derived, bootstrap=bootstrap, report=report)


def sheet_of(pr: PhaseRun):
    return rate_sheet.sheet(
        pr.report.paced.realization, pr.report.paced.goals, phase=pr.decl.LABEL,
        anchor_goal_id=pr.rates.anchor_goal_id, horizon_min=pr.report.horizon_min,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--phase", type=int, required=True)
    ap.add_argument("--anchor-rate", type=float, default=1.0,
                    help="anchor goal rate per minute; the run is sized at this rate")
    a = ap.parse_args(argv)
    pr = run(declaration(a.phase), anchor_rate_per_min=a.anchor_rate)
    print(rate_sheet.render(sheet_of(pr), pr.report.paced.data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
