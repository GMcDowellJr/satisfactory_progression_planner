# Decision records — index

Records are **immutable and amended forward**: never rewrite a past section;
add `## Amendment N — <date>. <title>`. The current architecture is
`docs/ARCHITECTURE.md`. It names the governing decision for each concept.

Since 2026-11-17 (`site_planner_reframe.md` A15.2, decided by Greg), archived
records are **historical evidence only**. Cite them for why something is the
way it is, not as a current requirement in general discussion. Each one ends
with an "Archived" amendment saying what, if anything, reframe A15.4 brought
forward.

## Current

| Record | What governs |
|---|---|
| `site_planner_reframe.md` | §1–§5; A1–A11, A13, A14; **A15** (tracks, one specification, B1–B5, Q1–Q6); **A16** (tie-break, by-products to the sink, withdrawals ignored, viewers are tests; power proposed); **A17** (fluid by-products converted or burned); **A18** (fuel routes, no offset, power stack); **A19** (power through later phases, declared mix, power-site check, ledger retired, `demand_expansion` kept). A12: Greg's stated facts in A12.2 only; A12.3 is a proposal |
| `demand_expansion_scope_and_site_capacity.md` | A5 (sub-1× floor reads) and A6 (R does not scale milestone or MAM costs) only; the rest is archived |

## Archived (historical evidence)

| Record | Dates | Brought forward by reframe A15.4 |
|---|---|---|
| `bus_allocation_backpressure_and_residual.md` | 2026-09-21 | none |
| `bus_level_recompute_and_alternate_crossover.md` | 2026-09-21 to 10-09 (A1–A36) | A1 and A7 in-game reads |
| `demand_expansion_scope_and_site_capacity.md` (base, A1–A4) | 2026-09-19 to 10-10 | §3.2.4–3.2.5 and A2 rounding reads |
| `extraction_wiring_and_provenance_stamp.md` | 2026-09-18 | provenance stamp and extractor tables (contracts) |
| `goal_run_driver.md` | 2026-09-23 to 10-06 | none |
| `production_building_power_model.md` | 2026-09-18 | producer and variable-power facts |
| `production_lp_formulation.md` | 2026-09-18 to 10-06 | §18 tier rule, §19 pool |
| `production_solver_selection.md` | 2026-09-18 | F1 backend (HiGHS via scipy) |
| `resource_authority.md` | 2026-09-18 | whole record (P3) |
| `toggle_propagation_and_demand_pass.md` | 2026-09-21 | none |

## Archived proposals (not decision records)

- `docs/plans/progression_optimizer_implementation_plan.md`: the original
  plan.
- `docs/plans/factory_design_*_2026-11-10.md`: the factory-design
  specification and its reconciliation.
- `docs/product/site_planner_spec_v1.0_proposed.md` and
  `repository_capability_inventory_2026-10-12.md`: the reframe's §2 inputs.
  They were never adopted.

Each carries an "Archived 2026-11-17" banner. Nothing in them binds unless a
current amendment brings it forward.
