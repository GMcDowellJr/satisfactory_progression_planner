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
