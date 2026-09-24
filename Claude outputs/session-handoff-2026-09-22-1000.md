# Progression Optimizer — handoff, 2026-09-22 10:00

    written   2026-09-22 10:00 Phoenix, after the push at 09:59:32
    this file is the CURRENT handoff — the one with the newest timestamp in its
    name always is. Supersedes 2026-09-22 07:17 and every handoff before it.
    It is SELF-CONTAINED: nothing below defers to a superseded file.
    a revision is a NEW FILE; once written, a handoff is never edited.
    Superseded handoffs are kept as the trail and are not read.

## How this document works

**The entry bar**, and it applies to whoever writes the next one:

    WRITE IT LAST  after the commit AND after the push, then read `.git`
                   and record what is actually there. A handoff written before
                   the push states a HEAD that may not survive — the push can
                   fail, the commit can be amended — so its State section is a
                   prediction wearing a measurement's clothes
    NEXT ACTIONS   at most five, ranked, each saying what it unblocks. If a
                   sixth matters more than one of the five, it replaces it
    A DEFECT       enters only if it has a CONSUMER — code that would read it,
                   or a decision it would change. Otherwise it stays recorded
                   where it was found and is not repeated here
    A FINDING      enters only if it changes what happens next
    PROCESS NOTES  the rule, plus at most two instances. No running tally
    REFERENCE      everything below the fold. Nobody should need to read it to
                   know what to do next
    SELF-CONTAINED a handoff that defers its next actions to a superseded
                   handoff is not one. Restate, do not cross-reference
    TARGET         two minutes to read, top to fold

**Quote a measured figure only as measured on a date, never as a prediction plus
a delta.** Every figure below names its machine and its time.

---

## Next actions

The 07:17 list is discharged except its actions 4 and 5, which are below
unchanged in substance. What replaces the top is new: everything built today is
GREEN AND UNCONSUMED, and wiring it is what turns fifteen commits into a number.

**1. Wire a bill to a declaration, end to end.** `progression.stock.bill_for`
emits `WithdrawalBill` per item; `BusDeclaration.withdrawal_bill` accepts one;
**nothing joins them.** No `ProjectedCoverage` has ever been computed from a
real bill — every figure on the record came from a hand-built fixture.

    unblocks   the first real T_bootstrap. The whole stock-basis chain is
               asserted end to end in tests and has never run on a solve
    caution    this is where P30's known limitation bites. Two buses on one
               recipe are refused whatever their provenance, so a build-material
               line for an item the solve ALSO produces on the same recipe
               cannot be declared alongside it. Concrete and Cable are the
               likely first casualties
    shape      the caller is the joint. `stock` may not import `realization`
               beyond `.contracts`, and `realization` may not import
               `progression` at all — both asserted

**2. Recompute A3.5 under a USAGE basis.** Unchanged since 07:17 and still
unblocked: A5.2 settles that average draw is usage in every state, so this is no
longer a choice between amendments. A5.3 predicts the table will be materially
smaller than 27 machines on the PRODUCTION rows, not only on the build lines.
Two rows of arithmetic are on the record; the cascade is not.

    tool       `tools/busmodel`, which computes it and cannot import the code
               it checks
    caution    A3.5 is still not a regression target — its withdrawal column
               sits inside the demand sum on two rows and outside it on four

**3. Demote `presents_peak_draw` to a report mode.** A5.2 removes its reason to
exist as a SIZING switch. `SizingBasis.PEAK` still answers a real question —
what a refill transient costs the production consumers sharing a source bus,
since splitters round-robin and do not prioritise — so this is a change of role,
not a deletion. Unchanged since 07:17.

**4. Read the Project Assembly multiplier's rounding, in game.** One glance, no
construction. `apply_project_assembly_quantity` multiplies and does not round,
which is the adapter's existing method and was followed rather than improved.
At 1.25x phase 1's 50 Smart Plating lands on **62.5** — exactly a tie — and the
rounding rule for THIS multiplier has never been observed. The recipe-input rule
was probed before it was locked; this one was not.

    probe      set the Project Assembly requirement multiplier to 1.25, read
               phase 1's Smart Plating requirement. 62 or 63 settles it
    unblocks   nothing today. It moves a figure from method-followed to
               observed, which is the cheapest epistemic upgrade on the list

**5. Correct the Smelter line in the decomposition note.** See finding 1. It is
a design note — current-state and replaceable by its own header — so it is
correctable in place or here, and does not need an amendment.

## State

    tests     638 pass, 0 fail — full suite, GREG'S MACHINE, 2026-09-22.
              This SUPERSEDES the 554 figure of 07:17
    reconciles  554 + 84 = 638. Not reconciled term by term this time: four
              commits added tests and the per-commit counts were predicted
              rather than collected. See process note 2
    HEAD      c46df350 "Regenerate manifests: unlock cost and Project Assembly",
              2026-09-22 09:59:29 Phoenix
    pushed    origin/master = c46df350, 09:59:32. Local and remote AGREE
    source    .git/logs/HEAD and .git/logs/refs/remotes/origin/master, read
              directly at 10:00. Not inferred from a prior handoff
    tree      fifteen commits landed today after 47486904. NO `COMMIT_MSG_*.txt`
              remain at the repo root — directory listing at 10:00. The 07:17
              handoff's five stale drafts are gone
    manifest  REPO_MANIFEST.csv mtime 09:59:29, the same second as the manifest
              commit, so it was written AFTER the commits it covers rather than
              before. `--check` was in every command block; its OUTPUT was not
              read back into this session, so "in sync" is intended-by-procedure
              and not measured here
    phases    2 IN PROGRESS. Phase 3, 4 and 5 NOT STARTED

**A second machine can now run part of the suite.** The realization subset,
the adapter tests and the progression tests run in an agent container with
only the sources and the reference CSVs staged — no scipy, no numpy. 332 of
them, 2026-09-22. That is not the full suite and does not replace
`uv run pytest` on Greg's machine, but it gives a red/green loop where there
was none, and every mutation result quoted today came from it.

## Findings

**1. The build-recipe name convention is wrong on two of eleven producers, and
they are swapped with each other.**

    Recipe_SmelterBasicMk1_C   builds   Desc_SmelterMk1_C    the SMELTER
    Recipe_SmelterMk1_C        builds   Desc_FoundryMk1_C    the FOUNDRY

`Build_X_C -> Recipe_X_C` does not fail on these — `Recipe_SmelterMk1_C` EXISTS,
so a naive join succeeds and charges every Smelter the Foundry's 20 Concrete +
10 Modular Frame + 10 Rotor instead of its own 5 Iron Rod + 8 Wire. A silent
wrong answer in every bill that would have been built on it, landing on Concrete
— the term the decomposition already calls the loosest floor.

`Build_X_C -> Desc_X_C -> building_recipes.building_class` is the join, 11 of
11, asserted by test with the naive mapping asserted WRONG on those two by name.

**The record carries the mislabel.** `build-material-bill-decomposition-2026-09-21.md`
quotes `Recipe_SmelterMk1_C — 20 Concrete, 10 Modular Frame, 10 Rotor` under a
line reading "Smelter". That is the Foundry. Next action 5.

**2. A commit message on the record describes a change that is not in the
commit.** `391ff88c` says "tests/conftest.py gains the realization src tree on
sys.path". It does not. The edit was written by a script that died on an earlier
line and the failure was not read before the file was shipped.

The suite was green throughout, and that is the part that matters:
`tests/test_progression_stock.py` imports `realization.contracts`, and on a full
run `tools/realization/tests/conftest.py` puts that tree on `sys.path` during
collection. The import succeeded because ANOTHER package's conftest ran first.
`pytest tests/` alone did not collect.

Fixed forward in `270f5cc7`, which names `391ff88c` in its subject. The prior
commit is not rewritten.

**3. The parked tier question was already answered, and nobody had looked.**
"Whether `unlocks.py` or `progression_clusters.csv` resolves a capability to a
numeric tier" stood open across four handoffs carrying the note THAT STORE HAS
NOT BEEN READ. `schematics.csv` carries `tech_tier` as an integer column and
`unlocks.py` has filtered on it since it was written. The item cost one read and
had been deferred four times.

## Process notes

**Read the exit status of the script that wrote the file, before shipping the
file.** Finding 2 is the instance: a heredoc died partway, one of its two edits
landed, and the unshipped half was described in a commit message as done. The
generalisation of the 2026-09-21 staged-directory failure — that one measured
the wrong population, this one reported an edit that never ran. Both look like
confident completeness from the outside.

**Do not quote a count you did not collect.** Predicted 632, the suite returned
638. Cause: `@parametrize` cases counted as one test each, which is the SAME
error as the 550/554 miss recorded on 2026-09-21. Recorded twice now; the fix is
to stop predicting suite counts, or to collect them.

---
---

# Reference

Nothing below is needed to know what to do next.

## What landed today, after 47486904

    7decff1e  07:37  Realization: BusDeclaration carries a recipe_id (P30)
    dc4543e6  07:37  Realization: test the declared-recipe path, mutation-checked
    45bf41a7  07:37  Regenerate manifests: P30 contract, body and tests
    391ff88c  08:28  Realization: the coverage criterion takes a stock basis (§6)
    f0f2f9f2  08:28  Realization: test the bill and the projected coverage
    d84f1939  08:28  Regenerate manifests: the stock-basis coverage criterion
    21b9caff  09:05  Adapter: load Build Gun construction costs, joined through
                     the building class
    1aef6fa0  09:05  Realization: a bill declares which terms it carries
    a921e649  09:05  Regenerate manifests: construction costs and bill terms
    b5edd931  09:16  Progression: the stock pass, canonical half
    b045ccd6  09:16  Progression: assert the import boundary this package never had
    0adaa7b7  09:16  Regenerate manifests: the stock pass and the progression boundary
    270f5cc7  09:59  tests: put the realization src tree on sys.path, as 391ff88
                     claimed it did
    a491082c  09:59  Progression: resolve a tier to its schematics and read costs
    cc355459  09:59  Progression: the stock pass sums UNLOCK_COST and PROJECT_ASSEMBLY
    c46df350  09:59  Regenerate manifests: unlock cost and Project Assembly

## The stock-basis criterion, in one paragraph

`Coverage` compares two RATES and answers with a boolean. That shape does not
survive `DERIVED_WHOLE_GAME_FLOOR`, because a whole-game bill is a STOCK and
converting it to a rate needs a horizon §9 forbids. **Both sides change shape:**
the declaration carries a quantity (`WithdrawalBill`) and the verdict carries
durations (`ProjectedCoverage`), `T = bill / R`, twice. **No boolean** — T is
finite whenever R > 0, so `covers` would be trivially true, and making it mean
something needs a tier horizon this layer may not hold. §8.1: of two
constructions differing only in whether the tool acquires an opinion, take the
one without. `Coverage` is untouched, so every GEOMETRIC_FLOOR verdict already
written keeps meaning what it meant — forward-only applied to a type.

**The split** is at what must exist BEFORE the next tier's chain can run:
bootstrap (the declared minimum MACHINE set — coal power is at least 1 coal
generator, 1 water extractor, 1 miner and the infrastructure between them; steel
at least 2 miners, 1 foundry, 2 constructors, 2 storage) and remainder. Both
halves are floors twice over: the sets are stated as minimums, and the
"infrastructure" in each is the spatial term, absent until phase 5.

**Dropping the boolean dissolved a dependency.** Coverage was going to need the
goal set, and `realize` takes none — so action 2 looked blocked on the signature
patch. Without a horizon it needs no goals, and the signature gap goes back to
being a standalone item.

## The bill's five terms, and which are summed

    MACHINE_CONSTRUCTION   summed. building_recipe_io.csv x settled counts
    BOOTSTRAP_SET          summed. The same arithmetic over a DECLARED set
    UNLOCK_COST            summed when a schematic set is given. Cumulative
                           through the tier, not incremental, and NOT "what
                           you still owe" — the difference is what the player
                           already bought, which is state this layer does not
                           hold
    PROJECT_ASSEMBLY       summed when phases are given. PHASES ARE DECLARED:
                           `delivery_unlocks` is prose ("Tiers 3 and 4",
                           "Project Assembly launch") and parsing English into
                           a tier mapping would be inventing one
    SPATIAL                never summed. Phase 5 owns the bounds, and its
                           absence is what keeps the bill a floor

`terms` reports what THAT CALL consulted, not what the module can consult, and
not what came out non-zero. Each optional pair is given together or not at all;
a half-supplied pair is refused, because a schematic set with no cost table sums
to zero and would be reported as the term COUNTED.

Both new terms land in the REMAINDER. The bootstrap half is "the initial
machines needed to start the next tier" as declared, and that is machines.

**Worked, tier 3 plus phase 1 at 1x, container 2026-09-22:** 3720 Wire, 2055
Iron Plate, 1775 Iron Rod, 1480 Concrete, 1300 Iron Screw, 1280 Cable. Three
unresolved rows named.

## Guardrails

Nine structural tripwires, plus the four candidates. **Three now have sites; the
fourth still does not.**

    _demand_oracle              AmbiguousDemand — cannot choose a recipe
    _fixed_recipe_expectations  takes a multiplier map it cannot compute
    _balance_check              verifies an answer it cannot produce
    lp_backend                  imports nothing that knows about progression
    analysis                    no ranking surface at all
    progression.unlocks         never walks schematic_dependencies; a filter
    demand expansion            may not select its own scope
    sink relation               reported as a duration, never a machine ceiling
    alternates                  never sorted

    no stateless residual   TEST
    matched needs a rate    TEST (P29)
    coverage names a basis  TEST, over two bases AND over a term set
    partition coverage      TEST
    no single-scale delta   STILL NO SITE. Phase 3 has not started

**The stock pass cannot derive a machine count.** `machines` is a parameter, and
a test asserts the signature. A module holding per-building costs, settled counts
and tier unlocks at once is enough to plausibly answer "what should I build
next", which is a broader and more authoritative question than "what does this
bill come to". The drift would arrive as one convenient extra return value.

**`progression` has an import tripwire as of today.** It never had one — the
downward rule was a docstring. Four assertions beyond the scan: the module set
is named by hand (the staged-directory failure, guarded again); only `stock.py`
may touch `realization.contracts`; `__init__` must not eagerly import `stock`;
and nothing in `production_adapter` imports upward, because a one-way rule
checked in one direction is checked in half.

    PERMITTED   production_adapter, .contracts, .gamedata, .scenario
                realization.contracts   the bill TYPES only
    FORBIDDEN   production_adapter.backend, .lp_backend, .analysis
                realization.buses, .residual, .realize, .capabilities
                scipy, at any depth

The realization layer's and the oracle's tripwires are unchanged.

## Defects with a consumer

    two buses on one recipe are refused, whatever their provenance. LIVE
      consumer  next action 1. A build-material line for an item the solve ALSO
                produces on the same recipe cannot be declared alongside it.
                `_check_partition`'s recipe -> bus map collapses. Closing it
                needs bus identity beyond (item, sources, recipe)

    the Project Assembly multiplier's rounding is unobserved. LIVE
      consumer  every scaled delivery quantity. 1.25x on phase 1 lands on a
                tie. Next action 4

    the delivery table has no item_id and is joined by DISPLAY NAME.
      consumer  every PROJECT_ASSEMBLY figure. Safe by MEASUREMENT — items.csv
                has no duplicate display name today and all fifteen rows
                resolve — so the loader REFUSES a name matching zero or more
                than one rather than resting on it. A test doctors the
                reference layer to keep that guard load-bearing

    idle power draw is assumed ~0, unverified against the reference layer.
      consumer  every MATCHED-vs-BACK_UP gap, and A5.2's claim that the states
                differ in power but not in average draw

    _demand_oracle credits no byproducts.
      consumer  surfaced as CreditedFlowCycle and refused by name. LIVE

    power_at_clock cannot reach a variable-power producer's draw.
      consumer  Converter, Particle Accelerator, Quantum Encoder carry
                base_power_mw = 0; the real draw is a per-recipe range on
                Recipe.power the signature cannot reach

    28 items are referenced by recipes and absent from items.csv.
      consumer  `machines_per_lane` refuses by name. Pinned by a test that
                deletes itself when the data closes the gap

    the Portable Miner and the Sink Coupon are build/unlock costs absent from
    items.csv.
      consumer  every bill containing a miner or an AWESOME Sink unlock. Both
                REPORTED in `StockPass.unresolved` and named, per respec §10.4's
                own verdict, through one rule with no special case

    `realize` takes no goals, so `RealizationReport.projections` is ALWAYS empty
    from it.
      consumer  `project_goals` is the surface. "Realize was given no goals",
                never "no goal completes". NOT on the critical path any more —
                the no-boolean decision removed the coupling

## Parked

    §10.4    Portable Miner — whether to recurse the outflow bill into workshop
             recipes. §8.1's shape was taken instead: report and name
    §19.4    MAM pool-dilution advisory. Phase 4
    §16.5    Do the other §11 alternates hide pairs?
    open     AWESOME Sink. NARROWED by A4.2 — gates only disposal of a genuine
             overflow
    §6       Somersloop absent and unscoped
    §17.6    Transport above a belt is not modelled
    §15.7    A second Phase 4/5 chain through the Quantum Encoder or Converter
    §18.7    Declaration ergonomics — research-node-level declaration
    §7.5     `canonical_mw`: re-evaluate or re-solve. Changes no emitted number
    F2       Fork delta gates the cardinality tie-break and the complexity weight
    open     Determinism is asserted within one scipy version only
    P28      Rename `Disposition` to `SteadyState`. NOT TAKEN
    spec     `ClockCause.FULL` is commented "at 100%" but a BACK_UP bus whose
             demand equals its supply gets (100.0, BACKPRESSURE)
    spec     `ClockDistribution.SPLIT` past the ceil yields a 0% machine
    game     Observe a fluid recipe at 1.25x and read the UNIT — m3 or mL

    CLOSED today: whether anything resolves a capability to a numeric tier.
    `schematics.csv` carries `tech_tier`; `unlocks.py` has always filtered on it

## Test hygiene

**Test file basenames must stay unique across `testpaths`.** No test directory
carries an `__init__.py`, so pytest imports each module under its bare basename
and two files with one name error the WHOLE collection. Two modules were added
under `tests/` today — `test_progression_stock.py` and
`test_progression_import_boundary.py` — and were checked against all four
directories before landing.

**A conftest must not depend on another conftest having run.** New, from
finding 2. `tests/conftest.py` now puts the realization src tree on `sys.path`
itself. Checked by running `pytest tests` and
`pytest tests/test_progression_stock.py` each on their own.

## Phases

    0  solver selection              COMPLETE, amended at §10
    1  data boundary + adapter       COMPLETE, 2026-09-19
    2  demand expansion + site cap   IN PROGRESS. Realization bodies committed
                                     2026-09-22. The stock-basis criterion and
                                     the stock pass landed the same day and are
                                     NOT YET WIRED TO EACH OTHER
    3  alternate-recipe optimization NOT STARTED. Gated by the set-valued
                                     valuation problem at LP §16.2 / §19.5
    4  run-state / progression       NOT STARTED. Owns the MAM advisory
    5  world integration             NOT STARTED. Owns spatial realization, and
                                     the bill's SPATIAL term

## Related

    repo     docs/decisions/bus_level_recompute_and_alternate_crossover.md
                  + a1..a5
    repo     docs/decisions/bus_allocation_backpressure_and_residual.md
                  §1 contradicted; §§5, 8, 10 superseded
    repo     docs/decisions/toggle_propagation_and_demand_pass.md
    repo     docs/decisions/{demand_expansion_scope_and_site_capacity,
                  production_lp_formulation, production_solver_selection,
                  production_building_power_model, resource_authority,
                  extraction_wiring_and_provenance_stamp}.md
    repo     docs/plans/progression_optimizer_implementation_plan.md
    repo     tools/busmodel/README.md
    project  build-material-bill-decomposition-2026-09-21.md   what the floor is
                  made of. CARRIES A MISLABELLED SMELTER LINE — finding 1
    project  busmodel-oracle-2026-09-21.md
    project  output-contract-respec-2026-09-21.md   governing spec.
                  §§4.5, 4.6, 5, 7.2 superseded
    project  contracts-delta-open-item-1-2026-09-21.md        the audit
    project  contracts-patch-set-open-item-1-2026-09-21.md    P1-P21, applied
    project  contracts-patch-addendum-open-item-1-2026-09-21.md
                  P22-P27 applied; P29 applied; P28 not taken; P30 applied
                  2026-09-22
    project  storage-model-bundle-review-2026-09-21.md   rev 4
    project  phase-2-rounding-in-the-transform-layer-2026-09-21.md
    project  pathing/backlog-verify-and-coordinate-pathing.md   separate track
