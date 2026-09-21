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
    backend.py     the seam                                DONE
    lp_backend.py  scipy/HiGHS LP, section 7 of the        LANDED 2026-09-18,
                   formulation record                      validated, not registered
    analysis.py    compares solve configurations;          LANDED 2026-09-18
                   quantifies, never ranks

The vendoring question is untouched by this. Section 10 of
`docs/decisions/production_solver_selection.md` reopened build-vs-vendor and named
the Python-native path the expected outcome; `lp_backend.py` is that path, written
from our own formulation record rather than from Candidate A's source. Fork delta
F1 and the Candidate A' licence request are still open and no longer gate anything.

`lp_backend` is **not registered on import**. `__init__.py` does not import it, so
`registered()` stays empty and the contract package stays dependency-free. Wire it
where you use it:

    from production_adapter import load, OutputTarget, SolveRequest
    from production_adapter.lp_backend import LpBackend, PowerStatistic

    backend = LpBackend(power_statistic=PowerStatistic.MEAN)
    response = backend.solve(SolveRequest(outputs=(OutputTarget(item, rate),)),
                             load(repo_root))

`power_statistic` has no default. D2 is deferred (formulation record section 12.1),
and a default would be a decision nobody made.

`analysis.py` is the tool for deciding it. It solves the same request under several
configurations and cross-prices each resulting plan under the others' metrics:

    from production_adapter.analysis import compare, power_statistic_variants

    print(compare(power_statistic_variants(request, data)).format_table())

It quantifies and never ranks — no `best`, no sort, nothing returns a single
variant, and variants that do not share a feasible set are reported as not
comparable rather than cross-priced into a misleading number. Formulation record
section 14 covers the guards and what the D2 comparison actually showed.

## Design notes

**Canonical data is never mutated.** `ReferenceData.with_scenario()` returns a new
object. The same loaded reference serves every scenario in a process.

**Inputs scale, outputs do not.** `recipe_input_multiplier` raises what a recipe
costs, not what it yields, and it compounds across stages — Smart Plating at 1.25x
needs 33.50 iron ore per minute rather than 23.25, not 29.06.

**Scenarios round.** The multiplier lands on a recipe's per-cycle part counts and
the result is rounded to the nearest whole number, per input — nearest integer,
halves away from zero. Confirmed in game at 1.25x in both directions. Rounding is
not expressible on a rate, so `Scenario.apply_input_rate` no longer exists;
`apply_input_amount(amount_per_cycle, unit)` replaces it and `Recipe` carries
`input_amounts` alongside the per-minute `inputs` it derives. Figures published
before 2026-09-21 — including this file's own 62.41 — are unrounded and overstate
the 1.25x case. See `docs/decisions/demand_expansion_scope_and_site_capacity.md`
sections 3.2.2 to 3.2.5.

**Sub-1x scenarios must declare a floor.** Below 1x an input can round to zero and
the game's floor rule is unobserved, so `Scenario` refuses to construct without an
explicit `input_amount_floor`. It cannot bind at 1x or above.

**Power is a range, not a number.** Particle Accelerator, Converter and Quantum
Encoder draw a recipe-dependent range, so `PowerReport` carries min and max
alongside the point estimates. A minimum-power objective sees the Quantum
Encoder's floor of 0 MW; decide which statistic you are optimising before Phase 3.

**The complexity weight is disabled.** `Weights(complexity=...)` raises. On the
vendored Candidate A engine it introduces binaries and every Phase 0 benchmark
case hit the engine's hardcoded 3-second limit. Fork delta F2. The reason no
longer transfers — `scipy.optimize.milp` takes `time_limit` as an ordinary
parameter — but lifting F2 is its own decision and its own record.

**Determinism is a property of the backend, not of HiGHS.** Recipes are ordered by
`recipe_id` and the LP is solved twice: once for the objective, once to minimise
total activity among the optima. Ties are reported in `SolveResponse.warnings`
rather than broken silently. "Fewer distinct recipes", the second step section 4
of the formulation record asks for, is a cardinality objective and needs the
binaries F2 rules out; it is not implemented.

## Testing

Pure unit tests live here. Tests that need the reference layer live in the
repository's top-level `tests/`, alongside `_demand_oracle.py` — an independent
demand propagation used only to check a solver's arithmetic, deliberately unable
to choose between recipes so that it cannot grow into a second solver.

    python -m pytest tools/production_adapter/tests tests
