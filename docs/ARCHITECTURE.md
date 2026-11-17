# Architecture — current specification

- Status: **current.** This file is corrected in place when the architecture
  changes. Decision records stay immutable and are amended forward; this
  document says which of them govern.
- Adopted: site-planner reframe Amendments 15–17 (decided by Greg, 2026-11-17).
- Last revised: 2026-11-17 (architecture reconciliation R3).
- Scope: the whole repository. `planning_data/ARCHITECTURE.md` covers the data
  layout only.

Read this first. Then read the governing decision named in §6 for whatever you
are about to touch. Records listed as **archived** in `docs/decisions/README.md`
are historical evidence: cite them for why something is the way it is, never as
a current requirement.

---

## 1. What the tool is

A Satisfactory **world-analysis and progression planner**. It answers three
kinds of question, in three tracks over one shared core:

| Track | Question | Method | Status |
|---|---|---|---|
| **Site portfolio** | What can be made where, and how do the sites connect? | Supply-bounded LP over declared sites and claimed sockets | Built (`portfolio_run.py`, `site_planner_web/`) |
| **Run planner** | What is next, and what would reaching a declared target take? | Demand-driven: a declared target and horizon give the rates, then the LP gives the plan | Built (R9: `run_plan.py` → `run-plan/1`; `to_factory_inputs` hands a step to the factory planner) |
| **Factory planner** | What can this factory deliver from what it has? | Supply-driven, the default for the current factory: maximise a **declared** goal mix within available supply | Built (R7: `factory_run.py`, `factory-inputs/1` → `factory-plan/1`; R8: `progression.timeline`) |

How the tracks connect:
- The run planner's output (`run-plan/1`, ordered steps) can feed the factory
  planner.
- The factory planner also accepts a hand-declared input: what is available,
  plus goals.
- The factory result goes back as a report. It never edits the run plan.
- The site-portfolio track is independent and unchanged.

What the tool never does (unchanged from the reframe):
- choose for the player: no hidden ranking, no default that stands in for a
  decision;
- invent a target or a product mix that was not declared;
- duplicate the canonical game data or the solver.

Physical factory layout and SFMD import are **not adopted**. The Nov-10
factory-design specification is archived as a proposal.

---

## 2. Layers and import direction

```
CLIENTS        site_planner_web (Pyodide: runs this repo's Python; no maths in JS)
TRACKS         tools/*.py root joints, one versioned record each
PROGRESSION    tools/progression      unlocks, pool, schedule, lag, stock, power, district
                                      playthrough, availability (R5), infrastructure (R6), timeline (R8)
REALIZATION    tools/realization      buses, residual, realize: whole machines, clocks, belts
                                      (steady state per bus; may not become a solver)
CORE           tools/production_adapter
                 gamedata    the ONLY reader of planning_data/game/reference/*.csv
                 scenario    R / P / E transforms and rounding
                 lp_backend  solve (demand) / solve_district / solve_portfolio (supply), HiGHS
                 analysis    recipe-set comparison
ORACLE         tools/busmodel         independent re-derivation; imports no realization internals
WORLD          planning_data/world + spatial tools (route, build_surface, corridor,
               multisurface, world_viewer): no production imports
```

Layers import downward only. Each rule is an AST test; if one fails, the
design is wrong, not the test:

- realization → `production_adapter.contracts/.gamedata` only
  (`tools/realization/tests/test_import_boundary.py`).
- progression → `production_adapter.contracts/.gamedata/.scenario`. Only
  `stock` may import `realization.contracts`, and `progression/__init__` does
  not import `stock` eagerly (`tests/test_progression_import_boundary.py`).
- busmodel opens no files and reaches no realization internals
  (`tools/busmodel/tests/test_busmodel_import_boundary.py`).
- **One loader**: no module in `tools/` outside `gamedata.py` builds a path
  into `game/reference` (`tests/test_one_loader.py`, R1). Two exceptions,
  with reasons, are listed in §7.
- A joint above several packages goes at `tools/` root, never inside one.

**Reading vs meaning.** `gamedata` reads tables into typed rows and does not
interpret them. Progression meaning (what a tier grants, what the pool holds,
which extractor is open) lives in `progression`. That is how the one-loader
rule and solver-selection §6 ("the adapter never sees a progression concept")
both hold.

---

## 3. Calculation authority

Each concept has one owner. "Planned" means the owner is decided and the
module is not built yet.

| Concept | Owner | Governing source |
|---|---|---|
| Item, recipe, building identity | `gamedata` | resource_authority (carried, A15.4) |
| R / P / E transforms, rounding | `scenario.Scenario` | demand §3.2.4–3.2.5, A2, A5, A6; reframe A7 |
| Sub-1× floor | `scenario` | A15.2 (B4): solids fixed at 1 (`SOLID_INPUT_FLOOR`, R4); fluid floor declared (`fluid_input_floor`), open until the 0.25× Plastic read |
| Recipe set at a tier | `progression.unlocks.at_tier` | LP §18 rule (carried) |
| Availability from milestones owned | `progression.availability` (R5); grant joins shared with `at_tier` (`unlocks.recipe_grants`, `extractors_open`, `generators_open`) | A15.2 (Q2) |
| Recipe status (owned / in pool / MAM research / locked) | `progression.availability.RecipeStatus` (R5) | A15.2 (B5, Q3) |
| Hard-drive pool | `progression.pool` (automatic entry) | LP §19 (carried) |
| Playthrough state (milestones, research and alternates owned) | `progression.playthrough` (R5) | A15.2 |
| Resource supply and socket claims | `site_card.load_sockets` (reader), `portfolio_run` (no double claim) | reframe A9, A10 |
| Extractor and belt marks per socket and link | `progression.infrastructure` (R6): policy `highest_then_step_down` | A15.2 (B2, Q1) |
| Production solve | `lp_backend` | reframe A2, A3, A6, A13; LP record (carried as implementation) |
| Byproducts | used by the solve where useful; leftovers disposed of by `progression.byproducts`: solids with sink points → AWESOME Sink, solids without (nuclear waste) `unsinkable`, Fuel → power, HOR → Residual Fuel → power, other fluids `needs_packaging`; generator fuel, water and waste folded in first | reframe A8.3, **A16**, **A17** |
| Whole machines, clocks, belts | `realization` | carried as implementation |
| Power, solve side | `lp_backend` power row + `progression.district` composers | reframe A3–A7, A11; staged generation ledger **proposed** for the run and factory tracks (A16.3, questions P1–P4) |
| Power, report side | `progression.power.ledger` | tests only; candidate for retirement (open) |
| PA demand | `gamedata.load_project_assembly` → `district.compose_bill` / `stock` | demand A1 |
| PA pacing (bill ÷ T) | `progression.schedule` | carried as implementation, demand-side only |
| Storage-priority banks, PA duration | `progression.timeline` (R8): FILLING then FULL segments, smart or standard splitter, container options by unlock | A15.2 (B3, Q6) |
| Recipe expansion to quantities | `demand_expansion` (tier-blind, primary outputs) | demand A1–A4; its role beside the LP is decided in R9 |

---

## 4. Records and schemas on the wire

| Record | Producer | Status |
|---|---|---|
| `portfolio-inputs/2` | picker, `portfolio_run --inputs` | current (`/1` refused by name, reframe A11.3). Scenario keys pinned (`SCENARIO_KEYS_V2`); `input_amount_floor` null or 1 only (R4) |
| `portfolio-plan/1` | `portfolio_run --export`, worker | current; its echoed scenario gained `fluid_input_floor` (additive, R4) |
| `neighborhoods/1` | `neighborhoods.py` | current |
| `district-plan/1` | `district_run.py` | deprecated with its CLI; no consumer in the repo |
| `factory-inputs/1` | hand-written, or the run planner (R9) | current (R7): every key required, unknown keys refused; `power_statistic` declared (no default, AGENTS.md) |
| `factory-plan/1` | `factory_run.py --export` | current (R7): echoes its inputs; per-socket marks, lanes, power by the draw |
| `run-plan/1` | `run_plan.py --export` | current (R9): horizon, one-machine ceiling, parts, blocked parts with their unlocks, plan, power diagnostic |

Breaking changes bump the major version. Older versions are refused by name or
migrated explicitly, never read as something else.

---

## 5. Workflows

| Entry | Track | Status |
|---|---|---|
| `portfolio_run.py`, `site_planner_web/`, `neighborhoods.py` | site portfolio | current |
| `factory_run.py` | factory planner (supply side) | current (R7) |
| `run_plan.py` | run planner (demand side) | current (R9) |
| `production_cli.py` | core inspection (tiers, solve, compare) | current |
| `demand_expansion_cli.py` (+ Netlify viewer, `netlify.toml`) | quantity datasets | current |
| `phase_run.py` | demand-side phase pacing (goal-paced T) | **deprecated** (A15.3). Ideas ported into the run planner. Library pieces `goal_run`, `schedule`, `stock` stay in use |
| `district_run.py` | hand-declared district solve | **deprecated** (A15.3). Kept as a numerical regression fixture |
| `site_card.py` (CLI) | one-site ceilings | **deprecated** (A15.3). Its socket readers stay in use by portfolio_run and the browser |
| `research/*` | scratch (step planner, link sheet, site links, multiplier studies) | background. Breaks repo rules on purpose; ideas are ported, never imported |

Deprecated means:
- a banner in the module docstring and a one-line notice on stderr;
- every test kept as a regression fixture;
- no new features.

---

## 6. Governing decisions

Current, in force:

- `site_planner_reframe.md`:
  - §1–§5;
  - A1–A11, A13, A14, each "holds until proven wrong";
  - **A15** (2026-11-17: this architecture, the two tracks, B1–B5, Q1–Q6);
  - **A16** (2026-11-17: tie-break fix, by-products to the sink, withdrawals ignored,
    viewers are tests; power ledger proposed);
  - **A17** (2026-11-17: fluid by-products converted or burned before the sink);
  - A12: only Greg's stated facts in A12.2; A12.3 is a proposal.
- `demand_expansion_scope_and_site_capacity.md`: A5 and A6 (in-game reads,
  post-reframe).
- Brought forward explicitly by A15.4, as **observed facts and implemented
  contracts**, not as product mandates:
  - resource_authority (P3);
  - demand §3.2.4–3.2.5 and A2 (rounding reads);
  - crossover A1 and A7 (in-game reads);
  - LP §18 (tier rule, measured) and §19 (pool);
  - production_building_power_model (producer facts);
  - extraction_wiring (provenance stamp).

Everything else under `docs/decisions/`, `docs/plans/` and `docs/product/` is
**archived**: see `docs/decisions/README.md`.

---

## 7. Approved exceptions

| Exception | Reason | Where recorded |
|---|---|---|
| `tools/check_game_docs_provenance.py` reads game/reference directly | audits the raw files themselves (hashes, build stamp) | `tests/test_one_loader.py` |
| `satisfactory_route_tool/poi.py` reads `crash_site_requirements.csv` via its planner package | standalone spatial engine; POI scoring, no production maths | `tests/test_one_loader.py` |
| `tests/` read reference tables raw | an independent oracle must not share the loader it checks | `tests/test_one_loader.py` docstring |
| `research/` breaks repo rules | self-declared scratch; nothing in `tools/` imports it | `research/*/README.md` |
| `demand_expansion` keeps its own recursive expansion beside the LP | different question (quantity totals, exact fractions, declared routes). The run planner uses the LP, not it (R9). Viewers are tests (A16.1), so the viewer is no reason to keep it | A15.5, A16.1 |

---

## 8. Open questions (Greg's to decide; nothing in code settles them)

- Power: the staged generation ledger proposed in reframe A16.3 needs answers to
  P1–P4. Separately, whether `power.ledger` is retired.
- By-products (reframe A17.2): which by-product of the HOR conversion was meant
  (Residual Fuel has none), and whether the disposal power should offset the plan's
  need (it belongs with the power ledger).
- The fluid floor unit at sub-1× R (demand A5.2): needs the 0.25× Plastic read.
- Milestone ordering inside a phase (A15.2 Q2): milestones need not be taken in
  order, or at all. Availability takes a declared set, so this is a UI
  question.
- Scanned-but-unclaimed hard-drive offers and pool odds (A15.2 B5): deferred.
- Storage withdrawals: ignored (A16.1).
- Physical layout, SFMD import, cross-district opportunity cost: deferred.
- **Fixed 2026-11-17 (decided by Greg):** `solve_portfolio` with a declared
  `target_scale` (reframe A13) and bill units of 5 or more came back Infeasible from
  its fourth stage. HiGHS presolve was rejecting a pinned stage that is feasible by
  construction. `LpBackend._run` now re-solves such a stage once without presolve.
  Only a stage that already failed takes that path, so no prior result moves.
  Regression: `tests/test_factory_run.py`.

---

## 9. Refactor status (reconciliation of 2026-11-17)

| Step | What | State |
|---|---|---|
| R0 | manifest header repaired; well-formedness test | done |
| R1 | one loader + AST guard | done |
| R2 | shared `compose_bill`; stale power notes | done |
| R3 | this document, A15, archive index, deprecations | done |
| R4 | solid floor 1 at sub-1× R; fluid floor declared | done (behaviour change recorded in its commit) |
| R5 | playthrough + availability (milestone-level) | done |
| R6 | infrastructure marks + step-down policy | done |
| R7 | factory track (`factory_run`, `factory-inputs/1`, `factory-plan/1`) | done |
| R8 | timeline: storage-priority banks, PA duration | done |
| R9 | run track (`run_plan`, `run-plan/1`) | done |
