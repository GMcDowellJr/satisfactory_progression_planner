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

## Amendment 1 — 2026-10-19. Portfolio inputs

Context: the site card (handoff 2026-10-19 12:35, actions 1-2) reports each
product's ceiling ALONE. Greg, 2026-10-19 13:14: a site makes a combination,
never one item ("you'd never have that oil site just make screws"), and
production must be balanced against power. A combination needs a demand and
other sites to trade with; it does not need a whole-world plan.

### A1.1 Adopted by Greg, 2026-10-19

Status `adopted` (§4): enough to build toward, and it holds only until something
comes up that proves it wrong (Greg, 2026-10-19 13:36). A reversal is recorded
forward, in a later amendment, naming what proved it wrong.

| # | Question | Adopted |
|---|---|---|
| P1 | Demand | Project Assembly + milestone bill for now. Declared target rates will be wanted later. |
| P2 | Power | Outside the solve, as spec F7 / §5 suggest: a later conditional screen. Reported, not constrained. |
| P3 | Transfers | Free between declared sites. Logistics complexity later. |
| P4 | Scope | A bounded set of declared sites. World search later. |
| P5 | Transfer volume units | 1 item = 1 m3 in the tie-break that minimises volume moved; stated as an assumption in every report. |
| P6 | Raw transfer | Raw resources may move between sites. |
| P7 | Delivery | The bill counts wherever it is made; no haul to the Space Elevator is modelled. |

### A1.2 Consequence recorded

With free transfers (P3) the bill scale equals that of one merged site with
every site's caps pooled; which site makes what is otherwise arbitrary. The
volume tie-break (P5) is what places production near its inputs. It is a
LATER stage than the bill scale, so it never trades bill coverage for less
haulage. Its order relative to the goal-cost stage is a design choice the
design note proposes and Greg confirms.

## Amendment 2 — 2026-10-19. Portfolio stage order

### A2.1 Adopted by Greg, 2026-10-19

A1.2 left the order of the volume stage and the goal-cost stage open. Greg,
2026-10-19 13:52: "produce locally better than transporting items". Adopted
(§4; holds until something proves it wrong): among plans of equal bill scale,
least volume moved comes before the cheapest goal cost. This is the order
`LpBackend.solve_portfolio` already uses, pinned by
`test_locality_comes_before_a_cheaper_recipe_mix`.

### A2.2 Recorded as ideas, not adopted

- Capacity left idle after the bill scale (scenario C: ~890 of 1020/min
  Crude Oil) is to be addressed, possibly as part of later progression steps.
- Whether power belongs in the portfolio solve is under discussion.

## Amendment 3 — 2026-10-19. Power into the portfolio solve (A1 P2 reversed)

### A3.1 What proved P2 wrong

Measured 2026-10-19 (container, scenario C: oil site r 500 m around
BP_ResourceNode98 + copper site r 500 m around BP_ResourceNode213, tier 6,
bill phase 3 + tiers 5-6, recipe x1). With power outside the solve, the
plan needed ~1534 MW (machines + extractors). Coal power for that is ~307
Coal/min plus ~920 Water/min, while Coal already bound at both sites for
steel; and ~890/min Crude Oil sat idle that could give ~595 Fuel/min,
~7,400 MW gross from Fuel generators. Outside the solve neither coupling
could appear, and spec scenario D (Coal to steel vs Coal to power) could not
be represented at all.

### A3.2 Adopted by Greg, 2026-10-19 (holds until proven wrong)

- Power is in the portfolio solve as ONE shared grid: generated + standing
  grid >= machines + extractors + spare, one row over every site.
  Generators may be built at any site and burn that site's supply, or fuel
  moved there (A1 P3 applies to fuel like any item).
- Machine power at 100 % clock is the default (mean draw for variable-power
  recipes). The scenario's machine-power multiplier already applies;
  clock changes, shards and Somersloops may move into the solve later.
- Which generators exist comes from the unlock data by tier:
  `progression.unlocks.generators_open_at_tier` (Build_X_C -> Desc_X_C ->
  build recipe -> schematic -> tier, the join `extractors_open_at_tier`
  already uses). Biomass tier 0, Coal tier 3, Fuel tier 5, Nuclear tier 8;
  Geothermal is MAM research and not implied by a tier. Sub-tier
  (milestone-level) granularity: possibly later, for recipes and
  generators together.

### A3.3 Carried conventions, not new decisions

- Extractors are charged at nameplate as a constant (A25.3 P2). Measured
  consequence: a site that can fuel no open generator cannot run its own
  miners, so the copper site alone in scenario C is infeasible (said so by
  name in the report). Whether extraction power should follow the draw is
  open.
- A declared supply (Water) carries no extractor power.
- After A3 the oil site draws ~265 of 1020/min Crude Oil; the A2.2 idea
  (put idle capacity to work, possibly in later progression steps) stands.

## Amendment 4 — 2026-10-19. Extraction by the draw; Water pumped, never free

### A4.1 What raised it

A3.3 left open whether extraction power should follow the draw. Under the
carried A25.3 P2 constant (every declared extractor at nameplate) the copper
site in scenario C was "infeasible" alone: 95 MW of miners and no generator
it could fuel. Greg asked why copper needed Water at all. It does not; power
does. At tier 6 the open generators are Biomass (no source in the solve),
Coal (45 m3/min Water each) and Fuel (no Oil at that site), and Water entered
the solve only as a free, capped `--supply` nobody had declared there.

### A4.2 Decided by Greg, 2026-10-19 (holds until proven wrong)

- Extraction is charged by the DRAW in the portfolio solve: MW per unit =
  base MW / nominal rate at 100 %, linear on what is extracted. An idle
  socket costs nothing. Floor-safe at or below 100 % clock, since the game's
  curve (P = base * clock ** 1.321929, extraction_buildings.csv) sits below
  the line.
- 100 % clock is the cap for now. Underclocking is always available (no
  shards); overclocking is limited and rare. A clock above 100 % is refused
  by the composer, not modelled.
- The report gives the draw WITH the nameplate figure beside it.
- Water is never free. Water extraction and pumps are expensive to operate.
  A site is DECLARED able to pump Water (the world data does not say where
  water bodies are, so nothing defaults it). There it is uncapped, charged as
  Water Extractors by the draw (20 MW per 120 m3/min), and reported as the
  amount needed, to be used later to count, group and clock extractors. The
  free declared Water supply is replaced: refused by name.
- Build counts (how many machines) are reported later, once belt speed, pipe
  volume, number of lanes, clocking and multipliers are taken into account.
  For now the materials to make the buildings are assumed on hand or to be
  obtained.

### A4.3 Measured 2026-10-19 (container, py3.13), not derived

- Scenario C (as A3.1, no site pumping): together 0.003499/min and oil alone
  0.000704, both unchanged; power was never the limit there (shadow 0).
  Extractors draw 141.9 MW of 380 MW nameplate. Fuel generators 5.515
  (1379 MW) where A3 built 6.528 (1632 MW). Copper alone is now 0.0, and the
  report says why: it cannot make Plastic, Rubber, Computer, Modular Engine
  or Adaptive Control Unit without Oil. The "infeasible" label had hidden
  that the bill, not power, was the reason.
- Spec scenario D (copper site alone, tier 4, bill phase 2 + tiers 3-4): Water
  declared pumpable 0.003770/min, 72.4 of 180 Coal/min burned in 4.82 Coal
  generators, 217 m3/min pumped, power limiting; no Water and no grid 0.0;
  a 5000 MW standing grid instead 0.006305/min with every Coal to steel. The
  power alternative is labelled CONDITIONAL on the Water declaration, as
  spec §10 D asks.

### A4.4 Not changed, said so

- `solve_district` (district_run, site card) keeps the A25.3 P2 constant;
  its `DistrictPower.extraction_nameplate_mw` is None there.
- The site card has no power in its solve, so its `--supply` of Water stays a
  capped declared supply. Whether that should change is open.
- Supersedes A3.3's first two bullets for the portfolio solve only.

## Amendment 5 — 2026-10-19. Power on the site card; shadow prices in plain language

### A5.1 Decided by Greg, 2026-10-19 (holds until proven wrong)

- "Add power to site card", answering A4.4. Each product shows BOTH
  ceilings side by side: the material ceiling (power from outside,
  unlimited, as before) and the self-powered ceiling (generators open at
  the tier burning the site's own supply, a declared standing grid, default
  0, extractors by the draw, Water only where declared pumpable). The gap
  between them is what powering itself costs the site. The self-powered
  ceiling is a one-site `solve_portfolio` with that product as a one-unit
  bill (spec §10 I), so A3 and A4 apply unchanged. The card's free Water
  `--supply` is refused, as in portfolio_run.
- Shadow prices read "per unit, marginal" in every report (site card,
  portfolio_run, district_run), through tools/shadow_text.py: "+1/min Iron
  Ore -> +0.6667 Iron Plate/min at the margin"; "+10 MW -> +2.042 Steel
  Ingot/min at the margin"; for a bill scale, "+10 MW -> horizon 265.2 ->
  262.0 min at the margin". Each report states once that a marginal figure
  holds only for small changes.

### A5.2 Defect found and patched while building it

The self-powered column first read "no gain at the margin" for caps it
was bound by. Under A4 a raw's cap was bounded twice, on its draw and on
its extraction segments, and the binding-cap price was read from the draw's
bound while HiGHS had put the dual on the segment. The price is now read
from the saturated segments, and the draw's own bound is lifted, since the
segments carry the same total (PortfolioSite checks this). Where segments
differ in MW per unit and power binds, one more unit is worth different
amounts depending on the socket, so the price is reported as a range
(`BindingCap.shadow_price_high`) rather than one socket being chosen.
The scenario C and D figures in A4.3 are unchanged (suite re-run).

### A5.3 Not changed, said so

- The card's pool comparison (`--compare-pool`) stays material only.
- A clock above 100 % leaves the card's material column and drops the
  self-powered one, naming why (A4: overclocking is not modelled).

## Amendment 6 — 2026-10-19. One power implementation; district_run by the draw

### A6.1 What raised it

After A4 and A5 the same work was assembled in several places. The site card
and portfolio_run each built their generator set at the tier and their
extraction segments (the card held helpers portfolio_run borrowed). The
solver had two power rows, one in `_build_core` (district, constant
extraction) and one in `solve_portfolio` (draw, as separate columns).
district_run still charged extractors at nameplate and could not pump
Water (A4.4). Greg, 2026-10-19: "we should have shared modules for stuff
like this".

### A6.2 Decided by Greg, 2026-10-19 (holds until proven wrong)

- Shared modules, and district_run moves to the draw (option a), with
  nameplate reported beside it.

### A6.3 What was built

- Solver: the extraction columns, link rows, bound lift (A5.2), power-row
  charge and power-goal price live in `_build_core`. `solve_district` and
  every site of `solve_portfolio` use them, and read binding prices and the
  drawn / nameplate / pumped figures through one helper each.
  `solve_portfolio` lays sites at their own offsets, since their extraction
  differs. `DistrictRequest.extraction` mirrors `PortfolioSite.extraction`,
  with one shared validator (`contracts.check_extraction`).
- Composer, in `progression.district`: `site_extraction` (sockets by the
  draw, declared supplies at 0 MW, pumped Water when declared),
  `pumped_caps`, `reach_caps`, `generators_at_tier`, and
  `extraction_at_share` (below). The site card, portfolio_run and
  district_run call these; tests/test_shared_power.py fails if any of them
  assembles extraction or a generator set itself, or passes a constant
  nameplate charge.
- district_run: solve mode charges the draw on the power row. Report mode
  has no power row, so each raw's sockets are read at the same share of its
  cap (`extraction_at_share`): no socket is preferred, and it is floor-safe
  at or below 100 %. The declaration must state `WATER_PUMPABLE`
  (district_phase2: False, since A35 G2 put the standing generators' water
  outside). Standing generators fed from the district's caps are refused in
  solve mode: the caps are then net of their draw and the draw feeding them
  would need its own charge.

### A6.4 Measured 2026-10-19 (container, py3.13), not derived

district_phase2, scenario 1.25x recipe / 5x machine power:

- shipped, power solve: extraction 4.99 MW drawn of 35 nameplate; scale
  0.000435 (was 0.000386), horizon 2296.4 min (was 2589.7); lanes 265.01 MW
  (was 235); 25 whole machines (was 24), 200.07 MW realized (was 174.41).
  The 25 % case gives the same plan: MW per unit does not depend on the
  clock.
- shipped, power report: extraction 25.95 MW at equal shares; SHORT by
  866.15 MW (was 875.20).
- Scenario C and D (A4.3) and the site card (A5) unchanged: the suite pins
  them and passes.

### A6.5 Open, not decided

- The 5x machine-power multiplier scales machine draw and has never scaled
  extraction (the 35 MW nameplate was always unscaled). Whether miners and
  pumps count as consumers under the multiplier is Greg's to decide.

## Amendment 7 — 2026-10-19. The machine-power multiplier applies to extractors

### A7.1 Decided by Greg, 2026-10-19 (holds until proven wrong)

"Yes, the 5x power multiplier affects extractors too", answering A6.5.
Miners, oil and water extractors and pumps draw power scaled by the
scenario's machine-power multiplier, like machines. Generators are not
scaled (unchanged; `GeneratorFuel`).

### A7.2 What was built

`progression.site_extraction` takes the scenario (required, no default)
and scales the canonical extractor MW through `Scenario.apply_power`, the
same transform machine power goes through. Everything that reads the
segments follows from that: the power-row charge, the power-goal price,
the drawn and nameplate figures, the pumped charge, and
`extraction_at_share`. The tools' nameplate now comes from the scaled
segments (`progression.nameplate_mw`). tests/test_shared_power.py refuses
a tool importing the unscaled `extraction_nameplate_mw`.

### A7.3 Measured 2026-10-19 (container, py3.13), not derived

district_phase2 (1.25x recipe / 5x machine power), shipped:

- power solve: extraction 23.22 MW drawn of 175 nameplate; scale 0.000406,
  horizon 2466.0 min (A6: 0.000435 / 2296.4; before A6: 0.000386 /
  2589.7); lanes 246.78 MW; 24 machines; 186.06 MW realized.
- power report: extraction 129.76 MW at equal shares; SHORT by 969.96 MW.
- Every canonical (1x) figure is unchanged: scenarios C and D, the site
  card. The suite pins them and passes.

### A7.4 Not changed, said so

`progression.power.ledger` (the report-only ledger from the D4/A5 goal_run
work) still lists bootstrap extractors at unscaled nameplate. No tool calls
it; tests do. Left as recorded. Carrying A7 there is open.

## Amendment 8 — 2026-10-19. By-products are used; idle capacity is reported only

### A8.1 What raised it

Greg, 2026-10-19, on the handoff's "the slowest item paces the bill and the
rest of the site sits idle": nothing is idle until storage fills, assuming
overflow doesn't go to a sink. Checking scenario C against that found a
built line with no consumer. The portfolio solve runs with unconsumed output
FREE (LpBackend D1 stopgap: a disposal activity is blocked on P5, and the
bill output is itself leftover flow, so FORBID is refused there, A31). So
the oil site's Fuel refineries leave Polymer Resin with nowhere to go, and
`portfolio_run.report` does not list it.

### A8.2 Measured 2026-10-19 (container, py3.13, master 6da07ee), not derived

Scenario C as in A3.1 (tier 6, bill phase 3 + tiers 5-6, recipe x1):

- No site pumps Water (the shipped case): Polymer Resin 53.33/min made,
  0 consumed, at the oil site, from 1.778 Fuel refineries. Heavy Oil Residue
  58.78/58.78 (all burned as Residual Fuel). Crude draw 234.19/min.
- Oil site declared to pump Water: resin 58.18/58.18, all of it consumed by
  0.970 Residual Plastic. Dedicated Plastic refineries 2.624 -> 1.654; Fuel
  1.778 -> 1.939; Crude 234.19 -> 214.80/min; 19.39 m3/min Water pumped.
  Scale unchanged (0.003499; Coal binds); grid 1378.7 MW either way.
- The same under goal "resources", and with both sites pumping.

Read: the solve already uses resin when a held recipe can take it. Both
held consumers (Residual Plastic: 60 resin + 20 Water; Residual Rubber:
40 resin + 40 Water) need Water, so without Water the resin is left over,
and FREE lets it go. Used, it displaces part of the dedicated Plastic line.

### A8.3 Decided by Greg, 2026-10-19 (holds until proven wrong)

- By-products are to be used, not left as free overflow. Mechanism open
  (A8.5). Greg's notes: one option is to sink the solids (a liquid cannot be
  sunk without being packaged first); resin can become Plastic or Rubber,
  which means the dedicated lines may not need to make as much.
- Capacity left unclaimed after the bill scale is REPORTED ONLY for now.
  This settles the A2.2 idea for the present: no later stage, no weighted
  extras.

### A8.4 A future note, not decided

The report's wording should be consistent across tools, but it has not
landed. The mockup of 2026-10-19 (drawn / unclaimed / backs up) is one
proposal and no more. Until it lands the tools keep their present wording.

### A8.5 Open: how by-products are used (options, unmeasured unless said)

1. No free overflow for non-bill items: a leftover of anything that is not
   a bill item is refused (or priced) in the portfolio solve. Then the solve
   must route resin into a consumer, or not make it. Whether C without Water
   stays feasible, and at what scale, is not measured.
2. A sink for solids: a disposal activity for solid items only, liquids
   refused by name until packaged. Blocked on P5 today: the reference layer
   carries no AWESOME Sink. Polymer Resin is solid (stack 200 in items.csv);
   Heavy Oil Residue and Fuel are fluids.
3. Report only: list every leftover with its rate, and a fill time against
   storage the caller declares (tools/storage_view.py already has the
   formula). Measures the problem; changes no plan.

These combine: 3 alongside 1 or 2 is likely either way.

## Amendment 9 — 2026-10-23. Resource neighborhoods: the policy is declared

### A9.1 What raised it

Handoff 2026-10-19 18:28 action 2: bring v0.20's resource neighborhoods
(research/v020_site_mapper/resource_clusters.py) into the repo as a
world-analysis tool, its radius, dedupe threshold and minimum node count as
declared inputs, tested by regenerating its 276. Porting it showed the 276
also rest on choices that list did not name: the order in which candidates
are walked before dedupe (dedupe is order-dependent, so the order decides
which of two near-duplicates exists), a second dedupe gate (seeds within
radius / 2), and which sockets count at all (the script's INCLUDE).

### A9.2 Measured 2026-10-23 (container, py3.13, master d029aa7), not derived

Over site_card.load_sockets (default_502094), with site_card.sockets_within
as the radius test, v0.20's settings regenerate all 276 neighborhoods (522
distinct sockets): same socket sets, same order. Changing one choice at a
time, the number of the 276 kept as identical sets:

- order by seed id instead of v0.20's "most types first": 249 (275 found)
- dedupe by Jaccard only, no seed gate: 238 (248 found)
- Jaccard 0.6: 237; radius 300: 86; radius 400: 60; min nodes 3: 263
- fracking cores excluded: 250; uranium included: 265

v0.20's INCLUDE leaves out uranium (5 nodes), Water wells (63 fracking
sockets) and geysers (31), and keeps fracking cores.

### A9.3 Decided by Greg, 2026-10-23 (holds until proven wrong)

- Dedupe is optional and, when used, wholly declared: Jaccard threshold,
  seed distance and a NAMED order, all three or none (half refused).
- Which sockets count is a declared list of (source_kind, item_id) pairs,
  (kind, any item) allowed; nothing is included by default.

### A9.4 Built (tools/neighborhoods.py), and not carried, said so

Radius and minimum node count are required. Orders: "most_types_first"
(v0.20's: most distinct items, most sockets, most purity-weighted sockets,
seed id) and "seed_id". Purity weights are extraction_rates.csv's
multipliers, refused if a purity carries two. Without dedupe every
candidate is reported, in socket file order. The export (neighborhoods/1)
carries the policy, the sockets it uses and display names.

Not carried: v0.20's candidate cap (1000; a cap truncates by the order, and
the 276 never reached it), its RC### ids (they number the walk, so they
change with the policy; a neighborhood is named by its seed socket), and its
purity-equivalent totals in the output (counts by purity are reported; a
weighted sum is an opinion outside the order that uses it).

## Amendment 10 — 2026-10-23. The picker: precomputed starting points, recompute and run in the browser

### A10.1 What raised it

Greg, 2026-10-23 14:58: work on the map picker, with the Rocky Desert
starting area as the first pick. Asked at 15:34 whether neighborhoods change
only with the world: they change with the declared policy, the world's
resource assignments (per configuration) and the game build; given those,
they are deterministic (A9.2's test reproduces the same 276 in order). So a
phone need not compute them, but it could.

### A10.2 Decided by Greg, 2026-10-23 15:36 (holds until proven wrong)

"Both": precomputed neighborhood exports are the picker's starting point,
and the policy can still be changed and recomputed in the browser session.

### A10.3 Built, and how it squares with "declared, never defaulted"

- The starting export is shown as what it is (its source and its whole
  policy on screen), and editing starts from it, not from a constant. The
  RUN inputs stay undeclared until filled: nothing in the run form is
  prefilled. So the default is a visible starting point, not a hidden
  choice. v0.20's policy is the only precomputed one so far.
- The shipped export is derived data; a test regenerates it from its policy
  file and compares byte for byte. The worker loads exactly the repo files a
  native trace of its own runs opens or imports (bundle_files.json, 42
  files); a test re-traces it.
- portfolio-inputs/1 (sites by socket id, every input required) is the one
  document both the CLI and the browser run.

### A10.4 Measured 2026-10-23 (container; Chromium, iPhone 13 viewport; served over http)

- Cold start (Pyodide 0.27.7 + numpy + scipy + 42 repo files): about 7.0 to
  7.4 s; then a run of Rocky Desert district A 0.17 to 0.24 s, a v0.20-policy
  recompute without fracking cores about 0.24 s (277 neighborhoods).
- Browser record (Python 3.12.7, scipy 1.14.1) and native export (Python
  3.13.17, scipy 1.18.1) of the same inputs: byte-identical with provenance
  set aside. Browser recompute equals native export_for for the same policy.
- provenance() in the browser: commit null, reason "emscripten does not
  support processes", as designed.

## Amendment 11 — 2026-10-23. Power: report the need, and what covering it takes

### A11.1 What raised it

District A (A10's first pick) at tier 2 has no modelled power: the only
generator open is the Biomass Burner, and no socket supplies a biomass fuel,
so under A3's shared grid the plan scales to 0 (with a declared 60 MW grid,
0.012147/min, still power-bound). Greg, 2026-10-23 16:21: early-game power
comes from biomass; the tool could say how many burners, and at what rate
each fuel must be fed, to power the factory. 16:26: we should know how much
power is needed, then work backwards to burners and each fuel's feed rate.

### A11.2 Decided by Greg, 2026-10-23 16:30 (holds until proven wrong)

"Reporting need is right." Join the fuel rows (to what the tier makes
available). Greg added that the power part of the tooling does not make sense
to him as it stands; that is recorded here as an OPEN question about A3's
grid mode, not as a decision to change or retire it.

### A11.3 Built (Claude's reading; Greg may reverse it)

Of the two shapes offered at 16:28, (a) a declared mode, not (b) `grid_mw:
null` (which would have given null a second meaning):

- `PowerBalance.report_need` (production_adapter): the portfolio solve reads
  the row's terms from the plan but does not impose the row, so the plan is
  bounded by the sites' caps alone; `DistrictPower.need_mw` = lanes +
  extraction drawn + spare. Refused beside it, by name: generators (nothing
  is sized in the solve), a standing grid (not modelled beside a need yet),
  a pumped supply (A4: only the grid row bounds it; without the row the plan
  is unbounded), and the district solve (the portfolio solve only). A4's
  "segments need a grid" contract is unchanged.
- portfolio_run `power_mode` "grid" (A3, as before) | "report_need". In
  report_need, for every (generator, fuel) row of the classes open at the
  tier: units = need / MW per unit, the whole count (ceiling, 1e-9
  allowance), each fuel's feed at the need, and the fuel join: every recipe
  that outputs it, held or not and why (MAM research, alternate not
  declared, not unlocked by this tier), and the sockets' pooled cap. Nothing
  is chosen among the fuels.
- portfolio-inputs/2 = /1 + required `power_mode`; a /1 document is refused
  by name, not read as "grid". The record (portfolio-plan/1, additive) gains
  `power_mode` and `power_need`, with each row's `source_text`. The picker
  form declares the mode; index.html shows the need and the fuel table.

### A11.4 Measured 2026-10-23 (container; claude/picker on 80e1efa + this change)

District A, tier 2, bill PA phase 1 + tiers 1-2 (the test placeholders),
report_need: scale 0.062338/min, bounded by its caps (the same with a
declared grid of 1 000 MW and above under grid mode); need 307.92 MW
(machines 258.70 + extraction 49.22), the same plan under all four goals.
Biomass Burner (30 MW): 10.26 units, 11 to build; feed at the need: Leaves
1231.7/min, Mycelia 923.8, Wood 184.8, Biomass 102.6, Solid Biofuel 41.1,
Packaged Liquid Biofuel 24.6. At tier 2 Biomass (Leaves), Biomass (Wood) and
Solid Biofuel are held; Biomass (Mycelia) and (Alien Protein) are MAM
research; Packaged Liquid Biofuel is not unlocked by the tier; Leaves, Wood
and Mycelia are made by no recipe. Browser run (Chromium, desktop and
iPhone 13 viewports, Pyodide 0.27.7): record equal to the native one with
provenance nulled; cold start plus run about 7.4 to 7.6 s.

### A11.5 Not covered

- A fuel made in a constructor draws power of its own; that loop is not in
  the need, and the report says so.
- Whether a feed rate is achievable (hand-feeding 1232 Leaves/min is not) is
  not assessed: the table says what covering the need would take.
- A standing grid beside the need, a pumping site in report_need, and the
  district solve (district_run, site_card) are refused, not modelled.

## Amendment 12 — 2026-11-01. Where one site stops being enough: the selection threshold

### A12.1 What raised it

The PA walk-back step planner (claude.ai Project, 2026-10-27 to 10-31; copied
to `research/step_planner/` in this change) answered "how much to make" lower
than Greg expected. Greg, 2026-11-01 12:50: the next question is where to
build what, and how the sites connect, for a minimal run and a whole-world
run alike. 12:58: site selection matters more as the share of the world used
rises. 13:01: a reasonable next step to look into, assumed to come before the
logistics that connect sites.

### A12.2 Stated by Greg, 2026-11-01 (facts and direction, not design decisions)

- 12:38: before the step planner he would maximise the output of nearby
  resources; its 1/min result needs far less extraction than that.
- 17:28: the step planner will be joined to the site locations from the
  neighbourhood work (A9); worth saving in the repo as part of the process.
- 17:28: the fuel alternates come from MAM Sulfur research, and from hard
  drives after that. The data agrees: `schematic_recipe_unlocks.csv` lists
  Turbofuel and Compacted Coal under `Research_Sulfur_TurboFuel_C` and
  `Research_Sulfur_CompactedCoal_C` as well as under `Schematic_Alternate_*`.
  `alternate_recipe_unlocks.csv` is a HUB-prerequisite table of 79 rows and
  does not list every alternate; that is not a data gap.
- 17:28: water is essentially unlimited. Ocean extractors are bounded only by
  the world border; treat water as infinite, power and logistics aside.

### A12.3 Claude's reading (proposed; Greg may reverse any of it)

- **"Maximise nearby" is a view, not an objective.** The step planner is
  demand-driven: raw draw comes from the PA bill, milestones and the
  carry-forward floor, and node counts follow from it. The supply-side
  reading already exists: `LpBackend.solve_district` stage 1 (A27.2, A31),
  max scale with every bill product held at its bill proportion, within the
  caps, is "what ppm can these nodes carry". `demand_expansion_scope_and_site_capacity.md`
  §5 ("node saturation is the wrong target"; design to a tier) is the nearest
  prior position. Wiring stage 1 in as the step planner's driver, rather than
  as a reported scale, is the drift to guard against.
- **The selection threshold.** Per raw and phase: ratio = draw ÷ the
  capacity of the single best neighbourhood of that raw alone, at the
  phase's extractor tier. Over 1, one place cannot supply that raw and a
  second site is forced on it. Capacity only, never location quality:
  location quality depends on logistics, so ranking by it would close a loop
  the order in A12.1 keeps open.
- **Three regimes, by share of the binding raw.** Low share: many choices are
  feasible and selection is about proximity. Middle: selection decides
  feasibility and which dispersed nodes are forced. Near full: "which nodes"
  collapses and routing dominates. Selection peaks in the middle; connection
  work keeps rising with share.

### A12.4 Measured 2026-11-01 (cloud container; master 3fcab38 + `research/step_planner/`)

Draws: `plant_resize.py` (factory peak per phase, standard recipes, as
`nodes.py`; power plant re-sized per case). Neighbourhoods:
`tools/neighborhoods.py`, one raw per run, no dedupe, min 1. Capacity:
`nodes.py`'s tier tables. Full output: `selection_threshold_output.txt`.
Ratios at 350 m / 1000 m; S0 = the run2 plant (coal, then standard Fuel).

    case          phase  over 1 at 350 m (S0)                         notes
    1/min         P4     Copper 1.08 / 0.46                           crude 0.95 / 0.70
    1/min         P5     Crude 1.84 / 1.36, Copper 1.31 / 0.56        crude is ~52% plant
    P5 at 5/min   P4     Copper 4.47 / 1.92, Crude 2.40 / 1.77
    P5 at 5/min   P5     Crude 4.00 / 2.96 (103% of map), SAM 1.69,
                         Coal 1.19, Iron 1.16
    P5 at 40/min  P5     every raw; crude 684% of map, SAM 158%,
                         nitrogen 124%

- **Radius is policy that changes the answer.** Copper at 1/min crosses at
  350 m and not at 1000 m. A9.3 already makes the radius declared; this is
  the first figure where the choice decides the result.
- **Power drives selection at scale.** run2 fixes 8 coal generators by P3 and
  covers all later growth with Fuel Generators, so every case's growth lands
  on crude (plant crude at P5: 983, 3 229, 22 680/min for the three cases).
- **Power alternates move the binding raw; they do not remove it.** Raw draw
  per MW of fuel-generator output, generator energy only (recipe_io.csv,
  generator_fuels.csv):

      set                          crude/MW   other raws per MW
      S0 standard Fuel             0.120      —
      S1 HOR + Diluted Fuel        0.030      water 0.080
      S2 S1 + Turbofuel            0.0135     water 0.036, coal 0.024, sulfur 0.024
      S3 S1 + Nitro Rocket Fuel    0.0042     water 0.011, N2 0.0083, sulfur 0.011, coal 0.0056

  At 1/min, S1 takes P5 crude to 1.12 / 0.82 and S2 to 0.98 / 0.73; copper
  (a factory draw) still crosses at P4 and P5. At P5 5/min, coal crosses in
  every set (S2 1.58) and SAM 1.69 is untouched by power. At P5 40/min no
  fuel route fits the map: S2 needs 105% of the map's sulfur, S3 156% of its
  nitrogen. Fuel power cannot carry that rate; geothermal or nuclear has to.

### A12.5 Defect found on the way (fixed at the site, 2026-11-01)

The Project's `step3-relief/site_data.py` added the crude for Fuel a second
time on top of `run2.power_block`'s `pb['raw']`, which already held it, so
plant crude was 2x. Fixed in the Project. `site_data.json`, `nodes.py`
`PLANT` and `node_defaults.json` were regenerated, with only the crude
fields changing. The repo copy is the fixed one. Session handoffs written
before the fix still quote the doubled figures (P5 crude 47% of the map at
1/min) and stay as written.

### A12.6 Not covered

- Production alternates. The factory draws are standard recipes; at P5
  5/min coal and SAM are factory draws, so that is the next lever.
- Unlock timing of S1–S3. They are applied from P4 (Diluted Fuel's HUB
  prerequisite is `tier_7_8`). Whether a player holds them by then depends on
  MAM Sulfur research and hard drives, and is not checked.
- The fuel chains' own machine power, and the Compacted Coal by-product of
  Nitro Rocket Fuel. S1–S3 read slightly better than real.
- Co-location: each raw's best neighbourhood is found on its own, and they
  may be far apart. That is the logistics step.
- Water is reported, not thresholded (A12.2).

## Amendment 13 — 2026-11-01. A declared target scale, and the first link sheet

### A13.1 What raised it

Greg, 2026-11-01 21:36: work out how to get resources and products around
the map. Claude offered (22:00) two framings: A, report the logistics after
the solve (transfers stay free in it); B, price transfers inside the solve.
B closes the loop A12.3 keeps open (sites would be chosen by logistics).

### A13.2 Decided by Greg, 2026-11-01 (holds until proven wrong)

- 22:25: option A; distance by the corridor tool; all modes; the 1/min run.
- Then, answering Claude's question (the portfolio solve only maximised the
  scale; the 1/min step planner has no sites or transfers): a fixed-rate
  portfolio mode, and Phase 4 for the first sheet.

### A13.3 Built

- `PortfolioRequest.target_scale` (contracts): positive and finite, or None.
  When set, the scale column's upper bound is the target, stage 1 still
  maximises, and a result short of the target raises `Infeasible` naming the
  maximum. Never delivered short. Stages 2 to 4 are unchanged, so at a target
  under the maximum the volume stage has slack the maximised plan does not.
  Tests: exact delivery under the maximum, equality with the maximised plan
  at the maximum, refusal over it, refusal of a bad target (each guard
  mutation-checked).
- `research/link_sheet/` (README there): the P4 run and the link sheet.
  Research, with its rule breaks declared.

### A13.4 Measured 2026-11-01 (cloud container; claude/step-planner-threshold 1e876f1 + this change)

Bill: each P4 part (Assembly Director System, Magnetic Field Generator,
Thermal Propulsion Rocket, Nuclear Pasta) at 1/min, tier 8, standard
recipes, Miner Mk.3 / oil pumps / resource wells at 100 %, water pumped at
every site, power from outside (no fuel moves). Sites: per raw, the
single-raw neighborhood (350 m, min 1) with the most capacity; a second one
while the draw is over it.

- One site holding the world draws Copper Ore 2053/min against 1440 at the
  best copper neighborhood (1.43), so Copper gets two sites; every other raw
  fits one. 10 sites in all.
- The 10-site plan: 36 transfers, 1362.6 items/min moved, over 29 directed
  pairs (22 site pairs, 7 of them both ways). Per raw its draw equals the
  one-site probe's except where the recipe mix moved: Bauxite 948 vs 316/min,
  Water 1299 vs 351, Raw Quartz 60 vs 218. Volume comes before goal cost
  (A1.2), so the solve trades raw draw for less moved.
- Corridor distance 0.91 to 10.84 km, 1.21 to 1.87 times the straight line.
  Bauxite 1's seed snaps into a 4-node component of the corridor graph: its
  10 directed pairs have no corridor distance.
- Belts: 5 pairs need more than one Mk.1 (heaviest Iron -> Coal, 291.7/min);
  every pair fits one Mk.4 (61 % at most).
- One vehicle per directed pair, needed average speed: Truck at most 48 km/h
  (Copper Ore 2 -> Crude Oil, 10.84 km corridor), median 1.1; Drone (straight
  line) at most 155 km/h, median 3.3, 5 pairs over 20 km/h.

### A13.5 Known limits

- The P4 draws here (PA parts only) do not reconcile with the step planner's
  P4 figures (A12.4: Copper 1557/min at 1/min). Those include milestones, the
  step build-up and the carry-forward floor; the difference is not
  decomposed.
- Placement-blind plan (research/link_sheet/README.md). Fluid vehicle
  capacity is unresolved; packaging is not offered as a mode.
- The site rule picks on capacity alone (A12.3), so distances are close to a
  worst case.

## Amendment 14 — 2026-11-02. Sites that work together, picked forward; neighbourhoods over deposits; distance by mode

### A14.1 What raised it

The P4 link sheet (A13.4) picked one capacity-best site per raw, so its
distances were near a worst case and its plan a mesh. Greg, 2026-11-02, on
why those ten: sites suit different phases (early iron, copper and limestone
close together; mid-game oil plus nearby raws not usually near oil), and
late-game sites should not be spent early.

### A14.2 Stated and decided by Greg, 2026-11-02 (holds until proven wrong)

- 12:52: a whole-world placement is not "yet another solver". Assume the
  default map has several options per phase; the aim is not the best site
  but a series of sites that work with each other. Claude had flagged that
  drift (A12.3, and in this session); that flag is withdrawn for this shape.
- 12:58: pick forward from the starting biome, not backward from P5. The
  link is the corridor: selecting a site (e.g. crude oil in the south-west)
  shows the sites that would support it, with their corridors and
  constraints; elsewhere (Blue Crater lake for oil) the other raws are much
  closer.
- 14:23-14:27: neighbourhoods are the sites, deposits an overlay (and the
  reverse view); the picker's v0.20 deduped set, so plans load in the
  picker. A later version should set the neighbourhood radius per phase
  (lower phases closer).
- 14:48: corridors read as the on-foot route without scaling a cliff. Belts
  with lifts move resources more or less in a straight line.
- 14:51: within a phase, sites without access to the phase's key products
  should fade back (P2: steel).

### A14.3 Built (research/site_links/, README in its docstrings)

- `build.py`: deposits (one raw's nodes chained within 350 m; wells by
  core), the v0.20 neighbourhoods with seed snap and elevation, the
  corridors_v1 graph with the corridor tool's own search cost, and the
  terrain at 32 m for the belt line. `page.py` + `page_template.html`: the
  Site links page, as published (rebuilt byte-identical, 2026-11-02).
- The page: pick by neighbourhood or by deposit; supporters per raw grouped
  by deposit, with the neighbourhoods that reach each; distance basis on
  foot (corridor), belt + lifts (straight, lifts = height change between
  seeds / 51 m, length over water), drone (straight); a "can make" filter
  from a product table declared in the page (standard recipes' bulk-step
  raws); a plan with clash check, phase coverage and a copy of its sites as
  portfolio-inputs/2 entries. Nothing ranks; lists sort by distance.
- `research/link_sheet/sites_run.py`: the P4 1/min run over a declared site
  list, with shared sockets resolved and reported; `link_sheet.py` adds the
  straight belt line per pair.

### A14.4 Measured 2026-11-02 (cloud container; claude/link-sheet)

- Raw combinations held together (any capacity; rough distinct places at
  350 / 700 / 1000 m): iron+copper+limestone ~21 / 13 / 8; oil+copper ~3 / 8
  / 5; oil+copper+caterium 0 / 8 / 5; oil+copper+quartz 1 / 4 / 5. Early
  phases have many options at any radius; late phases have few at 350 m.
- Greg's 12-site test (greg_test_sites.json): three overlaps (one site wholly
  inside another; two pairs sharing 2 nodes). After resolution: max 0.9935
  of P4 per minute, copper bound (2040 held vs 2053 drawn). At that scale 29
  transfers, 490.5 items/min (the capacity picks moved 1362.6 at 1.0).
- 14 of its 21 site pairs route over 3x the straight line on foot. Two
  causes, by the belt line: nb_521 sits ~250-290 m above its neighbours
  (5-6 lifts; Greg's RN596 -> FrackingCore6: 0.98 km straight, 3.41 km on
  foot, +257 m); the north-south split is flat and mostly water (nb_103 ->
  FrackingCore6: 0.99 km straight, 656 m of it over water, 11.98 km on foot).

### A14.5 Known limits

- The product table and the lift count are the page's own simplifications:
  lifts count only the height change between the two seeds; ridges between,
  supports and bridging are not costed. Rail is not a basis yet.
- Water access is not assessed beyond resource-well water.
- Nothing yet warns when a picked site is one of the few places a later
  phase could use (the scarcity badge proposed in this session).

## Amendment 15 — 2026-11-17. Architecture reconciliation: two planning tracks, one current specification

### A15.1 What raised it

Greg asked, 2026-11-17, for the architecture to be reconciled with the
accumulated decision records before new planning capabilities are added. A
functional audit of the same date was used as a starting hypothesis, not as
authority.

Discovery was run in a cloud container at `2d6ccfe`: 1435 passed, 1 skipped.
The checkpoint notes are in `Claude outputs/`. Discovery found:

- six modules reading the game-reference CSVs directly;
- a second planning model in `research/step_planner` (phase-index miner and
  belt tables);
- no implementation of staged upgrades, storage-priority banks,
  eligibility-vs-ownership, or PA duration from modelled production.

It also found that the new direction (supply-constrained individual factories)
sat outside §2's working direction ("never says exactly what to do and when"),
so it needed recording here. Those findings did not decide anything. Greg
decided the items below at checkpoints 1 and 2.

### A15.2 Decided by Greg, 2026-11-17 (holds until proven wrong)

- **A1 Tracks.** Individual-factory planning is in scope as a sibling track.
  One scope plans the run. Another takes that plan as input, or takes a
  per-factory plan at run time, where the user lists what is available and the
  goals. Site portfolio planning (A1–A14) continues unchanged beside them.
- **A2 One current specification.** `docs/ARCHITECTURE.md` is the current
  specification. Everything else goes to the archive and is referred to only
  as historical evidence, not in general discussion (Q4). Mechanism: records
  stay at their paths (21 files cite them). Each archived record gets a
  one-line forward amendment, and `docs/decisions/README.md` indexes current
  vs archived.
- **A3 Older workflows.** Kept as deprecated background; their ideas are
  ported into tooling. Exactly (Q5):
  - deprecated CLIs: `district_run.py`, `phase_run.py` and `site_card.py`;
  - libraries still in use: `goal_run`, `schedule`, `stock`, and
    `site_card`'s socket readers;
  - not deprecated: `portfolio_run`, `neighborhoods`, `site_planner_web` and
    `demand_expansion`;
  - `research/*` is background.
- **B1 Supply vs demand.** Supply-side is the preferred method for the
  current factory. Demand-side is needed to estimate what's next and what
  reaching a target takes. The deployed prototype at
  `eloquent-pothos-3073ca.netlify.app` points to the target determination:
  rate = PA bill × E ÷ horizon, with the horizon bounded by one machine of the
  slowest part. Its arithmetic is not carried (it ceils solid inputs, so at
  R = 1.25 an input of 1 becomes 2, against the §3.2.4 read of 1). Neither
  track invents a mix or a target: both are declared.
- **B2 Extractor and belt marks.** Which marks are considered follows what is
  unlocked: no Mk.4 belts in phase 2; at the start of phase 2 and steel, no
  Mk.2 miner and no Mk.3 belt yet. To maximise supply, use the highest mark
  available, and work back to a lower mark where the higher one does not help.
  "Does not help" (Q1):
  - same delivered rate, at lower power;
  - for belts, the lowest mark that carries the lane's actual flow (a lane
    that never carries more than 60/min takes Mk.1, not Mk.2);
  - build cost is not a criterion.
- **Q2 Availability.** Availability follows the milestones owned. "Phase N"
  or "tier N" is a shortcut for every milestone up to N. Milestones within a
  phase need not be taken in order, or at all, so a declared set is the
  input. Checked 2026-11-17: Miner Mk.2 comes from *Advanced Steel
  Production* and Belt Mk.3 from *Logistics Mk.3*, both tier 4, through
  `schematic_recipe_unlocks` × `building_recipes`.
- **B3 Storage-priority bank.** This is a practice from Greg's 50× and 100×
  elevator-part runs. Maximising Smart Plating worked, but left no
  construction inventory for other builds.
  - Bleeding storage off a PA lane failed: the lane's single Iron Plate
    constructor was either split between Smart Plating and storage, or
    starved Smart Plating until storage filled.
  - Current practice:
    - a smart splitter sends all product to a dedicated set of machines
      optimised for storage parts (example: 4 underclocked constructors,
      73 Iron Plate/min);
    - when storage fills, backpressure flips the splitter to overflow, which
      feeds the PA lanes;
    - as stock is drawn down, the splitter sends resources to refill storage
      first.
  - Observed working in game (Greg). It needs smart splitters, and a
    standard splitter works as a bootstrap. Likely less useful at lower E.
- **Q6 Storage capacity.** The storage container determines fill time.
  Container type is gated by tier, and choosing regular or industrial depends
  on how much the stock is used and how likely it is to be drawn down quickly
  enough to matter. The first version therefore reports fill time per
  available container option and the PA rate while filling and when full.
  Withdrawals are not declared yet.
- **B4 Rounding floor.** Solids have a floor of 1 at sub-1× R (A5.1 of the
  demand record, now the code default from R4). The fluid floor still needs
  the in-game read at R = 0.25 (demand A5.2) and stays declared.
- **B5 / Q3 Alternates.** "Eligible" and "accessible" collapse to the
  **pool**. Recipe status is owned / in pool / MAM research / locked.
  Resource accessibility is a separate, site-level axis. Scanned-but-unclaimed
  hard-drive offers are not modelled now. A future option takes them from
  game data or a declared list and removes them from the pool for the next
  scan (selecting one of the two returns the other to the pool), which bears
  on the odds of finding an alternate.

### A15.3 §2 amended, forward only

§2's working direction stands with one change. The tool now also computes
what a **declared** goal or target takes in the factory and run tracks: rates,
machines, marks, storage fill. It still never chooses the goal, the target,
the mix or the order, and it still never says exactly what to do and when.
The v1.0 product spec and the capability inventory named in §2 stay ideas, as
§2 said, and are archived as proposals. So is the 2026-11-10 factory-design
specification. Nothing in them binds unless brought forward here or in a
later amendment.

### A15.4 Brought forward explicitly (§3), as evidence and contracts

These are brought forward as observed facts and implemented contracts, not as
product mandates:

- `resource_authority.md` (P3);
- demand §3.2.4–3.2.5 and A2 (rounding reads);
- crossover A1 (tie rounding read) and A7 (idle draw, shard ceilings,
  container `slots × stack`);
- LP formulation §18 (tier rule, measured) and §19 (pool by automatic entry);
- `production_building_power_model.md` (producer facts);
- `extraction_wiring_and_provenance_stamp.md` (provenance stamp).

Demand A5 and A6 are post-reframe in-game reads and already govern.

### A15.5 Approved exceptions recorded

`docs/ARCHITECTURE.md` §7 lists them:
- two direct readers of game/reference, with reasons, enforced by
  `tests/test_one_loader.py`;
- raw reads in `tests/` (independent oracles);
- `research/` scratch;
- `demand_expansion`'s own expansion beside the LP, with its role to be
  settled when the run track is built.

### A15.6 Built so far (cloud container, branch `claude/practical-rubin-m3ard7`)

- R0 `0cceff4`: manifest header repaired; malformed manifests refused by name.
- R1 `5e6ca9c`: one loader; AST guard.
- R2 `e265739`: shared `compose_bill`; stale power notes.
- R3: `docs/ARCHITECTURE.md`, this amendment, the archive index and
  deprecation notices.

No figure changed in R0–R3. Container: 1444 passed, 1 skipped after R2.

### A15.7 Not changed, said so

- The portfolio solve, its schemas (`portfolio-inputs/2`, `portfolio-plan/1`)
  and power modes are unchanged. A11.2's open question on grid mode stands.
- A8.5 (by-product mechanism) stays open.

## Amendment 16 — 2026-11-17. Tie-break fixed; by-products to the sink; withdrawals ignored; viewers are tests; power proposal

### A16.1 Decided by Greg, 2026-11-17 (holds until proven wrong)

Greg's words: "Fix internal tie break", "By products can be sent to AWESOME
sink by default for now but should participate in production when available
and appropriate to supply", "Storage withdrawals ignored", "Netlify and other
viewers are tests. Nothing needs to stay in them".

- **Tie-break.** The A13 `target_scale` defect found in R9 is fixed.
  - Symptom: Infeasible from `solve_portfolio`'s fourth stage at bill units
    of 5 or more.
  - Cause: HiGHS presolve rejected a pinned stage that is feasible by
    construction.
  - Fix: `LpBackend._run` re-solves such a stage once without presolve. Only
    a stage that already failed takes that path, so no prior result moves.
  - Commit `c5ebdaa`.
- **By-products.** They feed production where the solve finds that useful;
  this is unchanged and was measured in A8.2. What is left over goes to the
  AWESOME Sink by default, solids only. This settles A8.5 for now, as option 2
  plus 3 (sink solids, report every leftover).
  - Built in `progression.byproducts`.
  - Each leftover is reported as `sink` (with sink points/min),
    `sink_not_unlocked` (before *Schematic_2-5_C*), or `fluid_no_sink`.
  - The factory and run tracks report this.
  - The solve still runs with unconsumed output FREE (LP D1 stopgap), so a
    fluid leftover is named, not refused.
- **Storage withdrawals** are ignored; `progression.timeline` already
  ignores them (A15.2 Q6).
- **Viewers** are tests: the Netlify demand-expansion viewer and the
  prototype pages. Nothing in them is a contract to keep. `demand_expansion`
  is not kept for the viewer's sake.

### A16.2 Open, said so

- **Fluid by-products.** The sink takes solids only; Heavy Oil Residue left
  over from Plastic is the measured case. Options:
  - package and sink (the packager's own power and its Empty Canisters
    loop);
  - refuse a plan with an unconsumed fluid;
  - keep naming them, as now.

  Greg's call.
- **Sink power.** It is not in the reference layer and is not charged.

### A16.3 Proposed, not adopted: how power should work (Greg's direction, 2026-11-17)

Greg: power was the number of generators required of each type, phase-aware.
Once coal power is in use, biomass burners are typically backup, unless the
available coal alone is enough, "possible on 5P".

Proposal: a **staged generation ledger** for the run and factory tracks. It
replaces neither A3's in-solve grid nor A11's report_need for the portfolio
track.

1. **Need.** The plan's machines plus extractors by the draw, P-scaled
   (A7), plus a declared spare. This is the A11 figure.
2. **Classes available.** From the milestones owned (`availability`): Biomass
   from the start, Coal with *Coal Power*, Fuel and Nuclear later.
   Geothermal only with its MAM research.
3. **A declared power stack per phase.** An ordered list of generator
   classes, for example phase 1 `[biomass]` and phase 2 onward
   `[coal, biomass]`. It is never inferred from tier. A preset matching
   Greg's practice is offered and named, not defaulted silently.
4. **Fill in order.** The first class covers the need up to what its fuel
   supply allows: coal from claimed nodes or a declared supply, with the coal
   generators' water pumped and charged. The next class covers the
   remainder.
5. **Report per class.**
   - whole generators (ceiling) and the load they carry;
   - fuel per minute and water per minute;
   - **backup units**: a class later in the stack sized to the need it
     would cover if the earlier class fell short, reported as idle
     capacity.

   On a 5× power save the machines draw five times more, so coal alone
   often cannot cover the need and biomass carries the rest as load, not
   backup.
6. **Fuel loops stay visible.** A fuel made in the factory (Solid Biofuel,
   packaged fuels) draws power of its own. The ledger names that loop
   rather than hiding it (A11.5).

Questions this proposal needs answered before it is built:

- **P1.** Is the stack declared per phase, or one stack with classes
  dropping in as they unlock?
- **P2.** Does "backup" mean built and idle (counted) or not built (only
  reported as available)?
- **P3.** Where does generator fuel come from by default: the factory's own
  claimed nodes (charged against its caps) or a declared external supply?
- **P4.** Is the 5P reading right? With P = 5, coal is not enough on its
  own, so biomass carries load instead of standing by.

## Amendment 17 — 2026-11-17. Fluid by-products: converted or burned before the sink

### A17.1 Decided by Greg, 2026-11-17 (holds until proven wrong)

"Fluids need to be converted or packaged before they can go to sink. Fuel gets
used for power. Heavy oil residue gets converted to fuel and the byproduct of
that conversion goes to sink." This answers A16.2's open fluid question.

Built in `progression.byproducts`. The ledger is now a chain:
- **Fuel** goes to power: Fuel Generators, units and MW.
- **Heavy Oil Residue** converts through `Recipe_ResidualFuel_C` (one Oil
  Refinery takes 60 and makes 40 Fuel), and its products are disposed of in
  turn: Fuel to power, any solid to the AWESOME Sink.
- **A step whose recipe, generator or sink is not unlocked** is named
  `*_not_owned` / `sink_not_unlocked`.
- **Any other fluid** is `needs_packaging`. Packaging is not modelled.

Conversion refineries are reported with their machine count and P-scaled MW
drawn. Generators are reported with units and MW generated.

Measured (container): oil nodes 100 and 14_609, tier 5.
- Plastic: 80 HOR/min → 1.33 Residual Fuel refineries (40 MW) → 53.3
  Fuel/min → 2.67 Fuel Generators, 666.7 MW.
- Rubber: twice those figures.

### A17.2 Claude's reading (Greg may reverse any of it)

- **Residual Fuel has no by-product** in the reference layer (60 HOR → 40
  Fuel). So "the byproduct of that conversion goes to sink" sends nothing
  from that step. The rule stays general: any solid a declared conversion
  makes goes to the sink. The by-product Greg had in mind may be something
  else, for example Polymer Resin from the Fuel recipe on Crude, or Petroleum
  Coke from HOR. That is to confirm.
- **"Fuel gets used for power" is applied to every fluid an owned generator
  burns**: Fuel, Turbofuel, Liquid Biofuel.
- **Disposal is a report**, not part of the solve. The power it yields does
  not yet offset the plan's own need. Doing that would put the fuel loop in
  the solve, and it belongs with the power-ledger proposal (A16.3).

## Amendment 18 — 2026-11-17. Fuel routes; disposal never offsets the need; the power stack

### A18.1 Decided by Greg, 2026-11-17 (holds until proven wrong)

- **Fuel.** "all fuel goes to generator or gets packaged for use [in]
  recipes that require unpacking or storage (with overflow to sink) for
  jet-pack and vehicles."
  - Built as a declared route, `fuel_byproducts` = `power` | `package`,
    required in factory-inputs/1 and run_plan.
  - `package` uses the packager recipe per fuel and reports the Empty
    Canisters it takes (their source is not modelled).
  - The packaged fuel is then stored, with the overflow to the sink.
- **Disposal and the plan's need.** "let's not have it reduce the plans own
  power need." Disposal power and the power stack are reports; neither nets
  the plan's need. This answers A17.2's third point.
- **Heavy Oil Residue and resin.** Greg thought every HOR recipe made resin
  as a by-product. Read 2026-11-17: Polymer Resin comes from the crude
  recipes that make HOR or Fuel (the Fuel recipe, and the Heavy Oil Residue
  and Polymer Resin alternates), not from the HOR conversions (Residual Fuel
  60 HOR → 40 Fuel, no by-product). That resin is a solid with sink points,
  so it already goes to the sink. Nothing changed.
- **Power: answers to A16.3's questions.**
  - **P1:** "generator order in order obtained per tier/phase."
  - **P2:** "backup means if power demand spikes above what coal or other
    provides the bioburners turn [on and] produce power to compensate up to
    its max before the power grid turns off."
  - **P3:** "leaves/wood gathered by hand - converted to biomass then biofuel
    through constructors."

### A18.2 Built: `progression.power_stack` (Claude's reading; Greg may reverse it)

- **The order** comes from the data: the tier of the schematic that unlocks
  each generator's build recipe.

  | Generator | Unlocked by | Tier |
  |---|---|---|
  | Biomass Burner | HUB Upgrade 6 | 0 |
  | Coal | Coal Power | 3 |
  | Fuel | Petroleum Power | 5 |
  | Nuclear | Nuclear Power | 8 |

- **The class obtained last is primary.** It carries the need in whole units,
  with each fuel's feed and its Water listed; none is chosen.
- **Every earlier class is backup.**
  - Its units are the declared `standing_generators`, the ones built in
    earlier phases.
  - Its full output is the spike headroom before the grid trips.
- **Solid Biofuel** gives, per hand-gathered source (Leaves, Wood), the
  amount by hand per minute and the Biomass and Biofuel constructors, with
  their P-scaled draw. That draw is not added to the need.
- **Reports:** run_plan always reports the stack; factory_run reports it in
  report_need mode. In grid mode the solve's own generators stand (A3). The
  old "each generator alone" diagnostic in run_plan is removed; there is one
  power view.
- **P4 (the 5× case)** follows: with P = 5 the need is five times larger, so
  more primary units are built and the backup headroom is a smaller share
  of it.
- **Not modelled:**
  - whether the primary's fuel is available at the factory;
  - Mycelia and Alien Protein biomass;
  - clocking burners down.

## Amendment 19 — 2026-11-17. Power through later phases; the power-site check; the ledger retired

### A19.1 Decided by Greg, 2026-11-17 (holds until proven wrong)

Answers to the open questions after A18:

1. **Power through later phases.** "power generation continues into future
   phases - bioburners act as backup because they only burn fuel/generate
   power when needed -- previous approach that looked to work reported how
   many of each type would be required by way of demonstrating needs and a
   separate ratio system for how to supply the power".
2. **When to check the stack's fuel.** "power stack should check supply if
   intent of factory is fuel -- coal/water combination is typically for
   power, coal/iron combination is typically for steel (rarely make steel at
   same site as power) -- oil almost always includes power generation unless
   specifically excluded or not needed (low P values may not need any power
   from fuel)".
3. **The fluid floor at sub-1× R:** still waiting on the in-game reading of
   Plastic from the 0.25× R run. Demand A5.2 stays open.
4. **`progression.power.ledger`:** "retire".
5. **`demand_expansion`:** "keep for whole-run quantity totals".
6. **Packaging containers:** "leave as reported for now -- there are multiple
   options depending on the recipe (plastic vs steel)".

### A19.2 Built (Claude's reading; Greg may reverse any of it)

- **`progression.power_stack` reports in two parts.** This supersedes
  A18.2's "every earlier class is backup".
  - **Each type alone.** For every owned class: the units needed to cover the
    whole need by itself, and every fuel option's feed. This part
    demonstrates the need.
  - **Supply.**
    - Standing generators run first, in the order obtained. These are the
      declared `standing_generators`, built in earlier phases.
    - Biomass Burners are **backup** once another class is owned. They are
      built but idle at steady state, and their full output is spike
      headroom. While they are the only class, they carry the load.
    - Whatever load the standing units leave goes to the **declared
      generation mix** (class → share, with the shares summing to 1). With
      no mix declared, it goes to the class obtained last.
    - New units are whole, after netting against that class's standing units.
    - A class named in the mix carries its share, even Biomass Burners.
- **The intent is declared, never inferred.** `factory-inputs/1` gains
  `power_from_site` (bool, required) and `generation_mix` (null or an object,
  required). Greg's pairings, "coal/water typically power" and "oil almost
  always", are typical, not rules. So the document says whether this factory
  powers itself; nothing reads it off the resources.
- **`power_stack.supply_check`** runs when `power_from_site` is true. It is
  report_need only: in grid mode the solve already burns the site's fuel
  (A3), so the check is refused there.
  - **Which lines it checks:** for every line carrying load, each fuel option
    and its supplemental fluids, against the site's leftovers. Backup lines
    are not checked, because they burn only on a spike.
  - **Leftover** is each cap less the solve's draw, plus fuel by-products
    routed to generators. Delivered goal-mix items leave the site and are not
    counted.
  - **Statuses:**
    - `covered` or `short`;
    - `pumped`, for Water with a Water Extractor owned;
    - `no_water_extractor`, for Water without one;
    - `by_hand`, for a Biomass Burner fuel the site does not make.
  - **`fed_by`** lists every fed fuel option per line. None is picked.
- **`run_plan`** takes `--mix CLASS=SHARE` and forwards the mix.
  `to_factory_inputs` requires `power_from_site`.
- **The ledger is retired (A19.1 item 4).** `ledger`, `PowerLedger`,
  `GeneratorReading`, `Role` and their line types are gone. The power tables
  stay (`load_power_tables`), because five callers read extractor power from
  them. As a side effect, the picker's browser bundle no longer ships
  `progression.stock` or the realization package (44 → 37 files).
- **`demand_expansion` stays (A19.1 item 5)** for whole-run quantity totals,
  beside the LP. The run planner still uses the LP (R9).

### A19.3 Not modelled, said so

- **Fuel availability:**
  - The stack lists every fuel a generator class can burn, including fuels
    the state cannot make yet (for example Ionized Fuel at tier 6).
  - When two lines would burn the same item, the check reads them one at a
    time and does not add their draws together. Today only Water is shared,
    and it is pumped.
- **Water Extractors beside coal generators:** the check names Water as
  pumped but does not add those extractors' count or power to the need.
- **Packaging containers' source:** left as reported (A19.1 item 6).

## Amendment 20 — 2026-11-18. The run and factory tracks in the browser

### A20.1 What raised it

Greg asked, 2026-11-18, for a browser UI covering the run and factory tracks
beside the portfolio picker, running the repo's own Python through the Pyodide
worker (A10), with no production maths in JavaScript and with every required
`factory-inputs/1` key behind an explicit control with no pre-filled guess.

### A20.2 Decided by Greg, 2026-11-18 (holds until proven wrong)

- **Layout: one page, tabs.** `tools/site_planner_web/planner.html`, with
  Playthrough, Run, Hand-off and Factory tabs sharing one state and one
  worker. `picker.html` and `index.html` stay for the portfolio track.
- **Sockets for the hand-off: the neighborhood export only.** The factory's
  site is one neighborhood of a `neighborhoods/1` export (the picker's kept
  export, else the precomputed v0.20 one), picked on the picker's map.

### A20.3 Claude's recommendations, adopted on Greg's "recommend and use" (2026-11-18)

Greg may reverse either.

- **A declared run record, `run-inputs/1`.** `run_plan.run_inputs(doc)` reads
  it as `factory_run` reads `factory-inputs/1`: every key required, unknown
  keys refused by name. Keys: `schema`, `playthrough` and `scenario` (the same
  shapes as `factory-inputs/1`), `phase`, `horizon_min`, `horizon_fraction`
  (exactly one non-null), `power_statistic`, `fuel_byproducts`,
  `standing_generators`, `generation_mix`. So a browser form's gaps are
  refused in Python, by name, never filled in JavaScript. `run-plan/1` is
  unchanged.
- **The hand-off from documents.** `run_plan.handoff(run_doc, decl)` plans the
  run and calls `to_factory_inputs` with every argument taken from `decl`
  (`HANDOFF_KEYS`), none from its keyword defaults (pinned by a test). A step
  with blocked parts is refused.
- **Milestones: a checklist, the tier as a button** (A15.2 Q2 left this to the
  UI). The page ticks what Python means by "through tier N"
  (`playthrough(through_tier=N).milestones`), and any box can be unticked. The
  documents carry the list, with `through_tier` null, as `to_factory_inputs`
  already wrote. A file with `through_tier` set is expanded to that list on
  opening, and the page says so.

### A20.4 Built (Claude's reading; Greg may reverse any of it)

- `tools/planner_catalog.py` (a joint at `tools/` root): the page's choices,
  read through the one loader. These are the milestones, research and
  alternates with names and tiers, plus names for items, recipes and
  buildings. It also gives the Project Assembly phases and each declared key's
  vocabulary, taken from the module that owns it. `tier_milestones` serves the
  tier button, and `generators_owned` gives the classes the state owns, in the
  order obtained.
- **Standing generators and the generation mix live in the Playthrough tab**,
  shared by the run and the factory, because they describe what the
  playthrough has built (A18, A19). `power_statistic` and `fuel_byproducts`
  are declared separately in the Run and Hand-off tabs, because
  `to_factory_inputs` takes them separately.
- **Undeclared means absent.** An undeclared key is left out of the document,
  so Python says `missing [...]`. A blank standing count for an owned class is
  sent as null, so `power_stack` refuses it. The page marks undeclared fields
  but never blocks a run.
- **The goal mix** comes from the run step (`run_plan.handoff`), or is
  declared in the Hand-off tab, where the page assembles `factory-inputs/1`
  and `factory_run` checks it. The Factory tab also runs a hand-written
  `factory-inputs/1` file as written.
- **The worker** gains the ops `catalog`, `tier`, `generators`, `run_plan`,
  `handoff` and `factory`. The `run-plan/1` and `factory-plan/1` texts are the
  CLIs' `--export` texts. The page also shows each CLI's printed report,
  because some figures exist only there, for example the power stack's
  headroom, which is a property and not in the record. The page computes
  none of them.
- **The bundle** grows from 37 to 44 files (`bundle.py` traces the planner's
  runs). The picker fetches them too, because the worker imports them at boot.

### A20.5 Not done, said so

- `run_plan.py` has no `--inputs` flag yet; a `run-inputs/1` file is read by
  the page and by `run_plan.run_inputs`.
- The hand-off picks one neighborhood as it stands; sockets cannot be added or
  removed individually (Greg chose the export only).
- The factory's power statistic and fuel route are declared again in the
  Hand-off tab, not copied from the run, so each document says what it was
  given.

### A20.6 Correction, 2026-11-18: the neighborhood export is a start, not the only source

Greg, 2026-11-18: "Socket source using neighborhoods is a start -- suggesting
-only- is overstating (only for now)". A20.2's "the neighborhood export
only" and A20.5's "(Greg chose the export only)" overstate his decision. What
he decided is that a neighborhood from the export is the **first** socket
source the hand-off offers. Other sources (typed socket ids, a site from a
saved `portfolio-inputs/2`, adding or removing single sockets on the map) are
not ruled out. They are not built, and which of them comes next is open and
Greg's to decide. The page is unchanged: it offers the neighborhood export,
as built.

### A20.7 Hosting, decided by Greg 2026-11-18

"Set up Netlify with a deploy preview and GitHub pages."

- **Netlify.** `netlify.toml` builds the demand-expansion viewer into
  `dist/index.html` as before. It then runs `tools/site_planner_web/publish.py
  --out dist`, which copies the site planner pages and exactly the files in
  `bundle_files.json` at their repo paths, and refuses a missing one by name.
  A pull request's deploy preview builds the same way. The pages are at
  `/tools/site_planner_web/planner.html` and `picker.html`.
- **GitHub Pages** serves the repository from a branch, with no build. A root
  `.nojekyll` keeps Jekyll from dropping the files named `_*` (the bundle's
  `__init__.py`). The branch is chosen in the repository's Pages settings, by
  Greg.
- Measured in the container, 2026-11-18: the Netlify build command run locally
  gives 53 files and 2.7 MB beside the viewer. The planner smoke test passed on
  that tree, and under a `/satisfactory_progression_planner/` path prefix as
  Pages serves it. Neither host was reachable from the container, so the first
  live check is Greg's.
- `.nojekyll` is not added to the manifests' `root_files`. The integrity scope
  is unchanged.
