Satisfactory Site & Logistics Planner

Durable product and system specification — v1.0 (proposed)

Status: Product boundary proposed for adoption; not a claim of implementation.
Date: 2026-10-12
Scope: Worldwide site suitability, complementary manufacturing, resource competition, logistics opportunity, and progression.
Basis: v0.20 retrospective and supplied archive; mobile Pyodide prototype; repository GMcDowellJr/satisfactory_progression_planner architecture and agent guidance (reviewed 2026-10-12).

0. Product charter

Primary question: Given a world configuration and a progression horizon, what can reasonably be made where, which sites complement or compete with one another, and what could connect them?

Product identity: A geographic industrial-development decision-support system, not a factory calculator, prescribed build order, or global optimal-play solver.

Success criterion: A player can inspect a place or manufacturing need, understand multiple plausible geographic arrangements, compare their bottlenecks and logistics burden, and choose a development direction without being told the exact machine layout or construction schedule.

Decision rights: The tool surfaces evidence and consequences; the player decides goals, site uses, routes, timing, and acceptable tradeoffs. Do not convert a heuristic score into an imperative recommendation.

1. Questions the product must answer

1. Site opportunity: What resources belong to this candidate site’s catchment? What manufacturing families or products could it support locally, at what approximate rate or bound, under stated phase, unlock and recipe assumptions? What limits it?
2. Complementarity: If a candidate lacks a key input, where might that input or a useful intermediate be supplied? Would moving Plastic be more plausible than relocating Computer manufacture, for example?
3. Competition: Which products, energy uses, and other candidate sites claim the same resource sockets, extraction capacity, or access corridors? What alternative opportunity does a commitment displace?
4. Connection: What viable or plausible corridors join the sites, and what must move, in which direction and in what quantity? How do horizontal distance, elevation, terrain, access, and transport maturity affect the comparison?
5. Progression: How does the opportunity change with phase, unlocked recipes, extraction/logistics technology, and game modifiers? What capabilities become available later, without prescribing when the player must build them?
6. Explanation: Why is a site, combination or route attractive; what assumption would reverse the result; and what remains unknown?

2. Non-goals and explicit boundaries

• Do not attempt to output an exact factory blueprint, floor layout, conveyor topology, machine count, clock setting, shard allocation, construction order, or minute-by-minute phase schedule.
• Do not reconstruct a second canonical game database, scenario multiplier implementation, or generic production LP engine inside the spatial tool or UI.
• Do not claim global optimality from bounded candidate generation, approximate catchments or unresolved routes.
• Do not treat future-phase reserves as mandatory, or assign a permanent industrial role to every resource cluster.
• Detailed power dispatch, extractor clock optimization, fluid-network hydraulics, and steady-state byproduct disposal are subordinate feasibility studies when relevant; they must not become the main player workflow.
• A higher-throughput candidate is not automatically preferable to one with shorter logistics or preserved optionality.

3. Planning vocabulary

• Socket: A canonical world resource location/identity, independent of purity and resource assignment.
• Materialized world: Socket placements paired with the selected world’s resource/purity assignment and build-aligned spatial data.
• Site: A candidate production location with a spatial footprint, access characterization, and an explicitly attributed set of resource sockets. Site labels are descriptive, not fixed product assignments.
• Catchment: A policy-generated relation between a site and potentially accessible resources; candidate membership is not ownership.
• Claim/ownership: A scenario-specific exclusive reservation of a socket or an explicit divisible share of available extraction, never counted twice.
• Opportunity: A product/family/site capability derived from recipe requirements, accessible supply, unlocks and stated constraints.
• Role: An optional label summarizing an opportunity (Steel, Oil, Electronics, Power); it must not constrain the search unless deliberately pinned by the player.
• Portfolio: Several products or families at one or more sites sharing material and resource limits.
• Stage: A recipe/process activity or intermediate transformation that may be performed at an eligible site; a stage location can be pinned, excluded or explored rather than predetermined.
• Flow: A directional transfer of a specified item between sites, with rate and mode assumptions.
• Connection: A relationship between sites. Distinguish geometric proximity, candidate topology, recovered corridor, and transport-validated route.
• Opportunity cost: The foregone feasible capability caused by consuming, reserving or routing a shared constrained resource; distinguish measured displacement from a speculative future alternative.
• Scenario: A reproducible combination of game build, world assignment, progression horizon, unlocked options, recipe/power multipliers, extraction/logistics assumptions and planning preferences.

4. Functional requirements

F1. World and site discovery (required)

• Explore all supported world regions; allow map selection, search, filtering and player-added candidate sites.
• Show raw socket IDs, resource, purity, per-socket assumed extraction rate and site association. Display vertical separation; it is a friction factor, not an automatic exclusion.
• Preserve overlapping candidate catchments; enforce exclusive ownership only within an evaluated portfolio.
• Explain catchment policy and gaps (terrain resolution, access uncertainty, approximate site surface).

F2. Local manufacturing opportunity (required)

• Show product/family feasibility under baseline recipes and selectable unlocked alternatives, using canonical recipe coefficients.
• Provide material ceiling, limiting resource(s), demand per limiting resource and utilization/residual capacity. A ceiling is not an operating production promise.
• Surface mixed opportunities; do not rank one family as a site’s intrinsic purpose.
• Explain what inputs must be imported when local supply is insufficient.

F3. Portfolio and stage placement (required)

• Evaluate simultaneous output targets across several sites while sharing raw socket budgets.
• Allow per-stage placement status: free to assign, pinned to site, excluded at site. Support split production where the model and stated policy permit it.
• Discover multiple materially different candidate portfolios, not just repetitions of a hardcoded Steel/Oil/Electronics partition.
• Track all local production, raw extraction, coproducts, residuals, imports, exports and unmet goals in a conservation ledger.
• Selection of stages must emerge from the portfolio problem, not from a fixed site-role template.
• A bounded, heuristic search is acceptable if its bounds, omissions, and coverage are explicit.

F4. Competing use / opportunity cost (required)

• Expose which alternatives contend for each limited socket, extraction share and material flow.
• Compare at least one alternate use for a contested resource where data supports it (e.g., Coal→Steel vs Coal→Power, Oil→Plastic vs Oil→Fuel).
• Report allocated, reserved, and unused separately. Do not count an unused owned socket as consumed.
• Preserve distinct portfolios with different throughput, logistical burden, compactness, and optionality; avoid a single hidden weighted score.

F5. Logistics opportunity (required)

• For each necessary transfer, report source, destination, item, direction and modeled flow rate.
• Distinguish connection evidence states: unresolved, straight_line_only, candidate_corridor, recovered_corridor, mode_feasible (only if verified under declared mode assumptions).
• Elevation, distance, grades/terrain, chokepoints, buildable access and transport unlocks influence route friction; no single vertical threshold is an absolute veto unless a mode-specific constraint is proven.
• Do not present a connecting line as a traversable vehicle route.
• Use reusable terrain/corridor/build-surface layers from the repository where available.

F6. Progression and scenario comparison (required)

• Support phase/tier horizons, unlock-aware alternate availability, resource assignment configurations, recipe multiplier and power multiplier; preserve game build identity.
• Show how a site’s opportunities or a portfolio’s ranking change across scenarios and which changed assumption caused it.
• Treat projected future uses as configurable opportunity scenarios, never as mandatory reservations.
• Do not silently equate phase with all recipes automatically unlocked; disclose simplified unlock policies.

F7. Explainability and uncertainty (required)

• Every capacity/result must carry its status: material_bound, constraint_screened, or operationally_validated, with evidence basis and unresolved checks.
• Each proposed allocation must answer: Why these sites? Why these stages? Which constraints bind? What must move? Which alternative was displaced? Which assumptions might reverse the comparison?
• Distinguish infeasible under modeled constraints, not assessed, not discovered by bounded search, and unknown due to missing data.
• Never describe twelve candidates as exhaustive or fully feasible merely because twelve were generated.

5. Shared mathematical service: how much precision is enough?

The authoritative repository production_adapter owns item/recipe IDs, scenario per-cycle rounding and the generic recipe balance. A spatial planning service may extend the formulation with site indices, attributed raw supply and transfer variables; it must not fork production mathematics or own competing recipe CSV loaders.

Minimum conservation invariant (for each site and item): local production + raw draw + inbound transfers = local recipe consumption + outbound transfers + selected target deliveries + modeled residual/disposal. Distinguish residual material from physically feasible disposal; the existing backend’s free/forbid modes and warnings remain significant.

Planning resolution: fractional rates are fine to compare opportunities and locate limiting inputs. Machine equivalents and clock speeds are optional diagnostic details, not primary outputs. Any operating capacity dependent on power, water or disposal must be labeled conditional until those constraints are modeled and checked.

Optimization boundary: Optimization is allowed for where production stages occur, what materials move, and how limited site resources are shared. It is not a request for the best factory design. Preserve multiple nondominated solutions instead of asserting one universally best solution.

6. Layer architecture and repository alignment

|Layer                |Owns                                                                           |Must not own                                |
|---------------------|-------------------------------------------------------------------------------|--------------------------------------------|
|Game reference       |Canonical IDs, recipes, buildings, unlocks                                     |Scenario assumptions or geographic decisions|
|Scenario             |Runtime modifier transformation, unlock policy                                 |Mutation of canonical game facts            |
|World extraction     |Stable sockets, world assignments, terrain/water                               |Site-use choices                            |
|World analysis       |Candidate surfaces, resource catchments, corridor topology                     |Player industrial goals                     |
|Shared production LP |Recipe coefficients, material conservation, backend numerical behavior         |Site ranking or map UI                      |
|Spatial planning     |Site-indexed supply, stage assignment, flow conservation, portfolio exploration|A second recipe database or solver kernel   |
|Decision presentation|Comparisons, explanations, map interactions                                    |Recipe or LP mathematics                    |

Repository constraints: Follow AGENTS.md import boundaries. production_adapter/gamedata.py remains the only reader of canonical game-reference CSV columns. Keep a site/world joint above subordinate packages (e.g., a root-level orchestration module), not imported upward into production_adapter. Preserve existing SolveRequest/SolveResponse; add a versioned spatial-planning contract rather than overloading aggregate requests. Do not modify past decision records; amend forward. Default-world build 502094 is a fixture, not a map-specific assumption.

Implementation seam: Share recipe coefficients, solver execution, tolerance and diagnostics; spatial formulation owns site-indexed variables, eligibility, transfers and socket claims. A single-site spatial formulation should reconcile with the aggregate material result under matching policies. Do not solve each site independently and merge the answers.

7. Mobile-first client contract

Execution: Pyodide on iPhone is an established viable path from earlier project experience. Python remains authoritative. The client visualizes and controls models and never duplicates formulae in JavaScript.

Primary UI: Map as default surface, with an adaptable bottom panel for selected Site / Opportunity / Portfolio / Connection / Scenario. Tapping a product may highlight candidate suppliers; tapping a transfer highlights sources, destinations and candidate corridors. A compare view presents 2–3 contrasting portfolios. Deep machine details, if exposed, live under optional diagnostics.

Future-proof protocol: The Python bundle declares an API/schema version, game/build provenance, capabilities, accepted filters and parameters, available output view-types, and diagnostic namespaces. Client components consume stable semantic records (site, resource, opportunity, portfolio, stage, flow, connection, evidence) rather than knowing internal Python module names or hardcoded recipe roles.

Compatibility rule: Backward-compatible additions may introduce fields, products, site layers and evidence types without altering the client. Breaking changes require a major schema version, migration or explicit unsupported-version message; unknown optional fields must be safely ignored, unknown required capabilities must fail visibly. Do not claim arbitrary future schemas can render automatically without a corresponding display component.

Performance: Cache precomputed worldwide opportunities as optional snapshots with matching provenance. Recalculate targeted allocations in Pyodide, preferably in a Web Worker to keep UI responsive. Show cancellation, progress and failures; prove memory/performance on actual iPhone devices before setting production budgets. Bundle the Python modules needed by the browser, not a second JS implementation.

Conceptual interchange envelopes (illustrative, not frozen field-level API)

{"schema":"site-planning/1.0","engine":{"name":"python-spatial","version":"0.x"},"world":{"game_build":"502094","assignment_id":"default"},"scenario":{"phase":3,"recipe_multiplier":1.25,"power_multiplier":5},"capabilities":["site_opportunity","portfolio_assignment","connection_evidence"],"request":{"kind":"compare_portfolios","targets":[]}}

{"schema":"site-planning/1.0","result_kind":"portfolio_comparison","status":"material_bound","portfolios":[],"evidence":{"routes":"unresolved","power":"not_assessed"},"warnings":[],"provenance":{}}

These examples specify meaning and versioning; adopt actual field schemas only after contract tests against the current Python modules.

8. Comparison model

Display objective dimensions separately, each with known units and evidence quality:

• Capability: feasible product set and throughput/material ceiling.
• Resource pressure: binding nodes, utilized and residual raw supply, displaced alternatives.
• Logistics: total transfer volumes by item, number of transfer relationships, lengths/grades/routes where supported.
• Site suitability: buildable area/access/corridor confidence where supported.
• Progression cost: unlock dependencies, equipment/transport requirements, later opportunity changes.
• Operational burden: power/water/disposal constraints only when actually assessed.

Maintain a Pareto-style candidate set, including distinct alternatives. Weighted ranking is optional, declared and inspectable; never present its first result as objective truth.

9. Reproducibility and evidence rules

Each result binds to a reproducible fingerprint: game build, world-assignment identity, world extraction manifest, candidate/catchment policy, recipe set and unlock policy, scenario modifiers, site/sockets and ownership, route policy, solver/backend version, objective configuration, numerical tolerances and search scope. Capture what was assessed vs what was assumed. Report solver infeasibility with named binding/violated conditions where available; do not fabricate a route, capacity, or missing-data estimate.

10. Acceptance scenarios (product tests, not merely unit tests)

A. Oil site limited by Copper: Show that a site rich in Oil but with one impure Copper node can have strong Oil/Plastic opportunity but Copper-limited local Computers; allow a complementary Electronics site and show Plastic transfers. Do not assume the site must be an Electronics district.

B. Mixed Phase 2 district: With Iron, Coal, Limestone and Caterium present, represent competing Steel Pipes / Motors / Heavy Modular Frames and other eligible products simultaneously. No double use of raw supply; expose residuals. The exact rate is scenario-dependent, not specified here.

C. Stage placement is actually free: Compare manufacturing Computers at Oil against moving Plastic and producing Computers near Copper/Caterium. Pinning one stage must change feasible assignments or explain infeasibility. No pre-coded three-role partition may be required for this test.

D. Power opportunity: Compare Coal dedicated to Steel versus a bounded Coal-to-Power alternative. If water or operating power cannot be verified, label the power alternative conditional rather than assigning a false MW certainty.

E. Progression/multipliers: At 1× vs 1.25× vs 2× recipe inputs, recompute through canonical per-cycle rules; show altered bottlenecks and relative geographic attractiveness with attributable causes. Power 5× changes operating-screening status, not raw-resource mathematics.

F. Terrain/elevation: Two complementary sites separated vertically remain candidates, with increased route friction and an honest connection-evidence label. A drawn line alone cannot pass as a verified road.

G. Search diversity: Candidate discovery must return materially distinct geographic/production alternatives when they exist. Report search bounds; a missing arrangement is not proof of infeasibility.

H. Browser parity and evolution: Identical versioned inputs produce numerically equivalent Python desktop and Pyodide results. Adding a new opportunity type or optional field does not break the client. An incompatible major schema fails clearly.

I. Canonical consistency: Single-site spatial material balances reconcile with repository production_adapter on same recipe set, caps, disposal and objective. Existing repository tests, import-boundary tests and manifest checks continue to pass.

11. Roadmap governed by the product questions

Release 1 — Site truth: Canonical loader integration, socket attribution, comparable resource budgets, local opportunity cards, explicit capability/bottleneck and provenance. Reconcile current v0.20 data before introducing more coverage.

Release 2 — Geographic relationships: Stage-assignable multi-site material allocation using the shared LP infrastructure, explicit transfers, scenario-sensitive recipe choices, portfolio diversity and explanations.

Release 3 — Competing development: Resource opportunity costs across products and energy uses; selectable future reservations; progression deltas.

Release 4 — Connection evidence: Recover supported corridors, incorporate buildable access/elevation and transport unlocks; distinguish mode feasibility from generic connectivity.

Release 5 — Operational screens: Introduce power, water, disposal and transfer capacity only where materially useful to screening geographic options, retaining conditional statuses elsewhere.

Cross-cutting: Mobile-first Pyodide UI and versioned capability contracts at every release. Existing playthrough/save state is optional and downstream, not a prerequisite for the worldwide opportunity explorer.

12. Development decision gate

Before approving a substantial feature or solver change, answer all four:

1. Which geographic or progression decision can the player make that they could not make before?
2. Which site, portfolio or connection evidence will change, and how will it be explained?
3. Does existing canonical data or production mathematics already support it? If so, why is a new implementation necessary?
4. What counterexample or acceptance case would prove that the feature misleads the player?

If a proposal only increases machine-count precision or introduces a new numerical objective without changing a planning decision, it belongs in the external factory-calculation domain, not this product roadmap.

13. Open decisions to record, not silently settle

• Whether the default comparison horizon is one phase, next-phase plus current, or user-defined.
• Whether sites are initially generated from resource neighborhoods, buildable-surface candidates, or a hybrid discovery policy.
• Which criteria determine candidate catchments versus player-claimed ownership and which extraction tiers are assumed for ceilings.
• How many alternative portfolios should the mobile view surface without suppressing Pareto diversity.
• Which operational constraints are mandatory screens at each phase versus optional diagnostics.
• How to describe transport friction without imposing unjustified monetary or numerical cost proxies.
• Whether player-created districts are named presentation groupings, saved scenario constraints, or both.

None of these questions blocks release 1. Where undecided, surface the policy as an explicit assumption and refrain from claiming optimization beyond it.

14. Definition of done for the specification

The planner is aligned to this charter when a user can answer, from a map: what could be made here; with which shared local resources; who else needs those resources; where might missing inputs come from; how plausible is the connection; what changes later; and why might another arrangement be preferable? It must do so without requiring the player to request an exact machine design.