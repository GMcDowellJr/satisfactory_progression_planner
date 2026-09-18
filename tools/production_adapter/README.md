# production_adapter

The narrow interface between the progression planner and whichever production
solver sits underneath (implementation plan section 7).

Progression code imports from `production_adapter` and nothing deeper. It never
sees a CSV path, a solver's data model, or an LP formulation.

    canonical game facts        planning_data/game/reference/*.csv
            |                   loaded by gamedata.load()
    scenario transformation     Scenario, applied at transform time
            |
    production solver           behind backend.Backend  <- not yet selected
            |
    progression optimizer       consumes SolveResponse

## Status

    contracts.py   SolveRequest / SolveResponse            DONE
    scenario.py    the three game modifiers                DONE
    gamedata.py    reference layer -> adapter types        DONE
    backend.py     the seam                                DEFINED, no backend wired

No solver is attached. Two things gate that, both recorded in
`docs/decisions/production_solver_selection.md`: fork delta F1 (Candidate A's LP
engine `glpk.js` is GPL-3.0) and the outstanding licence request on Candidate A'.
The contract is identical either way, which is why it was built first.

## Design notes

**Canonical data is never mutated.** `ReferenceData.with_scenario()` returns a new
object. The same loaded reference serves every scenario in a process.

**Inputs scale, outputs do not.** `recipe_input_multiplier` raises what a recipe
costs, not what it yields, and it compounds across stages — Smart Plating at 1.25x
needs 62.41 iron ore per minute rather than 23.25, not 29.06.

**Power is a range, not a number.** Particle Accelerator, Converter and Quantum
Encoder draw a recipe-dependent range, so `PowerReport` carries min and max
alongside the point estimates. A minimum-power objective sees the Quantum
Encoder's floor of 0 MW; decide which statistic you are optimising before Phase 3.

**The complexity weight is disabled.** `Weights(complexity=...)` raises. On the
vendored Candidate A engine it introduces binaries and every Phase 0 benchmark
case hit the engine's hardcoded 3-second limit. Fork delta F2.

## Testing

Pure unit tests live here. Tests that need the reference layer live in the
repository's top-level `tests/`, alongside `_demand_oracle.py` — an independent
demand propagation used only to check a solver's arithmetic, deliberately unable
to choose between recipes so that it cannot grow into a second solver.

    python -m pytest tools/production_adapter/tests tests
