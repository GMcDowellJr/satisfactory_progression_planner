# Production LP Formulation — Decision Record

- Date: 2026-09-18
- Scope: the LP model behind `production_adapter.backend.Backend`. Open item 1 of the
  2026-09-18 session handoff; discharges the three risks named in section 10 of
  `docs/decisions/production_solver_selection.md`.
- Supersedes nothing. Section 10 of the solver-selection record named these risks and
  deliberately did not resolve them; this record resolves them forward.
- Read against: `tools/production_adapter/src/production_adapter/` at mtime
  2026-09-18T06:01:50Z, `tests/_demand_oracle.py`, and the reference layer as of the
  same date.
- No code was written. No repository code was modified.

## State

    decision_status: RECOMMENDED — awaiting Greg's acceptance
    locked:          nothing in this record yet
    open:            D1 unconsumed output, D2 power statistic, D3 tie-breaking,
                     D4 cycles, D5 extraction scope
    pending_clarification: P5 — no AWESOME Sink or generator exists anywhere in the
                     reference layer (verified 2026-09-18, grep across
                     planning_data/game/reference/*.csv). D1's recommended option
                     cannot be implemented until that data exists.

---

## 1. Terminology, first, because the words are doing damage

"Surplus" is the word Candidate A uses and the word section 10 inherited. It reads as
storage — a buffer that fills — and that is not what it denotes. Retired here.

    unconsumed output   net production of an item that no enabled recipe consumes and
                        that is not a requested target. A quantity, per item, per minute.
    disposal            the modelled path by which unconsumed output leaves the system.
    slack               the LP-mechanical term for the same quantity, used only when
                        discussing the constraint algebra.

The distinction matters because unconsumed output is not inert. In game it has exactly
three fates: it backs up and stalls its producer, it is consumed by an AWESOME Sink, or
it is burned in a generator. A model that ignores all three is not modelling a factory.

## 2. D1 — unconsumed output

### 2.1 The three options are three different questions

This is not a choice of default. Each option answers a different question, and the
answers are not interchangeable.

    forbid    production == consumption for every non-target item.
              Question answered: "give me a factory that runs at steady state with
              nothing backing up anywhere."
    free      production >= consumption, no cost on the difference.
              Question answered: "give me the cheapest way to hit the target; I will
              deal with the leftovers myself."
    disposal  production == consumption, where disposal is itself a recipe that
              consumes the leftover at a real rate and a real power draw.
              Question answered: "what does this target actually cost me, including
              getting rid of what I do not want."

### 2.2 Why `forbid` is not obviously wrong

It is the physically accurate model of a steady-state factory. A factory with
unconsumed byproduct is not at steady state: the belt backs up, the producer stalls,
and real throughput falls below what the LP reports. Under `free`, a solution carrying
unconsumed output has machine counts and power figures that describe a factory that
cannot actually run at those numbers. `forbid` refuses to return that solution at all,
which is information rather than a limitation.

Its cost is concrete: any multi-output recipe whose byproduct has no enabled consumer
makes the problem infeasible. Plastic's base recipe emits Heavy Oil Residue; with no
enabled HOR consumer, a Plastic target under `forbid` has no solution. Section 3.2 of
the solver-selection record ran exactly that case and got an answer only because
Candidate A sinks leftovers by construction.

### 2.3 Why `free` is not obviously wrong either

It matches how the game is actually played early on — leftovers do just back up, or go
to a Sink, and the player does not model it. It is the smallest constraint set and adds
no variables.

Its costs are three: reported power and machine counts describe an unrunnable factory
(above); the solver has no reason to avoid producing large unconsumed quantities when
doing so is incidentally cheaper; and combined with D4, costless leftovers are what
makes spurious cycles attractive rather than merely possible.

### 2.4 Greg's reading of "price it", corrected in one respect

The question asked was whether pricing means increasing consumption and power. There
are two mechanisms and only one of them does that.

    (a) objective penalty    add lambda * unconsumed to the objective.
                             Discourages leftovers. Does NOT increase consumption or
                             power. lambda has no physical referent, and the reported
                             PowerReport and MachineCount still describe a factory with
                             no disposal in it. The response is quietly wrong in the
                             same way `free` is, plus an arbitrary constant.
    (b) disposal recipes     add a per-item disposal activity with a real throughput
                             and a real power draw. Leftovers are consumed by something
                             that exists. Power goes up. Machine count goes up.
                             Nothing arbitrary is introduced.

(b) is what the question was reaching for, and it is the right one. (a) is rejected.

### 2.5 The contract already has an opinion

Two pieces of evidence from `contracts.py`, which was written before this question was
asked and therefore did not beg it:

- `ItemFlow` carries `produced_per_min` and `consumed_per_min` separately and exposes
  `net_per_min` as a derived property. Under `forbid`, `net_per_min` is identically zero
  for every non-target item and the field is dead weight. The contract anticipates
  non-zero net.
- `Weights` has exactly four fields — `resources`, `power`, `buildings`, `complexity` —
  and no leftover-penalty term. Option (a) would require adding one, which is a contract
  change. Option (b) requires none: disposal power lands in `power`, disposal machines
  land in `buildings`, and the items consumed land in the existing balance.

The contract can express `disposal` and `free` without modification. It cannot express
(a) without modification.

### 2.6 Recommendation

**`disposal` as the default, `free` and `forbid` available as request-level modes.**
The progression optimizer's entire purpose is comparing the true cost of alternatives —
build now vs later, alternate recipe vs base. A cost that omits disposal is the wrong
number for that comparison, and it is wrong in a direction that systematically favours
byproduct-heavy recipes.

`forbid` stays reachable because "can this run at steady state with nothing sunk" is a
real question a player asks. `free` stays reachable because it is the cheapest lower
bound and useful as a sanity floor.

### 2.7 What blocks it

**P5, verified 2026-09-18**: `planning_data/game/reference/` contains no AWESOME Sink
and no generator. A case-insensitive grep for `sink`, `generator` and `ResourceSink`
across every CSV in that directory returns nothing. `production_buildings.csv` holds
exactly the eleven manufacturing classes; `extraction_buildings.csv` holds seven
extractors; `buildings.csv` is the older Desc_*-keyed crosswalk and stops at the Space
Elevator.

Disposal cannot be modelled from data that does not exist. Needed, at minimum:

    Build_ResourceSink_C      power draw, and items-per-minute throughput
    fuel generators           per-fuel burn rate and power output, if burning leftover
                              fuels is to count as disposal rather than as a cost

Until P5 lands, the implementable default is `free` with every leftover reported
explicitly in `SolveResponse.warnings`, so that the gap between the reported factory and
a runnable one is visible rather than silent. That is a stopgap, recorded as one.

## 3. D2 — which power statistic the objective minimises

`README.md` in the adapter package flags this and does not settle it: "A minimum-power
objective sees the Quantum Encoder's floor of 0 MW; decide which statistic you are
optimising before Phase 3."

The three variable-power producers — Converter, Particle Accelerator, Quantum Encoder —
carry `base_power_mw = 0` and a per-recipe `PowerRange`. An objective built on `min_mw`
treats every Quantum Encoder recipe as free power and will select them preferentially
and wrongly.

Recommendation: **the objective minimises `PowerRange.mean_mw`**, and `PowerReport`
continues to carry `min_mw` and `max_mw` untouched for the caller. Rationale: the mean
is the only statistic that is neither systematically optimistic nor systematically
pessimistic across the mixed fixed/variable set, and fixed-power producers have
`min == max == mean`, so nothing changes for the other eight classes.

This is a recommendation with a real alternative: `max_mw` is the right statistic if the
downstream question is grid sizing rather than running cost. If Phase 3 turns out to be
about power infrastructure, revisit — forward, in a new record.

## 4. D3 — degenerate optima and tie-breaking

Ties between equivalent recipe sets are broken arbitrarily by the simplex, and the
arbitrary choice is not stable across scipy versions, platform, or trivial input
reordering. Results that churn between runs are worse than results that are slightly
suboptimal, because the progression layer compares solutions to each other.

Recommendation, in order:

1. **Deterministic input ordering.** Recipe variables are built in sorted `recipe_id`
   order, items in sorted `item_id` order. Costs nothing, removes the largest source of
   run-to-run variation.
2. **A lexicographic tie-break, not a random one.** Where the objective ties, prefer
   fewer distinct recipes, then fewer total machine equivalents, then the
   lexicographically smaller sorted recipe-id tuple. The last is arbitrary but it is
   *stably* arbitrary, which is the property actually wanted.
3. **Report it.** When a tie is detected and broken, say so in
   `SolveResponse.warnings`. A silently-broken tie is the kind of thing that makes two
   progression runs disagree for no visible reason.

Explicitly not recommended: perturbing costs by a small epsilon to break ties. It works,
and it makes the objective value meaningless at the margin, which matters when the
progression layer is comparing objective values across scenarios.

## 5. D4 — cycles

Packager and unpackager form exact inverse pairs; refinery loops can too. Under `free`,
a cycle that produces a costless leftover can be run at any scale without penalty, and
under any formulation a numerically-neutral cycle can be run arbitrarily.

Three mitigations, in the order they should be applied:

1. **Every recipe activity carries a strictly positive cost.** With `buildings` weight
   at its default 1.0 and machine equivalents in the objective, no activity is free,
   which makes an unbounded cycle strictly worse than not running it. This alone
   removes the unbounded case.
2. **Bound every activity.** An explicit upper bound on each recipe variable turns an
   unbounded ray into a reported infeasibility or a bounded answer rather than a solver
   hang. The bound should be generous enough to never bind in practice and recorded in
   `warnings` when it does bind.
3. **Detect, do not forbid.** Packager/unpackager pairs are legitimate — fluids do get
   packaged for transport. The formulation should not prohibit the pair; it should
   report when both directions of an inverse pair are active at once, which is the
   signature of a spurious cycle rather than a real one.

## 6. D5 — extraction is outside the LP

Stated because the current code implies it and no record says it.

`gamedata.load()` reads `production_buildings.csv`, `recipe_variable_power.csv`,
`recipe_producers.csv`, `recipe_io.csv`, `recipes.csv` and `items.csv`. It does not read
`extraction_buildings.csv`, `extraction_rates.csv` or `resource_extraction_map.csv`,
all three of which exist. `RawInput` carries an item id and a rate and nothing else.

So raw resources enter the model at the boundary, free of extraction machinery, and
`PowerReport` therefore **excludes extraction power**. This is a defensible scope line —
extraction power depends on node purity and miner tier, which are world-placement facts
belonging to the Phase 5 world layer, not to a production solve.

It has one consequence worth writing down: the section 3 figures in the solver-selection
record include extraction power (Iron Plate 20/min reported 9.63 MW = 4 MW Constructor +
0 MW Smelter + 5.63 MW extraction). Those figures are therefore not directly comparable
to this backend's output even setting aside the power-data bias already recorded against
them in the session handoff. Compare raw-material columns and machine counts; do not
compare power totals at all.

Recommendation: keep extraction outside, and have `SolveResponse.warnings` state that
power excludes extraction, once per solve, so the omission is never inferred from silence.

## 7. The formulation

Given the decisions above at their recommended settings.

### 7.1 Sets

    R     enabled recipes, per SolveRequest.allowed_recipes, sorted by recipe_id
    I     items appearing as an input or output of any r in R, sorted by item_id
    I_raw I intersected with ReferenceData.resource_items
    T     requested output targets, item -> rate_per_min
    D     disposable items (D1 = disposal); empty until P5 lands

### 7.2 Variables

    x[r]  >= 0   machine equivalents of recipe r at 100% clock, continuous
    s[i]  >= 0   raw draw of item i in I_raw, continuous
    d[i]  >= 0   disposal activity for item i in D, continuous
                 (under D1 = free, d is replaced by an unbounded slack with zero cost;
                  under D1 = forbid, d is absent and the balance is an equality)

Machine equivalents are fractional throughout. `contracts.py` is explicit that rounding
is a presentation concern applied by the caller, and `MachineCount` carries both
`effective_count` and `physical_count_if_rounded` for that reason.

### 7.3 Constraints

Per-item balance, for every i in I:

    sum over r of out[r][i] * x[r]
      + s[i]                          (i in I_raw only)
      - sum over r of in[r][i] * x[r]
      - disposal_rate[i] * d[i]       (i in D only)
      == T[i]                         (target rate, or 0 if not a target)

where `in[r][i]` and `out[r][i]` are per-minute rates at 100% clock, taken from
`Recipe.inputs` and `Recipe.outputs` *after* `Recipe.scaled(scenario)` has been applied.
The input multiplier is already baked in at that point; the LP must not apply it again.

Raw caps, for each cap in `SolveRequest.resource_caps` with a non-null rate:

    s[i] <= cap[i]

Activity bounds, per D4:

    x[r] <= X_MAX

### 7.4 Objective

Minimise:

    w_resources * sum over i in I_raw of s[i]
  + w_power     * sum over r of mean_power[r] * x[r]
  + w_buildings * sum over r of x[r]
  + w_power     * sum over i in D of disposal_power[i] * d[i]
  + w_buildings * sum over i in D of d[i]

with `mean_power[r] = Recipe.power.mean_mw` per D2, already scenario-scaled by
`PowerRange.scaled()`. `w_complexity` does not appear: `Weights.__post_init__` raises on
any non-zero value, and the MIP that would justify it is fork delta F2, which does not
transfer to a scipy backend as a constraint — `scipy.optimize.milp` takes `time_limit`
as an ordinary parameter. Lifting F2 is a separate decision and a separate record.

Note the raw-resource term sums unweighted physical rates across dissimilar resources,
so one unit of Uranium costs the same as one unit of Iron Ore. That is Candidate A's
behaviour and it is almost certainly wrong for progression purposes, but changing it
means introducing per-resource scarcity weights, which is a Phase 3 valuation question
and not this record's to settle. Recorded so it is not mistaken for an oversight.

### 7.5 Response construction

    x[r] > tolerance          -> RecipeUse(recipe_id, producer_class,
                                           machine_equivalents=x[r],
                                           cycles_per_min=60/duration_sec * x[r])
    per-item produced/consumed -> ItemFlow; net_per_min non-zero only where D1 allows
    s[i] > tolerance          -> RawInput
    per producer_class        -> MachineCount, effective = sum of x[r] for that class,
                                 physical_count_if_rounded = ceil(effective)
    power                     -> PowerReport(canonical_mw from a second transform at
                                 Scenario(), scenario_mw from this one, min_mw and
                                 max_mw summed from the per-recipe ranges)

`canonical_mw` requires solving twice, or — cheaper and equivalent — evaluating the
canonical power of the *same* recipe mix. The two differ when the scenario changes which
recipes are selected. The second is what the contract's wording implies ("two transforms
of the same canonical facts"); the first is what a caller comparing scenarios probably
wants. Flagged as open; not decided here.

## 8. Validation

Ordered, and the first two gate the rest.

1. **Against `tests/_demand_oracle.py`**, base recipes only, on targets where the oracle
   does not raise `AmbiguousDemand`. Machine equivalents must match to four decimal
   places. This is the arithmetic check and it is independent of every decision above.
2. **Against section 3.3 of the solver-selection record**, Smart Plating 1/min: seven
   recipes, Iron Ore 23.25/min, the exact multipliers listed there. This is the one
   figure in section 3 that survives the caveat recorded in the session handoff.
3. **Raw-material columns only** from section 3.2 for the remaining fixed-recipe cases.
   Not power, not the section 3.4 or 3.5 selections — see the session handoff's open
   item 2.
4. **Degeneracy**: solve the same request twice with recipe order shuffled; the response
   must be identical. This is the test that makes D3 real rather than aspirational.
5. **Cycles**: a target reachable through a packager/unpackager pair must not activate
   both directions.

## 9. Open, carried forward

- P5, the missing sink and generator data. D1's recommendation is blocked on it.
- Whether `canonical_mw` re-solves or re-evaluates (7.5).
- Per-resource scarcity weighting (7.4). Phase 3.
- Whether `forbid` and `free` are exposed on `SolveRequest` — which is a contract change
  — or selected by the backend constructor, which is not. Leaning toward the latter until
  there is a caller that needs it per-request.

---

## 10. Amendment, 2026-09-18 — demand, not disposal

Three corrections from Greg, the first of which reframes D1 rather than adjusting it.

### 10.1 Most unconsumed output is not waste. It is demand the model does not represent.

Section 2 treated every non-target output as something to get rid of. That is wrong for
a progression model. In an actual playthrough the leftover Iron Plate is not waste — it
goes into conveyor belts, foundations, the machines themselves, HUB and MAM unlocks, and
the AWESOME Sink for coupons. Those are *demands*. They belong on the consumption side of
the balance, not in a disposal term.

This changes the order of operations. Represent real demand first; decide disposal only
for the residual, which is much smaller than section 2 assumed.

Verified against the reference layer, 2026-09-18:

    schematic_costs.csv               596 rows, schematic_id -> item_id -> amount
                                      canonical, exact. This is unlock demand.
    project_assembly_requirements.csv phase -> item -> quantity_default_1x
                                      canonical, exact. This is elevator demand.
    building construction cost        ABSENT. Fork delta F4 already recorded that
                                      buildCost is not populated in our reference layer.
    belts, foundations, infrastructure ABSENT, and not derivable from anything present.
    AWESOME Sink                      ABSENT — see P5.

**Architecturally this needs no new LP machinery and no contract change.**
`SolveRequest.outputs` is already a tuple of `OutputTarget`, and section 3.2 of the
solver-selection record exercised the multi-target path (Smart Plating + Versatile
Framework + Automated Wiring in one solve). Unlock and assembly demand enters as
additional output targets computed by the progression layer and passed in. The solver
continues to know nothing about progression, which is the boundary's whole purpose.

So D1's recommendation stands but its scope shrinks: disposal is for what remains after
real demand is represented, not for every non-target output.

### 10.2 The proportional idea, and the guardrail it touches

The suggestion was to allocate items to non-elevator uses in proportion to how much they
are used for unlocks, building and belts. That splits cleanly along the canonical line:

    unlocks, Project Assembly    canonical and exact. Model as demand. No estimation.
    belts, foundations, machines no canonical source exists in the reference layer.

For the second group, any proportional coefficient is a number we invent. The standing
guardrail in the session handoff is about exactly this kind of drift — the risk is not
that the coefficient is wrong, it is that an invented valuation constant sitting silently
in the objective stops being visible as an assumption. If such a factor is wanted, it is
an explicitly declared overhead with its derivation recorded, carried on `SolveRequest`
where a caller can see it, and never a constant compiled into the objective.

Recorded as an open question, not adopted.

### 10.3 Power is per machine-time, not per item — and a correction to my own example

The formulation in section 7.4 already does this: the power term is
`mean_power[r] * x[r]`, a cost on machine equivalents of a recipe, not on items produced.
That is the right primitive, and the reason is multi-output recipes: there is no
principled way to split a Refinery's 30 MW between the Plastic and the Heavy Oil Residue
it emits in the same cycle. Any split is arbitrary. Per-machine attribution never has to
answer the question.

The two coincide only for single-output recipes, where power-per-item can be *derived*
for reporting. It is a presentation statistic, not a model primitive, and it should be
labelled as one wherever it appears.

The Iron Plate example as I stated it in conversation was misleading. "0 MW Smelter" was
a description of the P1 defect being diagnosed in section 7 of the solver-selection
record, not a claim about the game. A Smelter draws 4 MW, and
`production_buildings.csv` now carries it.

Reconstructed exactly from `recipe_io.csv` and `production_buildings.csv`:

    Recipe_IngotIron_C    30 Iron Ore/min   -> 30 Iron Ingot/min   1 Smelter      4 MW
    Recipe_IronPlate_C    30 Iron Ingot/min -> 20 Iron Plate/min   1 Constructor  4 MW
                                                                   total          8 MW

    section 3.2 reported                                                          9.63 MW
        = 4 MW Constructor + 0 MW Smelter (the P1 gap) + 5.63 MW extraction
        extraction = 30/240 * 45 MW, Candidate A's hardcoded Miner Mk3 path (section 3.5)

So under D5, with extraction outside the LP and P1 landed, Iron Plate 20/min should
report **8 MW**. The 9.63 MW figure is reproducible only by reintroducing both defects.
This closes the section 3 power caveat with arithmetic rather than inference, and it is
the first validation case that should be written.

### 10.4 Revised open items

- Whether the progression layer or the adapter assembles unlock and assembly demand into
  output targets. Leaning to the progression layer, per 10.1.
- Whether a declared infrastructure-overhead factor is wanted at all (10.2).
- P5 is unchanged and still gates disposal, but matters less than section 2.7 implied.

---

## 11. Amendment, 2026-09-18 — demand expansion is a shared module

Resolves the first open item in 10.4. Greg's proposal, adopted.

### 11.1 The shape

    canonical tables ──> demand expansion ──> progression ──> production_adapter
                               ^                                      |
                               └──── any other caller ────────────────┘

The expansion module imports `production_adapter.contracts` for its types. The adapter
does not import the expansion module. The dependency runs one way, downward.

### 11.2 Why this rather than either alternative

10.4 framed the choice as progression-assembles versus adapter-assembles, and noted it
turned on who else would ever call the adapter — a question with no clean answer
available. A shared module is the option that does not require one.

The costs of being wrong are asymmetric. If progression turns out to be the only caller,
the module serves one consumer and nothing is lost. If the expansion had been built into
the adapter and a second caller later needed it separated, that is a breaking change to a
contract whose whole purpose is stability.

It is also a structural guardrail rather than a policy one, which is the preferred form:
the adapter cannot accrete progression knowledge by drift, because it does not import
anything that has any.

### 11.3 The drift line

"Demand expansion" sits close enough to "planner" to wander. It expands **declared**
requirements into item quantities, and does nothing else:

    does       expand a named schematic or assembly phase into item quantities
    does not   choose which schematics to unlock
    does not   sequence or prioritise them
    does not   decide rates

### 11.4 The quantity/rate gap

Found while specifying the above; load-bearing and recorded at discovery.

    schematic_costs.csv                amount               10.0 Iron Rod
    project_assembly_requirements.csv  quantity_default_1x  50 Smart Plating
    contracts.OutputTarget             rate_per_min         raises if <= 0

The demand tables carry **quantities**. The adapter contract takes **rates**. Converting
between them requires a time horizon, and choosing a horizon is a scheduling decision —
implementation plan Phase 2, the Project Assembly backward scheduler — not an expansion
concern.

Therefore the expansion module's output type is a **bill of quantities** (item ->
amount), not a tuple of `OutputTarget`. Progression converts the bill to rates against
whatever horizon it is planning over, then calls the adapter.

    expansion    declared requirements -> item quantities   canonical, no choices
    scheduling   quantities + horizon  -> rates             progression owns this
    solving      rates                 -> recipes, power, machines

This is what makes the module structurally incapable of becoming a second planner: it has
no concept of time, so it cannot schedule even if asked to.

### 11.5 Consequent open items

- The module's name and location. Not bikeshedding it here.
- Whether `project_assembly_requirement_multiplier` — already carried on `Scenario` and
  explicitly not applied by `Scenario.apply_*` — is applied by the expansion module or by
  the scheduler. The docstring says it is "consumed by the Phase 2 scheduler", which
  suggests the scheduler, but the quantity it scales is an expansion output. Unresolved.

---

## 12. Amendment, 2026-09-18 — D2, D3 and D4 dispositions

Greg's answers. Supersedes the State block's `open` list in part; the block itself
stands as written.

### 12.1 D2 — both statistics retained, decision deferred

**Disposition: DEFERRED, deliberately.** Greg has not played far enough into the
variable-power tier to judge how Converter, Particle Accelerator and Quantum Encoder
behave in practice, and declines to pick a statistic on theory alone.

`PowerReport` continues to carry `min_mw`, `mean_mw` and `max_mw`. Which one the
objective minimises stays unresolved. Revisit when the variable-power tier has actually
been played, not before.

This costs nothing today: both fixed-recipe validation cases involve only fixed-power
producers (Smelter, Constructor, Assembler), so min, mean and max coincide and the
cases are independent of D2 by construction. `test_iron_plate_power_is_unambiguous` and
`test_smart_plating_power_is_unambiguous` assert exactly that, so the independence is
enforced rather than assumed. The moment a case involving a variable-power producer is
added, those tests stop passing vacuously and D2 becomes forced.

### 12.2 D3 — the question was two questions

Section 4 conflated numerical degeneracy with recipe valuation. They separate cleanly
and only the first is D3.

**D3a — numerical degeneracy. Mechanical. Unchanged.** Two solutions with *identical*
objective values; the simplex picks one arbitrarily, and the pick is unstable across
scipy versions, platforms and trivial input reordering. Section 4's recommendation
stands: deterministic sorted input ordering, a lexicographic tie-break rather than an
epsilon perturbation, and a `warnings` entry when a tie is broken. Still RECOMMENDED.

**D3b — recipe valuation. Greg's actual point, and the larger question.** Which
alternate recipe is better is not a property of the recipe. It depends on:

- **Acquisition odds, which change with progression.** Alternates arrive from hard
  drives, and the drive pool expands as the game progresses. An early alternate —
  cast screws, iron wire — is comparatively likely to appear while the pool is small
  and becomes rare once it is large. So the cost of *obtaining* a recipe is a function
  of when you look for it.
- **The scenario multipliers.** A recipe that is C-tier in the base game can be A-tier
  once input and power multipliers are applied. Valuation is therefore
  scenario-parameterised and can never be a static tier list.

Desired behaviour, per Greg: the tool surfaces both versions and their downstream
impacts as part of the overall solution, rather than returning one ranked answer.

**Consequence for D3a.** A richer objective makes exact ties rarer, which is Greg's
point and it is correct. It does not make them impossible — symmetric sub-chains still
tie exactly — so D3a's determinism guard is still required. The two are complementary,
not alternatives.

**Scope.** D3b is Phase 3 and earns its own record. Data already present:
`alternate_recipe_unlocks.csv`, `alternate_choices.csv`, `hard_drive_system.csv`,
`non_hard_drive_alternate_unlocks.csv`, `mam_pool_effects.csv`. Two known blockers
carried from the session handoff: P4 (the slug-versus-`Recipe_*_C` join) and the
`is_alternate` disagreement on `Recipe_PureAluminumIngot_C` and
`Recipe_Alternate_Turbofuel_C`.

### 12.3 D4 — confirmed pointless, guard retained for a named reason

Greg's reading is correct: a loop where A feeds B and B feeds A produces nothing and no
player builds one. Under default weights the LP agrees — every activity carries positive
machine and power cost, so running an inverse pair is strictly worse than not running
it. That is mitigation 1 of section 5, and on its own it disposes of the objection.

The guard is still needed, for a specific and non-hypothetical reason: section 3.4 of
the solver-selection record sweeps Pareto weightings, and one of them is
**resources-only**, with power and buildings at zero. Under that weighting a
packager/unpackager pair costs exactly nothing and the solver has no reason to avoid it.

So the cycle mitigations are not defending against a player's bad idea. They are
defending against the Phase 3 Pareto sweep, where the weights that make the loop
pointless are precisely the ones set to zero.

Section 5's three mitigations stand as written, with that rationale substituted for the
vaguer one they were given.

### 12.4 Validation harness landed

    tests/_fixed_recipe_expectations.py     power and machines for a GIVEN multiplier
                                            map; never selects; inherits the oracle's
                                            guard by construction
    tests/test_fixed_recipe_expectations.py 8 tests

Covers the layer `_demand_oracle` deliberately omits. Confirmed against the reference
layer:

    Iron Plate 20/min     8.0000 MW   Smelter 1.0, Constructor 1.0        30.00 ore
    Smart Plating 1/min  26.0500 MW   Smelter 0.775, Constructor 2.175,
                                      Assembler 0.95                      23.25 ore

The two section 3.2 power figures are now reconstructed as executable assertions rather
than prose: 9.625 MW and 27.309375 MW are reproducible only by zeroing the Smelter (the
P1 gap) and adding Candidate A's hardcoded `ore / 240 * 45` extraction. Section 3.2
displays them as 9.63 and 27.31; the tests pin the exact arithmetic rather than either
language's rounding. The caveat recorded in the session handoff is now a test.

18 tests pass locally against a partial checkout. **The full repository suite has not
been run** — that needs Greg's machine.

### 12.5 Open items discharged

- Session handoff open item 6, `miner_extraction_rates.csv`: deleted by Greg.
- Session handoff open item 7, first manifest regeneration: run. Verified counts —

      REPO_MANIFEST.csv          413 -> 323   (handoff predicted ~305)
      planning_data/manifest.csv 322 -> 177   (handoff predicted ~182)

  Neither manifest still references the retired table. The 18-row gap on REPO_MANIFEST
  includes the two test files added above; the remainder is unexplained and probably not
  worth explaining, the prediction having been approximate.

---

## 13. Amendment, 2026-09-18 — the backend landed

Section 7 is implemented. This records what implementing it settled, what it could
not settle, one defect it found in prior evidence, and one behaviour of the
reference layer nobody had written down. Session handoff open item 2 is discharged.

The State block at the top of this record still reads
`decision_status: RECOMMENDED — awaiting Greg's acceptance`. It is not edited here.
Implementation proceeded on Greg's instruction to begin open item 2, which is
acceptance in practice but not in the record; whether the block should move is his
call, forward.

### 13.1 What exists

    tools/production_adapter/src/production_adapter/lp_backend.py
        scipy.optimize.linprog, method="highs". Written from this record, not from
        Candidate A's source. Neither vendored nor forked, so fork deltas F1, F3
        and F4 no longer gate anything.
    tests/test_production_lp_backend.py
        47 tests, section 8 items 1 through 5.

Not registered on import. `production_adapter/__init__.py` does not import
`lp_backend`, so `registered()` stays empty, the contract package stays
dependency-free, and `test_no_backend_is_wired_up_yet` keeps passing rather than
becoming order-dependent on collection sequence. A caller wires it explicitly.

scipy is now declared: `scipy>=1.11` in the root `dev` group, and as the adapter's
`lp` optional extra.

Validation, section 8 in order:

    1  machine equivalents vs tests/_demand_oracle.py        5 targets, to 1e-4
    2  Smart Plating 1/min, section 3.3 of the selection     7 recipes, Iron Ore
       record                                                23.25, 26.05 MW
    3  raw-material columns, section 3.2                     2 of 4 reconcile;
                                                             see 13.3
    4  same request, recipe order reversed                   identical response
    5  packager/unpackager pair                              never both directions

Iron Plate 20/min returns 8.0000 MW and 30.00 ore, which is the case section 10.3
asked to be written first.

**Measured in the session container, not on Greg's machine**: 87 passed against a
partial checkout (Python 3.11, scipy 1.17.1, pytest 9.1.1) — the 47 new tests plus
the 40 pre-existing ones whose data was staged. The full suite, previously 97
green, has not been run with these additions. That needs `uv run pytest` on Greg's
machine.

### 13.2 Decisions taken at implementation time

Each is reversible, each is a constructor argument or a named constant rather than
a compiled-in assumption.

    power_statistic     REQUIRED, no default. D2 is deferred (12.1), so a default
                        would be a decision nobody made. Every producer in the
                        current validation set is fixed-power, so the cases stay
                        D2-independent by construction and the deferral costs
                        nothing today.
    unconsumed          FREE by default, per the 2.7 stopgap, with every leftover
                        above 1e-4/min named in warnings. FORBID available and
                        exercised. DISPOSAL raises NotImplementedError naming P5.
    canonical_mw        re-evaluates the selected recipe mix at canonical power.
                        7.5 flags the alternative (a second solve at Scenario())
                        as open; a warning on every response says which reading
                        this is, so the choice is never inferred from silence.
    tolerance           1e-6. HiGHS' primal feasibility tolerance floors around
                        1e-7 and it returns activities at ~1e-8 that are noise,
                        not production; the option to tighten it below that is
                        rejected by HiGHS outright. 1e-6 sits above the noise and
                        two orders below the four decimals section 8 validates to.
    leftover reporting  1e-4, the precision the warning prints at. A figure that
                        renders as 0.0000/min is residue, and naming it as
                        unconsumed output is a false positive. SolveResponse.items
                        still carries every flow exactly.

**Section 4 step 2 is not fully implementable and this record did not notice.**
"Prefer fewer distinct recipes" is a cardinality objective. It needs binary
variables — which is precisely what section 7.4 rules out while fork delta F2
stands. The two cannot both hold. What is implemented is step 1 (sorted recipe
ordering) plus a second LP that minimises total activity among the optima of the
first, which is lexicographic, LP-expressible, and stable. The
lexicographically-smallest-tuple step is also omitted, for the same reason: it
needs the cardinality step to be meaningful. Recorded rather than silently
approximated. If F2 is ever lifted, the cardinality tie-break and the complexity
weight become available together, which is an argument for lifting them in one
record rather than two.

**Tie detection compares recipe activities only.** Leftover slack carries zero
cost by construction (2.4 rejects a penalty on it), so it is degenerate in the
primary objective whenever any leftover exists at all. Comparing the full solution
vector fired the warning on nearly every solve and therefore meant nothing.
Section 4's concern is recipe selections churning between runs; that is what is
compared. Observed effect: under default weights only Computer over the full
recipe set ties; under the resources-only Pareto weighting from section 3.4 of the
selection record, essentially every target does — which is 12.3's point, now
measured rather than argued.

### 13.3 Defect — section 3.2's Versatile Framework raw-material column is wrong

    section 3.2      Versatile Framework 6/min   9 recipes   Coal 144.00, Iron Ore 144.00
    this backend     Versatile Framework 6/min   9 recipes   Coal 144.00, Iron Ore 216.00
    _demand_oracle   Versatile Framework 6/min               Coal 144.00, Iron Ore 216.00

The backend and the oracle share no code. Both read the same reference layer and
agree on 216.00. The arithmetic is not marginal: 6 Versatile Framework/min needs
36 Steel Beam/min, which is 144 ore through steel, *and* 3 Modular Frame/min,
whose Reinforced Iron Plate and Iron Rod branch draws a further 72. Section 3.2's
figure is the steel branch alone.

The recipe *count* matches at 9, and Coal matches exactly, so this is not a
different plan — it is the same plan with iron ore under-reported. The cause is in
Candidate A's `totalRawResources` reporting or in the Phase 0 harness that read
it; it has not been chased further, because the figure is superseded either way.

Consequence, and the reason this is here rather than only in a test: the session
handoff records section 3.2's raw-material columns as *usable*, in contrast to its
power columns. That conclusion does not survive. Reinforced Iron Plate 5/min and
Automated Wiring 1.2/min still reconcile exactly; Versatile Framework does not,
and the multi-target row inherits the same 95.25 gap (Iron Ore 149.40 recorded,
244.65 actual) while its Coal and Copper Ore still reconcile.

Pinned as two executable assertions rather than prose, in the shape section 12.4
used for the power figures:
`test_versatile_framework_raw_column_contradicts_phase_0` and
`test_multi_target_raw_column_inherits_the_same_divergence`.

### 13.4 Found while validating — a resource cap is a routing signal, not a ceiling

`Recipe_Iron_Limestone_C` is a **base** recipe that produces Iron Ore from Stone
and SAM. Capping Iron Ore at 29/min against an Iron Plate 20/min target therefore
does not make the problem infeasible: the model covers the missing ore through the
Converter. Nothing in this record or the selection record anticipated that, and it
matters in two places.

- A `ResourceCap` constrains extraction of a resource, not availability of the
  material. Anything downstream reasoning about node depletion needs to know that.
- The Converter is variable-power, so the first case that binds a cap is also the
  first case that is **not** D2-independent. The test pins the routing and
  deliberately does not assert a power figure.

### 13.5 Open, carried forward

Unchanged: P5 still gates disposal (13.2 keeps FREE as the stopgap); 7.5's
canonical_mw reading is still undecided and now warns; D2 still deferred and now
structurally so; D3b still Phase 3; per-resource scarcity weighting (7.4) still
Phase 3; the demand expansion module (section 11) still unnamed and unlocated.

New:

- F2 now gates the cardinality tie-break as well as the complexity weight (13.2).
  Its original justification — Candidate A's hardcoded 3-second MIP limit — does
  not transfer to scipy, which takes `time_limit` as an ordinary parameter.
- Determinism is asserted within one scipy version. Section 4 worries about
  instability *across* versions and platforms; sorted ordering and the second-stage
  refinement address the reordering and degeneracy sources, but nothing here has
  been run on two scipy versions.
- Whether the State block moves off RECOMMENDED.

---

## 14. Amendment, 2026-09-18 — the comparator, and what D2 actually costs

D2 remains undecided. This amendment does not decide it; it records what the choice
is worth, measured, so that the deferral in section 12.1 is now an informed wait
rather than a blind one.

### 14.1 What exists

    tools/production_adapter/src/production_adapter/analysis.py
    tests/test_production_analysis.py                            20 tests

`analysis.compare()` solves N variants of one request and cross-prices each
resulting plan under every other variant's metric. A variant is a
`(label, request, data, backend)` tuple, so the axis of difference is whatever the
caller varies — power statistic, weights, allowed recipes, scenario, unconsumed
mode. `power_statistic_variants()` is the D2 instance of the general tool.

Greg's calls, all three taken before any code was written:

    output scope   QUANTIFY ONLY. No best, no rank, no score, no sort.
    generality     ANY SOLVE-CONFIGURATION AXIS, not the power statistic alone.
    placement      SIBLING MODULE inside the adapter package. It imports
                   lp_backend; nothing in the adapter imports it; __init__.py does
                   not import it, so the contract package stays dependency-free.

One change to `lp_backend.py`: `_enabled_recipe_ids` is now public as
`enabled_recipe_ids`, because the comparator needs it and a second implementation
of "which recipes are enabled" could drift from the first silently.

### 14.2 Two structural guards

**It cannot recommend.** `Comparison.variants` is returned in the caller's order
and never sorted; nothing returns a single variant; the public surface carries no
ranking vocabulary. Three tests assert this by inspection rather than by review,
in the shape `test_expectations_cannot_choose_recipes` established. The guardrail
being defended is the standing one: a comparator that ranks has become the
progression layer, which is the drift this project exists to avoid. Sorting the
output would be ranking under another name, which is why caller order is asserted.

**It cannot mislead.** Two variants can only be priced against each other when they
share a *feasible set* — when only the metric differs. `Feasibility` captures what
determines the constraint set (scenario, enabled recipes, targets, caps, unconsumed
mode, activity bound). If those differ, one variant's plan is not a valid plan for
the other, and re-pricing it would produce a number that looks like a comparison
and is not. Those cells return `None` with the reason named, never a value.

Consequence worth stating plainly: **weights are comparable, scenarios are not.**
Comparing a canonical run against a challenge run is not a regret calculation, and
the tool refuses rather than pretending.

Regret is non-negative by construction, since a comparable variant's plan is always
feasible for the other. A negative beyond `REGRET_NOISE` raises
`InconsistentComparison` rather than being rounded away — it would mean either the
feasibility check admitted a bad pair or a solve missed its optimum. Small negatives
are expected and snapped: D3a's second-stage LP accepts the primary optimum within a
1e-9 relative slack, so a cross-priced plan can undercut a reported optimum by about
that much.

### 14.3 What D2 costs, measured

All fourteen validation and Space Elevator targets, `RecipeMode.ALL`, canonical
scenario, default weights. "sel" is whether the selected recipe set differs across
min/mean/max; "rel regret" is the largest cell of the regret matrix relative to the
optimum it is measured against.

    target                        sel   rel regret     raw min/max    reported MW min -> max
    Iron Plate                      =      0.0000%     8.67/   8.67      9.30 ->     9.30  x1.00
    Reinforced Iron Plate           =      0.0000%    15.30/  15.30     21.42 ->    21.42  x1.00
    Smart Plating                   =      0.0000%     3.89/   3.89     18.15 ->    18.15  x1.00
    Versatile Framework             =      0.0000%    66.72/  66.72     78.90 ->    78.90  x1.00
    Automated Wiring                =      0.0000%    13.29/  13.29     24.73 ->    24.73  x1.00
    Modular Frame Heavy             =      0.0000%    45.08/  45.08    149.34 ->   149.34  x1.00
    Modular Engine                  =      0.0000%   195.35/ 195.35    338.22 ->   338.22  x1.00
    Adaptive Control Unit           =      0.0000%    45.84/  45.84     71.91 ->    71.91  x1.00
    Assembly Director System        =      0.0000%   542.19/ 542.19    943.03 ->   943.03  x1.00
    Magnetic Field Generator        =      0.0000%   692.72/ 692.72    975.72 ->   975.72  x1.00
    Nuclear Pasta                DIFF      0.0000%  1521.24/1521.24   1539.39 ->  3539.39  x2.30
    AI Expansion Server             =      0.0000%   232.10/ 232.10    314.89 ->   381.55  x1.21
    Ballistic Warp Drive            =      0.0000%  2030.14/2030.14   3740.54 ->  9288.87  x2.48
    Thermal Propulsion Rocket    DIFF      1.5526%   361.92/ 391.92    744.67 ->  3111.34  x4.18

**The choice barely moves the plan and enormously moves the number.**

Twelve of fourteen targets select an identical recipe set under all three
statistics. Nuclear Pasta's difference is an exact tie — one additional activity at
zero relative regret. Thermal Propulsion Rocket is the only case where the statistic
costs anything real: 1.55% on the objective, and 30/min of raw material (361.92 vs
391.92, an 8% difference), where MAX takes the base Dark Matter route and MIN and
MEAN take `Recipe_Alternate_DarkMatter_Crystallization_C`.

Reported power, by contrast, swings by up to 4.18x on the same target.

### 14.4 Consequence for D2

Section 3 recommended `mean_mw` on the grounds that it is neither systematically
optimistic nor pessimistic, and noted one real alternative: *"max_mw is the right
statistic if the downstream question is grid sizing rather than running cost."*

The evidence above reframes which of those arguments carries weight. Section 3's
reasoning is about the objective — about not biasing selection — and selection
turns out to be almost insensitive to the choice. The grid-sizing argument is about
the reported figure, which is where the entire sensitivity lives. **On current
evidence D2 is a reporting decision, not an optimization decision.**

That is not a recommendation to switch, and this record does not make one. It is a
statement that the question "which statistic biases selection least" has been
answered — *none of them, materially* — and that whatever settles D2 will be a
question about what the number is for. Section 12.1's deferral until the
variable-power tier has been played remains the right call; the thing to pay
attention to while playing is what the power figure will be used to decide.

Two caveats on the measurement. It is single-target and default-weighted; a
power-only or resources-only weighting has not been swept this way, and the
resources-only sweep is where section 12.3 expects degeneracy to be the rule.
And `Recipe_FicsiteIngot_*` and the residual-oil routes make several of these
solves degenerate, so "identical selection" partly reflects the D3a tie-break
landing the same way each time, which is the guarantee it was built to give.

### 14.5 Correction — D2 does not gate Phase 1

A claim made in session, and carried briefly in the session handoff, held that
Phase 1's exit condition could not be met while D2 was deferred, because every
Phase 4/5 chain activates variable-power producers. **Withdrawn.**

The measurement behind it used `RecipeMode.ALL`, which is the optimization mode.
Plan section 11 requires *fixed-recipe* validation — the recipe set is given, so the
statistic cannot change selection, and `PowerReport` carries min, mean and max
regardless of which one the objective used. D2 gates Phase 3, where the objective
chooses. It does not gate Phase 1.

What the late-game validation case does need is a **curated route**, because "base
recipes only" is not an unambiguous tree past the oil tier. After excluding the 12
unpackage recipes, Nuclear Pasta needs exactly two route decisions:

    Desc_Silica_C     Recipe_AluminaSolution_C  vs  Recipe_Silica_C
    Desc_Plastic_C    Recipe_Plastic_C          vs  Recipe_ResidualPlastic_C

Thermal Propulsion Rocket adds the Ficsite ingot route (aluminium vs caterium vs
tungsten), which has no default and is a genuine choice. Small deliberate work,
not a blocker.

### 14.6 Defect — `_demand_oracle`'s docstring overstates its own guarantee

`tests/_demand_oracle.py` says of `allowed_recipes=None`: *"which is the only
configuration guaranteed to be unambiguous across the whole tree."* That is false
past the oil tier. Base-only leaves `Recipe_Plastic_C` vs `Recipe_ResidualPlastic_C`,
`Recipe_Rubber_C` vs `Recipe_ResidualRubber_C`, the 12 unpackage recipes, and the
multi-route Ficsite ingots all ambiguous, and the oracle correctly raises on every
Space Elevator part above Adaptive Control Unit.

The behaviour is right; only the claim is wrong. Per the standing defect rule this
is a documentation defect and belongs at the site, not here — recorded in this
record only because it bears on 14.5's account of what Phase 1 still needs.

### 14.7 Open

- D2 itself, unchanged and still deferred, now with 14.3 to decide against.
- Whether a power-only or resources-only sweep changes 14.3's conclusion.
- The curated late-game routes of 14.5, which are Phase 1 work.
- Whether `Comparison` should ever gain a Pareto-frontier filter. That is plan
  section 12 and Phase 3; the comparator was deliberately built as the primitive
  beneath it rather than as it.

---

## 15. Amendment, 2026-09-18 — plan section 11 completed, and a limit on the oracle

All fourteen cases in the implementation plan's section 11 validation set now exist
as tests. This records how each was made a *fixed-recipe* case, one finding that
changes what `_demand_oracle` can be used for, and one case in the plan that turns
out to exercise nothing.

### 15.1 What exists

    tests/test_plan_section_11_validation.py   38 tests, the nine cases that were missing
    tests/_balance_check.py                    a third independent reference — see 15.3

Section 11 requires each case to compare *item rates, recipe rates, machine
equivalents, raw inputs, and power* against independently verified values. The
alternate and scenario cases compare all five against `_demand_oracle` and
`_fixed_recipe_expectations`. The late-game case is covered differently and 15.4
says how.

### 15.2 "Fixed recipe" had to be constructed, not assumed

An item can have several *base* producers, so no mode of `AllowedRecipes` yields a
fixed-recipe case on its own past the early game. Every case here names an explicit
recipe set, and the guarantee that a set really is fixed is that `_demand_oracle`
resolves it without raising `AmbiguousDemand` — that raise fires exactly when an
item on the demand path has more than one enabled producer, so silence means the
route was forced and the solver had nothing to choose.

Alternate cases are the base set with one recipe swapped:

    Stitched Iron Plate   Recipe_Alternate_ReinforcedIronPlate_2_C  <- Recipe_IronPlateReinforced_C
    Iron Wire             Recipe_Alternate_Wire_1_C                 <- Recipe_Wire_C
    Solid Steel Ingot     Recipe_Alternate_IngotSteel_1_C           <- Recipe_IngotSteel_C
    Steeled Frame         Recipe_Alternate_ModularFrame_C           <- Recipe_ModularFrame_C
    Steel Rotor           Recipe_Alternate_Rotor_C                  <- Recipe_Rotor_C

The pairing is asserted rather than assumed: a test checks each alternate and the
recipe it displaces produce the same item set, because a swap that changed what the
chain produces would not be the same case.

Section 11's "Rotor/Stator + Steel Rotor where applicable" is covered by two
targets, Rotor 10/min and Motor 5/min, the second because Motor is the chain that
consumes Rotor and Stator together.

The three scenario rows are now run across **all five** fixed-recipe targets rather
than one target each, which is what the earlier PARTIAL status referred to.

### 15.3 `_demand_oracle` stops being a valid reference where byproducts feed back

Found while building the late-game case, and it changes a standing assumption, so
it is here rather than only at the site.

The oracle propagates demand item by item and credits no byproducts. A production
solver nets everything in one balance and credits them all. The two agree on every
chain where nothing feeds back — which is every case section 11 had until now — and
diverge structurally the moment an enabled recipe's byproduct satisfies another
demand.

Nuclear Pasta is such a chain. `Recipe_AluminaSolution_C` is the sole source of both
Alumina Solution and Silica, so:

    _demand_oracle    Recipe_AluminaSolution_C  4.1000   runs it once per demand
    LP backend        Recipe_AluminaSolution_C  3.0750   runs it once for both, and
                                                         leaves 246.00/min of Alumina
                                                         Solution as unconsumed output

Every other recipe in the 30-recipe chain agrees to four decimals, which localises
the divergence rather than merely asserting it. Neither implementation is wrong;
they answer different questions. What is wrong is treating the oracle as *the*
independent reference, which is how it has been described until now.

So a third reference was written, crippled the same way as the other two:

    tests/_balance_check.py    takes a SolveResponse and a target map and returns
                               the ways the response fails to be a consistent answer
                               — items that do not balance, targets not met, raw
                               draws that are not resources, reported ItemFlow
                               disagreeing with the activities. It reads the CSVs
                               directly. It does not solve, cannot produce an answer,
                               and has no notion of a better one.

This is the reference that works on any chain, byproducts included, because it
verifies the answer rather than recomputing it.

### 15.4 What the late-game case does and does not establish

The representative Phase 4/5 chain is Nuclear Pasta 1/min, 30 recipes across eight
producer classes including the Particle Accelerator, on a curated route: base
recipes, minus every Unpackage recipe, minus two byproduct routes that would
otherwise leave an item with two producers.

Two route choices, recorded because they are choices:

    Recipe_Silica_C           dropped. Recipe_AluminaSolution_C is the only source of
                              Alumina Solution and the chain needs it, so Silica
                              arrives as that recipe's byproduct rather than direct.
    Recipe_ResidualPlastic_C  dropped. Plastic comes from the direct route.

Established independently: the response balances and meets the target
(`_balance_check`, reading the CSVs); power and machine counts follow from the
activities (`_fixed_recipe_expectations`, also reading the CSVs); the power range
spans exactly 2000 MW, so the case genuinely exercises the variable-power tier.

**Not** established independently: that those activities are the only ones that
balance. For a forced route the balance system pins them, and the one place the
route is not forced is precisely the Alumina byproduct credit in 15.3, which is
pinned by an explicit assertion instead. Stating the gap rather than implying it is
covered.

The case also makes section 14.5 executable: all three power statistics return the
same plan and the same power range, because a fixed recipe set leaves the objective
nothing to choose. That is why Phase 1's exit condition does not wait on D2.

### 15.5 Defect — section 11's "Smart Plating + Iron Wire" row exercises nothing

Smart Plating is Reinforced Iron Plate plus Rotor. Neither uses Wire. Enabling
`Recipe_Alternate_Wire_1_C` therefore changes no recipe, no rate and no power: the
solve is identical to the baseline Smart Plating case, to four decimals.

The row is implemented and kept, because "an unused alternate must not perturb a
fixed-recipe result" is a real invariant worth holding. But it is not evidence that
the Iron Wire route was validated, and the test says so in its own docstring so that
nobody reads the row that way. If an Iron Wire case is wanted, it needs a target
whose chain contains Wire — Automated Wiring is the obvious candidate.

### 15.6 Phase 1 exit condition

Plan section 17: *"fixed production targets reconcile correctly for early and late
game."* All fourteen section 11 cases now exist and pass, early and late.

What that rests on, stated plainly rather than assumed: 145 tests pass against a
partial checkout in a session container (Python 3.11, scipy 1.17.1, pytest 9.1.1).
The full repository suite — predicted at 202 — has not been run. Nothing here
observes the pre-existing 97 still passing alongside these additions, and uv has not
resolved scipy on the machine that matters. Declaring Phase 1 closed is a call for
Greg to make after `uv run pytest` on his own machine, not something this record
can assert from where it was written.

### 15.7 Open

- Whether an Iron Wire case against a Wire-bearing target replaces or joins 15.5's.
- Whether `_demand_oracle`'s docstring should now carry 15.3's limit as well as the
  ambiguity limit added in 14.6. It currently carries neither in full.
- The curated late-game route is one route. A second Phase 4/5 chain through a
  different producer mix (Quantum Encoder, Converter) would exercise the other two
  variable-power classes, which nothing currently does.

---

## 16. Amendment, 2026-09-18 — section 15.5 was wrong; the pair, and what it implies for D3b

Greg's correction, verified. Section 15.5 recorded plan section 11's "Smart Plating
+ Iron Wire" row as a defect — a case that exercises nothing — and suggested moving
it to a Wire-bearing target. **That conclusion is withdrawn.** The measurement it
rested on was right; the reading of it was not.

### 16.1 Iron Wire is not a standalone row, it is the second half of a pair

Baseline Smart Plating is Reinforced Iron Plate plus Rotor, and neither uses Wire —
so Iron Wire alone genuinely changes nothing, which is what 15.5 measured. What 15.5
missed is *why section 11 lists it next to Stitched Iron Plate*.

Stitched Iron Plate is an early alternate for Reinforced Iron Plate that consumes
Wire instead of Screws. That is what puts Wire into the chain, and Wire's base recipe
runs on Copper Ingot — so Stitched on its own is a gain only where copper is close
enough to be worth belting in. Iron Wire then makes Wire from Iron Ingot, taking the
copper back out.

Measured, Smart Plating 1/min, canonical scenario, default weights:

    variant                raw inputs                     power      machines  recipes
    baseline               23.2500 ore                    26.0500    3.9000    7
    stitched only          16.2500 ore + 3.3333 copper    23.5833    3.3444    9
    iron wire only         23.2500 ore                    26.0500    3.9000    7
    stitched + iron wire   19.9537 ore                    23.9290    3.4309    8

Stitched alone trades 7.00 ore for 3.33 copper. Iron Wire buys the copper back for
3.70 ore. The pair is 3.30 ore/min and 2.12 MW cheaper than baseline, on iron alone.

One precision on the mechanism: Iron Wire removes Screws from the *Reinforced Iron
Plate* branch, not from the chain. Rotor still consumes Screws, so `Recipe_Screw_C`
is active in all four variants above.

### 16.2 The structural point, which is larger than the row

**An alternate's value is not a property of the alternate.** Iron Wire's marginal
value here is exactly zero held alone and 3.30 ore/min held with Stitched Iron Plate.
The two are not additive, and no independent per-recipe score reproduces the pair.

Section 12.2 (D3b) already said valuation is scenario-parameterised and cannot be a
static tier list. This is the sharper version: it cannot be a per-recipe list at all,
static or not, because value is conditional on which *other* alternates are held. Any
Phase 3 valuation that scores alternates one at a time and sums them gets this case
wrong, and this case is an early-game one that a player meets in the first hours.

That does not make Phase 3 a combinatorial search over 110 alternates — it makes the
unit of valuation a *set*, and it means the comparator from section 14 is the right
primitive for it, since a variant is already an arbitrary recipe set rather than a
single swap.

### 16.3 Proximity is not expressible to this model, and a cap does not fake it

"Only worth it if copper is close" cannot be stated to a production solve. Capping
Copper Ore at zero does not make the Stitched-only chain infeasible: the solver
routes copper from Raw Quartz and SAM through the Converter, the same behaviour
section 13.4 recorded for `Recipe_Iron_Limestone_C` and iron. The cap is a routing
signal, not a distance.

Distance is a world-layer fact and belongs to Phase 5, per plan section 16. Until
then, "stitched is conditional on copper access" is a true statement about the game
that the model cannot represent, and the honest handling is to report the raw mix and
let the world layer judge it — which is what `RawInput` already does.

### 16.4 Tests

Section 11's row count is unchanged; its reading is not. Added to
`tests/test_plan_section_11_validation.py`:

    Smart Plating + Stitched Iron Plate + Iron Wire   reconciled as a seventh
                                                      alternate case
    test_stitched_plus_iron_wire_removes_the_copper_dependency
    test_alternate_value_is_not_additive              16.2, executable
    test_a_copper_cap_does_not_express_copper_distance 16.3, executable

`test_iron_wire_is_inert_for_smart_plating` is renamed
`test_iron_wire_is_inert_alone_but_not_in_the_pair`; its assertions are unchanged and
its docstring no longer draws 15.5's conclusion.

### 16.5 Open

- Whether section 11's remaining rows hide other pairs. Solid Steel Ingot, Steeled
  Frame and Steel Rotor were each validated alone; nothing has checked whether any of
  them is conditional on another in the same way.
- Section 15.7's suggestion of an Iron Wire case against a Wire-bearing target
  (Automated Wiring) still stands on its own merits, but it is no longer a *fix* for
  anything — the row was not broken.

---

## 17. Amendment, 2026-09-18 — per-resource scarcity: rejected as a weight, relocated as a constraint

Section 7.4 left an open item: the raw-resource term sums unweighted physical rates
across dissimilar resources, so one unit of Uranium costs what one unit of Iron Ore
costs, which "is almost certainly wrong for progression purposes." This amendment
investigates that and **closes it in the negative**: the bias is real, and
per-resource weights in the objective are the wrong instrument for it.

Greg's line of questioning drove this and his correction is what settled it. No code
was written. Nothing in the adapter changed.

### 17.1 The bias is real and pervasive

Measured with `RecipeMode.ALL`, canonical scenario, default weights. The solver
reaches for Caterium and Raw Quartz on nearly every mid and late target, because a
unit of each costs exactly what a unit of Iron Ore costs:

    Automated Wiring 1.2/min    Caterium   6.71   Raw Quartz   2.25
    Adaptive Control Unit       Caterium   9.86   Raw Quartz   3.75
    Motor 5/min                 Caterium  17.91   Raw Quartz  11.88
    Modular Engine              Caterium  47.69   Raw Quartz  30.96
    Magnetic Field Generator    Caterium  61.61   Raw Quartz  28.87
    Assembly Director System    Caterium 125.62   Raw Quartz  90.67   Sulfur 15.00

A prototype that scaled the objective's raw block by node-count-derived weights
changed the answers substantially — Motor 5/min drops Raw Quartz entirely and cuts
Caterium from 17.91 to 6.25, paying with iron (5.62 to 33.44). Scarcity-weighted
cost roughly halves; physical material moved rises about a third. So the instrument
works. The question is whether it is the right one.

### 17.2 Three quantities were being conflated

    global abundance          nodes on the map, by purity. A map constant.
    reachable availability    what can be extracted and moved to where you are
                              building, given transport. Local, and it EXPANDS.
    progression availability  whether the recipe or extractor is unlocked at all.

Only the first is a property of a resource. The second is a property of a base
position and a transport tier. The third is a property of progression state. A
single scalar per resource can express the first and silently stands in for the
other two.

### 17.3 Why a map-wide weight is the wrong shape, not merely premature

Greg's correction, and it is the load-bearing point of this amendment:

> the world ceiling only matters if and when you can transport resources from other
> locations — until then it is locally bound. You cannot just add more machines if
> the nearest node is half way across the map.

A weight derived from map totals is wrong in both directions at once. Early it is
far too permissive, because even Iron Ore is limited to the handful of nodes that
can actually be belted to the build site. Late it is too restrictive, because trains
make the map total genuinely reachable. It is not a number awaiting better
calibration; it is a constant standing in for a function that starts local and grows.

Two supporting measurements, both against the reference layer:

**Map-wide extraction ceilings never bind at working scales.** Assembly Director
System's 125.62 Caterium/min sits against a 1,500/min map-wide ceiling at Miner Mk1
— 8%. Nothing at single-part rates comes close.

    resource                      Mk1        Mk2        Mk3     (items/min, 100% clock)
    Desc_OreIron_C              9,210     18,420     36,840
    Desc_Stone_C                6,930     13,860     27,720
    Desc_Coal_C                 4,230      8,460     16,920
    Desc_OreCopper_C            3,690      7,380     14,760
    Desc_OreGold_C              1,500      3,000      6,000
    Desc_RawQuartz_C            1,350      2,700      5,400
    Desc_OreBauxite_C           1,230      2,460      4,920
    Desc_Sulfur_C               1,080      2,160      4,320
    Desc_SAM_C                  1,020      2,040      4,080
    Desc_OreUranium_C             210        420        840

**Belt throughput is not a scarcity term either.** A belt is not a ceiling — another
belt can always be run, at the cost of belts, splitters and space. That is plan
section 1.5's *logistics complexity*, which it lists as a metric to keep separate
and to compare in a Pareto rather than fold into a composite. And it rarely binds:
from `logistics_capabilities.csv` and `extraction_rates.csv`, at 100% clock the belt
is the binding side in exactly one place — Tier 0 to 1 on a pure node, where a Miner
Mk1 produces 120/min and a Mk1 belt carries 60. From Tier 2 onward the miner binds
everywhere. The exception is overclocking: a Mk3 miner on a pure node at 250% is
1,200/min, which equals belt Mk6 exactly, so overclocked pure nodes are
transport-bound at any tier below 9.

Note also that Miner Mk2 and belt Mk3 both unlock at Tier 4, so the extraction and
transport steps land together rather than staggered.

### 17.4 Disposition — the mechanism already exists and is not in the objective

**Scarcity is a constraint, sourced from the world layer, not a weight in the
objective.** `SolveRequest.resource_caps` already takes an item and a rate per
minute, which is exactly the shape of "this is what you can actually get here". The
production solver stays ignorant of geography; the world layer computes the numbers
from base position, transport tier and terrain. That is plan section 16 in both
directions, including its own sentence that "district constraints can eventually
feed the production optimizer: available iron, available coal, belt tier, miner
tier, local oil, transport capacity."

No contract change. Nothing invented. Section 7.4's open item is closed by
relocation rather than by a coefficient.

Two consequences worth keeping:

- The behaviour recorded at 13.4 — that a cap is a routing signal rather than a
  ceiling — becomes the useful property here. Capping Copper Ore to what is
  reachable makes the solver show what it would do instead, which is the actual
  answer to "is it worth belting copper in": two plans to compare, not a weight
  asserting a trade rate.
- Caps are part of the comparator's feasibility signature, so two transport horizons
  are two feasible sets and cross-pricing is refused. Had scarcity been a weight,
  the comparator would have cheerfully produced a regret number comparing a Tier 3
  plan against a Tier 8 metric. Modelling it as a cap makes the section 14 guard
  fire on precisely the comparison that would mislead.

### 17.5 Defect — `resource_totals.csv` does not join to `resources.csv` for fluids

Found while deriving the weights, and load-bearing for anything that derives capacity
later.

    resource_totals.csv   crude_oil_nodes, crude_oil_wells, geyser
    resources.csv         crude_oil, geothermal_geyser
    water, nitrogen_gas   no row in resource_totals.csv at all

So a naive join silently drops every fluid, and a weight table built from it gives
Crude Oil, Water and Nitrogen the default — as abundant as Iron Ore, the most
abundant solid. That is what made the prototype's weighted plans lean so heavily on
oil, and the oil-heavy magnitudes in 17.1 should not be relied on. The direction of
the finding stands; those specific numbers do not.

This is the same class of join defect as P3 and P4. Not patched: it is canonical
world data, the fix is a naming decision rather than an obvious correction, and
nothing consumes the join today.

### 17.6 What exists, and what does not

Checked in the repository, 2026-09-18:

    planning_data/world/canonical/world_resource_sockets.csv    625 sockets with
                                                                east_m, north_m, elevation_m
    planning_data/world/configurations/default_502094/resource_assignments.csv
                                                                the same 625 socket ids
                                                                -> resource and purity
    planning_data/game/reference/logistics_capabilities.csv     belts, lifts, pipelines
                                                                and miners, with unlock tiers
    docs/BUILD_SURFACE_V*.md, VEHICLE_PASSABILITY_PIPELINE.md   terrain and passability

So reachable availability is a join plus the pathing machinery already in this
repository, not new research.

**Absent from `logistics_capabilities.csv`: every transport mode above a belt.** No
trucks, trains or drones. The thing that expands the horizon — and therefore the
thing that makes the map ceiling eventually real — is not modelled at all.

### 17.7 Open

- A base position. Reachable availability is a function of one, and nothing in the
  repository carries the concept. Phase 5.
- Vehicle, train and drone capability data, per 17.6.
- The fluid join, per 17.5.
- Whether per-resource weights ever return. They are not ruled out for a question
  that is genuinely about trading one resource against another at a known exchange
  rate; they are ruled out as a stand-in for locality.

---

## 18. Amendment, 2026-09-18 — tier unlock resolution, and the trap in it

Greg's call: a recipe set should come from a tech tier rather than a hand-maintained
list, because "if I'm on steel I won't have oil and plastic." Adopted, in the form
of a tier filter that **reports its own incompleteness** rather than one that looks
complete and is not.

### 18.1 What exists

    tools/progression/src/progression/unlocks.py   at_tier() -> TierUnlocks
    tests/test_progression_unlocks.py              27 tests

`at_tier(repo_root, tier, declared=())` returns the granted recipe ids, an
`AllowedRecipes` ready for `SolveRequest`, and — always — what it withheld.

**Placement.** A new sibling package, `tools/progression/`, above the adapter and
importing downward. A tech tier is a progression concept and section 6 of the
solver-selection record says the adapter never sees one, so `gamedata.py` does not
grow two more tables. This also answers, provisionally and by precedent rather than
deliberately, the open question at 11.5 about where the demand expansion module
lives. It is cheap to move now and will not be later, so it is flagged rather than
assumed settled.

### 18.2 The rule, and the trap that shaped it

    a recipe is granted at tier N when some schematic of type Milestone, Tutorial or
    Custom, with tech_tier <= N, unlocks it, and recipes.csv does not flag it as an
    alternate

The obvious rule — Milestone and Tutorial only — is wrong, and wrong in a way that
would have been hard to notice from the outside. `Recipe_IngotIron_C`,
`Recipe_IronPlate_C` and `Recipe_IronRod_C` are unlocked by "Starting Blueprints",
an **EST_Custom** schematic at tier 0. A Milestone-only filter returns a recipe set
that cannot smelt iron, and every solve against it would be infeasible or bizarre
rather than visibly broken. `test_tier_zero_can_smelt_iron` is the guard.

EST_Custom also carries cosmetics, FICSMAS and asphalt, which is harmless: nothing
targets them, so the solver never runs them.

Sanity, measured:

    tier   granted base   reachable
       0             11   iron
       3             24   iron, steel — and not plastic, rubber, motor
       4             28   "
       5             50   plastic, quickwire arrive
       9            135   Matter Conversion arrives

### 18.3 Unlock sources, measured

Every recipe in `recipes.csv` is unlocked by at least one schematic; there are no
orphans. But base recipes come from four places, not one:

    EST_Milestone    79 base    the tier ladder, ordered by tech_tier
    EST_MAM          58 base    MAM research across 53 nodes — player-driven
    EST_Custom       48 base    mixed: starting blueprints, milestone companions,
                                alternate companions, cosmetics
    EST_Tutorial      8 base    HUB upgrades, tier 0
    EST_Alternate     2 base    hard-drive schematics granting non-alternate recipes

Counts overlap. After the rule at 18.2, tier 9 grants 135 of 181 base recipes;
**the remaining 46 are reachable only through MAM research**, which a tech tier does
not imply. The report states that count on every call, and `declared` is how a
caller names what they have actually researched. Nothing infers it.

**P4 does not block this.** P4 is the slug-versus-`Recipe_*_C` join on
`alternate_recipe_unlocks.csv`. `schematic_recipe_unlocks.csv` is a different table
and keys on `recipe_id` directly — 1,016 rows, no orphans among production recipes.
Tier gating was buildable without touching P4, which had not been noticed.

### 18.4 Open item — the `is_alternate` disagreement, reconciled and corrected

The session handoff recorded the disagreement as two rows,
`Recipe_PureAluminumIngot_C` and `Recipe_Alternate_Turbofuel_C`, with
`schematic_recipe_unlocks.csv` as the authoritative check. Checked:

    Recipe_PureAluminumIngot_C     is_alternate=true    unlocked by EST_Alternate
                                   CONSISTENT — not a defect
    Recipe_Alternate_Turbofuel_C   is_alternate=false   unlocked by EST_MAM "Turbofuel"
                                   and EST_Custom "Alternate: Turbofuel"
    Recipe_PackagedTurboFuel_C     is_alternate=false   unlocked by EST_Alternate
    Recipe_UnpackageTurboFuel_C    is_alternate=false   unlocked by EST_Alternate

So the recorded pair was wrong in both halves: one of the two named rows is fine,
and two rows that were not named are defective. The actual set is three recipes,
all flagged `is_alternate=false` while being reachable only through research or hard
drives.

Not patched — `recipes.csv` is canonical reference data and changing a flag there is
a data decision with its own blast radius. Instead the filter grants them (the flag
says base) and lists them under `uncertain`, saying the tier may be overstating what
the player has. The mechanism is general: any granted recipe that is also unlocked
by a MAM or Alternate schematic is reported. It found these three without being told
about them, which is the property worth having.

### 18.5 A retrospective confirmation

"Matter Conversion" is an **EST_Milestone at tech_tier 9**. The SAM-and-Raw-Quartz
route to Copper Ingot that prompted the whole scarcity investigation at section 17
is therefore a Tier 9 capability. Its appearance in unconstrained early solves was a
progression artefact, not a valuation failure — which is what 17.2 argued from
structure and this now shows from the data.

It also means the tier filter removes that route from early-game answers for free,
with no weighting and no cap.

### 18.6 What this deliberately is not

    does       resolve a tier into a recipe set; report what it withheld
    does not   walk schematic_dependencies.csv, or infer one unlock from another
    does not   choose which schematics to pursue, or value them
    does not   know what a hard drive is

Two tests hold the line: one asserts the module contains no reference to
`schematic_dependencies.csv` or `alternate_recipe_unlocks.csv` in code (checked
against string literals, since the docstring names them in order to disclaim them),
and one asserts by AST that no adapter module imports `progression`.

The moment this needs the dependency graph to answer a question, it has become plan
section 17's Phase 3 deliverable "unlocked-recipe candidate generation", and should
be moved there deliberately rather than by growth.

### 18.7 Open

- The 46 MAM-only recipes have no declaration convenience. Naming them one id at a
  time is workable now and will not scale; a research-node-level declaration
  ("Quartz done", "Caterium done") is the obvious next shape and needs the MAM
  schematic ids, which this module does not currently expose.
- Whether `tools/progression/` is where the demand expansion module belongs, per
  18.1.
- Whether the three `is_alternate=false` research-gated recipes should be corrected
  in `recipes.csv` rather than reported, per 18.4.
- No CLI yet. The shape settled with Greg is one entry point with two subcommands,
  `solve` and `compare`, since costing and comparing are the only two operations and
  multi-target and multi-axis are parameters rather than separate tools.

---

## 19. Amendment, 2026-09-18 — the hard-drive pool, and P4 resolved

Greg's reframe, and it changes what the tool is for: the recipe set should be what
is **obtainable**, not what is **held**. An alternate sitting in the hard-drive pool
is something you can go and get, so a plan that uses one is actionable. Whether you
have pulled it yet is a separate question, and mostly a to-do.

### 19.1 What exists

    tools/progression/src/progression/pool.py    available_at() -> PoolAvailability
    tests/test_progression_pool.py               26 tests

`unlocks.at_tier` gains `include_pool=False`. Default off, because it changes what
the returned set *means* and no existing caller asked for a wider one.

### 19.2 P4 is resolved

The session handoff has carried P4 since it was written: `alternate_recipe_unlocks.csv`
keys on slugs (`cast_screws`) while `recipes.csv` uses `Recipe_Alternate_Screw_C`,
and that gap was recorded as blocking progression-gated recipe sets.

It resolves on normalised display names. The unlock table's `recipe_name` is
"Cast Screws"; the recipe's `display_name` is "Alternate: Cast Screws". Strip the
prefix, compare alphanumerics only: **79 of 79 rows matched, nothing ambiguous,
nothing unmatched.** `resolve_slugs` raises on any failure rather than dropping a
row, so a future game build that breaks the match fails loudly instead of quietly
shrinking the pool.

P4 was recorded as a Phase 3 blocker. It was one join.

### 19.3 Defect — `alternate_choices.csv`'s progression columns are unusable

This table looks like the better source and was briefly treated as such in session.
It keys on `recipe_ids` directly — 109 ids, no orphans — and carries `tech_tier` and
`dependency_schematic_ids`. The ids are sound. The progression columns are not:

    dependency_schematic_ids   98 of 107 recipe rows carry truncated fragments:
                               '1_C', '2_C', '4_C', '5_C', and values such as
                               'Research_Quartz_1_1_C;4_C'
    tech_tier                  places 71 alternates at tier 0 while marking every
                               one of them dependency-gated, which cannot be true —
                               there is no MAM at tier 0

Not patched: it is canonical reference data, the fragments are a loss rather than a
mistake to invert, and the correct values are not recoverable from what remains.
`pool.py` does not read it, and a test asserts so, because reading it would look
like an upgrade over the slug join and would silently be wrong.

### 19.4 Scope — automatic entry only, and why MAM is deliberately excluded

Every row in `alternate_recipe_unlocks.csv` carries
`eligibility_type: automatic_hub` — 79 alternates that enter the pool on reaching a
tier band, with no research. Bands come from `progression_clusters.csv`, six of them
in `sort_order`; the band's top tier is read off the identifier (`tier_3_4` -> 4,
`pre_tier_1_2` -> 0) and `resolve_clusters` asserts the result is monotonic in
`sort_order`, which is what keeps that from being a guess.

    tier   obtainable   in later bands   research-gated
       0            2               77               31
       2            6               73               31
       4           24               55               31
       9           79                0               31

The remaining 31 alternates enter the pool only through MAM research, and are
reported as unaccounted rather than modelled. Greg's reasoning, which is the
substance of the exclusion:

> those will need to be an additional layer that acts, in the early stages, as a
> hold suggestion — to not contaminate the pool while the numbers are still low.
> Later it won't matter.

MAM research *widens* the pool. Early, with few drives found, a wider pool costs odds
on the specific recipes still wanted; late, with most of them held, dilution stops
mattering. So a MAM node has a **negative** expected value early and a neutral one
later. That is an advisory about run state — drives found, drives remaining — not a
property of a recipe, and it cannot be a filter: it never changes what is reachable,
only what it costs to reach.

`mam_pool_effects.csv` already carries the raw material for it, in prose:
`hard_drive_pool_effect_text` per research node, with `planning_note_text` entries
like "Safe with respect to Hard Drive pool" and "Major early pool-expansion point".
Turning that into an advisory is a real piece of work and belongs with run state,
which is Phase 4. Recorded, not built.

### 19.5 The first non-obvious answer

Smart Plating 1/min at tier 2, held-only versus reaching into the pool:

    held only    23.2500 iron                        26.0500 MW
    pool          9.3333 iron + 7.3333 copper        17.4644 MW

Iron drops 60%, power drops 33%, at the cost of 7.33 copper/min. The solver takes
Cast Screws, Stitched Iron Plate and Copper Rotor.

**It does not take Iron Wire** — which section 16 measured as worth 3.30 ore/min when
paired with Stitched Iron Plate alone. Once Copper Rotor puts copper in the chain
anyway, Iron Wire's entire argument, getting the copper back out, evaporates.

That is 16.2 arriving a second time from a different direction, and more sharply:
the pairwise analysis at section 16 was itself too narrow. An alternate's value is a
property of the whole enabled set, and even a two-alternate comparison can mislead
about a six-alternate pool. Anything in Phase 3 that ranks alternates — pairwise or
singly — will reproduce this error.

### 19.6 Open

- The MAM pool-dilution advisory, per 19.4. Needs drives found and drives remaining,
  so it is Phase 4 and it is genuinely useful there.
- `alternate_choices.csv`'s dependency column, per 19.3 — whether it can be
  regenerated from the game docs rather than repaired.
- Whether `include_pool` should become the default once a CLI exists. It is the more
  useful question to ask, and the less useful one to ask silently.

---

## 20. Amendment, 2026-09-18 — the command line, and Iron Wire corrected

### 20.1 What exists

    tools/production_cli.py          three subcommands
    tests/test_production_cli.py     29 tests

    tiers     what a tier grants, what it withholds, and --find to look up an id
    solve     plan a target
    compare   two or more configurations side by side

**Placement.** A standalone script at `tools/` root, beside
`check_game_docs_provenance.py` and `regenerate_manifests.py`, which is this
repository's convention for runnable things. It is not inside either package
because `solve` and `compare` are adapter operations while `--tier` is a
progression concept: an entry point inside `production_adapter` would have to
import `progression`, inverting the direction the boundary exists to protect. It
sets up `sys.path` itself, since the repo is not installed and a user has no
`conftest.py`.

**What it refuses.** Four arguments exist purely to be rejected, each naming the
phase that owns the question:

    --by, --deadline    scheduling is Phase 2 — nothing in this model knows time
    --inventory         existing stock is Phase 4; existing_inventory already raises
    --what-next         needs run state; Phase 4

A tool that answers production questions at a prompt will be asked progression
questions. Declining by name is the structural version of the guardrail; answering
approximately is how it would drift.

`--pool` is opt-in rather than default, matching `include_pool` at 19.1. The
completeness report prints above every `solve`, so the withheld counts are never
absent from an answer a player acts on.

### 20.2 Iron Wire is never selected — and section 16 overstated it

Running the tier-2 pool raised Greg's question: the solver takes Stitched Iron
Plate but not Iron Wire, which section 16 presented as its natural partner.

It is never selected, and not because of Copper Rotor:

    full tier-2 pool            7.3333 copper +  9.3333 iron   17.4644 MW
    pool minus Copper Rotor     3.3333 copper + 16.2500 iron   21.4167 MW

Neither takes it. The arithmetic:

    Copper Wire    15.0 Copper Ingot -> 30.0 Wire    0.5000 ingot per wire
    Iron Wire      12.5 Iron Ingot   -> 22.5 Wire    0.5556 ingot per wire

Both ingots are one ore each, so copper wire is strictly cheaper per wire in raw
ore. **Iron Wire cannot win against an objective that prices one copper ore at one
iron ore.**

Section 16.1's figures are correct but its framing was not. It compared
stitched-plus-iron-wire against *baseline* and reported 3.30 ore/min saved, which is
true. Against stitched *alone* it is worse on total raw: 19.95 versus 16.25 + 3.33 =
19.58. Iron Wire's benefit was never a raw-total benefit; it was avoiding copper.
Section 16 said so — "the pair is 3.30 ore/min and 2.12 MW cheaper than baseline, on
iron alone" — but reading that as a recommendation over stitched-alone would be
wrong, and the tier-2 solve makes the error visible.

### 20.3 The consequence: this is section 17's question, on a first-hour decision

Re-running the tier-2 pool under the scarcity weights section 17 derived and
rejected (copper 2.50, iron 1.00, from purity-weighted node counts):

    unweighted           7.3333 copper +  9.3333 iron    Iron Wire chosen: no
    scarcity-weighted    4.0000 copper + 13.0370 iron    Iron Wire chosen: yes

So whether Iron Wire is worth taking *is* the per-resource valuation question, and
it lands on a decision a player faces in the first hours rather than in some late
edge case.

That does not reopen 17's disposition — a map-wide weight is still the wrong shape
for a quantity that starts local and expands with transport. What it does is raise
the cost of 17's conclusion: until reachable availability exists (Phase 5), the tool
will systematically prefer whichever resource is nearer to hand in *ore terms*, and
that will sometimes disagree with how the resource is actually valued in a run.

Greg's observation that this plan does not match community consensus is consistent
with exactly that: a player weighing copper above iron early — fewer nodes, and iron
is usually running first — would reach a different answer, and would be applying a
valuation the model has deliberately declined to make.

**Recorded as a known divergence, not a defect.** The model's answer is correct
under its stated assumption. The assumption is visible, is recorded at 7.4 and 17,
and is not yet resolvable.

### 20.4 Open

- Nothing new. 17.7's open items are what would close 20.3, and they are unchanged.
- The CLI has no `--weights` beyond four named presets, deliberately: arbitrary
  weight tuples belong in a script rather than an argument parser, and the named
  ones are the Pareto corners section 3.4 of the selection record sweeps.
