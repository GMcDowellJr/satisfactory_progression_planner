# Site Planner Reframe — Decision Record

- Date: 2026-10-12
- Status: adopted as a working direction (Greg, 2026-10-12). Adopted means enough to build toward, revisable when a better idea arrives or this one proves flawed.
- Supersedes, forward-only: the *standing* of earlier records, not their content. No prior record is edited.
- Intended home: `docs/decisions/site_planner_reframe.md` in `satisfactory_progression_planner`.

> **Provenance.** Drafted in conversation on 2026-10-12 while Greg's computer was off;
> written to the claude.ai Project first and copied into the repo on 2026-10-19, after
> PR #2 was merged (§5 updated accordingly before commit). The 2026-10-12 repo state in
> §5 was read from the public `origin` in a cloud clone; the 2026-10-19 state is as
> reported from Greg's machine.

## 1. Why

Working on the repo version kept losing the thread of what it was doing and where it was
going. The work went down a deep hole that may be technically correct but answers
different, more complex questions than the tool exists for. The diagnosis is the
*volume of decisions*: thoughts, ideas and items under consideration were recorded in
conversation as decisions, and each one then carried weight in later sessions.

## 2. The reframe

Treat two documents as a fresh concept baseline, as if starting over in concept:

- `docs/product/site_planner_spec_v1.0_proposed.md` — "Satisfactory Site & Logistics
  Planner", product and system specification v1.0 (proposed), 2026-10-12.
- `docs/product/repository_capability_inventory_2026-10-12.md` — capability inventory
  against that spec. A source and document inventory; nothing in it was executed.

Both are inputs to think with. Their contents are ideas until individually adopted.

Working direction: the tool helps with a general approach to **what can be made where,
and how to get resources from point A to B**. It never says exactly what to do and when.
Machine counts, under/overclocking and alternate-recipe specifics are well understood
and available elsewhere; they are not rejected, just not the priority now. Alternates
matter here from a progression and site-planning perspective.

## 3. Standing of earlier records

Everything recorded before this date is an **exploration log**: a history of ideas and
why they came up. It stays as written. Nothing in it binds the reframe unless it is
brought forward explicitly, and anything can be rediscovered during the work. This
covers, as of the state read in §5:

- `bus_level_recompute_and_alternate_crossover.md` A1–A36, including A26–A36 from the
  `claude/district-client-a26` branch merged as PR #2 on 2026-10-19;
- `demand_expansion_scope_and_site_capacity.md` A1–A4, `goal_run_driver.md` A1–A6,
  and the other records under `docs/decisions/`;
- the design notes and session handoffs in the claude.ai Project, 2026-09-18 to 2026-10-06.

Open for rethinking under the reframe, for example: whether a bootstrap is needed at all,
and whether any bill is needed beyond the required Space Elevator parts.

## 4. Status vocabulary from here

Every recorded item carries one status:

- `idea` — the default for anything that comes out of conversation;
- `under consideration` — actively being weighed;
- `adopted` — only when Greg says so; enough to build toward, revisable.

Nothing is recorded as decided by inference from discussion.

## 5. Repo state at commit

- Observed 2026-10-12 from the public origin: `master` at `a331323` (2026-10-10, merge
  of PR #3, demand expansion); branch `claude/district-client-a26` at `2a19efa` carrying
  crossover A26–A36 (2026-10-08/09), unmerged.
- 2026-10-19, before this note was committed: PR #2 merged into `master` on Greg's
  machine. Conflicts were `REPO_MANIFEST.csv` (regenerated) and the
  `production_adapter.__all__` export list (union of both sides). Suite on Greg's
  machine: 1215 passed, 3 skipped.
- **A26/A27 numbering.** The 2026-10-06 handoff records a different A26 and A27 that
  were written into Greg's working tree and never committed. They were discarded on
  2026-10-19; their substance survives in the claude.ai Project handoff
  `session-handoff-2026-10-06-1025.md`. In this repository, A26 and A27 mean the
  2026-10-08 amendments from PR #2. Cite by date as well as number when referring to
  the discarded pair.
