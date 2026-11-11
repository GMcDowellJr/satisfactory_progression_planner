# Factory Design Integration — Repository Specification (Proposed)

**Repository:** `GMcDowellJr/satisfactory_progression_planner` (default branch `master`)  
**Prepared:** 2026-11-10; **decision-record reconciliation:** 2026-11-10  
**Status:** **PROPOSED / UNDER CONSIDERATION** — not an adopted decision, implementation, or repository commit. This revision incorporates decision-record reconciliation; the precedence notes in §2A supersede any conflicting shorthand elsewhere in this draft.  
**Inputs:** repository architecture and decision records; `satisfactory-netlify-ready(1).zip` (three-file browser prototype); current Steel Outpost / Satisfactory Modeler layout discussion.  
**Scope:** integrate supply-driven individual-factory planning, reusable phase/power-sizing analysis, SFMD interchange, and editable foundation-grid layout *downstream of* existing world/site/progression engines. 

## 1. Executive decision boundary

The repository's product is **world/site opportunity, logistics and progression**. It already owns game facts, scenario transformation, production solving, site portfolios, and terrain/connectivity analyses. Do **not** create a second canonical game database, solver, or competing whole-product application. The proposed factory designer is an **optional downstream detailed-realization workspace** that can be opened from a site/portfolio result or from an imported model. It does not prescribe a factory or a build order.

The October 12 site-planner product spec explicitly lists precise machine layout as a *non-goal*. This document does **not** retroactively revise that document. The new functionality is an independently scoped extension; if adopted, append a forward-only decision/amendment describing this limited exception and the ownership boundary.

**User-stated direction for this specification:** favor an original implementation; prefer supply-driven design of an individual factory to arbitrary per-minute output targets (keep demand-driven as an option); use Satisfactory Modeler import when practical; make production steps movable on a foundation canvas; offer manifold, balanced, and manual routing per step. The attached Netlify experiment is prior research, **not** authoritative game/solver code.

## 2. Verified existing repository boundaries

| Existing asset | Keep its responsibility | Integration action |
|---|---|---|
| `planning_data/game/reference/` | Build-pinned items, recipe I/O, producer/building identity, logistics unlocks, Project Assembly requirements | Use through `production_adapter.gamedata.load(repo_root)`; no duplicate recipes in UI |
| `production_adapter/` | Canonical IDs, scenario transformations, fixed/LP calculations | Call via contracts/approved root orchestration, never from layout code directly |
| `realization/` | Bus capacities, residuals, realization (not a new solver) | Reuse evaluated outputs; don't insert spatial optimization here |
| `progression/` / `tools/phases/` | Unlocks, phase planning, stock/power | Reuse for phase/elevator sizing; avoid phase-index hardcoded miner assumptions |
| `tools/portfolio_run.py`, `tools/district_run.py` | Multi-site and district portfolio calculations | Export/input adapter for chosen site and allocation; preserve source provenance |
| `planning_data/world/{canonical,spatial,manifests}/` | World sockets, assignments/purity, terrain/water | Resolve site supplies against a **materialized** world; do not assume vanilla assignments |
| `build_surface_tool/`, `corridor_tool/` | Candidate surfaces, regional topology | Optional site/route overlays; no game-world routing inside factory layout core |
| `tools/site_planner_web/{picker.html,index.html,worker.js}` | Site picker and portfolio rendering in browser/Pyodide | Add an optional link/workspace, not a rewrite of these pages |
| `planning_data/planning/{model,plans,strategies,playthroughs}/` | General semantics, inputs, choices and run state | Store factory design records with linked site/portfolio IDs and scenario identity |

Relevant repo authority: `README.md`, `AGENTS.md`, `planning_data/ARCHITECTURE.md`, `docs/decisions/site_planner_reframe.md` (including later amendments), `docs/product/site_planner_spec_v1.0_proposed.md`, `docs/plans/progression_optimizer_implementation_plan.md`. Earlier decisions may be exploratory or superseded by the site-planner reframe; do not reinstate them by implication. Read all newer amendments in full before implementing. Root orchestration is placed in `tools/` rather than importing upward across protected layers.

## 2A. Decision-record reconciliation — controlling interpretation (2026-11-10)

**Record precedence.** `docs/decisions/site_planner_reframe.md` (2026-10-12) makes earlier records an **exploration log**, not automatically binding product requirements. Its amendments A1–A11 (2026-10-19 through 2026-10-23) are later explicit decisions, subject to their own supersessions. Older LP/crossover/demand records can remain factual evidence or current implementation descriptions without reinstating their prior product mandates. This draft is **not** an adopted amendment. The spec must not invent decisions where no authoritative later ruling exists.

| Issue | Verified decision/evidence | Required integration behavior |
|---|---|---|
| **Scope conflict** | Reframe §2 and proposed `docs/product/site_planner_spec_v1.0_proposed.md` §2 exclude exact layouts from the *site opportunity* tool. | Optional downstream factory-design workspace; no change to site-planner contract. New layout scope needs a forward-only adoption decision if accepted. |
| **Supply-first objective** | Crossover A24 / A27 K2 articulate supply-side district vs bill-side scheduling, but predate the reframe and are exploratory as product authority. Reframe A1–A3 subsequently adopt bill-based bounded portfolios, locality-first, and shared-grid power. | Default *factory workspace UX* can be supply-first per current user direction, but **do not assume** existing portfolio solver is goal-free or transplant A27's objective. An allocation without a named objective/preference produces a feasible-space report or asks for a user allocation. |
| **Current portfolio schema** | Reframe A10 initially describes `portfolio-inputs/1`; A11.3 explicitly supersedes it with **`portfolio-inputs/2`**, adding required `power_mode`. Result remains **`portfolio-plan/1`** with additive power fields. | Input adapter accepts the current `/2` record; `/1` requires explicit migration or a named refusal. Retain `power_mode`, `power_need`, `source_text`, identity/provenance. Do not represent `/1` as live wire format. |
| **Power modes** | Reframe A3–A7 establish shared-grid power, draw-scaled extraction, declared water pumping, P on extractors but not generator MW. A11 introduces `grid` versus `report_need`; latter does **not** size sources in the solve, and has specific refusals. | Preserve mode semantics. `report_need` is a fuel/generator **requirements report**, not a feasible self-powered production solution. It refuses standing-grid combination, pumpable water, and district solve in the documented implementation; downstream UI must surface these exclusions. |
| **Power prototype** | A11.5 leaves powered fuel manufacture and feed practicality unresolved. A8 says use byproducts, but mechanism remains open. | Biomass/coal/fuel scenario comparison is a separate **proposed diagnostic**. Do not call it the current portfolio power solver; explicitly include/refuse generator fueling loops, byproduct destinations, water and power multipliers as supported. |
| **0.25× solids** | Demand expansion A5.1 (2026-10-26) **closes** earlier uncertainty: nearest integer, half away from zero, floor **1 item per solid recipe input**. | Replace earlier 'sub-1× solids unknown' caution. Require explicit test to validate application against current `Scenario.apply_input_amount`; don't silently assume code defaults implement the observed floor. |
| **0.25× fluids** | Demand expansion A2 identified mL granularity; A5.2 leaves floor unit unresolved, with current floor=1 m³ a **code assumption**, not a game observation. Discriminating read: Plastic crude input at 0.25×, expected 0.75 vs 1 m³. | Mark fluid floor **unverified**; expose input-floor policy and provenance, refuse unsupported scenario or label the assumption. Never apply the solids floor to fluids without disclosure. |
| **What R scales** | Demand expansion A5.3/A6: R scales crafting ingredients, **not** Build Gun construction, milestone or MAM costs. E independently scales Project Assembly quantities. | No generic multiplier applied to all construction/phase bill items. Obtain exact unlock/project quantities from canonical data. |
| **What P scales** | Reframe A7 and demand A5.4: P scales machines, miners, extractors and powered sinks; **not** generator output; clock-power exponent is unchanged. | Reuse scenario/extraction models, do not scale generator nameplate or omit power for extractors and fuel preparation. |
| **Resource claims** | Reframe A9: included socket (kind, item) pairs are declared; deduplication policy must be all-or-none with seed order. A10 allows labelled precomputed neighborhoods plus browser recompute. | Source selection and site → factory must preserve materialized assignments and socket ownership; never infer ownership from a candidate catchment, richness label or map average. |
| **Byproducts** | Reframe A8.3 adopts 'byproducts are used' and 'unclaimed capacity only reported'; A8.5 leaves enforcement/sink/report mechanism unsettled. | Export produced/consumed/unallocated/byproduct/backpressure separately. Treat 'free infinite disposal' as an unresolved modeling gap, not viable routing. |
| **Existing power and old district choices** | Crossover A34–A36 contain revisions (A35 supersedes A34's report-only/default and external plant fuel draw for its fixture), but are pre-reframe. | Do not impose A35's 300 MW fixture or A34's single-recipe-per-bus rule as universal factory policy. Record explicit recipe choices per bank and preserve standing grid versus site-fed generation distinctions. |
| **Installed vs planned** | Crossover A36 parks planned-vs-installed as a separate tool; pre-reframe. Site-planner A8 reports idle/unclaimed, not all installed machines. | MVP focuses on *proposed factory model and layout*; no automatic claim to reconcile against save-installed production. Save-state integration is independently scoped. |
| **Physics claims** | Site spec F5/F7 makes connection evidence explicit; geometry and topology are not transport proof. | Differentiate diagram edge, estimated belt path, verified clearance, and buildable route. Unknown elevation cannot be certified crossing-free. |

**Specific current data-contract check:** inspect and test the implementation of `tools/portfolio_run.py` and `tools/site_planner_web/picker.html` against the source fixture before finalizing field-by-field mapping. This reconciliation establishes documented schema **names and semantics** but has not executed the repository; no runtime contract conformance is claimed.

**Preservation principle:** do not turn old reference calculations into game facts; `Scenario.apply_input_amount`, world socket ownership, declared node clocks, recipe unlocks, power modes and phase quantities belong to existing authoritative packages. The proposed Netlify UI is a *client feature inventory*, not a second engine.

## 3. Audit of attached standalone Netlify test

### 3.1 Inventory and observed behavior

The attachment contains only `index.html` (~45 KB), `README.md`, `netlify.toml`. It is a static browser-only, self-contained Project Assembly phase calculator with embedded `DATA` (standard recipes), `PARTS`, `PHASES`, power constants, node-average counts and algorithms. It saves selections to browser `localStorage` with an `sf_full_v4_` prefix and makes no API calls. It is not a general supply-driven factory graph, an SFMD importer, or a physical-layout planner.

| Prototype feature | Observed implementation | Integration disposition |
|---|---|---|
| Five Project Assembly phase tabs | Hardcoded `PHASES` output quantities and phase labels | **Reuse UX idea**; derive requirements via canonical phase/Project Assembly data |
| R/P/E settings | Selectable global recipe, power and elevator multipliers; E multiplies deliveries with ceil | **Keep concept**; use canonical per-save scenario contracts and exact per-cycle rounding |
| Phase duration / fraction slider | `limit(i)` computed from slowest phase product using one standard 100%-clock machine; 5/10/25/50/100% presets; default 25% | **Preserve as optional phase comparison view**, not default factory sizing |
| Production chain expansion | Recursive standard-recipe tree from embedded JSON; cycles detected and rejected | **Replace** with repo solver; supports alternates and coproduct accounting |
| Machines and electricity | Fractional recipe equivalents; ceil installed counts; mostly nameplate electricity; avg/peak | **Reuse presentation only**; reconcile with repository's clock, rounding, variable-power, extraction and power rules |
| Raw extraction | Miner tier chosen by phase index; purity-weighted global average; water/oil/well assumptions | **Replace** with materialized socket assignments and unlock-aware extraction; isolate unknowns |
| World generation presets | Default/Basic Resource Rich/Advanced Resource Rich/Fossil Fuel Rich labels; no numeric changes modeled | **Keep scenario UI as explanatory placeholders** until supported assignments/seed resolution exist; no invented resource bonus |
| Power scenarios | Biomass, coal and fuel separate complete supply scenarios plus adjustable gross-generation mix | **Keep testable functionality**; route fuel/power demand through existing power-aware portfolio model or a typed scenario evaluator |
| 10% headroom | Peak load × 1.10; fixed | **Make explicit configurable assumption**, not a hidden game rule |
| Local save and Netlify deployment | `localStorage`, static hosting, no bundler | **Preserve offline/mobile delivery goals** while adding versioned JSON import/export; do not treat local storage as authoritative |

### 3.2 Known prototype modeling gaps / conflicts — must not migrate silently

1. **Recipe rounding:** prototype applies `ceil(R × input-per-cycle)` to **each solid input** and continuous scaling to fluids. Repo decision records record *nearest-integer, half-away-from-zero* per solid input with a minimum of **1** (A5.1 closes low-R solids), while the fluid-floor unit remains open (A5.2). **Repository scenario implementation and tests win**; record any open sub-1× cases as unresolved, not as a substituted ceil policy.
2. **Canonical game data:** embedded recipe tables, machine power, Project Assembly requirements and phase miner unlocks can drift from build 502094 or later. One source: reference data loaded through the prescribed adapter.
3. **Byproducts/loops:** recursively expands requirements but doesn't credit coproducts (returned Water, HOR, resin, etc.); cycles cause error. Do not use this math as authoritative for oil/aluminum/recycling or late-game production.
4. **Power accounting:** `solveSupply` iterates whole Biomass/Coal/Fuel generator counts using peak load and self-fuel inputs, with an iteration ceiling; not the repository's adopted portfolio shared-grid and extraction-by-draw rules. Compare as **scenario diagnostic** with explicit assumptions, not production truth.
5. **Purity presets:** global purity averages, shifted distributions and default resource counts are not localized socket claims; richness presets change explanatory text only. Do not pretend they modify the materialized world.
6. **Nitrogen:** assumed six satellites per well, estimated capacities/pressurizer power; site-well configuration is not proved by the prototype. Require resolved world/satellite data or mark estimated.
7. **Transport/belts:** no belt caps, pipe throughput, spatial machine geometry, pump/headlift, shared trunk capacity, or routing validation. These belong in factory layout/feasibility extensions.
8. **Duration target is not site supply:** it calculates output demand from Project Assembly totals / duration. Supply-constrained site design must not inherit this target-selection policy.
9. **State semantics:** R/P/E selects are global to the page; phase-specific duration and power mix are persisted separately. Do not confuse this with changing the run's actual per-save rules between phases. For what-if phase comparisons, represent explicit per-phase *scenario overrides* and distinguish them from an actual save configuration.
10. **No test evidence:** uploaded ZIP contains no unit tests or benchmark outputs. Treat every calculation as unvalidated until independently reconciled.

## 4. Functional workflows and user ownership

### 4.1 Factory from site (default)

1. Open a selected site from a materialized world and chosen run/scenario. Show **claimed/available** resource sockets, extractor unlocks, capacity and external imports. Distinguish ownership, capacity, allocation, reserves, and residual; do not double-count across overlapping sites.
2. Choose known recipes (or allow solver exploration) and **allocate local input supply** among simultaneous products, production families, power and potential exports. Never fabricate a per-minute output target just to make a solver run.
3. Show feasible production possibilities, binding constraints, residuals and multiple options; user pins a chosen allocation or constraints. Distinguish capacity ceiling from committed operating rate.
4. Convert a selected feasible solution into a **canonical production graph** (recipe instances, rate balances, typed transfers and byproducts).
5. Realize graph into physical machine banks; allow clocks, blueprint grouping, row decisions and per-bank manifold/balanced/manual routing.
6. Place banks on an editable foundation-grid canvas; check throughput, clearances, collisions and crossings. Persist positions independent of production quantities.
7. Optionally report required site surface and logistics connections upstream to site/corridor analysis. A saved design is a proposal, not proof of real-world feasibility.

### 4.2 Factory from SFMD (import)

Parse and validate the user's `.sfmd` export into the same canonical graph. Preserve any native node coordinates separately as *source diagram coordinates*, not physical foundation positions unless specified by format evidence. Preserve original file hash, import diagnostics, unresolved recipe/product IDs, and unrecognized fields. Allow manual mapping; never silently substitute a different recipe.

### 4.3 Demand-driven optional mode

User supplies minimum outputs or target rates explicitly. Existing production solver returns required resources and a graph; it can subsequently be placed at a selected site and tested for supply/power/logistics feasibility. Demand mode is not the default for individual factory creation.

### 4.4 Phase sizing and power comparison (from attached experiment)

Add a separate **phase analysis** view that shows Project Assembly bill totals, time-at-rate or rate-for-declared-horizon, production-machine equivalents, raw draw, power/capacity scenarios and readiness/unlocks. Default view is not a claim about how fast to build. Provide separate Biomass/Coal/Fuel and mixed-source comparisons with explicit fuel supply, reserve margin, phase availability, unknown data, and accounting basis. Preserve the 25% phase-duration preset as a convenience **only in this view**, not a global planning default. An actual run has one scenario triple (R/P/E); compare scenarios explicitly rather than silently changing a save's rules by phase.

## 5. Canonical internal contracts (proposed; not yet schemas)

Version all persisted/exchanged records. Use canonical item/recipe/building identifiers, rates per minute with explicit unit, and build/scenario/world manifest identity. No presentation labels as primary keys.

### 5.1 `factory-inputs/1`

- `factory_id`, optional `site_id`/`portfolio_id`/`playthrough_id` and provenance paths/hashes.
- `game_build`, `world_manifest_id`, `world_assignment_id`, `scenario_id`/R/P/E, unlocked recipe/extractor/belt/pipe set.
- `supply`: resource socket ID, material, purity/assignment, miner, rated capacity, optional ownership/share, allocated / reserved / residual, import allowance.
- `choices`: permitted/pinned recipes, constraints, optional output minima, preferred allocation, power grid/headroom, optional capacity reservations.
- `mode`: `site_supply`, `explicit_demand`, or `imported_graph`.

### 5.2 `factory-production/1`

- Immutable **solution snapshot ID** and input version/hash; solver provenance and completeness/feasibility status.
- Steps: stable step ID, recipe ID, producer building ID, cycles/min, product/co-product rates, fractional machine equivalents, physical capacity/clock policy.
- Typed edges: source/target **step IDs**, material ID, amount/min, unit, internal/external/byproduct status; support split/merge and multiple steps producing the same item.
- Resource and power ledgers: consumed/produced/imported/exported/unused/overdraw; generator inputs and extraction power separately accounted.
- Diagnostics: unmet demand, oversubscribed socket, unresolved alternate, insufficient unlock, missing byproduct sink, uncertain extraction/transport.

### 5.3 `factory-layout/1`

- Links to immutable `factory-production/1` snapshot, but persists **independently** of recalculation.
- `grid`: 8 m foundations and local origin, rotation, elevation/floor, world transform only when site geometry is known.
- Banks: stable **bank ID** distinct from recipe step ID; step ID(s), instance range/machine count, physical footprint with clearances; position (foundation x,y,z), orientation, locked/manual state.
- Ports: typed in/out connector anchors with material and maximum throughput; preserve actual connector orientation and elevation when known.
- Routes: graph edges to lane/pipe paths, tier, line rates, split/balance mode, intermediate splitter/merger/lift/pipe entities, capacity/clearance status.
- Per-step routing policy: `manifold` / `balanced` / `manual`, plus routing overrides and row/bank grouping; state **unverified** if routing has only schematic topology.
- Display state (viewport, hidden materials, groups) is optional client metadata and not part of production truth.
- Validation results include collisions, clearance, unsatisfied ports, overloaded belts/pipes, unconnected lines, ambiguous crossings, footprint and expansion capacity. Unknown connector geometry is marked unknown, never assumed pass.

### 5.4 `factory-import/1` diagnostic wrapper

`source_format`, `source_version` if observed, raw file hash, import timestamp, original node/edge IDs, mapping table, warnings/errors, opaque preserved fields and normalized output pointer. Reject incompatible or ambiguous fields by name; do not quietly coerce.

## 6. Layout invariants and geometry

- A production **step** is a recipe/rate calculation. A **bank** is a physical group of one or more instances of a step. One step may appear in several banks; splitting a bank must conserve rate across its instances.
- Machine geometry comes from canonical building data where available; use an explicit geometry adapter for **ports, belts, clearance and rotation**. A rectangle that contains a building body does not validate its conveyor connections.
- In physical mode, bank coordinates are in 8 m foundation units; dependency mode may use arbitrary graph-coordinate units. Switching views must not treat diagram coordinates as meters.
- User drag/rotate/lock survives rate recalculation; changed banks may resize and be flagged as colliding. Never reset placement without an explicit reset command.
- Route throughput is checked **per distinct material lane and shared segment**; Mk-tier capacity cannot be inferred solely from a machine row count. Track pipe constraints separately. Sushi belts require sum-of-items capacity checks.
- Balanced routing is a *network topology* (splitter ratios and split counts), not merely shorter lines. Validate branch rates and splitter/merger input-output port limitations. A schematic drawn line is not a claim of construction validity.
- Multi-floor layouts, lifts, pipe headlift and collision in 3D can be deferred; early results should label them unsupported or unresolved, not zero violations.
- Report separately: area, belt/pipe distance, crossings, route bends, belt utilization, power, reserved expansion area, and uncertainty. No opaque score until dimensions are validated and user selects priorities.

## 7. Proposed package seams and presentation

```text
tools/
  factory_model/             # typed graph + source adapters + validation contracts
    contracts.py
    from_portfolio.py        # maps stable portfolio/solver outputs into graph
    sfmd_import.py           # inspect format, parse, resolve, report diagnostics
    serialize.py
  factory_layout/            # production-agnostic geometric realization
    contracts.py
    footprint.py
    routing.py               # manifold/balanced/manual policies
    validation.py
    metrics.py
  factory_run.py             # orchestration above production/site/graph/layout modules
  site_planner_web/
    factory.html             # optional browser workspace; does not own calculations
    factory_canvas.js       # drag/snap/render/export; add build pipeline only if justified
planning_data/planning/
  plans/                     # optional sample factory-input records, if in scope
  templates/                 # versioned JSON examples/schema documentation
 docs/product/
  factory_design_integration_spec_2026-11-10.md  # this document, if adopted into repo
```

This is a **suggested ownership map**, not authorization to create every file. Apply repo's import-boundary rules: `production_adapter` does not import upward; layout modules should depend on typed graph/layout contracts, not solver internals; cross-layer calls live at `tools/` root; only `production_adapter.gamedata.py` knows game CSV names/columns. A `factory_model` adapter may consume game facts provided by the orchestrator instead of reading CSV files directly.

**Client boundary:** start with a static browser canvas consistent with `site_planner_web`, with Python/Pyodide calculation only where it already makes sense. UI state is not the authoritative scenario/solution; use versioned JSON records that can be round-tripped and validated offline. Avoid forcing a new frontend framework before testing the interaction model.

## 8. Integration interfaces and round trips

1. **Site → Factory:** site/portfolio export yields identity, owned sockets, capacities, scenario, selected production and transfer ledger. Adapter validates all IDs and maps to `factory-inputs/1` plus a computed `factory-production/1`.
2. **SFMD → Factory:** parser maps exporter products/recipes/machines/edges to `factory-production/1`; importer logs unresolved fields. Site link may be attached afterward; no fabricated world position.
3. **Factory → Site:** report material input/output/import/export, available reserve requirements, area envelope, confidence and verified/unverified connections; upstream *consumes* the report and need not adopt the physical drawing.
4. **Factory → Phase analysis:** compare selected factory production capacity against Project Assembly demand and inventory; show fill times, missing parts and power assumptions without inventing a schedule.
5. **Factory production recompute:** reconcile step IDs by stable recipe/role/lineage where possible; preserve bank IDs and manually placed coordinates; mark orphaned/split/merged banks for resolution.

## 9. Test plan and acceptance criteria

### A. Contracts and provenance

- Canonical references are looked up using the repository loader; no duplicated recipes or game facts in browser source.
- Missing/ambiguous IDs are refused and shown in import diagnostics; game build, scenario, materialized world and source hash survive export/import round-trip.
- All pre-existing import boundary tests still pass; manifest update follows repo's separate `Regenerate manifests` commit convention **when code is actually committed**.

### B. Source-to-graph reconciliation

- Known Solid Steel → Beam → Versatile Framework chain plus Pipe branch reconciles item balance and fractional/rounded machine counts against existing production outputs. Use fixed source rates, no invented default product rate.
- SFMD fixture from the user's Steel Outpost parses successfully or reports exact unsupported fields; graph totals match the source, and original node IDs/coordinates are retained.
- Multi-product flow, byproduct flow, explicit imports, multiple producers for one product, and split-step banks conserve rate.

### C. Layout and feasibility

- Drag bank on 8 m grid, rotate 90°, save/reload: original position/orientation/step links unchanged.
- Recalculate production after moving bank: placement survives; any new collision is reported rather than silently fixed.
- Mk.3 (270/min): 360 ingots/min requires at least two independent lanes; one-lane attempt is rejected or flagged. For a 540/min steel supply, three 180/min trunks are a valid topological division.
- Both manifold and balanced six-machine banks preserve total flow and per-belt capacity; compare footprint, crossings, total run lengths, and clearances under identical bank placements.
- Crossing count distinguishes a same-elevation intersection from a validated lift/bridge; unknown elevation is not automatically crossing-free.

### D. Netlify prototype regression / parity checks

- For each of five phases, Project Assembly totals match canonical reference after E and rounding policy; slider derives the explicit completion horizon and one-machine maximum from unlocked recipes/producer capabilities.
- At R=1, P=1, E=1, reproduce selected simple chains independent of the prototype. At R=1.25 verify per-cycle half-away rounding; at 0.25× test solid-item floor=1 against in-game observations. Fluid-floor assumptions remain labeled at all affected sub-1× settings.
- Coal/fuel/biomass independent power comparisons and custom mix account for fuel-source demand and reserve; show nonconvergence rather than plausible-looking results.
- Node presets do not change world resources without a materialized assignment dataset; extractor tiers derive from actual unlock rules.
- UI usable at 375 px and on desktop, keyboard accessible, with no obligatory external server dependency for opening a saved design.

## 10. Incremental delivery plan (gates, not assumed commitments)

| Gate | Deliverable | Exit condition |
|---|---|---|
| **0 — Inspect/contract** | Inspect actual SFMD file/schema and current portfolio export; write exact field maps and gap register | Zero invented field meanings; one source fixture each |
| **1 — Canonical factory graph** | Typed versioned `factory-production/1`, source adapters, conservation tests | Existing solver output and SFMD can express same chain without loss of known fields |
| **2 — Layout editor MVP** | Movable/rotatable/snap-to-grid machine banks; preserve edits through recalculation | Steel Outpost fixture saved, reopened, and moved reproducibly |
| **3 — Routing strategies** | Per-bank manifold/balanced/manual selection and explicit ports/lanes | Mk.3 360/min split, rate conservation and segment capacity tests pass |
| **4 — Site round trip** | Factory linked from picker/portfolio and exported back as capacity/area/logistics requirements | Existing site-planner functionality unchanged; provenance intact |
| **5 — Phase/power integration** | Reworked standalone experiment's phase duration, R/P/E, power mixes, extraction scenarios | Canonical reference and scenario parity tests pass; speculative cases labeled |
| **6 — Optional optimization** | Candidate placement and Pareto comparison of area/crossings/lengths | Never displaces manually locked positions; reports uncertainty |

A minimum useful demonstrator is gates **0–3** on the Steel Outpost, without forcing integration of the entire prototype or a full optimizer.

## 11. Open decisions and evidence gaps

These are **not** silently resolved by this specification:

- Whether the optional factory designer is a new app page under `site_planner_web` or a separately deployable client consuming the same contracts.
- Whether source `.sfmd` includes complete recipe IDs, machine clocks, flow links, machine quantities, and coordinates. Examine a real fixture; coordinate units may not be foundations.
- Who owns persistent factory designs (per-save vs per-site vs independent library), and whether multi-user/cloud sync matters.
- How a supply-side solver chooses among feasible product mixes when no target or preference has been supplied: present possibilities and request allocation, rather than inventing one.
- Which physical connector coordinate set is authoritative (game export, verified manual tables, mod inspection) and whether machines may be freely rotated/stacked.
- What 'balanced' means for non-divisible machine counts, fluid networks and mixed-clock banks; start with exact conveyor splitter topologies.
- Support for randomized world-resource presets: need save-derived assignments or documented deterministic seed materialization, not global-average purity assumptions.
- How the **adopted** shared-grid mode and the **implemented** `report_need` mode (A11) are represented alongside **proposed** stand-alone hypothetical biomass/coal/fuel and generation-mix diagnostics. The UI must distinguish constraints, prerequisites and refusals.
- Multi-floor/vertical geometry, transport mode, pipe headlift and crossing semantics are deferred until data supports validation.

## 12. Implementation discipline and source inventory

- Do not copy unclarified-license Satisfactory Production Planner application code. The intent is an independent design; a compatible licensed SFMD parser could be evaluated separately with attribution.
- Before touching repo: review current HEAD and later amendments to `site_planner_reframe.md`; inspect exact current `portfolio-plan/1`/`portfolio-inputs/2` export records and current `production_adapter.contracts` APIs. This document is intentionally interface-level until those contracts are mapped against running fixtures.
- Follow `AGENTS.md`: read the governing decision, preserve one canonical loader, refuse ambiguity, maintain AST import boundaries, test standalone + full, run manifests and separate manifest commit if files are changed. Never claim tests passed without execution.
- **Source files inspected:** repo `README.md`, `AGENTS.md`, `CLAUDE.md`, `planning_data/ARCHITECTURE.md`, `docs/plans/progression_optimizer_implementation_plan.md`, `docs/decisions/site_planner_reframe.md` (partial initial read), `docs/decisions/demand_expansion_scope_and_site_capacity.md` (partial initial read), `docs/product/site_planner_spec_v1.0_proposed.md` (partial initial read), `tools/site_planner_web/README.md`, `tools/site_planner_web/picker.html` (header), and attached ZIP files. Decision-record reconciliation checked the later amendments of all eleven files under `docs/decisions/`, with detailed re-read of the governing site-planner A1–A11, demand A5–A6, selected older crossover A24/A27/A34–A36, and solver-selection amendment §10. This is a source review, not runtime validation. Before implementation, recheck HEAD and any newer amendments. No code was executed from the ZIP and no repository tests were run for this specification.

---

**Summary:** Preserve existing world/site/progression authority. Add a source-independent factory production graph, import and placement adapters, and a physical layout workspace as an optional downstream realization. Reuse the Netlify experiment's user-facing phase and power-comparison ideas while replacing its embedded facts and calculations with the repository's data, scenario and production services. Treat layout as a distinct proposal with explicit validation and source provenance.