# Factory Design Integration — Decision Record Reconciliation

**Date:** 2026-11-10  
**Status:** Review of proposal; **not** a new adopted decision or a repository edit.  
**Primary artifact:** `factory_design_repository_integration_spec_reconciled_2026-11-10.md`

## Outcome

The proposed factory-design extension remains architecturally compatible **if it is optional and downstream**. The original draft needed several concrete corrections and precedence qualifications. The linked reconciliation table in §2A of the revised specification is the authoritative change register for this review.

## Material corrections

1. **Decision precedence:** the October 12 reframe makes pre-reframe records exploratory, even when they say “decided” in their historical context. Later site-planner A1–A11 define the current portfolio workflow. Existing algorithms are facts about implementation, not automatically current product requirements.
2. **Rounding:** demand-expansion A5.1 (October 26) establishes minimum **one** for *solid* ingredient amounts at R=0.25, nearest integer half-away-from-zero. The previous draft incorrectly left low-R solids unresolved. A5.2 keeps *fluid floor units* unresolved. Its current 1 m³ behavior is an assumption, not proof of game behavior; a 0.25× Plastic recipe in-game read would discriminate.
3. **Multiplier scope:** R does not change Build Gun, milestone or MAM costs; E changes Project Assembly quantities. P changes powered machine/extractor/sink consumption but not generator output or the clock-power exponent (demand A5.3–A6; reframe A7).
4. **Portfolio schema:** `portfolio-inputs/2` and `portfolio-plan/1`; `/2` adds required `power_mode`. Reframe A10's `/1` was superseded by A11.3. Enforce explicit migration/refusal for earlier inputs.
5. **Power:** shared-grid solve (A3–A7) and `report_need` (A11) have different contracts; report_need does not guarantee fuel feasibility, and explicitly refuses pumped Water, standing-grid combinations and district solving. Independent generator-mix UI remains a proposed diagnostic, not adopted solving behavior.
6. **Byproducts:** use is adopted, but enforcement/overflow/sinking remains unresolved (A8); model unallocated byproducts and backpressure explicitly.
7. **Site sockets:** resource neighborhoods do not confer ownership. A9/A10 require declared included kinds, policy-provenance, materialized assignments and an explicit socket claim when used as factory supply.
8. **Factory placement:** the existing site planner disclaims exact layouts; optional downstream layout tool does not supersede the reframe. Routing/crossing validity remains a separate technical verification.
9. **Old district rules:** A24/A27 supply-first and A34–A36 single-recipe/300-MW/installed-vs-planned are older exploratory records. They may inform design but must not silently govern the new client. Supply-first is newly requested behavior, not an automatically imported binding historical decision.

## Status by category

| Category | Status | Next proof |
|---|---|---|
| Scope isolation | Compatible as proposal | Explicit forward-only adoption decision if selected |
| Production solver/data ownership | Compatible | Current adapter/fixture tests |
| SFMD import | Proposed, schema not confirmed | Parse a genuine export and reconcile IDs |
| Supply-first client | Proposed | Declare objective/allocations; do not invent an output optimum |
| Layout geometry, balanced routing | Proposed | Ports, belt throughput and collision tests |
| Phase prototype migration | Rework required | Five phases against canonical build-pinned records |
| Low-R solids | Observed rule | Confirm code behavior and add regression test |
| Low-R fluid floor | Open | In-game 0.25× Plastic crude input read |
| Power-mix comparison | New diagnostic | Reconcile fuel production loops and mode exclusions |
| Browser portfolio format | Current schema known | Actual `/2` fixture and current HEAD contract |

## Repositories and decision sources checked

- `GMcDowellJr/satisfactory_progression_planner`: `README.md`, `AGENTS.md`, `planning_data/ARCHITECTURE.md`, `docs/product/site_planner_spec_v1.0_proposed.md`, `tools/site_planner_web/README.md`.
- All eleven `docs/decisions/*.md` files: heading/dated-amendment inventory; selected governing amendments read in detail, especially `site_planner_reframe.md` A3–A11, `demand_expansion_scope_and_site_capacity.md` A5–A6, `bus_level_recompute_and_alternate_crossover.md` A24/A27/A34–A36 and `production_solver_selection.md` §10.
- No code edits, builds, tests, changes to decision records or GitHub commits were performed.