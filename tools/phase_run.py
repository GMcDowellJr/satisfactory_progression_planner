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

**D6 (crossover A23): standing at phase open.** `run` takes a
`stock.StandingLanes` or None (nothing standing), and never looks one up. The
CLI resolves it, in this order (project doc D6, "Resolution order"):

    1  --standing FILE                 DECLARED
    2  player_state/phase<N-1>.toml    SAVED_PLAN (N-1, its rate)
    3  a run of phase N-1 at 1/min     PLACEHOLDER, itself resolved by 1-3
    phase 1                            none: nothing is placed before it

`--save` writes the phase's have-after (per lane standing + to build, and
the infrastructure) to player_state/phase<N>.toml; phase N+1 reads it. The
directory is gitignored: it is the player's state, not canon (D6 O2).

A declaration carries either BOOTSTRAP (declared outright, phase 1) or
PREVIOUS_TIER + POWER_STEP (A19 derived + A20 declared); both is refused
(D6 Amendment 2 P1). Standing INFRASTRUCTURE nets the declared step only,
before A20's addition; the A19 minimum is never netted (D6 O4).
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib
import sys
import tomllib
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


#: D6 O2 (proposed default, taken 2026-09-24): gitignored player state
PLAYER_STATE = REPO / "player_state"
#: D6 O3: the placeholder N-1 runs at 1/min on its anchor (phase 1: T = 50)
PLACEHOLDER_RATE = 1.0


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
    #: None when the declaration declares BOOTSTRAP outright (phase 1)
    derived: stock.DerivedBootstrap | None
    bootstrap: stock.BootstrapSet
    report: object  # goal_run.PacedRunReport
    #: D6. The standing list the run netted against; None: nothing standing
    standing: stock.StandingLanes | None = None
    #: D6 O4. The declared step netted against standing infrastructure
    infrastructure: stock.NetInfrastructure | None = None
    #: the rate the run was sized at, as passed; a saved plan records it
    anchor_rate_per_min: float = 1.0


def _declared_step(decl):
    """(derived-or-None inputs, the declared step) per D6 Amendment 2 P1."""
    has_boot = hasattr(decl, "BOOTSTRAP")
    has_a19 = hasattr(decl, "POWER_STEP") or hasattr(decl, "PREVIOUS_TIER")
    if has_boot and has_a19:
        raise PhaseRunError(
            f"phase {decl.PHASE}: BOOTSTRAP is declared beside POWER_STEP/PREVIOUS_TIER. "
            "A declaration is either a declared bootstrap or A19 + a power step"
        )
    if not has_boot and not (hasattr(decl, "POWER_STEP") and hasattr(decl, "PREVIOUS_TIER")):
        raise PhaseRunError(
            f"phase {decl.PHASE}: declare BOOTSTRAP, or PREVIOUS_TIER and POWER_STEP"
        )
    return has_boot, (decl.BOOTSTRAP if has_boot else decl.POWER_STEP)


def run(decl, *, anchor_rate_per_min: float = 1.0, repo: pathlib.Path = REPO,
        standing: stock.StandingLanes | None = None) -> PhaseRun:
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
    declared, step = _declared_step(decl)
    if standing is None:
        infra = None
        owed_step = step
    else:
        infra = stock.net_infrastructure(step, standing)
        owed_step = tuple((pc, n) for pc, n in infra.owed.items() if n)
    if declared:
        derived = None
        if not owed_step:
            raise PhaseRunError(
                f"phase {decl.PHASE}: standing infrastructure meets the whole declared "
                "BOOTSTRAP, so there is nothing to bring the next tier online with. "
                "A bootstrap names at least one building; revise the standing list"
            )
        bootstrap = stock.BootstrapSet(tier=decl.RECIPE_TIER, buildings=owed_step)
    else:
        derived = stock.derive_bootstrap(
            data, tuple(u.recipe_id for u in backend.solve(solve, data).recipes),
            open_before=at_tier(repo, decl.PREVIOUS_TIER).recipe_ids,
            extractors_open=unlocks.extractors_open_at_tier(repo, decl.PREVIOUS_TIER),
            tier=decl.RECIPE_TIER,
        )
        bootstrap = (
            stock.add_bootstrap(
                derived.bootstrap,
                stock.BootstrapSet(tier=decl.RECIPE_TIER, buildings=owed_step))
            if owed_step else derived.bootstrap
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
            standing_lanes=standing,
        ),
        horizon_min=rates.horizon_min,
    )
    return PhaseRun(decl=decl, rates=rates, derived=derived, bootstrap=bootstrap,
                    report=report, standing=standing, infrastructure=infra,
                    anchor_rate_per_min=anchor_rate_per_min)


def have_after(pr: PhaseRun) -> tuple[tuple[tuple[stock.LaneKey, int], ...],
                                      tuple[tuple[str, int], ...]]:
    """What stands when the phase closes (D6): per lane, standing + to build of
    the PACED build (surplus lanes keep their machines), and infrastructure =
    standing infrastructure + the declared step's owed buildings. The A19
    derived producers are not carried (they are not lanes and not a declared
    step; A23 names this). Regroupings of returned counts; nothing chosen."""
    paced = pr.report.paced
    if pr.standing is None:
        lanes = goal_run.lanes_of(paced.realization)
        held: dict[str, int] = {}
    else:
        lanes = paced.stock.lane_net.have_after()
        held = dict(pr.standing.infrastructure)
    _, step = _declared_step(pr.decl)
    owed = dict(step) if pr.infrastructure is None else pr.infrastructure.owed
    infra = dict(held)
    for pc, n in owed.items():
        infra[pc] = infra.get(pc, 0) + n
    return lanes, tuple(infra.items())


# --------------------------------------------------------------------------
# D6: player state. A standing list as TOML; read with tomllib, written by hand
# (no new dependency), LF pinned.
# --------------------------------------------------------------------------


def read_standing(path: pathlib.Path, kind: stock.StandingProvenance) -> stock.StandingLanes:
    """A standing file as `kind` (DECLARED for --standing, SAVED_PLAN for a
    saved plan). A saved plan names its phase and rate; a declared file may.
    REFUSED: a missing file, an entry missing a field."""
    path = pathlib.Path(path)
    if not path.exists():
        raise PhaseRunError(f"standing file {path} does not exist")
    doc = tomllib.loads(path.read_text(encoding="utf-8"))
    head = doc.get("plan", {})
    try:
        lanes = tuple(((e["bus"], e["recipe"], e["class"]), int(e["count"]))
                      for e in doc.get("lane", ()))
        infra = tuple((e["class"], int(e["count"])) for e in doc.get("infrastructure", ()))
    except KeyError as missing:
        raise PhaseRunError(f"{path}: an entry lacks {missing}") from None
    return stock.StandingLanes(
        lanes=lanes, infrastructure=infra,
        source=stock.StandingSource(
            kind=kind, phase=head.get("phase"),
            anchor_rate_per_min=head.get("anchor_rate_per_min"), path=str(path)),
    )


def _q(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def write_plan(pr: PhaseRun, path: pathlib.Path) -> pathlib.Path:
    """The have-after of `pr` as TOML at `path`. States the provenance of the
    standing the plan itself netted against, so a chain of placeholders is
    visible in the file."""
    lanes, infra = have_after(pr)
    src = pr.standing.source if pr.standing is not None else None
    anchor = pr.anchor_rate_per_min
    out = [
        "# D6 have-after, written by tools/phase_run.py --save. Edit it and pass",
        "# it with --standing to declare what actually stands.",
        "[plan]",
        f"phase = {pr.decl.PHASE}",
        f"anchor_rate_per_min = {anchor!r}",
        f"netted_against = {_q(src.kind.name if src else 'NONE')}",
        "",
    ]
    for (bus, recipe, pc), n in lanes:
        out += ["[[lane]]", f"bus = {_q(bus)}", f"recipe = {_q(recipe)}",
                f"class = {_q(pc)}", f"count = {n}", ""]
    for pc, n in infra:
        out += ["[[infrastructure]]", f"class = {_q(pc)}", f"count = {n}", ""]
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8", newline="\n")
    return path


def resolve_standing(phase: int, *, standing_path: pathlib.Path | None = None,
                     state_dir: pathlib.Path = PLAYER_STATE,
                     repo: pathlib.Path = REPO) -> stock.StandingLanes | None:
    """D6 resolution order. Recursion on phase - 1 terminates at phase 1."""
    if standing_path is not None:
        return read_standing(standing_path, stock.StandingProvenance.DECLARED)
    if phase <= 1:
        return None
    saved = pathlib.Path(state_dir) / f"phase{phase - 1}.toml"
    if saved.exists():
        return read_standing(saved, stock.StandingProvenance.SAVED_PLAN)
    prev = run(declaration(phase - 1), anchor_rate_per_min=PLACEHOLDER_RATE, repo=repo,
               standing=resolve_standing(phase - 1, state_dir=state_dir, repo=repo))
    lanes, infra = have_after(prev)
    return stock.StandingLanes(
        lanes=lanes, infrastructure=infra,
        source=stock.StandingSource(
            kind=stock.StandingProvenance.PLACEHOLDER, phase=phase - 1,
            anchor_rate_per_min=PLACEHOLDER_RATE),
    )


def sheet_of(pr: PhaseRun):
    return rate_sheet.sheet(
        pr.report.paced.realization, pr.report.paced.goals, phase=pr.decl.LABEL,
        anchor_goal_id=pr.rates.anchor_goal_id, horizon_min=pr.report.horizon_min,
    )


def standing_of(pr: PhaseRun):
    """The D6 table for `pr`: the paced build's lanes, as returned."""
    return rate_sheet.standing(
        pr.report.paced.stock.lane_net,
        source=pr.standing.source if pr.standing is not None else None,
        infrastructure=pr.infrastructure,
        payment=pr.report.bootstrap_payment,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--phase", type=int, required=True)
    ap.add_argument("--anchor-rate", type=float, default=1.0,
                    help="anchor goal rate per minute; the run is sized at this rate")
    ap.add_argument("--standing", type=pathlib.Path, default=None,
                    help="a DECLARED standing file; else the saved phase N-1 plan, "
                         "else a placeholder run of phase N-1 at 1/min (D6)")
    ap.add_argument("--save", action="store_true",
                    help="write this phase's have-after to player_state/phase<N>.toml")
    ap.add_argument("--state-dir", type=pathlib.Path, default=PLAYER_STATE,
                    help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    decl = declaration(a.phase)
    standing = resolve_standing(a.phase, standing_path=a.standing, state_dir=a.state_dir)
    pr = run(decl, anchor_rate_per_min=a.anchor_rate, standing=standing)
    data = pr.report.paced.data
    print(rate_sheet.render(sheet_of(pr), data))
    print(rate_sheet.render_standing(standing_of(pr), data))
    if a.save:
        path = write_plan(pr, pathlib.Path(a.state_dir) / f"phase{a.phase}.toml")
        print(f"\n  saved have-after to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
