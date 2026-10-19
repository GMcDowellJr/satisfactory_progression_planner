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
