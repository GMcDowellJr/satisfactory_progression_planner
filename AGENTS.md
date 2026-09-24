# AGENTS.md

Instructions for coding agents working in this repository. Read this first;
then read the decision record that governs whatever you are about to touch.

## What this repo is

A Satisfactory **world-analysis and progression planner**, not a machine-count
calculator. Production solving is a subordinate capability; the product lives
above it (scenario modifiers, Project Assembly pacing, unlock awareness, stock
and power accounting, later world/district integration). See `README.md`,
`planning_data/ARCHITECTURE.md` and
`docs/plans/progression_optimizer_implementation_plan.md`.

Build **502094 / Satisfactory 1.2.4.0** is the default-world *test fixture*,
not the architecture. Don't write anything that only works for that map.

## Layout

    planning_data/          canonical data; its own manifest.csv
      game/reference/       build-pinned game facts (items, recipes, buildings, unlocks)
      world/                versioned world extraction (sockets, terrain, POIs)
      planning/             planner model, plans, strategies, playthrough state
      analysis/             derived analyses; analysis/derived/ is gitignored
    tools/
      production_adapter/   the only seam to the solver; gamedata.py is the ONLY
                            code that knows CSV filenames/columns
      realization/          buses, residuals, realize(); may not become a solver
      progression/          unlocks, stock pass, power, schedule, lag, pool
      busmodel/             the oracle: reproduces published tables, checks realization
      phases/phase<N>.py    phase declarations (data, not logic)
      *.py at tools/ root   cross-package joints/CLIs: goal_run, phase_run,
                            production_cli, rate_sheet, chain_view, storage_view,
                            regenerate_manifests, check_game_docs_provenance
      build_surface_tool/, corridor_tool/, multisurface_tool/,
      satisfactory_route_tool/, world_viewer/   world-analysis tools (spatial)
    scripts/                orchestration wrappers for the spatial tools
    tests/                  cross-package tests + conftest that wires sys.path
    docs/decisions/         decision records (immutable, amended forward)
    docs/plans/             the source implementation plan
    research/               solver evaluation scratch, kept for provenance
    Claude outputs/         agent-session artefacts (design notes, handoffs)

## Running things

Python 3.11+, managed with `uv`. The repo is **not installed**
(`[tool.uv] package = false`); `tests/conftest.py` and each package's own
conftest put the `src/` trees on `sys.path`.

    uv run pytest -q                                   # full suite (~10 s)
    uv run pytest tests/test_goal_run.py               # one file
    uv run python tools/phase_run.py --phase 2 --anchor-rate 3
    uv run python tools/goal_run.py ...
    python tools/regenerate_manifests.py               # --check (default)

Baseline on a clean clone, Linux container, 2026-09-24: **925 passed,
1 skipped**. Don't quote a suite count you didn't collect. `@parametrize`
cases count separately, and predictions have been wrong before.

`pytest` only collects the `testpaths` in `pyproject.toml`: `tests/`,
`tools/production_adapter/tests`, `tools/realization/tests`,
`tools/busmodel/tests`. The spatial tools' `tests/` dirs are **not** in the
default run.

## Hard rules

### Import boundaries are tests, not docstrings

Layers import downward only. Each boundary is asserted by an AST-scanning test.
If one fails, your design is wrong. Don't fix it by editing the test.

- `realization` may import `production_adapter.contracts` and `.gamedata`
  only. Never `.backend`, `.lp_backend`, `.analysis`, or scipy
  (`tools/realization/tests/test_import_boundary.py`).
- `progression` may import `production_adapter.contracts/.gamedata/.scenario`.
  Only `progression/stock.py` may import `realization.contracts`, and
  `__init__` must not eagerly import `stock`
  (`tests/test_progression_import_boundary.py`).
- `busmodel` opens no files and may not import `realization.buses`,
  `.residual`, or `.realize`. An oracle that can reach the code it checks is not
  an oracle (`tools/busmodel/tests/test_busmodel_import_boundary.py`).
- Nothing in `production_adapter` imports upward.
- A joint above several packages goes at `tools/` root (like `goal_run.py`),
  never inside one of them.

### One loader

`production_adapter/gamedata.py` is the only code that knows CSV filenames and
column names. Don't read `planning_data/game/reference/*.csv` anywhere else. Go
through `gamedata.load(repo_root)`.

### Canonical data is not scenario data

Don't write challenge-run settings (input multipliers, power multipliers,
Project Assembly multipliers) into reference tables. Scenario modifiers are
applied at runtime by `production_adapter.scenario`.

### Layers report; they don't choose

Many modules are guarded against making decisions nobody made: no `min`, `max`,
`sorted` or ranking in the driver, no machine count derived inside the stock
pass, no default for `power_statistic`, no parsing English prose into a tier
mapping. When a value would need a choice, take it as a declared input or
refuse by name. Don't pick a plausible default. Guardrail tests in
`tests/test_goal_run.py`, `tests/test_progression_*` and the realization tests
enforce this.

### Refuse, don't guess

Ambiguous or unresolvable inputs (an unknown item, a display name matching zero
or several rows, a half-supplied optional pair) raise a named error or show up
in an `unresolved` list. Don't coerce them silently.

## Tests

- **Test file basenames must be unique across all `testpaths`.** There is no
  `__init__.py`, so a duplicate basename breaks the whole collection. Before
  adding a test file, check all four dirs.
- A conftest must not rely on another conftest having run. Check a new test
  both in the full suite and on its own
  (`uv run pytest tests/test_x.py`).
- Guardrail tests should be mutation-checked: break the property once, see
  the test fail, and restore it.
- Don't skip, xfail or delete a test to get green. A test that pins a known
  data gap and "deletes itself when the data closes it" is intentional.

## Manifests

Two integrity manifests: `REPO_MANIFEST.csv` (repo-relative) and
`planning_data/manifest.csv` (relative to `planning_data/`). Both are
`path,bytes,sha256`, sorted, with CRLF line endings. They hash **working-copy
bytes**. The scope is declared in `tools/regenerate_manifests.py`. At the repo
root, only the files listed in `root_files` are covered.

- Convention: every content commit is followed by a separate
  `Regenerate manifests` commit (`python tools/regenerate_manifests.py --write`).
- `.gitattributes` makes a checkout's bytes the same on every platform. Text
  is LF in the index and in the working copy, and the two manifests are
  `-text` so their CRLF is stored as written. `--check` on a fresh clone is
  in sync anywhere, and `--write` is safe from a container.
- **Writers can still put CRLF in a working copy.** `csv.writer` defaults to
  `"\r\n"`, and text-mode writes on Windows translate `"\n"`. Git stores LF
  on commit, but the file on disk stays CRLF, and a manifest written then
  hashes bytes no clone will have. After a script rewrites a data file,
  commit it and refresh the working copy before `--write`
  (delete the file, then `git checkout -- <file>`). Better still, write LF
  (`newline=""` plus `lineterminator="\n"`).
- Adding a directory or a root-level file to the integrity baseline means
  changing the scope in `regenerate_manifests.py`. Do that on purpose, never
  as a side effect.

## Decision records and docs

- `docs/decisions/*.md` are **immutable decision records, amended forward**.
  Never rewrite a past section. Add an amendment
  (`## Amendment N — <date>. <title>`, with `AN.1` sub-sections) and supersede
  explicitly. Crossover amendments (A13, A14, ... A22) live in
  `bus_level_recompute_and_alternate_crossover.md`, and commit subjects cite
  them.
- Design notes (for example in `Claude outputs/`) are current-state and may
  be corrected in place.
- Every figure should say where and when it was measured (machine, date,
  commit) and be **run**, not derived as "prior figure plus a delta". Separate
  measured values from predicted ones.
- Greg makes decisions. Record them as "decided by Greg, <date>". Propose
  options; don't settle open design questions on your own.

## Commits

- Subject: imperative, names the layer and cites the amendment when there is
  one, e.g. `Phase declaration module + phase_run CLI; ... (crossover A22)`.
- Body: what changed per file, then the measured test result and where it ran
  (`Container: 925 passed, 1 skipped.`).
- When a commit fixes an earlier one, fix forward and name the earlier commit.
  Don't rewrite pushed history.
- Commit message drafts (`COMMIT_MSG*.txt`) are gitignored scratch. Pass one
  with `git commit -F` and then delete it.
- Before you describe an edit as done, check the exit status of the script
  that made it. A heredoc can die halfway through and still leave a plausible
  file behind.

## Style

Match the surrounding code. Docstrings are dense and explain *why* a
constraint exists and which decision set it, citing the section or amendment
(for example `§8.1`, `A20`). Use frozen dataclasses and typed contracts, and
`from __future__ import annotations`. No new runtime dependencies at the root:
the `dev` group is `pytest`, `numpy`, `scipy`, and each addition there is
justified in a comment.
