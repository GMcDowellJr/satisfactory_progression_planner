# Production Solver Evaluation Harness (Phase 0)

Supporting evidence for `docs/decisions/production_solver_selection.md`. Throwaway spike, not
production code. Nothing here is imported by the planner.

## What is here

    adapt_canonical.py   canonical planning_data CSVs -> Candidate A GameData JSON.
                         Applies recipe_input_multiplier / machine_power_multiplier at
                         transform time. Reports producer/building coverage gaps.
    run_cases.ts         the plan's required evaluation cases 1-12.
    run_weights.ts       weight sweep on hard targets; demonstrates Pareto spread and the
                         complexity>0 MIP timeout.
    run_scenario.ts      baseline / 1.25x inputs / 2.0x power / combined comparison.

Candidate repositories are **not** vendored here. Clone them alongside if reproducing.

## Reproducing

    git clone --depth 50 https://github.com/lunafoxfire/yet-another-factory-planner.git

Copy these four files out of that clone into `./src/`, rewriting the three relative imports
in the first to point at the other three:

    client/src/utilities/production-solver/index.ts   -> src/production-solver.ts
    client/src/contexts/gameData/types.ts             -> src/gameData-types.ts
    client/src/contexts/production/types.ts           -> src/production-types.ts
    client/src/utilities/error/GraphError/index.ts    -> src/GraphError.ts

Then:

    npm install glpk.js@4.0.2 nanoid tsx typescript @types/node
    python3 adapt_canonical.py 1.0 1.0 gameData_canonical.json
    npx tsx run_cases.ts gameData_canonical.json
    npx tsx run_weights.ts gameData_canonical.json
    python3 adapt_canonical.py 1.25 1.0 gameData_s125.json
    python3 adapt_canonical.py 1.0  2.0 gameData_p20.json
    python3 adapt_canonical.py 1.25 2.0 gameData_combined.json
    npx tsx run_scenario.ts

`adapt_canonical.py` reads the reference layer by absolute path — edit `REF` at the top.

## Known harness caveats

- `glpk.js` is GPL-3.0. Running it locally for evaluation carries no distribution
  obligation; vendoring it into a distributed build would.
- The adapter synthesizes `Desc_WaterPump_C`, `Desc_OilPump_C` and `Desc_MinerMk3_C` with
  whatever power the repo has (0, 0, 45 MW) because the solver's report pass reads those
  keys literally. Extraction power in the benchmark is therefore under-reported.
- `area` and `buildCost` are left empty, so build-area and material-cost report fields are
  zero throughout.
