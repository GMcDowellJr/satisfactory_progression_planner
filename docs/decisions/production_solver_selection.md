# Production Solver Selection — Phase 0 Decision Record

- Date: 2026-09-18
- Scope: Phase 0 of the Satisfactory Progression Optimizer plan (`docs/plans/progression_optimizer_implementation_plan.md`) only.
- Repo evaluated against: `satisfactory_progression_planner` (canonical reference layer at `planning_data/game/reference/`).
- No solver was written. No repository code was modified.

## State

    decision_status: SUPERSEDED IN PART — see section 10 (2026-09-18 amendment)
    blocking_open_item: Candidate A-prime licence — issue filed 2026-09-18, no response yet
    locked: evaluation evidence in section 3 (reproducible via research harness)
    locked: F1 resolved — HiGHS, for speed and maintenance (Greg, 2026-09-18)
    locked: engine must be permissively licensed; GPL-3.0 is not acceptable even
            though distribution is unlikely (hobby project, but no painted corners)

---

## 1. Headline

**Recommendation: VENDOR COMPONENT from Candidate A (`lunafoxfire/yet-another-factory-planner`)** — import the
single 884-line solver file behind our own adapter, at a pinned commit, with the LP backend swapped.

Formally this is a *fork at a pinned commit with no upstream sync*, because the upstream repository was
deprecated seven days before this evaluation. "TRACK" is not available for any candidate.

Rejected as the production solver: Candidate B (not an optimizer), Candidate D (AGPL + no optimizer).
Reference only: Candidate C (no license, confirmed), Candidate A-prime (no license, confirmed).

---

## 2. Contradiction with the plan, flagged

The plan's section 3 states Candidate A's risk as "upstream activity may be intermittent" and its initial
disposition as "primary fork/adaptation candidate."

Evidence contradicts both framings:

1. **Candidate A is formally deprecated.** Commit `29b0edb` (2026-09-11, seven days before this evaluation)
   added a `# DEPRECATED` header to the README pointing at a successor repo. The last *functional* commit is
   2023-07-15. This is not intermittence; it is end-of-life.
2. **Candidate A's permissive license does not extend to its LP engine.** YAFP's own code is MIT, but the
   solver's only algorithmic dependency is `glpk.js`, published under **GPL-3.0**. The plan's "permissive
   license" advantage does not survive contact with the dependency tree.
3. **A fifth candidate exists that the plan does not know about**: `lunafoxfire/satisfactory-planner`, the
   named successor. It is technically superior on every axis except the one that matters — it has no license.

The plan's *structure* held up. Its *candidate dispositions* did not. Sections 4 and 5 below reflect the
evidence rather than the plan's priors.

---

## 3. Evidence

### 3.1 What was cloned and evaluated

    candidate  repository                                          commit    date
    A          lunafoxfire/yet-another-factory-planner             29b0edb   2026-09-11
    A-prime    lunafoxfire/satisfactory-planner                    a1089cd   2026-09-11
    B          satisfactory-dev/Satisfactory-Production-Calculator c8ae37e   2026-08-16
    C          kentskinner/satisfactory-planner                    d29a908   2026-07-10
    D          satisfactory-factories/application                  6ede1f6   2026-09-18

Note a namespace collision: Candidate C and Candidate A-prime are both named `satisfactory-planner`, under
different owners. Any future `external/` directory must not use the bare repo name.

### 3.2 Candidate A executed against our canonical data

A harness was built that transforms `planning_data/game/reference/*.csv` into Candidate A's `GameData` shape
and calls its `ProductionSolver` directly, headless, with no UI and no upstream game data. Adapter and runners
are in `research/production_solver_evaluation/`.

Fixed-recipe cases, base recipes only, all 291 canonical recipes loaded:

    case                                 ms   recipes  power        raw
    Iron Plate 20/min                    42   2        9.63 MW      Iron Ore 30.00
    Reinforced Iron Plate 5/min          13   5        42.25 MW     Iron Ore 60.00
    Smart Plating 1/min                  38   7        27.31 MW     Iron Ore 23.25
    Versatile Framework 6/min            11   9        201.50 MW    Coal 144.00, Iron Ore 144.00
    Automated Wiring 1.2/min             28   7        31.74 MW     Coal 5.40, Cu 28.80, Fe 5.40
    SP 1 + VF 6 + AW 1.2 (multi-target)  15   17       260.55 MW    Coal 149.40, Cu 28.80, Fe 149.40
    Plastic 100/min (byproduct)          10   1        150.00 MW    Crude Oil 150.00

Automatic optimization over the full recipe set (base + 110 alternates), `complexity = 0`:

    target                     ms   recipes  power       raw total
    SP 1 + VF 6 + AW 1.2       37   27       123 MW      69.3
    Nuclear Pasta 1/min        10   37       586 MW      317.9
    Ballistic Warp Drive 1/min 12   58       1624 MW     1284.6
    AI Expansion Server 1/min  10   45       402 MW      288.1

**Independent reconciliation.** A separate recursive demand propagation written from the CSVs (no solver
involved) reproduces Candidate A's Smart Plating result exactly:

    Recipe_IngotIron_C            0.7750
    Recipe_IronPlateReinforced_C  0.2000
    Recipe_IronPlate_C            0.3000
    Recipe_IronRod_C              0.9500
    Recipe_Rotor_C                0.2500
    Recipe_Screw_C                0.9250
    Recipe_SpaceElevatorPart_1_C  0.5000
    RAW: Iron Ore 23.25/min

Solver output for the same case: `Recipe_IronPlate_C@0.3000 Recipe_IronRod_C@0.9500 Recipe_IngotIron_C@0.7750`,
Iron Ore 23.25. Match to four decimal places, fractional machines preserved.

### 3.3 Scenario transformation works entirely at the adapter layer

The three challenge multipliers were applied during the CSV-to-`GameData` transform. **Zero solver changes.**

    case              scenario            power       raw
    Iron Plate 20     baseline 1.0/1.0    9.63 MW     Iron Ore 30.00
    Iron Plate 20     inputs 1.25x        12.79 MW    Iron Ore 46.88
    Iron Plate 20     power 2.0x          19.25 MW    Iron Ore 30.00
    Iron Plate 20     combined            25.58 MW    Iron Ore 46.88
    Smart Plating 1   baseline            27.31 MW    Iron Ore 23.25
    Smart Plating 1   inputs 1.25x        42.20 MW    Iron Ore 62.41
    Smart Plating 1   combined            84.39 MW    Iron Ore 62.41
    SP1+VF6+AW1.2     combined            872.08 MW   Coal 294.43, Cu 70.31, Fe 294.43

Multi-stage compounding is visible and correct (Smart Plating raw demand rises by more than 1.25x because the
multiplier applies at every stage). This is the single strongest argument for an adapter boundary over a fork:
plan section 1.2 ("canonical facts unchanged, modifiers applied at runtime") is satisfied without touching
solver code.

### 3.4 Pareto behaviour is already available

Sweeping Candidate A's exposed weights produces genuinely distinct solutions on the same target:

    SP1+VF6+AW1.2            weights            recipes  power    raw total
                             balanced           27       123 MW   69.3
                             resources-only     26       191 MW   68.1
                             power-only         21       118 MW   186.9
                             buildings-only     33       205 MW   99.4

Plan section 12's Pareto set is reachable by sweeping these weights and filtering dominated points. No new
solver required for Phase 3.

### 3.5 Where Candidate A breaks

- **`complexity > 0` times out, always.** The weight adds binary variables, turning the LP into a MIP, and
  `TIME_LIMIT = 3.0` is a hardcoded module constant. Every case above failed with `TIMED OUT` at
  `complexity = 1`, including the small SP+VF+AW target. The complexity dimension is unusable against a
  291-recipe 1.2-era dataset without a fork change.
- **Extraction power is hardcoded.** The report pass reads `Desc_WaterPump_C`, `Desc_OilPump_C` and
  `Desc_MinerMk3_C` by literal key and divides by literal `120`, `120`, `240`. Miner tier, purity and the
  `machine_power_multiplier` cannot reach it. This produced the harness's first failure mode
  (`Cannot read properties of undefined (reading 'power')`) before those three keys were synthesized.
- **Build cost / area reporting is dead weight for us.** `totalBuildArea`, `estimatedFoundations`,
  `totalMaterialCost` and `buildingsUsed[].materialCost` all derive from `BuildingsInfo.area` and
  `.buildCost`, neither of which our reference layer populates.

### 3.6 Candidate B is a resolver, not an optimizer

Confirmed from source, not documentation:

- `lib/types.ts` defines `recipe_selection = {[item]: Recipe_*_C | Build_*_C}` — the **caller** picks the
  recipe for each item. There is no selection search.
- `production_result = {ingredients, output, combined, surplus}` — item quantities only.
- Grep across `lib/` for `power`, `machine`, `producedIn`: **zero hits**. Six hits for `building`, none of them
  a machine-count or power computation.
- No LP or optimization dependency in `package.json`.

Against the plan's required evaluation cases, Candidate B fails 7 (no selection), 8 (no optimization), 10 (no
power) and machine counts outright. It also carries heavy coupling: nine `peerDependencies` on
`@satisfactory-dev/*` and `@signpostmarv/*` packages, a Docker devcontainer, a `Docs.json` copy, and two code
generation steps (`make generate`, `make generate--validators`) before it runs at all.

Its one real strength is exact rational arithmetic (`fraction.js` / `bignumber.js` / `IntermediaryNumber`) and
support declared through game version 1.2.2.0, with nine test files including `power-shards` and
`save-compatibility`.

### 3.7 Candidate C confirmed unlicensed

`git log --all --diff-filter=A --name-only` across full history: no LICENSE or COPYING file has **ever**
existed in the repository. The plan's caution was correct and is now verified rather than assumed.

The author's own README calls it "a working experiment, shelved at a good stopping point... research code... the
plan has not been verified inside the game." It is 1,931 lines of Python; `recipe_graph.py` (440 lines) holds
the byproduct fixed-point recycling and the build-time-vs-run-time scale factor, which are the two ideas worth
borrowing for plan sections 10 and 14.

### 3.8 Candidate D rejected

AGPL-3.0-or-later confirmed at `LICENSE` and in `package.json`. No LP or optimization library anywhere in the
workspace. The "calculation engine" is ~9,500 lines of TypeScript under `web/src/utils/factory-management/`,
inside the Vue application — it models a user-authored factory and validates it, rather than solving for one.
Both the legal and the technical disposition point the same way.

### 3.9 Candidate A-prime — the successor

`lunafoxfire/satisfactory-planner`, 34 commits between 2026-09-05 and 2026-09-11, actively developed.

Better than Candidate A on every technical axis:

- LP backend is **HiGHS (`highs`, MIT)**, not GPL glpk.js.
- Game data is **v1.2**; Candidate A tops out at Update 7 (2022).
- Solver is a dedicated four-file module (`src/lib/solver/{problem,linear-model,lp,solver}.ts`, 770 lines)
  rather than one file living under `utilities/`.
- Modern toolchain (Vite, Cloudflare Worker, zod schemas).

**Blocked by one thing: there is no LICENSE file.** Default copyright applies — all rights reserved. It cannot
be copied, forked or vendored. The author is demonstrably active (last commit seven days ago), so a license
request is cheap and high-value.

---

## 4. Evaluation matrix

    criterion                  A (YAFP)              A' (successor)        B (SPC)              C (kentskinner)   D (sf-factories)
    license compatibility      MIT code /            NONE (all rights      Apache-2.0           NONE (all rights  AGPL-3.0-or-later
                               GPL-3.0 LP engine     reserved)             OK                   reserved)         reciprocal
    language / runtime         TypeScript            TypeScript            TypeScript           Python 3          TypeScript / Vue
    solver algorithm           LP (+ optional MIP)   LP (HiGHS)            recursive resolver   recursive +       imperative
                               via glpk.js                                 exact rationals      fixed-point       recalculation
    recipe selection           YES (search)          YES (search)          NO (caller picks)    NO (curated)      NO (user picks)
    multi-output support       YES (37 verified)     YES                   YES                  YES               YES
    byproduct handling         YES (surplus sunk)    YES                   YES (surplus field)  YES (recycled)    YES (disposal)
    resource constraints       YES (per-item caps    YES                   NO                   partial (cap      partial
                               + weights)                                                       heuristic)
    power support              YES, but extraction   YES                   NO                   YES               YES (declared)
                               power hardcoded
    machine count support      YES, fractional       YES                   NO                   YES               YES
    performance (our data)     8-42 ms full 291      not run (unlicensed)  not run              not run           not run
                               recipe set
    performance (complexity>0) FAILS - 3 s hardcoded n/a                   n/a                  n/a               n/a
                               MIP time limit
    test coverage              none in solver path   none visible          9 test files, good   none              extensive .spec.ts
    data-model coupling        LOW - 5 flat maps,    LOW - zod schema      HIGH - Docs.json.ts  MEDIUM - reads    HIGH - app state
                               3 hardcoded Desc_*    boundary              peer deps + codegen  Docs.json direct
    adapter construction       PROVEN - ~120 lines   would be similar      high friction        n/a               n/a
                               Python, end to end
    upstream tracking          IMPOSSIBLE -          possible if licensed  possible             none (shelved)    possible
                               deprecated 2026-09-11
    required fork divergence   SMALL, 4 known deltas unknown               LARGE (would be      n/a               n/a
                               (see 5.2)                                   writing an optimizer)
    verdict                    VENDOR COMPONENT      REFERENCE ONLY        REJECT as solver;    REFERENCE ONLY    REJECT
                                                     (blocked on license)  keep as test oracle

---

## 5. Decision

### 5.1 Dispositions

    A   lunafoxfire/yet-another-factory-planner      VENDOR COMPONENT @ 29b0edb
    A'  lunafoxfire/satisfactory-planner             REFERENCE ONLY - blocked on license; supersedes A if resolved
    B   satisfactory-dev/...-Production-Calculator   REJECT as solver; optional adjunct as exact-arithmetic oracle
    C   kentskinner/satisfactory-planner             REFERENCE ONLY - no license, ever
    D   satisfactory-factories/application           REJECT - AGPL and not an optimizer

Vendor exactly one file:

    client/src/utilities/production-solver/index.ts   (884 lines, MIT, (c) 2022 Rane Fields)

plus the three small type/error files it imports. Nothing else from Candidate A is taken. Its game data
(Update 7) is discarded entirely — ours is authoritative per plan section 1.2.

Record it under `external/production_solver/UPSTREAM.md` per plan section 5, with
`integration_method: vendored single module`, `update_procedure: none - upstream deprecated`, and the MIT
notice preserved.

### 5.2 Fork deltas accepted up front

    F1  swap glpk.js (GPL-3.0) for highs (MIT)          LICENSE   required before any distribution
    F2  expose TIME_LIMIT, or pin complexity weight 0   BLOCKING  complexity dimension unusable otherwise
    F3  route extraction power through our data         DATA      remove hardcoded /120 /120 /240 and Desc_* keys
    F4  declare area/buildCost reporting unsupported    SCOPE     or populate from schematic_costs.csv later

F1 is the only one that changes the legal posture. If the project is never distributed, GPL-3.0 obligations do
not trigger and F1 can be deferred — but it should be settled deliberately, not by default.

### 5.3 Parallel action, cheap and high value

Open an issue on `lunafoxfire/satisfactory-planner` asking the author to add a license (MIT would mirror their
own prior work). If granted, A-prime replaces A: newer game data, MIT LP backend, cleaner module boundary, and
a live upstream to actually track. The vendored A module is the fallback, not the destination.

---

## 6. Minimum adapter boundary

The boundary proved sufficient in the harness. Two pure functions, one direction each, and nothing else
crosses.

    progression optimizer
            |  SolveRequest  (plan section 7)
            v
    +-------------------------------+
    |  adapter                      |
    |    to_solver_gamedata()       |  canonical CSV + scenario -> GameData
    |    to_solver_options()        |  SolveRequest -> FactoryOptions
    |    from_solver_results()      |  SolverResults -> SolveResponse
    +-------------------------------+
            |
            v
    vendored ProductionSolver  (never imported outside the adapter)

Mapping, verified end to end:

    SolveRequest.outputs[]           -> FactoryOptions.productionItems[]   mode 'per-minute'
    SolveRequest.allowed_recipes     -> FactoryOptions.allowedRecipes      {recipe_id: bool} over all 291
    SolveRequest.resource_caps       -> FactoryOptions.inputResources[]    unlimited:true by default
    SolveRequest.existing_inventory  -> FactoryOptions.inputItems[]        (Phase 4 hook, already supported)
    SolveRequest.weights             -> FactoryOptions.weightingOptions    complexity pinned to 0 until F2
    scenario.recipe_input_multiplier -> applied to RecipeInfo.ingredients[].perMinute
    scenario.machine_power_multiplier-> applied to BuildingsInfo.power

    SolverResults.productionGraph    -> recipes[] {recipe_id, machine_equivalents, producer_class}
                                     -> items[]   {produced_per_min, consumed_per_min, net_per_min}
    SolverResults.report.totalRawResources        -> raw_inputs[]
    SolverResults.report.powerUsageEstimate.total -> power.scenario_mw
                                                     (power.canonical_mw = second solve at multiplier 1.0)
    derived from machine_equivalents + machine_policy -> machines[].physical_count_if_rounded

Invariants to hold:

- The solver never sees a canonical CSV. The adapter never sees a progression concept.
- `producedIn` in `GameData.buildings` is keyed by **`Build_*_C` producer_class**, matching `recipe_producers.csv`.
  Do not introduce `Desc_*` keys except the three that F3 removes.
- `power.canonical_mw` and `power.scenario_mw` come from two transforms of the same canonical facts, never from
  mutating the reference layer.
- `physical_count_if_rounded` is computed in the adapter, not the solver. Fractional equivalents stay internal
  per plan section 15.

---

## 7. Data normalization prerequisites (blocking for Phase 1)

Measured against the repo, not assumed. These are plan section 6 work, now quantified.

**P1 — production-building reference is 5 of 11 short.** `recipe_producers.csv` uses eleven distinct
`Build_*_C` classes. `buildings.csv` holds ten rows keyed by `Desc_*` `class_name`, of which six are production
machines. Missing entirely:

    Build_SmelterMk1_C      Smelter                6 recipes
    Build_Packager_C        Packager              24 recipes
    Build_Converter_C       Converter             25 recipes
    Build_HadronCollider_C  Particle Accelerator  12 recipes
    Build_QuantumEncoder_C  Quantum Encoder        6 recipes

**73 of 291 recipes (25.1%) currently resolve to zero power.** This is visible in the benchmark: Iron Plate
20/min reports 9.63 MW = 4 MW Constructor + 0 MW Smelter + 5.63 MW extraction. The Smelter contributes nothing.
Any power-weighted optimization run before P1 is fixed is systematically biased toward smelting, packaging,
converting and particle-accelerator recipes.

**P2 — extraction buildings absent.** `Desc_WaterPump_C` and `Desc_OilPump_C` have no record at all;
`Desc_MinerMk3_C` exists (45 MW). Until F3 lands, the vendored solver requires all three keys to exist or it
throws.

**P3 — `resources.csv` cannot join to anything.** Its keys are human slugs (`bauxite`, `caterium`, `crude_oil`)
with no `item_id` column, so it does not join to `items.csv` or `recipe_io.csv`. The harness used
`items.csv WHERE category = 'resource'` (13 rows) instead. Note the two disagree: `resources.csv` has 14 rows
including `geothermal_geyser`, which is not an item. Either add an `item_id` column or declare `items.csv` the
sole resource authority.

**P4 — alternate unlock IDs do not join either.** `alternate_recipe_unlocks.csv` keys on slugs (`cast_screws`,
`iron_wire`) while `recipes.csv` uses `Recipe_Alternate_Screw_C`, `Recipe_Alternate_Wire_1_C`. Phase 3 cannot
gate the allowed-recipe set by progression until this join exists. Not blocking for Phase 1.

Validation invariant to enforce in tests, per plan section 6:

    every recipe_producers.producer_class
        -> exactly one production-building record keyed by that same Build_*_C
        -> non-null base power
        -> non-null machine identity

---

## 8. What this does not settle

- Whether GPL-3.0 exposure matters. It depends on whether this project is ever distributed or hosted. Unsettled
  by choice, flagged rather than assumed away.
- Whether A-prime's author will license the successor. Cannot be known without asking.
- Whether Candidate A's LP formulation produces *good* progression answers, as opposed to correct production
  answers. It reconciles against hand calculation on fixed recipes; it has not been judged on recipe-selection
  quality, and plan section 1.4 says that judgement waits until Phase 1 validation is complete.
- Byproduct handling was demonstrated only on Plastic. The 37 multi-output recipes in the canonical set, and
  fluid backpressure cases in particular, are Phase 1 validation work.

## 9. Exit condition

Plan section 17 Phase 0 exit condition — "one upstream solver is selected for tracking/forking, or there is
documented evidence that none is usable" — is **met**, with the qualification that the selected engine is
vendored at a pinned commit rather than tracked, because no viable candidate has a live, permissively licensed
upstream.


---

## 10. Amendment, 2026-09-18 — build vs vendor reopened

Three facts have landed since section 5 was written. Together they weaken the case
for vendoring and were not available when the disposition was set.

**F1 is resolved: HiGHS.** Greg's call, on speed and maintenance rather than
licensing, though it settles the licensing question as a side effect. GPL-3.0 is
out. The project is unlikely to be distributed, but the corner is not worth
painting into.

**The repository is Python; both candidates are TypeScript.** Section 4's matrix
recorded the language mismatch but under-weighted it. Vendoring either candidate
means a subprocess or Node boundary between the adapter and the solver —
serialisation, a second toolchain, a second dependency tree, and an integration
surface that does not exist on a Python-native path. That is real, permanent work
that the "roll our own" option simply does not incur.

**HiGHS is already in the dependency tree.** `scipy.optimize.linprog` uses HiGHS as
its default method, and scipy is a declared dependency of `build_surface_tool`
(>=1.11) and `corridor_tool` (>=1.13). scipy is BSD-licensed. The preferred engine
is therefore already present, permissively licensed, and callable from Python with
no new dependency at all. `highspy` (MIT, the official pybind11 wrapper) is
available if the scipy interface proves too thin.

### Revised estimate

A Python LP backend producing our `SolveResponse`:

    variables      one continuous var per allowed recipe (<= 291)
    constraints    per-item balance; raw-input caps
    objective      weighted resources + power + machine count
    size           roughly 200-300 lines, plus tests

Candidate A's solver is 884 lines, but a large share is scope we have already
declined — build area, foundation estimates, material cost (fork delta F4), AWESOME
Sink points targets, and Ficsmas filtering. The LP core itself is smaller than the
file suggests.

Validation is unusually well-supplied: `tests/_demand_oracle.py` gives independent
fixed-recipe figures, and section 3 of this document records Candidate A's own
results on the same targets. Two reference implementations to check against before
writing a line is not the normal starting position.

### Risks, named rather than discovered later

- **Byproduct and surplus semantics.** Candidate A handles surplus explicitly.
  A naive balance constraint either forbids surplus (infeasible for multi-output
  recipes) or lets it accumulate free. Fluid backpressure makes this a real
  modelling question, not a formality.
- **Degenerate optima.** Ties between equivalent recipe sets will be broken
  arbitrarily by the solver unless tie-breaking is explicit. Results that churn
  between runs are worse than results that are slightly suboptimal.
- **Cycles.** Packager/unpackager pairs and refinery loops can admit spurious or
  unbounded cycles unless costs are set to penalise them.

These three are where "it is just an LP" goes wrong, and they are the reason the
estimate above is for a *correct* backend rather than a *working* one.

### Disposition

Candidate A remains MIT, so reading its formulation as a reference is legitimate
and recommended — it has already solved the byproduct and surplus questions, and
copying the approach is permitted whether or not any code is taken.

The vendoring decision is **deferred, not reversed**, pending the A-prime licence
answer. But the Python-native path is now the expected outcome rather than the
fallback, and guardrail 1.1's "documented gap" is documented above: no permissively
licensed, actively maintained, Python-native production solver was found, and the
two TypeScript candidates each carry an integration cost or a licence defect.
