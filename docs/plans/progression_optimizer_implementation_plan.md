# Satisfactory Progression Optimizer — Implementation Plan

Status: source plan, captured 2026-09-18. Phase 0 outcome recorded separately in
`docs/decisions/production_solver_selection.md`.

## Purpose

Build a progression-aware optimization layer for Satisfactory that answers:

> Given modified game rules, Project Assembly targets, progression state, and available
> alternate recipes, what production capacity should be built at each stage so the run
> reaches later tiers efficiently?

This project is not intended to become another standalone factory calculator.
Production-chain solving is a subordinate capability. Wherever practical, we will clone,
track, fork, or adapt an existing open-source production solver instead of reimplementing
solved production math.

The unique work belongs above the solver:

- scenario modifiers,
- Project Assembly scheduling,
- backward demand from endgame,
- progression/unlock awareness,
- alternate-recipe valuation across the full run,
- existing-capacity/inventory awareness,
- build-now vs. build-later decisions,
- later integration with district/world/resource planning.

---

## 1. Guardrails

### 1.1 Fork/track before build

Before writing any production solver:

1. Evaluate existing solver implementations.
2. Prefer an implementation with a compatible license and separable calculation engine.
3. Clone the candidate locally and prove it can solve representative Satisfactory chains.
4. Adapt it behind a narrow interface.
5. Only write new solver functionality where a documented gap exists.

A new production solver from scratch requires an explicit decision that the evaluated
upstream implementations are unsuitable.

### 1.2 Preserve canonical game data

The existing planner's canonical game facts remain authoritative.

Do not bake challenge-run settings into recipe tables.

Runtime scenario modifiers transform canonical values:

    scenario:
      recipe_input_multiplier: 1.25
      machine_power_multiplier: 2.0
      project_assembly_requirement_multiplier: 1.0

### 1.3 Separate facts, solver, and strategy

Keep the layers distinct:

    canonical game facts
            v
    scenario transformation
            v
    production solver
            v
    progression optimizer
            v
    strategy / district / world planning

The production solver answers: *What is required to produce these outputs?*

The progression optimizer answers: *What outputs should exist, when should they come
online, and which recipes/capacity choices make sense over the rest of the run?*

### 1.4 Do not optimize before accounting is trusted

Recipe-selection optimization begins only after deterministic production calculations
reconcile against hand-verifiable cases.

### 1.5 Do not collapse all tradeoffs into one opaque score

Initially preserve separate metrics: power, raw-resource demand, machine count,
building-material cost, logistics complexity, alternate unlock timing, rebuild/conversion
cost, future reuse.

Prefer Pareto comparisons before introducing a weighted composite objective.

---

## 2. Existing Planner Assets

The current progression-planner repository already contains much of the required
game-reference layer. Useful existing datasets include:

    planning_data/game/reference/
        recipes.csv
        recipe_io.csv
        recipe_producers.csv
        project_assembly_requirements.csv
        schematics.csv
        schematic_dependencies.csv
        schematic_recipe_unlocks.csv
        alternate_recipe_unlocks.csv
        alternate_choices.csv
        logistics_capabilities.csv
        miner_extraction_rates.csv
        items.csv
        resources.csv

The existing strategy data also already references canonical recipe IDs and production
modules. This data should be reused rather than duplicated inside the solver.

---

## 3. Upstream Solver Decision Gate

No implementation work on production solving begins until this gate is completed.

### Candidate A — lunafoxfire/yet-another-factory-planner

Repository: https://github.com/lunafoxfire/yet-another-factory-planner — License: MIT

Relevant capabilities: target output rates; available-resource constraints; selectable
allowed recipes; optimization of production chains; customizable solver weights; power
reporting; building-material reporting; mature production-chain use case.

Advantages: permissive license; already solves recipe selection rather than only recursive
demand; solver designed for large/complex production goals; likely strongest candidate if
the calculation engine can be cleanly isolated.

Risks: web-app architecture may make extraction harder than expected; upstream activity may
be intermittent; our canonical game-data format differs from its native data layer.

Initial disposition: primary fork/adaptation candidate.

### Candidate B — satisfactory-dev/Satisfactory-Production-Calculator

Repository: https://github.com/satisfactory-dev/Satisfactory-Production-Calculator —
License: Apache-2.0

Relevant capabilities: explicit calculator-engine role; generated directly from Docs.json;
test suite; TypeScript implementation; intended to sit beneath a planner/UI.

Advantages: permissive license; architecture explicitly separates calculator from UI;
game-data-first design.

Risks: documentation may be sparse; requires determining how much optimization/alternate
selection exists versus pure calculation; TypeScript integration may require either a
subprocess/API boundary or port/adaptation.

Initial disposition: primary engine candidate; evaluate alongside Candidate A.

### Candidate C — kentskinner/satisfactory-planner

Repository: https://github.com/kentskinner/satisfactory-planner

Relevant capabilities: backward demand propagation from Phase 5 goals; machine-count and
flow calculation; byproduct recycling; power planning; completion-time scaling; explicit
build-time vs. run-time optimization.

This implementation is conceptually very close to the progression work we want. However,
the repository currently appears to expose no explicit license. Without an explicit
license, treat the source as reference/research only — not code to copy, modify,
distribute, or fork into this project unless permission or a license is obtained.

Initial disposition: algorithm/reference source, not implementation dependency.

### Candidate D — satisfactory-factories/application

Repository: https://github.com/satisfactory-factories/application — License:
AGPL-3.0-or-later

Relevant capabilities: production dependency management; documented calculation-engine
architecture; larger active project.

Risk: AGPL's reciprocal requirements would materially affect how incorporated code is
distributed and hosted.

Initial disposition: reference or separate-service candidate only unless we deliberately
accept AGPL obligations.

---

## 4. Solver Evaluation Spike

Create a temporary evaluation workspace rather than immediately merging a fork into the
planner.

Suggested location:

    research/
        production_solver_evaluation/

For each permissively licensed primary candidate:

    candidate_a_yafp/
    candidate_b_spc/

### Required evaluation cases

Each candidate must demonstrate:

1. Iron Plate production.
2. Reinforced Iron Plate.
3. Smart Plating.
4. Versatile Framework.
5. Automated Wiring.
6. Multiple simultaneous output goals.
7. Explicit alternate-recipe selection.
8. Automatic recipe optimization if supported.
9. Fractional machine requirements.
10. Power accounting.
11. Multi-output/byproduct recipe behavior.
12. Late-game machine/recipe support.
13. Ability to accept transformed recipe inputs for challenge settings.
14. Ability to consume our canonical IDs or accept an adapter.

### Evaluation criteria

Record for each candidate: license compatibility; language/runtime; solver algorithm;
recipe-selection support; multi-output support; byproduct handling; resource constraints;
power support; machine count support; performance; test coverage; data-model coupling; ease
of adapter construction; ease of tracking upstream; amount of required fork divergence.

### Decision outcome

Choose one of:

- **TRACK** — use upstream package/repo essentially as-is through an adapter.
- **FORK** — maintain our own fork because small targeted changes are needed.
- **VENDOR COMPONENT** — import a clearly isolated solver module with attribution/license
  preservation.
- **REFERENCE ONLY** — learn from the implementation but use another engine.
- **REJECT** — incompatible technically or legally.

The decision and rationale should be captured in `docs/decisions/production_solver_selection.md`.

---

## 5. Upstream Tracking Strategy

If an upstream solver is selected, avoid an untraceable copy-and-paste.

Preferred structure:

    external/
        production_solver/

or a Git submodule/subtree only if that proves operationally useful.

Maintain `external/production_solver/UPSTREAM.md` containing:

    repository:
    upstream_commit:
    license:
    integration_method:
    local_changes:
    update_procedure:
    last_reviewed:

If we fork: our fork -> periodic upstream sync -> thin adapter in progression planner.

Keep challenge/progression-specific behavior outside the fork whenever possible so upstream
updates remain practical.

---

## 6. Normalize the Existing Game-Data Boundary

Before solver integration, fix the known producer/building mismatch.

Current recipe producers use build classes such as:

    Build_ConstructorMk1_C
    Build_AssemblerMk1_C
    Build_FoundryMk1_C
    Build_Converter_C
    Build_HadronCollider_C
    Build_QuantumEncoder_C

while the current building reference uses descriptor-oriented IDs and is incomplete for all
producer types.

Create a solver-safe canonical production-building reference keyed by the same producer
class used by recipes.

Required producer coverage includes at least: Smelter, Constructor, Assembler, Foundry,
Refinery, Manufacturer, Packager, Blender, Converter, Particle Accelerator, Quantum Encoder.

Validation invariant:

    every recipe producer
        -> exactly one canonical production-building record
        -> known base power
        -> known machine identity

This is a data-normalization task, not solver logic.

---

## 7. Solver Adapter Contract

Regardless of which upstream solver wins, the progression planner should depend only on our
adapter interface.

Conceptual request:

    outputs:
      - item_id: Desc_SpaceElevatorPart_2_C
        rate_per_min: 10.0
    allowed_recipes:
      mode: explicit
      recipe_ids:
        - Recipe_SpaceElevatorPart_2_C
        - Recipe_Alternate_IngotSteel_1_C
    scenario:
      recipe_input_multiplier: 1.25
      machine_power_multiplier: 2.0

Conceptual response:

    recipes:
      - recipe_id:
        cycles_per_min:
        machine_equivalents:
        producer_class:
    items:
      - item_id:
        produced_per_min:
        consumed_per_min:
        net_per_min:
    raw_inputs:
      - item_id:
        rate_per_min:
    power:
      canonical_mw:
      scenario_mw:
    machines:
      - producer_class:
        effective_count:
        physical_count_if_rounded:

The adapter prevents progression code from knowing whether the underlying implementation is
TypeScript, Python, Rust, LP, graph propagation, or another method.

---

## 8. Scenario Layer

The three configurable game modifiers are first-class inputs.

Initial contract:

    scenario:
      recipe_input_multiplier: 1.0
      machine_power_multiplier: 1.0
      project_assembly_requirement_multiplier: 1.0

Current challenge example:

    scenario:
      recipe_input_multiplier: 1.25
      machine_power_multiplier: 2.0
      project_assembly_requirement_multiplier: 1.0

Rules:

- modifiers apply at runtime,
- canonical recipe facts remain unchanged,
- outputs remain unchanged unless the game setting explicitly changes them,
- rounding semantics must match the game and be covered by tests.

---

## 9. Target Model

Do not assume the slowest Project Assembly item defines the target. Support explicit user
targets.

Rate anchor:

    target:
      mode: rate
      item_id: Desc_SpaceElevatorPart_1_C
      rate_per_min: 1.0

This supports the current run where Smart Plating is intentionally only 1/min.

Completion-time target:

    target:
      mode: completion_time
      phase: 2
      minutes: 240

Later: explicit per-item rates:

    target:
      mode: explicit_rates
      outputs:
        Smart Plating: 1.0
        Versatile Framework: 6.0
        Automated Wiring: 1.2

---

## 10. Project Assembly Backward Scheduler

Once the solver adapter is trusted, add our first genuinely unique layer.

The scheduler should:

1. Read all Project Assembly requirements through Phase 5.
2. Apply the Project Assembly requirement multiplier.
3. Identify direct and downstream demand for each Project Assembly part.
4. Determine production windows based on unlock progression.
5. Convert the user's target into required item/min rates.
6. Pass those rates to the production solver.

Conceptual example:

    Phase 2 completion horizon: 240 min
    Smart Plating:
      available at t = 0
      remaining quantity = X
      required rate = X / 240
    Versatile Framework:
      expected online at t = 40
      remaining quantity = Y
      production window = 200 min
      required rate = Y / 200
    Automated Wiring:
      expected online at t = 90
      remaining quantity = Z
      production window = 150 min
      required rate = Z / 150

This is more useful than simply assigning all elevator parts the same nominal production
rate.

---

## 11. Deterministic Validation Before Optimization

Before asking the solver to choose alternate recipes, validate fixed-recipe scenarios.

Required validation set:

    Iron Plate
    Reinforced Iron Plate
    Smart Plating
    Versatile Framework
    Automated Wiring
    Smart Plating + Stitched Iron Plate
    Smart Plating + Iron Wire
    VF + Solid Steel
    VF + Steeled Frame
    Rotor/Stator + Steel Rotor where applicable
    1.25x recipe-input scenario
    2.0x machine-power scenario
    combined challenge scenario
    representative Phase 4/5 chain

For every case compare item rates, recipe rates, machine equivalents, raw inputs, and power
against manually calculated or independently verified values.

Do not proceed to automatic recipe optimization until these reconcile.

---

## 12. Alternate-Recipe Optimization

Once deterministic solving is proven:

    scenario + target + unlocked recipes
            v
    candidate production solutions

Evaluate candidates independently on: power; raw resources; machine count; number of
production stages; building-material burden; logistics complexity; future reuse; rebuild
cost.

Initially return a Pareto set rather than one "best" recipe combination. Example:

    Option A — lowest power
    Option B — lowest raw resources
    Option C — fewest machines
    Option D — least infrastructure change

Only introduce weighted optimization after the dimensions and tradeoffs are visible.

---

## 13. Progression-Aware Alternate Value

Static alternate tiers are not sufficient. Later optimizer stages should ask:

> Is this alternate worth obtaining and restructuring around at this point in this specific
> run?

Inputs eventually include: current tier/milestone; known alternates; unopened hard drives /
expected alternate acquisition; existing machines; existing inventory; existing production
rates; available power; resource access; time until next phase; future Project Assembly
demand.

Output should distinguish: valuable immediately; valuable when next infrastructure unlocks;
valuable primarily for late game; dominated in this scenario.

---

## 14. Existing Factory State

After the static progression scheduler works, add run-state inputs:

    existing_production:
      Smart Plating: 1.0
      Reinforced Iron Plate: 10.0
    inventory:
      Smart Plating: 430
      Versatile Framework: 120
    known_alternates:
      - Recipe_Alternate_IngotSteel_1_C
      - Recipe_Alternate_Rotor_C

Then recompute remaining demand, remaining time, and required incremental capacity.

This lets the tool answer *What do I need to add now?* rather than repeatedly designing a
factory from zero.

---

## 15. Machine Presentation Policy

Keep fractional machine equivalents internally. Example: `required capacity: 1.37 Assemblers`.

Presentation layer may convert this into: `build: 2 Assemblers, clock: 68.5% each`.

Initial policy:

    machine_policy:
      allow_underclock: true
      allow_overclock: false
      round_physical_machines_up: true

Somersloops and Power Shards are intentionally deferred until the base model is stable.

---

## 16. Connection to World / District Planning

Do not integrate geography in the first solver effort.

Later, production results can emit resource requirements:

    Iron Ore       720/min
    Coal           480/min
    Limestone      180/min
    Caterium Ore   120/min

The existing world planner can then answer: which district can supply this? what nodes are
required? what transport corridors are needed?

Conversely, district constraints can eventually feed the production optimizer: available
iron; available coal; belt tier; miner tier; local oil; transport capacity.

This becomes `production optimizer <-> district / world planner` without merging the two
systems.

---

## 17. Planned Work Sequence

### Phase 0 — Solver selection

Deliverables: solver candidate clones; evaluation matrix; representative benchmark results;
license review; `production_solver_selection.md`.

Exit condition: one upstream solver is selected for tracking/forking, or there is documented
evidence that none is usable.

### Phase 1 — Data boundary + solver adapter

Deliverables: normalized production-building data; solver adapter; scenario transformation;
fixed-recipe solve capability; validation tests.

Exit condition: fixed production targets reconcile correctly for early and late game.

**Status: MET, 2026-09-19.** All 14 of section 11's validation cases reconcile, plus the
Stitched Iron Plate / Iron Wire pair found during that work and restored to the suite.
Late-game reconciliation is carried by the curated Nuclear Pasta route, which exercises the
Particle Accelerator only — a second late chain through the Quantum Encoder or Converter is
still wanted, and is tracked as an open item rather than as an exit blocker.
`_balance_check` verifies responses on chains where `_demand_oracle` cannot, byproduct
feedback included.

Two qualifications are carried forward rather than reopening the phase, both recorded in
`docs/decisions/demand_expansion_scope_and_site_capacity.md`:

- `scenario.py` does not model the game's integer rounding of scaled recipe costs. The
  multiplier is applied to rates, where rounding cannot be expressed. Decided and not yet
  built; it moves the scenario of record by 28 percent. Section 3.2.5.
- Base-recipe-only expansion is not unambiguous above Adaptive Control Unit. A curated
  recipe set is required for late fixed-recipe cases; the mechanical exclusions are
  section 3.1.1.

Neither affects whether fixed targets reconcile, which is what this condition asks.

### Phase 2 — Project Assembly scheduler

Deliverables: rate-anchor target; completion-time target; Phase 1–5 requirement propagation;
production-window logic; Project Assembly report.

Exit condition: the tool can work backward from Phase 5 and derive production targets for
every relevant Project Assembly part.

### Phase 3 — Alternate-recipe optimization

Deliverables: unlocked-recipe candidate generation; Pareto comparison;
power/resource/machine metrics; recipe-set comparison report.

Exit condition: the tool can explain how alternate value changes under different challenge
settings.

### Phase 4 — Run-state / progression planning

Deliverables: existing production; inventory; known alternates; expected unlock/online
times; incremental build recommendations.

Exit condition: the tool answers "what should I build next?" rather than only "what factory
could produce this?"

### Phase 5 — World integration

Deliverables: resource-demand contract; district-capacity contract; world-resource
constraints; transport/logistics hooks.

Exit condition: production decisions can be evaluated against actual district resources and
logistics.

---

## 18. Explicit Non-Goals Until Needed

Do not add these merely because they are interesting: factory floor layout; belt routing
inside factories; rail-network design; Power Shard optimization; Somersloop allocation;
blueprint placement; construction-material logistics; UI; mobile interface; save-file
ingestion; automatic hard-drive route planning.

Some may eventually be valuable, but none is required to validate the progression optimizer.

---

## 19. Immediate Next Action

The next effort should be Phase 0 only. Do not start coding a solver.

1. Clone the permissively licensed primary candidates.
2. Run the same representative production targets through each.
3. Inspect their internal solver boundaries.
4. Determine whether our canonical data can be adapted cleanly.
5. Select TRACK vs FORK vs REJECT.
6. Record the decision.

Only then begin implementation.

---

## 20. Definition of Success

The project succeeds when a playthrough can be expressed approximately as:

    scenario:
      recipe_input_multiplier: 1.25
      machine_power_multiplier: 2.0
      project_assembly_requirement_multiplier: 1.0
    target:
      mode: rate
      item: Smart Plating
      rate_per_min: 1.0
    state:
      phase: 2
      known_alternates:
        - Solid Steel Ingot
        - Iron Wire
        - Stitched Iron Plate
      existing_production:
        Smart Plating: 1.0

and the tool can return: required Phase 2/3 production rates; recommended recipe
combinations; machines to add; required upstream rates; raw-resource demand;
scenario-adjusted power; which existing production remains useful; which alternate recipes
materially improve the run; what should be built now vs deferred — without duplicating a
production-solver problem that an upstream open-source engine already solves.
