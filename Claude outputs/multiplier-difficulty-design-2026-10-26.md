Multiplier difficulty tool — design note, 2026-10-26

```
this file  DESIGN NOTE (current-state; correct in place). Not a decision record.
thread     Multiplier Comparison Lab review (2026-10-25) -> redesign Q&A with Greg
           (2026-10-25 18:23 -> 2026-10-26 00:33, America/Phoenix)
repo read  GMcDowellJr/satisfactory_progression_planner master 4a32faa, shallow
           clone in a cloud container. Suite NOT run this session.
figures    Container scratch runs of the repo LpBackend, 2026-10-25/26. Measured,
           not derived. Script: multiplier_ratios.py (project doc beside this).
companions multiplier_ratios.py, lab_rounding_check.py, lab_ui_reference.md
corrected  2026-10-26 07:51: action 1 done (record A5, branch
           claude/multiplier-a5-floor 3da34ad); O4/O5 effect cells corrected;
           fluid-floor unit added to §6 and §7.
           2026-10-26 08:30: §5.1 milestone load measured (milestone_load.py);
           action 2 split on two questions for Greg (§7, first two items).
           2026-10-26 09:50: Greg decided both (D17 serial, D18 Mycelia
           hand-supplied); §5.1 re-run with the serial E multiplier.
           2026-10-26 10:05: O9 added (record A6, branch 9b3e665); milestone-
           cost-under-R open item closed.
           2026-10-26 10:40: D19, D20; §5.2 work multiplier; R time-vs-
           machines open item resolved.
           2026-10-26 11:05: §5.3 MAM bill measured (mam_bill.py); four
           questions for Greg added to §7.
           2026-10-26 10:55: O8 corrected (crash-site hard drives, not MAM);
           D21, D22; §5.4 component breakdown; equipment question restated.
           2026-10-26 11:20: D23; §5.5 power axis (power_axis.py); §6 water-
           rate row corrected (the rate was present).
           2026-10-26 11:40: D24, D25; §5.6 full work multiplier (work_axis.py)
           supersedes the §5.2–5.4 tables; §4.4 adds why E is sub-linear.
           2026-10-26 11:45–12:50: §5.7–5.9 (mock-up, selector, biomass
           routes); D26–D30. 13:00: next actions refreshed; committed to
           the repo with the scratch scripts under
           research/multiplier_difficulty/.
           2026-10-26 20:50: action 3 run (§5.10, node_ceiling.py, master
           3fcab38). §4.4 corrected: caps give a ceiling on the "same pace"
           endpoint, not super-linear E on "same factory". Next actions
           refreshed.
           2026-10-26 21:20: §5.11 (impossible-to-finish cut-offs).
```

## Above the fold

**Goal.** Before starting a new game, show a player what each R/P/E setting
does to play, as **per-axis multipliers against a 1R/1P/1E run**. For example,
"1.25R: machines 2.6–2.7x, power 2.1x, raw 3.5x in phase 4". It shows the
order of magnitude, not absolute T or machine counts.

**Why the external lab is not the base.** Its data rounds recipe inputs with
ceil (reproduced to every printed digit at all seven R values; see
`lab_rounding_check.py`). So every R >= 1.25 row is wrong. Phase-1 iron at
1.25R reads 13.2x; nearest-plus-floor gives 1.44x. Its E and P axes are pure
linear scalars, it compares against an invented fixed MW budget, and it
assumes a 25% clock. Only its UI shape is kept (`lab_ui_reference.md`).

**Next actions (ranked; Greg chooses).** Current as of 2026-10-26 20:50. The
session handoff carries the same list.

1. Record §3.3 vs this tool (§7, last item): forward amendment before any
   repo code. §5.10 adds a case it should cover: a cell whose "same pace"
   endpoint is unreachable on default nodes (k < 1) or whose plant nets
   ≤ 0 has no ×1/1/1 figure on that endpoint; it is reported, with the
   binding resource named.
2. Promote to repo: a `tools/` root joint with tests that emits `grid.json`
   through `gamedata`, with pickups, generator fuels and the D30 gathering
   mix declared.
3. Node pressure on the page (§5.10): show k (how many 1/1/1-pace factories
   the default world feeds) or only a pass/fail at k = 1. Greg's call;
   `node_ceiling.json` holds k for every cell either way.
4. Gathering card for factory pickups (Mycelia, slugs, remains): needs a
   declared source per pickup, since the LP's choice among free pickups is
   arbitrary.
5. Fluid floor unit: the 0.25R Plastic read, then the `input_amount_floor`
   default (record A5.2).

## 1. In-game observations (Greg, as stated)

| # | Observation | Date | Effect |
|---|---|---|---|
| O1 | P applies to every powered building, including miners, extractors and the AWESOME Sink. Belts and lifts are unpowered. | 2026-10-25 | Repo already scales extractors (A7, 2026-10-19) |
| O2 | P changes consumption only, not generator output | 2026-10-25 | Parasitic generator loads scale; output does not |
| O3 | P does not change the clock-power curve; clock is a lever against high P | 2026-10-25 | Clock is a machines-vs-power trade within a scenario |
| O4 | R does not change Build Gun recipes | 2026-10-25 | Corroborates storage review §11.1 (closed 2026-09-21; that review's §10.3 probe). Now stated in record A5.3 |
| O5 | At 1.25R a cost of 2 reads 3 | 2026-10-25 | Third read of half-away at a tie; first observed 2026-09-21 (crossover record A1) |
| O6 | The 1.75x liquid-zeroing bug is fixed in game | 2026-10-25 | R=1.75 needs no special case |
| O7 | 0.25R: 1 Iron Ingot makes 1 Iron Rod (unfloored would be 0) | 2026-10-26 | Confirms floor of 1 for solids. Rule: nearest, half away from zero, never below 1. Fluid floor unit not observed (record A5.2) |
| O8 | Only one hard-drive unlock at crash sites needs an item that cannot be picked up off the ground. Clarified by Greg 2026-10-26: about crash-site hard drives, not MAM (an earlier read of this note applied it to MAM) | 2026-10-25 | No effect on the MAM bill; crash sites are outside the current scope (alternates) |
| O9 | R does not scale milestone or MAM unlock costs | 2026-10-26 | Confirms `unlocks.schematic_costs` (unscaled); record A6. §5.1's falling milestone share under R is real, not an artefact |

The earlier read "1 ingot -> 2 plates at 0.25R" (3 x 0.25 = 0.75 -> 1) is
consistent with nearest rounding, but it does not exercise the floor. O7 does.

## 2. Decisions (decided by Greg)

| # | Decision | Date |
|---|---|---|
| D1 | Difficulty is per axis. E is mostly time; R and P drive machines, logistics and power, and also affect time | 2026-10-25 |
| D2 | The output is a per-axis breakdown, not a single score. Pareto-style, not a ranking | 2026-10-25 |
| D3 | Scope: Project Assembly, milestones and MAM. Building/construction costs are deferred ("not worth the effort today") | 2026-10-25 |
| D4 | Audience: a player choosing settings before a run | 2026-10-25 |
| D5 | Profiles stay OPEN. Seeds: "Dabbling Pioneer" (efficient expansion, buffering, local production, progression focus) and "Hardcore Pioneer" (goal-oriented, benchmark scaling, modular, blueprints) | 2026-10-26 |
| D6 | Generator by tier (no coal in tier 1) | 2026-10-25 |
| D7 | Rate is the axis; neither target T nor target items/min is chosen | 2026-10-25 |
| D8 | Minimal-factory anchor: one 100%-clock final machine per Project Assembly part, working backwards | 2026-10-25 |
| D9 | Default recipes are the baseline. "Optimistic alternates" is an option showing how much alternates matter; recipe/family selection later | 2026-10-25 |
| D10 | Milestones and MAM are paid from factory capacity. Milestones belong to their tier's phase window; MAM nodes go to the phase where their inputs first become producible | 2026-10-26 |
| D11 | Display multipliers against 1/1/1, not raw T or machine counts | 2026-10-26 |
| D12 | Include extractor MW, using the highest extractor mark available by tier/phase | 2026-10-26 |
| D13 | Machine count is the build-effort metric | 2026-10-25 |
| D14 | Re-solve per P (alternates objective not fixed at a reference P) | 2026-10-25 |
| D15 | A Pareto front is about trade-offs, not ordering. Compatible with record §3.3 | 2026-10-26 |
| D16 | MAM phase numbering: a Tier 3 item (Steel Pipe) belongs to phase 2 | 2026-10-26 |
| D17 | Milestones are paid serially from factory capacity ("sounds like serial is the way to go"); machine-minutes treated as fungible on one factory | 2026-10-26 |
| D19 | R (and E) show as BOTH time and machines, either/or, never stacked ("yes, either/or, not stacked"). One work multiplier (machine-minutes vs 1/1/1); time x machines = work; endpoints "same factory" (all time) and "same pace" (all machines) | 2026-10-26 |
| D20 | Idealised assumptions (fungible machine-minutes, free construction, hand-crafted early milestones) are accepted when held identical on both sides of the comparison: the goal is order of magnitude, not hours or machine counts | 2026-10-26 |
| D21 | Every pickup is hand-supplied, not only Mycelia ("pickups as hand-supplied is good"); extends D18. List in §5.3 | 2026-10-26 |
| D22 | Phase-1 front-loading from earliest-producible MAM is fine. The multiplier is shown with its components (Project Assembly / milestones / MAM) as a subset: what the multiplier is made of. Likely to apply to other axes too | 2026-10-26 |
| D23 | Equipment consumed as a MAM research cost stays unpriced, named, for now ("leave them unpriced for now") | 2026-10-26 |
| D24 | Power-plant machines count toward work: generators, the machines making their fuel, and the extractors for fuel and water. Factory extractors are counted too, as their own component (consistency; Claude's addition, visible in D22's breakdown) | 2026-10-26 |
| D25 | Show the whole open generator set; prune later if needed | 2026-10-26 |
| D26 | Display baseline: every figure is × the 1/1/1 factory, before power, so power sources compare directly; each source row also shows its own 1/1/1 run ("make those headline and row changes") | 2026-10-26 |
| D27 | Power-source rows are sole-source alternatives, not cumulative ("maybe a sub about non-cumulative or sole power source") | 2026-10-26 |
| D28 | The run is named by the record §3.3.1 triple (ore grade · utility load · order book), shown with the selector. The naming may later expand to node purity/randomness options | 2026-10-26 |
| D29 | Hand-gathering is its own output in item counts (stacks), not part of work ("adding it here feels like mixing too many things"). Also consistent with record §9's no-player-time line | 2026-10-26 |
| D30 | Biomass burners are fed from a declared gathering mix: 5 stacks of Leaves to 1 of Wood (Greg's typical 1/1/1 haul, no chainsaw). Mycelia (occasional) and Alien Protein (goes to DNA capsules) are left out. Two routes are shown: burn Biomass, or via Solid Biofuel (D25 style). This replaces the hand-fed-Leaves fuel of §5.5 | 2026-10-26 |
| D18 | Mycelia is a hand-supplied input ("treat mycelia as hand-supplied input"): a leaf with no extractor and no machine time; Biomass and Fabric are still machine-made | 2026-10-26 |

## 3. Structural findings

**3.1 A Pareto front across settings is nearly empty.** By O4, O7 and the
monotonic rounding, lower R, P and E are easier on every axis, so
0.25/0.25/0.25 dominates almost everything. The fronts that do something are
*within* a scenario:
- machines vs power via clock (P-independent shape; power per throughput is
  about clock^0.32, machines about 1/clock);
- resources vs power vs machines via alternates (repo `Weights(resources,
  power, buildings)`; for a pure LP, a weight sweep traces the whole efficient
  set, so the front replaces choosing weights);
- extractor mark: higher marks save nodes and cost more power per item.

Settings are then compared as profile shifts against 1/1/1. Greg confirmed
(D15, 2026-10-26) that a Pareto front shows trade-offs, not an ordering, so
it is compatible with record §3.3 ("no ordering over combinations is
admissible").

**3.2 Rate axis in natural units.** Rate = k final machines per part; k = 1 is
the minimal factory. The non-arbitrary points on the axis are k = 1 and the
node ceiling (max sustainable scale under node caps). A profile, when
defined, chooses where on the curve the player sits.

**3.3 Default-recipe anchor T at 1E** (one machine per part, 100% clock):

| Phase | Bottleneck part | T |
|---|---|---|
| 1 | Smart Plating (2/min) | 0.42 h |
| 2 | Smart Plating, 1000 at 2/min | 8.33 h |
| 3 | Versatile Framework / Modular Engine (tied) | 8.33 h |
| 4 | Assembly Director System (0.75/min) | 11.11 h |
| 5 | Nuclear Pasta (0.5/min) | 33.33 h |

That's about 61.5 h at 1E, and it scales linearly in E only under a fixed anchor.

## 4. Model

**4.1 Anchors.** A = every part at its one-machine rate at once (the peak
factory; non-bottleneck lines idle once their part is done). B = bottleneck
part at one machine; the others are sized to finish at the same T (the
sustained factory).

**4.2 The A/B choice mostly washes out of the multiplier.** Absolute size
differs up to about 6x (phase 5), but ratios to 1/1/1 agree within about 10%.
Show A and B as a **band**; don't average them (an average mixes two
definitions).

**4.3 Unlock offsets (B').** A part starts when its unlock milestone is
paid: phase 2 has Smart Plating at 2-1 (start), Versatile Framework at 3-4,
Automated Wiring at 4-1. Start time = milestone bill paid so far / factory
rate. Rate = q / (T - start). There are no dependencies between milestones
inside a tier, so the order is a player choice (a profile setting). Greg's
reason for liking A: the smaller Automated Wiring quantity looks like
deliberate balance against its late unlock. Given 4.2, offsets move absolute
size more than the R/P multipliers. Deprioritized.

**4.4 The E time multiplier.** E scales Project Assembly quantities, not
milestones:

    T multiplier(E) = (E * T_PA + T_milestones) / (T_PA + T_milestones)

It is sub-linear, which matches Greg's "not simply 10x for 10E". It needs
milestone time paid from factory capacity (D10), not offsets.

**Why sub-linear, and what would make it super-linear (2026-10-26).** Greg
expected it to scale higher than E. In this model it can't. The LP has
constant returns to scale: the 10,000th Smart Plating costs the same machine
time and power as the first. So work is affine in E:
fixed (milestones, MAM) + E × PA (plus its extractors and power plant). A
positive fixed term always gives a ratio below E. The things that would make
the marginal unit cost more as E grows are exactly what's held out:

- node caps: finite nodes, then impure or distant nodes, then a node ceiling
  (not modelled; §7 action 4)
- logistics: belt and pipe tier limits, trunk length, travel
- construction cost (deferred, D3)
- overclocking to hold a machine count: power per item goes as clock^0.32,
  so it's super-linear in power

So the current E figure is a lower bound on its effect. Node caps are the
mechanism that's both measurable here (`solve_portfolio` stage 1) and
likely to dominate.

**Corrected 2026-10-26 20:50 (§5.10).** Node caps do not make E super-linear
on D19's "same factory" endpoint: a fixed factory draws a fixed rate, so E
only lengthens the run. They act on the "same pace" endpoint, where E (or R)
raises the rate: first the cheap sockets fill, then the expensive ones, then
a hard ceiling. §5.10 measures the ceiling. The rising cost below it (MW and
extractors per unit as impure sockets come in) is not measured.

**4.5 Power.** Manufacturing MW, plus extractor MW (D12), plus generators by
tier (D6) with parasitic loads (O2). Generator availability by tier, from
`schematic_recipe_unlocks.csv`: Biomass at Tutorial 5; Coal at 3-1; Fuel at
5-5; Nuclear at 8-1; Geothermal via MAM Caterium. Phase 1 is produced on
tiers 0–2, so biomass only. At 5P a single Mk1 miner draws 25 MW, close to a
whole biomass burner. Coal parasitic load at 5P: one 20 MW water extractor
(120 m3/min) feeds about 2.67 x 75 MW generators, so about 50% of output goes
to the pump at 5P against 10% at 1P.

**4.6 Extractors by phase (D12).** Mk1 at Tutorial 4; Mk2 at 4-1; Mk3 at
8-4; Oil Extractor at 5-1; Water Extractor at 3-1; resource wells at 8-2. MW
per item/min at normal purity: Mk1 0.083, Mk2 0.125, Mk3 0.188.

**4.7 Purity.** A uniform purity cancels out of every ratio (impure doubles
both scenario and baseline extractor MW). It matters for absolute MW and for
node-capacity feasibility. Proposed input: purity mix including
"all impure", where high R/P may be infeasible, which is itself the answer.

**4.8 MAM phase assignment.** Earliest phase in which all required items can
be produced; "defer" is a profile setting. Tier N production falls in the
window of the phase whose predecessor's delivery unlocked tier N (tiers 3–4
means phase 2). Confirmed by Greg 2026-10-26 (D16): Steel Pipe is phase 2.

## 5. Measured multipliers (default recipes, floor 1, 100% clock, normal purity)

Ratio to 1/1/1, same anchor, A | B. "Ext MW" excludes water extractors.

**1.25R / 1P:**

| Phase | Machines | Mfg MW | Ext MW | Raw |
|---|---|---|---|---|
| 1 | 1.23 / 1.23 | 1.14 / 1.14 | 1.44 / 1.44 | 1.44 / 1.44 |
| 2 | 1.44 / 1.34 | 1.34 / 1.27 | 1.97 / 1.89 | 1.97 / 1.89 |
| 3 | 1.89 / 1.93 | 1.65 / 1.65 | 2.40 / 2.36 | 2.43 / 2.43 |
| 4 | 2.67 / 2.64 | 2.08 / 2.15 | 3.48 / 3.38 | 3.56 / 3.55 |
| 5 | 2.30 / 2.20 | 1.58 / 1.51 | 2.79 / 2.66 | 2.84 / 2.57 |

**Rounding cliff, phase-1 raw:** 1.25R 1.44x, 1.5R 16.3x, 2R 22.4x. Phase-5
machines: 1.25R about 2.2x, 1.5R about 15x, 2R about 34x. 0.25R phase-4
machines about 0.08x.

Caveat (2026-10-26): sub-1x figures depend on the fluid floor's unit, which is
unobserved (record A5.2). Whether `multiplier_ratios.py` ran them with the
repo's per-m3 floor was not checked.

**P:** exactly 5x on manufacturing and extractor MW at 5P, 1x on machines and raw.

**1/1/1 absolute (B):** phase 4: 204 machines, 2,491 manufacturing MW,
436 extractor MW (871 impure). Phase 5: 106 machines, 2,769 MW, 403 MW.

Full sweep: `python -I multiplier_ratios.py <repo> --scenarios ... --absolute`.

### 5.1 Milestone load and the serial E multiplier (measured 2026-10-26 09:50, container, master 4a32faa)

W = machine-minutes, the sum of LP machine-equivalents needed to make the
whole bill (BASE_ONLY, 100% clock, floor 1 per stated unit). It is independent
of T. Milestones are the progression-type schematics in the phase's tier
window (ph1 0–2, ph2 3–4, ph3 5–6, ph4 7–8, ph5 9), at unscaled costs. Under
D17, T multiplier(E) = (E·W_PA + W_ms)/(W_PA + W_ms) at fixed R. Script:
`milestone_load.py` (project doc beside this).

**Serial T multiplier vs E, at 1R:**

| E | 0.25 | 0.5 | 1 | 2 | 5 | 10 | 25 | 50 | 100 |
|---|---|---|---|---|---|---|---|---|---|
| ph1 (ms 79%) | 0.84 | 0.89 | 1 | 1.21 | 1.86 | 2.93 | 6.15 | 11.5 | 22.3 |
| ph2 (38%) | 0.54 | 0.69 | 1 | 1.62 | 3.47 | 6.55 | 15.8 | 31.2 | 62.1 |
| ph3 (36%) | 0.52 | 0.68 | 1 | 1.64 | 3.56 | 6.76 | 16.4 | 32.4 | 64.4 |
| ph4 (21%) | 0.41 | 0.60 | 1 | 1.79 | 4.17 | 8.13 | 20.0 | 39.8 | 79.5 |
| ph5 (27%) | 0.45 | 0.63 | 1 | 1.73 | 3.93 | 7.59 | 18.6 | 36.9 | 73.5 |

**Milestone share by R:**

| R | ph1 | ph2 | ph3 | ph4 | ph5 |
|---|---|---|---|---|---|
| 0.25 | 86% | 41% | 43% | 36% | 32% |
| 0.5 | 83% | 40% | 42% | 32% | 30% |
| 1 | 79% | 38% | 36% | 21% | 27% |
| 1.25 | 77% | 38% | 32% | 15% | 25% |
| 1.5 | 59% | 26% | 25% | 11% | 11% |
| 2 | 56% | 26% | 24% | 9% | 10% |

**Cross-axis.** R shrinks the milestone share because the PA chains are
deeper than the milestone bills. So E's time multiplier rises with R: at E=10
it is 6.6–8.1x across phases 2–5 at 1R, 7.7–9.2x at 2R, and 6.1–7.1x at
0.25R. The display can't treat E as independent of R.

**Hand-supplied (D18).** Mycelia for Hazmat Suit (7-3, 50 Gas Filter): 150
at 1R, 55 at 0.25R, 240 at 1.25R, 800 at 2R. Milestone costs are not
R-scaled, but the Fabric and Biomass recipes are.

Excluded, named: coupon-priced Custom rows (not parts). Not modelled:
tier-gated recipe sets (BASE_ONLY ignores tier); early milestones
hand-crafted before a factory exists, which is most of phase 1's share; MAM.

**LP scale note.** Solving a bill as a per-minute rate makes `LpBackend`
report `Infeasible` at 2R phase 5. The cause is that `ACTIVITY_UPPER_BOUND`
(1e6) binds, not that the bill is unproducible. The script solves at
bill/1000 and rescales. No real caller path reaches that scale; it's noted
here and not patched.

### 5.2 Work multiplier (D19), measured 2026-10-26, from the §5.1 run

Work(R, E) = (E·W_PA(R) + W_ms(R)) / (W_PA(1) + W_ms(1)), with Project
Assembly plus milestones in machine-minutes. Display it as one figure with two
either/or endpoints: same factory means Work× time; same pace means Work×
machines. At E=1:

| R | ph1 | ph2 | ph3 | ph4 | ph5 |
|---|---|---|---|---|---|
| 0.25 | 0.66 | 0.38 | 0.22 | 0.10 | 0.11 |
| 0.5 | 0.78 | 0.57 | 0.39 | 0.23 | 0.27 |
| 1.25 | 1.16 | 1.34 | 1.81 | 2.46 | 2.16 |
| 1.5 | 2.16 | 3.40 | 4.20 | 7.26 | 11.9 |
| 2 | 2.65 | 4.83 | 7.69 | 17.4 | 26.7 |

Sub-1x rows assume a per-m3 fluid floor (record A5.2). Under D20 the
idealisations cancel in the ratio. They don't make absolute hours or machines
meaningful, and none are shown.

### 5.3 MAM bill (measured 2026-10-26 11:05, container, master 4a32faa)

Script: `mam_bill.py` (project doc beside this). 120 MAM nodes; 20 excluded,
named ("Discontinued - " nodes and the FICSMAS tree). All 100 others place.

- **Placement (D10).** A node goes in the first phase where every priced cost
  is producible: tier-granted base recipes at the window's top tier, plus
  recipes from MAM nodes already placed (closure), plus extractables with an
  open extractor, plus pickups. Result: ph1 53, ph2 21, ph3 20, ph4 4, ph5 2.
  MAM tree order is NOT enforced: `schematic_dependencies.csv` has no MAM
  rows. Recipe-unlock order is enforced, because Quickwire research waits for
  the Caterium Ingot node.
- **Pickups as hand-supplied (D18 extended, pending Greg).** These are all
  items with no producing recipe that aren't extractable: Mycelia, Paleberry,
  Beryl Nut, Bacon Agaric, Leaves, Wood, Mercer Sphere, Somersloop, the four
  remains and the three slugs. Hard Drive is also treated as a pickup. Which
  remains the LP draws for Alien Protein is arbitrary, since pickups cost
  nothing.
- **Pricing.** Base recipes plus MAM-unlocked recipes, including two
  alternate-flagged ones: Enriched Coal and Polyester Fabric. Compacted Coal
  is reachable only through Enriched Coal, so Turbofuel and Rocket Fuel
  research need it. PA and milestone W are unchanged from §5.1.
- **Unpriced, named.** Equipment costs that aren't in items.csv: Nobelisk
  (up to 500), Spiked Rebar, Rifle Cartridge (up to 1000), Object Scanner.

MAM share of phase work at 1R: ph1 70%, ph2 18%, ph3 16%, ph4 0.2%,
ph5 0.4%.

**Work multiplier (D19) with MAM [without]**, E=1:

| R | ph1 | ph2 | ph3 | ph4 | ph5 |
|---|---|---|---|---|---|
| 0.25 | 0.46 [0.66] | 0.37 [0.38] | 0.22 | 0.10 | 0.11 |
| 1.25 | 1.30 [1.16] | 1.37 [1.34] | 1.78 [1.81] | 2.46 | 2.16 |
| 1.5 | 2.34 [2.16] | 3.21 [3.40] | 4.01 [4.20] | 7.25 | 11.9 |
| 2 | 3.22 [2.65] | 4.62 [4.83] | 7.29 [7.69] | 17.4 | 26.6 |

Serial E=10 at 1R with MAM: ph1 1.59x, ph2 5.54x, ph3 5.86x, ph4 8.12x,
ph5 7.56x. Without MAM these were 2.93, 6.55, 6.76, 8.13 and 7.59. MAM
dilutes E most where it lands, which is phase 1.

Only phase 1 moves materially. That's a consequence of D10's
earliest-producible rule, which puts 53 nodes in phase 1.

### 5.4 What the multiplier is made of (D22), from the §5.3 run

Each component is W_k(R)/W_total(1/1/1), so the components sum to the work
multiplier. That split is additive, and it's separate from the time-or-
machines split of D19. Format: total = PA + milestones + MAM, at E=1.

| R | ph1 | ph2 | ph3 | ph4 | ph5 |
|---|---|---|---|---|---|
| 1 | 1 = 0.07+0.24+0.69 | | | | |
| 0.25 | 0.46 = 0.03+0.17+0.26 | 0.37 = 0.18+0.13+0.06 | 0.22 = 0.11+0.08+0.03 | 0.10 = 0.06+0.03+0.00 | 0.11 = 0.08+0.04+0.00 |
| 1.25 | 1.30 = 0.08+0.27+0.95 | 1.37 = 0.68+0.42+0.27 | 1.78 = 1.04+0.49+0.25 | 2.46 = 2.09+0.37+0.00 | 2.16 = 1.60+0.55+0.01 |
| 1.5 | 2.34 = 0.27+0.39+1.68 | 3.21 = 2.05+0.72+0.44 | 4.01 = 2.65+0.90+0.47 | 7.25 = 6.43+0.82+0.00 | 11.9 = 10.6+1.33+0.05 |
| 2 | 3.22 = 0.36+0.45+2.41 | 4.62 = 2.92+1.02+0.68 | 7.29 = 4.96+1.53+0.81 | 17.4 = 15.8+1.54+0.00 | 26.6 = 23.8+2.76+0.09 |

The breakdown shows the shape of R's cost. In phase 1 it's mostly MAM; from
phase 3 onward it's mostly Project Assembly. E scales only the PA component.

### 5.5 Power axis (measured 2026-10-26 11:20, container, master 4a32faa)

Script: `power_axis.py`. It runs on the §5.3 bill (PA + milestones + MAM,
E=1). Energy is in MW-minutes for the whole bill, so it's invariant under
D19, like machine-minutes.

- **Demand** is manufacturing, plus ore/oil extraction at the highest open
  mark (D12), plus water extraction. All of it is normal purity and scaled
  by P (O1).
- **Supply** is reported per generator type open at the phase's top tier
  (D6), and no generator is chosen. Net MW per generator = gross (not
  P-scaled, O2) minus the energy to make its fuel at burn rate and pump its
  water.
- **Declared fuels:** Biomass on Leaves (a pickup, so zero parasitic, D21),
  Coal on Coal, Fuel on Fuel, Nuclear on Uranium Fuel Rod. Nuclear waste
  isn't handled.

**Finding: demand is exactly linear in P, and supply isn't.** P scales every
consumer, so energy(R,P) = P·energy(R,1) to the digit (1.25R/5P: 6.25 =
1.25 × 5). The non-linearity is all in the generators: their own fuel and
water loads scale with P, but their output doesn't.

Net MW per generator and parasitic share, R=1 (Mk2 miners, ph2–3):

| P | Coal 75 | Fuel 250 | Nuclear 2500 (ph4–5) |
|---|---|---|---|
| 0.25 | 72.7 (3%) | 243.8 (2%) | 2460 (2%) |
| 1 | 65.6 (13%) | 225 (10%) | 2342 (6%) |
| 2 | 56.2 (25%) | 200 (20%) | 2183 (13%) |
| 5 | 28.1 (63%) | 125 (50%) | 1708 (32%) |

(The 1P row is DERIVED: parasitic(5P)/5, since parasitic load is linear in
P. It wasn't run at 1R/1P. The other rows are measured.)

**Generator-minutes multiplier vs 1/1/1, same generator:**

| Scenario | Biomass | Coal | Fuel | Nuclear |
|---|---|---|---|---|
| 1R / 2P | 2.00 | 2.33–2.38 | 2.25 | 2.15 |
| 1R / 5P | 5.00 | 11.7–13.8 | 9.00 | 6.85 |
| 1.25R / 1P | = energy | ≈ energy | +0–1% | +2–3% |
| 1.25R / 5P, ph4 | 11.5 | 31.8 | 23.1 | 20.4 |

So 5P is 5x the power but 7–14x the power plant, depending on the
generator. Coal is hit hardest, because its water pumps and miners are a
large share of a small output. Biomass reads exactly P only because it's
hand-fed (D21); that flatters it, and the ratio hides it.

Components at 1R (energy = mfg + ore + water): ph1 0.89+0.11, ph2
0.81+0.19, ph3 0.82+0.18, ph4 0.80+0.19+0.01, ph5 0.86+0.14+0.01 (each
times P). Nitrogen Gas extraction is unmapped (resource wells only) and
named.

### 5.6 Full work multiplier (D22, D24, D25), measured 2026-10-26 11:40

Script: `work_axis.py`. The components are PA + milestones + MAM + extractors
+ power plant, each divided by the 1/1/1 total for the SAME generator type.
Generators are reported as the whole open set (D25). This supersedes the
§5.2–5.4 tables, which counted no extractors and no plant. Their component
logic stands.

| Scenario | ph2 | ph4 | ph5 |
|---|---|---|---|
| 1R/5P | Biomass 1.86, Coal 2.68 | Biomass 2.26, Coal 3.99, Fuel 1.77, Nuclear 1.29 | Biomass 2.81, Coal 5.54, Fuel 2.29, Nuclear 1.50 |
| 1.25R/1P | 1.41 (both) | 2.45–2.59 | 2.00–2.28 |
| 1.25R/5P | Biomass 2.58, Coal 3.72 | Biomass 5.35, Coal 9.38, Fuel 4.59, Nuclear 4.04 | Biomass 5.11, Coal 9.87, Fuel 4.74, Nuclear 4.15 |
| 1R/1P/10E | 5.48 | 8.13–8.18 | 7.63–7.91 |

**With D24, P becomes a work axis.** At 5P the plant component dominates:
ph5 Coal 5.54 = 0.43 PA + 0.16 ms + 0.06 ext + 4.90 plant. Generator choice
matters most under P: at 1.25R/5P ph4, nuclear is 4.0 and coal is 9.4. Under
R alone, the generator barely matters (2.45–2.59).

Plant share at 1/1/1: Biomass 16–45% (30 MW burners), Nuclear 5–9%.
Extractors: 4–11%. Full component strings are in `work_axis_output.txt` (project doc)
and reproducible from the script.

### 5.7 Display mock-up (2026-10-26 11:45)

Design canvas "Multiplier Difficulty Mock-up" (claude.ai artifact), phone
width, for 1.25R/5P/1E. It has three cards:

- **Total work:** a range over power sources, with the D19 either/or line
  shown once.
- **Factory:** PA, milestones, MAM and extractors, normalised to the
  factory's own 1/1/1 total, so it doesn't depend on the generator.
- **Power plant:** a "drawn by the factory, any source" row, then per source
  the plant multiplier (generators plus the machines and extractors feeding
  them, vs 1/1/1 same source) and the total work.

Factory figures at 1.25R/5P/1E, from `card_numbers.py`: ph1 1.33, ph2 1.41,
ph3 1.83, ph4 2.52, ph5 2.22. Nuclear's plant multiplier is the largest at
1.25R (ph4 33x), because R scales the fuel-rod chain, but the plant is a
small share of the total (4.04x).

The scenario is the R/P/E triple plus the fixed assumptions of §5.1–5.6,
held identical on the 1/1/1 side (D20). Other cards are possible (time vs E,
raw resources and pickups, node pressure) but not built.

### 5.8 R/P/E selector (2026-10-26 12:25)

The mock-up now selects R, P and E. The levels and names come from record
§3.3.1, and the run is named by the triple (D28). Data: `grid.py` produced
`grid.json`, 48 R×P pairs × 5 phases, container, master 4a32faa, 108 s. E is
applied on the page and isn't solved for: E scales only the PA bill's work,
extractors and energy, which are linear in E (§4.4). Check: 1.25R/5P/1E ph4
reproduces §5.6/D26 (factory 2.52, energy 11.53, totals 7.81 / 12.24 / 5.08
/ 4.25).

**Finding:** at 1.75R and 2R with 5P, phases 4–5, a nuclear plant's own
fuel-rod chain plus water draws more than its 2,500 MW. Its net is ≤ 0, and
the page shows that rather than a number. It's the same mechanism as coal at
5P, taken past the break-even point.

### 5.9 Biomass routes and gathering (2026-10-26 12:50)

`biomass_routes.py` patches `grid.json` with no LP: the chain is fixed. Per
burner-minute it gives net MW, constructors and leaves/wood. Recipe inputs are
R-scaled and constructor power is P-scaled.

**Biofuel's gathering advantage disappears at 1.25R.** At 1R, 8 Biomass make
4 Solid Biofuel (1,440 MJ in, 1,800 MJ out), which saves 20% of the
gathering. At 1.25R the input rounds to 10 Biomass, which is 1,800 MJ in
either route, so the saving is zero. At 2R it takes 16 Biomass, and biofuel
needs about 1.8x the gathering of burning Biomass directly. Under P alone it
still saves 20%, at about 0.9 MW per burner at 5P. Greg's read that you're
better off burning the Biomass holds on work at high P, and on gathering too
from 1.25R up.

**Scale check, ph4, 1/1/1, biomass only:** about 1,900 stacks of leaves plus
380 of wood. At 1.25R/5P it's about 29,700 plus 5,900. The card makes
biomass's impracticality past phase 1 visible, which the hand-fed-Leaves
model hid. Biomass total work in ph4 at 1.25R/5P is now 8.81 (burn) and
9.53 (biofuel); §5.6/D26's 7.81 assumed no constructors.

### 5.10 Node ceiling on the default world (measured 2026-10-26 20:40, container, master 3fcab38)

Script: `node_ceiling.py` (rules in its docstring). Data: `node_ceiling.json`
(world purities) and `node_ceiling_all_normal.json` (same socket counts, every
one normal), 8 R × 6 P × E{1,10} × 5 phases, factory plus each open
generator. Prompted by Greg (2026-10-26): use nodes by their proportion in the
world rather than all normal, since some combinations may be impossible on
default nodes before shards, somersloops or augmenters.

**What is measured.** `solve_portfolio` stage 1 on one site holding every
default socket, at the highest extractor mark open at the phase's top tier
(D12), 100% clock. The bill is the whole phase bill (PA × E + milestones +
MAM) per minute at the reference pace T_ref, so the scale is **k**: how many
1/1/1-pace factories the default world feeds. T_ref = §3.3's anchor T ×
W_total/W_PA at 1/1/1 (serial, D17): ph1 6.36 h, ph2 16.54, ph3 15.43, ph4
14.04, ph5 45.72. The script re-derives §3.3's anchor T (0.42 / 8.33 / 8.33 /
11.11 / 33.33 h). k < 1 means the "same pace" endpoint (D19) can't be reached
on default nodes. "Same factory" always can; it just takes longer
(T_min = T_ref / k).

**Proportion vs all-normal.** The world is richer than all-normal for most
raws, in normal-node equivalents (2·pure + normal + ½·impure, against the
count): iron 1.21x, limestone 1.23x, caterium 1.47x, quartz 1.32x, bauxite
1.21x, coal 1.14x, copper 1.12x, sulfur 1.12x, oil nodes 1.10x, nitrogen wells
1.78x. It is poorer for SAM (0.89x) and uranium (0.70x). So the world purity
mix raises most ceilings 5–20% against all-normal. It lowers them where SAM
binds (phase 2 at every R ≤ 1.25, where MAM's SAM costs bind) and in some
power-bound cells. 79 of 712 E=1 cells are lower on the world than on
all-normal. Assuming all-normal is not the pessimistic case it was taken for.

**Factory ceiling (power outside the solve), world k, E=1:**

| R | ph1 | ph2 | ph3 | ph4 | ph5 |
|---|---|---|---|---|---|
| 0.25 | 1367 | 976 | 1572 | 2039 | 1060 |
| 1 | 246 | 82 | 68 | 11.0 | 24.4 |
| 1.25 | 155 | 49 | 28 | 3.78 | 8.33 |
| 1.5 | 26 | 18 | 4.95 | 1.65 | 1.86 |
| 1.75 | 22 | 15 | 3.39 | **0.78** | **0.90** |
| 2 | 17 | 11 | 2.42 | **0.52** | **0.52** |

At 1.75R and above, phases 4–5 can't be built at the 1/1/1 pace on every
default node, even with free power. Binding at 2R: ph4 Bauxite, Copper Ore
and Crude Oil; ph5 Bauxite, Caterium Ore and SAM. At 1R the world feeds 11x
the anchor pace in ph4, the tightest phase (Crude Oil binds). At E=10, k
falls below 1 from 1.25R in ph4 (0.43) and from 1.5R in ph3–5.

**Sole-source power (D27), E=1.** Each generator's fuel comes from the same
sockets, and extractors are charged by their draw × P. The lowest R where
k < 1:

| Generator | P ≤ 1 | P2 | P5 |
|---|---|---|---|
| Coal | ph4–5 from 1.75R | ph4–5 from 1.75R | ph4 from 1.25R (0.86), ph5 from 1.5R, ph3 at 2R |
| Fuel | ph4 from 1.5R (P1) or 1.75R; ph5 from 1.75R | ph4–5 from 1.5R | ph4–5 from 1.25R (0.51 / 0.70), ph3 from 1.75R |
| Nuclear | ph4–5 from 1.75R | ph4–5 from 1.75R | ph4–5 from 1.5R (≈0.2); **unreachable at 2R** |
| Biomass | same as factory (Leaves are a pickup) | | |

The nuclear zero at 2R/5P reproduces §5.8's net ≤ 0 by a different route.
Nuclear holds best otherwise: 1.97 at 1.25R/5P ph4, against 0.86 for coal and
0.51 for fuel, and it is bound by Uranium (5 sockets, none pure).

**"grid" cells.** In 16 cells (Fuel at 1.75–2R/5P, Nuclear at 2R/5P) the
power row binds and no raw is at its cap: the cheap sockets are full and the
rest aren't worth working. Checked once (2R/5P ph3 Fuel): doubling the pure
oil sockets lifts k 1.69x, doubling the impure ones 1.00x. This is purity
doing what the question expected: under high P, impure sockets cost twice the
MW per unit and stop paying for themselves.

**Held out (named).** Belts never bind at the top tier (Mk1 pure 120 on Mk2
120, Mk2 pure 240 on Mk3 270, Mk3 pure 480 on Mk5 780). They would bind
earlier in a window, which D12 doesn't model. Wells are charged one 150 MW
pressurizer per core, averaged over the resource's satellites. Geysers are
left out (geothermal isn't in the generator set). Water is pumped from open
water without limit. Distance is ignored: every socket on the map is in one
site. Pickups are dropped from the bill (D29). Raws named directly in the
bill pass through a zero-power pseudo recipe. Nitrogen is now priced through
wells (it was unmapped in §5.5); this affects only §5.10.

**Conditioning (corrected in the run).** A first pass solved the raw bill per
minute (scale about 1e-5) with pickups capped at 1e9. HiGHS then returned 0
for 1.5R/5P ph5 Coal and short scales for Biomass at 5P, and the plant's
binding report missed capped raws. Normalising the bill to T_ref (scale = k)
and capping pickups at 1e7 made all of it regular. Every figure here is from
the normalised run.

### 5.11 When a phase can't be finished at all (measured 2026-10-26 21:20, container, branch claude/node-ceiling)

Greg (2026-10-26): is there a mix of multipliers and node purity that makes
the game impossible to finish, and where is the cut-off? Scripts:
`node_ceiling.py --purity=impure` (`node_ceiling_all_impure.json`) and
`plant_cutoff.py` (bisects P per generator, R and purity world).

**k < 1 is not impossible.** It means the 1/1/1 pace can't be held, so the
run is slower. Impossible means k = 0: no positive rate at all. With the
factory alone (power outside the solve), k never reaches 0 in any purity
world: the lowest is 2R ph5, at 0.52 (world), 0.46 (all-normal) and 0.23
(all-impure). k = 0 happens only when a sole-source plant (D27) can't net
positive power. That happens when its own extraction, fuel chain and water,
all × P, eat its gross output.

**P cut-off above which the source nets ≤ 0** (phases with the same value
are merged):

| Source | Purity | 1R | 1.5R | 1.75R | 2R |
|---|---|---|---|---|---|
| Nuclear (ph4–5) | world | >8 | 7.60 | 5.86 | **4.29** |
| | all-normal | >8 | 6.20 | **4.67** | **3.29** |
| | all-impure | >8 | **4.47** | **3.27** | **2.21** |
| Fuel (ph3 / ph4–5) | world | >8 | >8 | >8 | >8 |
| | all-normal | >8 | >8 | 7.69 | 7.14 |
| | all-impure | 7.14 / >8 | 5.56 / 7.41 | **5.00** / 6.78 | **4.55** / 6.25 |
| Coal (ph2–3 / ph4–5) | world | >8 at every R | | | |
| | all-normal | 8.00 / 7.27 at every R | | | |
| | all-impure | 6.67 / 5.71 at every R | | | |

Bold is at or below P = 5, the top of the grid's P levels. Nuclear at 1.25R
and below has no cut-off under 8 in any world.

- Coal's cut-off doesn't depend on R, because its fuel is a raw. It checks by
  hand: (75 MW) / ((15 coal × miner MW per unit + 45 m3 water × 20/120) ×
  P). All-impure Mk2 gives 75 / 11.25 = 6.67, and Mk3 gives 75 / 13.125 =
  5.71. All-normal gives 8.00 and 7.27.
- Fuel in phase 3 has only oil extractors. From phase 4, wells add oil at an
  averaged pressurizer charge that doesn't vary with purity, so the phase 4–5
  cut-off is higher. The averaging is an approximation (§5.10).
- Two solves near a cut-off had HiGHS fail after stage 1, both at a scale of
  about 0 (1.5R ph4 Nuclear at P 4.47, Fuel at P 7.41, all-impure). These are
  counted as k = 0.

**So, in this model, the game is never impossible with a power mix.**
Biomass on hand-fed Leaves always nets positive, and coal nets positive up
to P ≈ 5.7 even on all-impure. What the multipliers and purity can make
impossible is a given power source. On the default world at P = 5, that is
nuclear from 2R. On all-impure at P = 5, it is nuclear from 1.5R and fuel in
phase 3 from 1.75R. Biomass at scale is impractical (§5.9), which is a
different kind of limit. Whether the game offers P above 5 hasn't been
checked here.

## 6. Repo capability map (read at 4a32faa)

| Need | Present | Notes |
|---|---|---|
| Recipe rounding | `scenario.apply_input_amount`, per cycle, ROUND_HALF_UP on Decimal | `input_amount_floor` defaults to None and refuses inputs that could round to zero. O7 says it should be 1 for solids; whether to change the default is a code decision for Greg. For fluids the floor is applied in m3, which binds 31 inputs at 0.25R and 6 at 0.5R/0.75R; unobserved (record A5.2) |
| Project Assembly quantity rounding | `apply_project_assembly_quantity` | Rounds; floor not applied there |
| Milestone / MAM costs | `schematic_costs.csv` (597 rows) | Not confirmed whether the current demand bill includes them |
| Building recipes | `building_recipes.csv`, `building_recipe_io.csv` | Record §10.1 gap appears closed; D3 defers use |
| Extractor power x P | `progression/district.py` via `Scenario.apply_power` (A7) | Ledger: ore extraction is UNKNOWN, never 0 |
| T | `progression.schedule.horizon_from_anchor` = total / chosen rate | No capacity-derived T. `solve_portfolio` stage 1 (max scale under caps, optional shared power row) gives the node ceiling |
| Weights | `Weights(resources, power, buildings)`, default 1/1/1, secondary objective; `complexity` pinned 0 | Sweeping weights traces the within-scenario front |
| Water extraction rate | `extraction_rates.csv`: Build_WaterPump_C, purity `none`, 120 m3/min | Corrected 2026-10-26: an earlier read here called it missing. `multiplier_ratios.py` looks rates up by (class, purity) with a `normal` fallback, so the `none` row never matched. Used in §5.5 |

Repo constraints that apply when this moves into code: `gamedata.py` is the
only CSV loader (the scratch script breaks this); scenario modifiers apply
at runtime, never in reference tables; layers report and don't choose (no
default profile, no hidden min/max); new joints go at `tools/` root.

## 7. Open

- Profiles (D5): the lever set and what defines each preset.
- Water extraction rate source; generator parasitic model.
- RESOLVED D17 — **Serial vs parallel**. Serial: milestones time-share the factory; this needs machine-minutes to be fungible across products, which is an assumption, and gives the sub-linear E of §4.4 and §5.1. Parallel: milestones run on their own lines over the same T, which is the repo's goal_run A15 semantics. Then T = E·T_PA exactly under anchor B, and milestones add machines but no time, so E is linear in time. D10 says "paid from factory capacity", which reads as serial, but the scheduling is unspecified.
- RESOLVED D18 — **Gas Filter (7-3)**: exclude it with the reason named; price Fabric by Polyester Fabric under the optimistic-alternates option; or treat Mycelia as a gathered leaf (hand-supplied, like O8).
- Clock policy as an input (the 25% vs 100% question); the anchor fixes final machines at 100%.
- Optimistic-alternates option: unlock timing not constrained (the lab's limitation carries over).
- `input_amount_floor` default.
- Fluid floor unit (record A5.2). Read not yet available (Greg, 2026-10-26: no 0.25R Plastic yet). Discriminating read: Plastic's Crude Oil in a Refinery's recipe UI on a 0.25R save — 0.75 m3 (per internal unit; floor never binds on fluids) or 1 m3 (per stated unit; the repo's current behaviour).
- RESOLVED O9 (2026-10-26) — **Milestone costs under R**: unscaled, observed. Covers MAM too.
- RESOLVED D19 (2026-10-26) — **What R costs: machines or time.** Serial with the factory held at the 1/1/1 size gives T(R,E)/T(1,1,1) = (E·W_PA(R) + W_ms(R)) / (W_PA(1) + W_ms(1)), so R shows up as time. The anchor model (§4.1) sizes the factory to R, so R shows up as machines and T doesn't move. These are two readings of one trade; neither is chosen. Example, ph4 at 1.25R, E=1: 2.46x time on a fixed factory, against the §5 machine ratios on an anchored one.
- RESOLVED D21 — **MAM: pickups as hand-supplied.**
- RESOLVED (O8 clarified, 2026-10-26) — **MAM: O8 tension.** O8 says only one MAM node needs an item that can't be picked up off the ground. In the data, 77 of the 100 active nodes cost at least one manufactured part (SAM Fluctuator, Quickwire, Crystal Oscillator, ...). Either O8 means something narrower (each tree's entry node?) or the reading here is wrong. Unresolved.
- RESOLVED D22 — **MAM: phase-1 front-loading.** Earliest-producible puts 53 nodes in phase 1 (Caterium, Quartz and Sulfur open at tier 0 miners). MAM becomes 70% of phase 1's work. "Defer" is a profile setting (D10, D5); there's no default.
- RESOLVED D23 (for now) — **MAM: equipment as a research COST.** Greg (2026-10-26): building equipment for the player's own use stays out. Still open: six MAM nodes CONSUME equipment as their unlock cost — Nobelisk ×10/100/200/500, Spiked Rebar ×10/150/200, Rifle Cartridge ×500/1000, Object Scanner ×1. Those are spent to unlock, so they are part of the MAM bill like any part. Equipment Workshop recipes are not in the reference layer; currently unpriced and named.
- RESOLVED D24 — **Power-plant machines in the work multiplier?** §5.5 counts generators separately. The machines and extractors that make generator fuel (and pump its water) aren't in W (§5.2), so P never raises the work multiplier. If D13 (machine count is build effort) should include the power plant, P enters W too.
- RESOLVED D25 — **Generator display.** Every open generator is reported and none is chosen (layers report). Should the display show the set, or the cheapest per phase under a declared rule?
- **Super-linear E (and R).** Node caps / purity mix via `solve_portfolio` stage 1 is the measurable source of decreasing returns (§4.4). Ceiling measured 2026-10-26 (§5.10); the rising cost below it (stage 3 at a swept fixed scale) is not measured. Whether it is worth measuring depends on the display choice (next action 3).
- **Node ceiling scope.** Every default socket is in one site. A start-area or reachable-socket version (the whole-world idea's start biomes) would lower k; not built. Shards, somersloops and augmenters stay out of "default".
- **Idea (Greg, 2026-10-26; not adopted): power mix.** Unlocking Fuel doesn't stop coal production, so a later version could model a mix of sources per phase rather than D27's sole-source rows.
- **Contradiction to settle before promotion: record §3.3.** §3.3 says scenarios "may be described, never priced against each other". This tool prices every scenario against 1/1/1 (D11). D15 squared the Pareto front with §3.3's no-ordering line, but not with the no-pricing line. The likely reading is that a per-axis multiplier against a fixed reference, never ranking two non-reference scenarios, is description. That needs a forward amendment to the record saying so. Greg's call.
