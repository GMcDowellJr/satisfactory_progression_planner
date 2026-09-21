# Demand Expansion Scope and Site Capacity — Decision Record

- Date: 2026-09-19
- Supersedes, forward-only: nothing wholesale. Extends `docs/plans/progression_optimizer_implementation_plan.md`
  §10 / §17 Phase 2 in scope and adds a spatial dimension it does not carry.
  Neither the plan nor `session-handoff-2026-09-18.md` is edited.
- Intended home: `docs/decisions/` in `satisfactory_progression_planner`.

> **Provenance.** Reasoning developed in conversation on 2026-09-19; every factual
> claim below was then checked against the repo at
> `C:\Users\Greg\source\repos\satisfactory_progression_planner` in the same session.
> Files read: `docs/plans/progression_optimizer_implementation_plan.md`,
> `docs/decisions/production_lp_formulation.md` §11, `tools/production_cli.py`, and
> the reference tables named in section 8. **A first draft of this record, written
> before repo access, asserted a supersession that the plan does not support; see
> section 1.2.** Numbers below are computed from the reference layer and the
> computation is stated so it can be re-run.
>
> **Committed to `docs/decisions/` on 2026-09-19. This repo copy is the source of
> record and is immutable from here.** Corrections go forward-only, in a successor
> document or a dated amendment section appended below — never by editing what is
> above. The claude.ai Project copy is a derivative snapshot from this point on.
>
> The session handoff is refreshed separately and freely: it is a status document,
> current-state and replaceable, which is the opposite of this file.

---

## State

    decision_status: NEW — extends Phase 2 scope; no phase renumbering
    locked: the game states totals, not rates (section 2, verified)
    locked: demand partitions into bounded/canonical and unbounded/discretionary
            (section 3, quantified)
    locked: layout geometry, module activation and running machines are three
            separate commitments with different reversibility (section 4)
    locked: geometry reserves AREA and TRUNK THROUGHPUT, never machine
            identity — a recipe swap changes the mix (section 4.2)
    locked: the sink bound is reported as a fill time, never as a machine
            ceiling (section 4.1)
    locked: NO player-time parameters. Build time and away time are both
            residuals of how the player plays (section 9)
    locked: a site's design tier is bounded by near-term unlocks, not node
            saturation (section 5, unlock table verified)
    locked: module gates are of two kinds — scheduled (tier) and conditional
            (recipe holding). The plan is a condition set, not a sequence
            (section 5.4)
    locked: alternates are REPORTED, never ordered — ranking them reproduces
            the set-valued defect at LP §16.2 (section 5.5)
    locked: demand expansion expands DECLARED requirements only — the caller names
            the scope; the module never selects it (section 6, LP record §11.3)
    locked: design-tier lookahead is DECLARED, in progression clusters; the
            derived form is reportable but never the default (section 8.1)
    locked: construction overhead is a geometric rule over buildings.csv, not
            a scalar factor (section 8.2)
    locked: module sequencing is Phase 2; spatial realization defers to world
            integration (section 8.4)
    locked: curated recipe set = base minus Unpackage, Converter and the three
            is_alternate-defect recipes. 159 of 181 (3.1.1)
    locked: section 3's totals are LOWER BOUNDS within a 1.08x band; the
            residual three ambiguities are structural and immaterial (3.1.2)
    locked: the three scenario modifiers are NOT commensurate — power is not
            material at all, and which of the other two dominates depends on
            position in the option sets. No ordering is admissible (3.3)
    locked: settings are discrete, asymmetrically capped, and NEW GAME ONLY,
            so a scenario is a per-save constant (3.2.1)
    locked: axis nomenclature — ore grade / order book / utility load, named
            per LEVEL not per combination. A run is a triple, never one
            label. Identifiers, not a ranking (3.3.1)
    locked: SCENARIOS ROUND. scenario.py must apply the multiplier to
            per-cycle amounts, nearest integer, per input. Contract-shaped:
            apply_input_rate takes a rate and cannot express it (3.2.5)
    locked: nearest-integer confirmed IN GAME at 1.25x, both directions,
            per-input — 1 stays 1, 3 becomes 4, 12 becomes 15 (3.2.4)
    locked: the rounding rule is NOT in the shipped game data — en-US.json
            grepped, zero hits. It lives in compiled runtime code (3.2.3)
    locked: fluids are NOT exempt from rounding — from the 1.2.3.0 liquid bug.
            Unobserved in game; Plastic not unlocked on that save (3.2.3-4)
    locked: 66,423 for the scenario of record is IDENTICAL under all four
            rounding variants. The open details do not affect it (3.2.3)
    open:   sub-1x settings (0.25, 0.50) still diverge under the floor
            assumption; figures at those settings stay open (3.2.3)
    closed: game_builds.csv now records game_version 1.2.4.0 and build_number
            502094 (CL). After 1.2.3.0, so this install has the fixed liquid
            rounding. CL matches the terrain build already cited (3.2.4)
    closed: five buildings.csv footprint rows applied 2026-09-19; all eleven
            producers now carry a footprint (section 8.2)
    closed: re-derivation through scenario.py — faithful to the repo, which
            is not faithful to the game (3.2, 3.2.2)
    withdrawn: the CLI refusal-string defect asserted in the first draft (section 7.1)

    scenario of record for worked examples: MARGINAL - PEAK DEMAND -
    DEBOTTLENECK (1.25 recipe / 2x power / 2x Project Assembly), single-player,
    game 1.2.4.0 CL#502094. Named per 3.3.1.

---

## 1. What this changes, and what it does not

### 1.1 What is new

Plan §10 specifies a Project Assembly backward scheduler over a user-declared
completion horizon, with production windows staggered by unlock progression. Three
things sit outside it:

1. **A spatial dimension.** §10 is purely temporal. It has no concept of a site, a
   node set, a footprint, or a logistics ceiling. Sections 4 and 5 add one.
2. **The sink bound.** §10 sizes to a target and a horizon. It does not model the
   fact that a line feeding a container has a finite total output equal to that
   container. Section 4.1.
3. **The inverted report.** §10 step 5 converts a target into a required rate.
   The reverse — given a rate, how long until canonical demand is satisfied — is a
   different and, for the sizing question, more useful statistic. Section 2.

And one change of scope: §10 step 1 reads *Project Assembly requirements through
Phase 5*. Section 6 widens the demand set beyond Project Assembly.

### 1.2 What the first draft got wrong, recorded because it is the same failure twice

The pre-repo draft asserted that the Phase 2 framing "rests on an assumption nobody
tested: that a deadline exists."

**The plan makes no such assumption.** §10's worked example reads:

    Phase 2 completion horizon: 240 min
    Smart Plating:
      available at t = 0
      remaining quantity = X
      required rate = X / 240

The horizon is declared by the user, and §10 step 5 says so explicitly — "convert
the *user's* target into required item/min rates." The plan was already in the
declare-a-duration form that the conversation reconstructed from first principles.

The handoff's process-defect note warns against moving a number without measuring
it. This was the same failure applied to a framing: a claim about a document was
carried into a record without reading the document. Caught before commit; recorded
because the catch was luck, not process.

What the conversation actually contributed is an *interpretation* of that horizon —
that the useful value for it is the player's away interval — not the discovery that
it was declared.

## 2. The game states totals, not rates

Verified. `project_assembly_requirements.csv` carries `quantity_default_1x`;
`schematic_costs.csv` carries `amount`. Neither is a rate. `contracts.OutputTarget`
carries `rate_per_min` and raises if it is <= 0, which is the quantity/rate gap
already recorded at LP record §11.4.

A rate exists only as total ÷ a duration the player chose.

Two consequences:

1. "Is N per minute a reasonable target" is not answerable as posed.
2. The answerable inverse requires no forecasting:

       at rate R, all remaining canonical demand for item X is satisfied in time T

   The tool emits T. It does not emit a recommended R — that would be an opinion
   about how the player should spend their time.

## 3. Bounded and unbounded demand, quantified

    bounded / canonical        project_assembly_requirements.csv
                               schematic_costs.csv (milestones + MAM research)
                               construction parts for a declared set of buildings
                               -> finite, summable from the reference layer today

    unbounded / discretionary  how large a factory the player wants
                               the AWESOME Sink, infinite appetite
                               -> not a demand; an ambition, with no correct value

**Worked case — Modular Frame, the item behind the "300/min" community target.**
Expanding every Space Elevator phase and every schematic and MAM research cost to
base Modular Frame units, at 1x requirements, base (non-alternate) recipes:

    Space Elevator, all 5 phases        18,945
    Schematic + MAM research costs       8,310
                                        ------
    bounded lifetime demand              27,255

    at 300/min   satisfied in    91 min   (1.5 h)
    at  60/min   satisfied in   454 min   (7.6 h)
    at  10/min   satisfied in 2,726 min  (45.4 h)
    at   2/min   satisfied in       227 h

300/min clears the entire game's canonical Modular Frame requirement in about an
hour and a half. It is not a progression target; it is an answer to the unbounded
question. The same holds for the "1,000 screws/min" class of figure.

Cross-check on the secondary source that prompted this: a video cited one Modular
Engine machine at 1/min needing ~8 hours for 500 units. `project_assembly_requirements.csv`
gives Phase 3 Modular Engine = 500. The arithmetic is exact.

### 3.1 The figures above are a LOWER BOUND, not a total — corrected 2026-09-19

The expansion required choosing a producing recipe where several non-alternate
recipes produce the same item. `tests/_demand_oracle.py` **raises `AmbiguousDemand`
rather than choosing**, by design, and its docstring is explicit that base-only is
not unambiguous: "every Space Elevator part above Adaptive Control Unit raises… a
late-game fixed-recipe case therefore needs a curated `allowed_recipes` set."

An earlier revision of this section said the Modular Frame path runs through fixed
recipes and the figure was "probably insensitive" to those choices, flagged as an
inference. **The inference was wrong.** Tested by computing set-valued Modular Frame
content per unit across every base-vs-base combination: of 108 target items, six
depend materially on an ambiguous choice.

    Ballistic Warp Drive      7.5  .. 17.5   MF per unit
    Crystal Shard             0    ..  0.5
    Aluminum Casing           0    ..  0.3
    Compacted Coal            0    ..  0.25
    Turbofuel                 0    ..  0.2
    Empty Gas Tank            0    ..  0.0625

Propagated to totals, by set-valued computation over the whole base-recipe space:

    1x bounded total    27,255 .. 29,695      spread 1.09x

**A looser figure was recorded briefly and is withdrawn.** An intermediate pass
propagated independent per-item min/max, which permits inconsistent choices across
branches and reported 27,255 .. 42,335. The set-valued computation is the sound one.
Corrected within the same session; noted because the arithmetic looked authoritative
either way.

### 3.1.1 The curated set — three mechanical exclusions

Rather than pick routes by taste, three exclusion rules, each with a stated reason:

    12 Unpackage recipes   reversals, not production routes. They create cycles
                           and spurious producers for every packaged fluid.
    9 Converter recipes    Recipe_Coal_Iron_C, Recipe_Iron_Limestone_C and kin
                           make raw resources from other raws plus SAM. Tier 9
                           routing options, never a default production path.
                           This is LP §13.4 / §16.3 seen from the demand side.
    3 is_alternate defect  Recipe_Alternate_Turbofuel_C, Recipe_PackagedTurboFuel_C,
                           Recipe_UnpackageTurboFuel_C — flagged base while
                           research- or drive-gated, per handoff §18.4.

    181 base recipes - 22 excluded = 159 curated

Effect: ambiguous targets fall from six to three, and the 1x bound tightens to
**27,255 .. 29,364 (1.08x)**.

### 3.1.2 The residual three — not arbitrary, and small

What remains is structural rather than a coin-flip, which is why it is recorded
rather than pinned:

    Compacted Coal     has NO direct base producer. The direct recipe
                       (Recipe_Alternate_EnrichedCoal_C) is an alternate, so
                       base-only reaches it solely as a byproduct of Rocket Fuel
                       and Ionized Fuel. This is the byproduct-feedback case the
                       oracle is already known-invalid for (§15.3).
    Power Shard        four legitimate routes — three slug colours plus Synthetic
                       Power Shard. Which a player has is genuinely run-dependent,
                       not a modelling choice.
    Ballistic Warp Drive  single recipe; inherits both through Dark Matter Crystal,
                       Singularity Cell and Superposition Oscillator.

Pinning Compacted Coal to its direct alternate was tried and rejected: admitting one
alternate opened a new branch at Superposition Oscillator, trading three ambiguities
for three others. The curated set stops at the three mechanical rules.

**The residual moves the total by under 8%, and no conclusion in this document turns
on it.** A run-specific pin belongs in the caller's `allowed_recipes`, which is
exactly the mechanism the oracle's docstring prescribes.

**Consequences, all of them load-bearing:**

1. The 27,255 / 92,598 figures are the **minimum** over base choices. They coincide
   with first-non-alternate by luck, not method.
2. No single total is derivable from "base recipes only." A curated
   `allowed_recipes` set pinning at least the six items above is required, and that
   curation is a **decision to record**, not a derivation.
3. Section 2's claim survives unharmed and is in fact strengthened: 300/min clears
   even the 42,335 upper bound at 1x in 2.4 hours.
4. Recorded as process: this is the second claim in this document to be carried
   forward as "probably" and then falsified by running the check. Both were caught
   only because the check was eventually run.

### 3.2 The same case under the scenario of record

Greg's current run: **1.25x recipe cost, 2x power, 2x Project Assembly,
single-player.** Recipe multiplier applied to recipe inputs at each expansion stage
(compounding, per the documented behavior — inputs scale, outputs do not), Project
Assembly multiplier to elevator quantities, schematic amounts unscaled:

                              1x        scenario of record
    elevator              18,945                    81,315
    schematics + MAM       8,310                    11,283
    bounded total         27,255                    92,598

    at 300/min               1.5 h                     5.1 h
    at  60/min               7.6 h                    25.7 h
    at  10/min              45.4 h                   154.3 h

3.4x overall: 2x from the Project Assembly setting, the remainder from 1.25
compounding across roughly 3.4 stages on average between Modular Frame and the
elevator parts.

**This is why the tool computes T rather than anyone holding an intuition.** At 1x,
300/min is plainly absurd for progression. Under the scenario of record it is merely
fast. Neither judgement survives a change of scenario — and the feasibility guard
already forbids pricing one scenario against another, so T is describable per
scenario and never comparable across them.

**Re-derived through `scenario.py`, 2026-09-19 — discharged.** The figures above
were recomputed importing the repo's own `Scenario` class and calling
`apply_input_rate` and `apply_project_assembly_quantity` rather than this session's
arithmetic. Identical to the digit. The multiplier half of the caveat is closed; the
ambiguity half (3.1) is not, so these remain lower bounds.

One finding from reading it: the repo's named preset `CHALLENGE_1_25X_2X` carries
`project_assembly_requirement_multiplier=1.0`. **The scenario of record is not that
preset** — it is 1.25 / 2.0 / 2.0. Worth a named constant of its own if these
worked examples are to be reproducible.

### 3.2.1 The settings are discrete, capped asymmetrically, and fixed at world creation

Supplied by Greg, 2026-09-19, from the game's custom-settings documentation. **Not
independently verified against a primary source in this session** — recorded as his
statement of game behaviour, which is authoritative for this project but is not a
repo or wiki citation.

    Space Elevator deliverable   0.25 0.50 0.75 1 2 5 10 25 50 100
    Recipe parts cost            0.25 0.50 0.75 1 1.25 1.50 1.75 2
    Power consumption            0.25 0.50 0.75 1 2 5

Three consequences.

**The axes are capped asymmetrically.** Space Elevator reaches 100x; recipe parts
stop at 2x; power stops at 5x. Any treatment of them as a common scale is wrong on
range before it is wrong on kind (3.3).

**Sub-1x settings exist.** An earlier revision assumed 1x was the floor and said the
permitted range had not been checked. It is not the floor.

**New Game Only.** The settings are fixed at world generation and cannot be changed
on that save. So a scenario is a *per-save constant*, and comparing two scenarios is
comparing two different playthroughs. The feasibility guard — weights are comparable,
scenarios are not — stops being a modelling convention here and becomes a statement
about the world: there is no run in which both values were observed.

### 3.2.2 Integer rounding — `scenario.py` does not model it, and it is large

Greg's source also states: *recipe costs are rounded to the nearest whole integer,
which can occasionally cause lower-tier adjustments to feel harsher or inconsistent
at specific step values like 1.25x or 1.5x.*

`scenario.py.apply_input_rate` returns `rate_per_min * multiplier`. It neither rounds
nor operates at a granularity where rounding is expressible — per-cycle integer item
counts are where the game rounds, and the adapter applies the multiplier to rates.

Modelled by applying the multiplier to `amount_per_cycle` for `unit == items`,
rounding to nearest, with a floor of 1:

    recipe    unrounded    rounded     delta
      0.25        2,978      6,824    +129.2%
      0.50        6,396     14,522    +127.0%
      0.75       13,491     22,331     +65.5%
      1.00       27,255     27,255       0.0%
      1.25       51,941     38,069     -26.7%
      1.50       93,375    182,753     +95.7%
      1.75      159,358    231,729     +45.4%
      2.00      260,145    260,145       0.0%

The mechanism is visible in the shape: at 1.25x an input of 1 rounds back to 1, and
most early recipes are full of 1s, so the real cost lands *below* linear. At 1.50x
every 1 becomes 2, so it lands far above. This is exactly the "harsher or
inconsistent at 1.25x or 1.5x" the source describes, and it is monotonic but wildly
unevenly spaced — 1.25 → 1.50 is a 4.8x step, 1.50 → 1.75 only 1.27x.

**Effect on the scenario of record: 92,598 becomes 66,423, about 28% lower.** Every
figure in 3, 3.2 and 3.3 is an unrounded figure and overstates or understates
accordingly.

### 3.2.3 Checking the rounding rule against the game files — and what that settles

**The rule is not in the shipped game data.** Checked directly: the repo's pinned
`en-US.json` snapshot (`planning_data/game/source_snapshots/docs_a81d250e96aa/`,
sha256 `a81d250e96aa…`, 5.2M characters) contains zero occurrences of
`AdvancedGameSettings`, `GameSetting` or `RoundTo`. Its 1,197 `Multiplier` hits are
unrelated gameplay fields — `mWeaponDamageMultiplier`, `mHoverSprintMultiplier`,
`mChargeRateMultiplier`, `mFluidStackSizeMultiplier` and kin. The only cost-shaped
one is `mBuiltWithPipelineCostMultiplier`, a building field, not the game setting.
Docs.json is the 1x recipe database; the multiplier and its rounding live in compiled
runtime code. **No file in the repo or in the game's shipped docs can establish this
rule.**

Wiki evidence, `satisfactory.wiki.gg/wiki/New_game`, retrieved 2026-09-19, which
also confirms the option sets in 3.2.1 independently of Greg's paste:

> Values are rounded up or down to next whole number.

Nearest-integer confirmed. And from Patch 1.2.3.0:

> Fixed Recipe Cost Multiplier for x1.75 setting all the recipe costs to 0 for liquids

That kills two assumptions this document made: **fluids are not exempt** — the code
scales and rounds them, which is how they could reach zero — and **a floor of 1 was
not universal**, at least before the fix.

**Version gap, recorded.** `game_builds.csv` carries no `game_version` and no
`build_number` — "No embedded game version/build number; SHA-256 is the canonical
provenance key." So the reference layer cannot say whether its pin sits before or
after 1.2.3.0. For a rule that changed in that patch, the sha256 pin identifies the
data but not the behaviour.

**What that uncertainty actually costs — nothing, here.** Recomputed under all four
combinations of the unresolved details:

    variant                       0.75x     1.00x     1.25x     1.50x    SoR
    A items only, no floor       22,331    27,255    38,069   182,753   66,423
    B items only, floor 1        22,331    27,255    38,069   182,753   66,423
    C items+fluids, no floor     22,331    27,255    38,069   182,753   66,423
    D items+fluids, floor 1      22,331    27,255    38,069   182,753   66,423
      no rounding at all         13,491    27,255    51,941    93,375   92,598

Identical to the unit. On the Modular Frame paths no input rounds below 1, so the
floor never binds, and no fluid lies between a Modular Frame and a raw resource, so
fluid treatment is irrelevant. **66,423 for the scenario of record is robust to every
open question about the rule.** What is *not* robust is the difference between
rounding and not rounding, which is the defect above.

Two scope limits on that robustness:

    - it is specific to Modular Frame. A fluid-heavy target — plastic, rubber,
      fuel — would separate variants C and D from A and B.
    - the sub-1x settings (0.25, 0.50) were not included above and DO diverge
      under the floor assumption. Any figure at those settings stays open.

### 3.2.4 Observed in game, 2026-09-19 — the rule is confirmed for solids

Read by Greg from a live 1.25x save, version **1.2.4.0 CL#502094**:

    recipe          1x            observed at 1.25x     unrounded    verdict
    Smart Plating   1 Reinforced Iron Plate   1              1.25     rounds DOWN
                    1 Rotor                   1              1.25     rounds DOWN
    Modular Frame   3 Reinforced Iron Plate   4              3.75     rounds UP
                    12 Iron Rod              15             15        exact, control

**Nearest-integer confirmed empirically**, in both directions, on the same save the
worked examples describe. The control row moving by exactly its unrounded value rules
out any per-recipe or per-stage rounding — it is per-input.

Still open: **fluids.** Plastic is not unlocked on that save, so the m3 case was not
observed. The floor question is also unobserved, but it cannot bind at multipliers
>= 1x, so it only affects the sub-1x settings.

**The version resolves the behaviour question.** 1.2.4.0 is after patch 1.2.3.0,
which fixed the Recipe Cost Multiplier zeroing liquid costs at 1.75x. This install
therefore carries the fixed behaviour, and `game_builds.csv` now records
`game_version` and `build_number` so a future session can tell. CL#502094 also
matches the build the terrain data already cites, so the reference layer and the
spatial layer are from one build — previously assumed, now checked.

### 3.2.5 Decision: scenarios round

**Adopted, 2026-09-19.** `scenario.py` models the game's rounding.

    apply to   amount_per_cycle, per input
    rounding   nearest integer, half away from zero
    scope      solids confirmed (3.2.4); fluids to follow the same rule until
               observed otherwise, since 1.2.3.0 establishes the code scales them
    floor      unresolved; cannot bind at >= 1x, so it gates only sub-1x settings

This is not a one-line change to `apply_input_rate`. That method takes
`rate_per_min`, and rounding is not expressible on a rate — the multiplier has to
move to per-cycle amounts, which means the transform point moves and
`apply_input_rate` either changes signature or is replaced. Contract-shaped, and it
belongs in the transform layer where the scenario is already applied, not in the
solver.

Consequence for every figure in this document: the rounded column of 3.2.2 is the
one that describes the game. The unrounded column describes the adapter as it stands
today and is retained only to size the defect.

### 3.3 The three modifiers are not commensurate

Gridded over the curated set. Bounded Modular Frame demand, relative to 1x:

    recipe   PA 1.0   PA 2.0   PA 3.0
      1.00     1.00     1.70     2.39
      1.25     1.91     3.40     4.89
      1.50     3.43     6.31     9.19
      2.00     9.54    18.22    26.90

Three properties, each with a consequence:

1. **`machine_power_multiplier` has no material effect at all.** Verified: demand at
   power 1x and power 4x is identical to the unit. It moves the power report and
   nothing else. Any presentation that treats the three settings as one difficulty
   dial is wrong on this axis.
2. **`project_assembly_requirement_multiplier` is sub-linear on the total.** 1x → 2x
   gives 1.70x, not 2.00x, because schematic and MAM costs do not scale with it.
3. **`recipe_input_multiplier` is strongly superlinear** — 1.25 alone is 1.91x, 2.0
   alone is 9.54x, consistent with compounding across roughly three stages.

**Consequence for the scenario of record — stated too broadly in an earlier
revision.** Unrounded, of its 3.40x the recipe setting contributes 1.91x and the
Project Assembly setting the remainder, and that was written up as "the setting that
sounds milder is the larger lever." **That holds at these two values and nowhere
else.** Across the real ranges of 3.2.1 the ordering reverses: recipe parts caps at
2x (260,145 unrounded) while Space Elevator reaches 100x (2,845,115 with rounding at
recipe 1.25) — an order of magnitude beyond anything the recipe axis can reach.

Rounded, at recipe 1.25 the Space Elevator axis alone gives:

    SE   0.25x       16,804        4.7 h @ 60/min
    SE   1.00x       38,069       10.6 h
    SE   2.00x       66,423       18.5 h     <- scenario of record
    SE   5.00x      151,485       42.1 h
    SE  10.00x      293,255       81.5 h
    SE 100.00x    2,845,115      790.3 h

The honest general statement is the negative one: **which axis dominates depends on
where you are in the option sets, and no ordering over combinations is admissible.**

### 3.3.1 Axis nomenclature

480 combinations (10 x 8 x 6). Naming them individually is not possible and naming
them as a single difficulty ladder is not admissible (above). Each *level* on each
axis carries a name instead, and a run is named by the triple. Figures are bounded
Modular Frame demand with the other axes held at 1x, curated set, rounded.

**Recipe parts cost — ore grade.** More input per unit out is a poorer grade, which
is what the mineral-processing vocabulary already describes.

    0.25x  Bonanza            1,935    0.07x
    0.50x  High Grade        14,522    0.53x
    0.75x  Mill Grade        22,331    0.82x
    1.00x  Head Grade        27,255    1.00x
    1.25x  Marginal          38,069    1.40x
    1.50x  Low Grade        182,753    6.71x
    1.75x  Cut-off          231,729    8.50x
    2.00x  Tailings         260,145    9.54x

**Space Elevator deliverable — order book.** Escalating volume commitments.

    0.25x  Bench Scale       13,046    0.48x
    0.50x  Pilot Lot         17,782    0.65x
    0.75x  Pre-Production    22,519    0.83x
    1.00x  Nameplate         27,255    1.00x
    2.00x  Debottleneck      46,200    1.70x
    5.00x  Uprate           103,035    3.78x
     10x   Second Train     197,760    7.26x
     25x   Brownfield       481,935   17.68x
     50x   Greenfield       955,560   35.06x
    100x   Megaproject    1,902,810   69.82x

**Power consumption — utility load.** Every level is 27,255. No material effect.

    0.25x  Off-Peak
    0.50x  Base Load
    0.75x  Firm Load
    1.00x  Contract Demand
    2.00x  Peak Demand
    5.00x  Curtailment

    scenario of record   Marginal - Peak Demand - Debottleneck     66,423   2.44x
    all lowest           Bonanza - Off-Peak - Bench Scale           1,935   0.07x
    all highest          Tailings - Curtailment - Megaproject  23,679,585    869x

Two things the per-level view shows that named corners did not:

- **The ore-grade axis has a cliff, not a slope.** Marginal to Low Grade is 1.40x to
  6.71x for one notch. That is the integer rounding of 3.2.2 surfacing as a step
  change — at 1.25x an input of 1 rounds back to 1, at 1.50x it becomes 2.
- **The triple is the only honest name.** Off-Peak and Curtailment are the same
  number of Modular Frames. Any single label collapsing all three axes misrepresents
  at least one of them.

These are identifiers for describing a save, not a ranking, and nothing in the
tooling should sort or compare by them.

**Consequence for naming or ordering scenarios.** Because the axes differ in kind —
one material and superlinear, one material and sub-linear, one not material at all —
any single ordering over combinations asserts a commensurability that does not exist.
This is the feasibility guard arriving from a new direction: scenarios may be
described, never priced against each other. Labels for identification are fine; a
difficulty ladder is not.

## 4. Sizing is three commitments, not one

    layout geometry        reserved AREA and TRUNK THROUGHPUT — not machine
                           identity (4.2); committed at the site's DESIGN TIER
                           expensive, effectively irreversible

    module activation      which modules are switched on
                           gated by UNLOCK EVENTS, not elapsed time (5.4)
                           moderate cost

    machines running now   fill time reported as  sink capacity / production rate
                           cheap, reversible; no player parameter (9)

The asymmetry that makes the split work: belt and miner upgrades are performed in
place — the building is swapped, the route is not. Footprint and trunk routing are
not. So the irreversible commitment is made at the design tier while the reversible
one tracks today's demand.

*Plan geometry for the design tier, build machines for today.*

### 4.1 The sink bound — a report, not a ceiling

A line feeding a container has a finite total output equal to that container unless
something draws it down. Rate sets only how fast the cap is reached; after that the
line's marginal output is zero. This is the **useful life** of a production line.

    fill time = sink capacity / production rate

**The tool reports fill time. It does not derive a machine ceiling from it.**
Whether a full container is a failure depends on what the run is for: a player
sizing output to demand reads it as overbuild, a player stockpiling for a large
construction reads it as the goal reached. Phrasing the relation as
`min(target, sink) / interval` — a bound on useful machines — smuggles the first
reading in as a default. Phrased as a duration it carries no preference, and both
readings can use the same number.

Same guardrail as section 2: report the consequence, decline the threshold.

Observed instance, 2026-09-19, **not measured**: roughly four refineries on plastic
filled a standard storage container in approximately the time taken to plan and
build the equivalent rubber line. If it holds under measurement it is also a first
empirical estimate of build-and-revise duration per site. It is **not** an input to
the tool — see section 9.

### 4.2 Geometry reserves area and throughput, not machine identity

Correction to 4 as first written. The geometry commitment was stated as "footprint
for the final module count," which silently assumes the machines are known. They are
not: an alternate recipe arriving can change the mix outright. Solid Steel Ingot
removes a stage; Encased Industrial Pipe rebuilds the beam chain. Reserving space for
"three more foundries" is reserving the wrong thing if the answer turns out to need
constructors.

    reserve   area (m2), and trunk throughput (items or m3 per min) at the
              design tier's belt and pipe Mk
    not       machine counts by type, which a recipe swap invalidates

Area and throughput survive a recipe change. Machine mix does not. Section 8.2's
overhead rule is expressed in foundations and trunk length for the same reason — both
are mix-invariant once the area is fixed.

## 5. Site design tier

**Node saturation is the wrong target.** A site is not scaled indefinitely to its
nodes; it saturates at a design tier, keeps running, and is superseded by a *new*
site founded at a higher starting logistics tier. Progression is a sequence of sites
with a rising floor.

### 5.1 The unlock table, verified

From `logistics_capabilities.csv`:

    belt      Mk.1   60/min    Tier 0 - HUB Upgrade 4
              Mk.2  120/min    Tier 2 - Logistics Mk.2
              Mk.3  270/min    Tier 4 - Logistics Mk.3
              Mk.4  480/min    Tier 5 - Logistics Mk.4
              Mk.5  780/min    Tier 7 - Logistics Mk.5
              Mk.6 1200/min    Tier 9 - Peak Efficiency

    miner     Mk.1   60/min    Tier 0 - HUB Upgrade 5
              Mk.2  120/min    Tier 4 - Advanced Steel Production
              Mk.3  240/min    Tier 8 - Leading-Edge Production

    pipeline  Mk.1  300 m3/min Tier 3 - Coal Power
              Mk.2  600 m3/min Tier 6 - Pipeline Engineering Mk.2

**There is no miner Mk.4 in the reference layer.** Miners cap at Mk.3. Any
saturation arithmetic assuming a fourth tier is wrong.

### 5.2 The design tier has a canonical unit

Logistics upgrades land at progression-cluster boundaries. `progression_clusters.csv`
defines the bands: `pre_tier_1_2`, `tier_1_2`, `tier_3_4`, `tier_5_6`, `tier_7_8`,
`tier_9`. Belt Mk.2 closes `tier_1_2`; belt Mk.3 and miner Mk.2 both close
`tier_3_4`; belt Mk.4 opens `tier_5_6`; miner Mk.3 sits in `tier_7_8`.

So "one tier band of lookahead" is not a fudge — the band is the cluster, and the
clusters are canonical. That gives section 8.1's declared-constant option a
well-defined unit.

### 5.3 The worked intuitions, checked

Two design-tier judgements were offered in conversation. Both hold against the table:

    starter base (2 iron, 1 copper, 1 limestone)
        founded Tier 0-1; belt Mk.2 arrives Tier 2, miner Mk.2 not until Tier 4
        -> design to saturate Mk.2 belts, ignore miner upgrades   CONFIRMED

    steel site (3 pure iron, coal, limestone and copper nearby)
        founded ~Tier 3; belt Mk.3 + miner Mk.2 at Tier 4; belt Mk.4 at Tier 5
        -> design tier Mk.2 miner / Mk.4 belt                     CONFIRMED

That miner Mk.2 unlocks with a schematic literally named *Advanced Steel Production*
is the clearest evidence available that the design tier of a steel site is one
cluster out, not five.

**The point of section 5 is that these should be a table the tool emits, not
knowledge the player carries.** All inputs are canonical: the tier→Mk mapping above,
node purity via `extraction_rates.csv` and `resource_extraction_map.csv`, recipe
rates via `recipe_io.csv`.

### 5.4 Two kinds of gate — the plan is a condition set, not a sequence

5.1–5.3 gate modules on logistics tier, which is *scheduled*: belt Mk.2 arrives at
Tier 2 whether or not you want it. Recipe acquisition is not. A site's layout is
changed materially by alternates as they arrive — Solid Steel Ingot removes an ingot
stage, Encased Industrial Pipe rebuilds the beam chain, and the final configuration
holds all of them — but hard-drive alternates are **drawn, not earned on a timeline**.
You may never see a given one.

So a module plan cannot be a sequence with dates or even with tiers alone. It is a
set of conditions:

    module N available when { tier >= T, holding {recipe set} }

    scheduled gate     tier / logistics Mk        predictable, canonical
    conditional gate   recipe holding             not predictable; declared

The conditional half is already expressible: `--declared RECIPE_ID` (repeatable) and
`--declared-file` on the CLI. A phased plan is computed against a **declared
holding**; "what changes if I acquire X" is a second call, not a forecast folded into
the first.

**Consequence for `--pool` as default.** Pool returns alternates *obtainable* at a
tier band, not *held*. A phase plan computed over pool is therefore a plan over
recipes the player may not have. With `--pool` defaulted on (handoff #13, resolved
yes), the response must say so on every call, the way the tier filter already reports
its own incompleteness. The alternative — stating it nowhere — is precisely the
"less useful question asked silently" that #13 warned about.

### 5.5 Alternates are reported, never ordered

The natural next request is a list of alternates "in order of importance" for a site.
**That reproduces a defect already on the record.** LP §16.2 / §19.5: alternate value
is set-valued. Iron Wire is worth nothing alone, 3.30 ore/min paired with Stitched
Iron Plate, and is never chosen from the full tier-2 pool. Any valuation scoring
alternates singly or pairwise gets this wrong, and that problem gates Phase 3.

Admissible instead, and sufficient for the question actually being asked — *which of
these will make me rebuild*:

    report per alternate   machine-mix delta, building-type delta, trunk
                           throughput delta, footprint delta
    never                  a score, a sort, a "best", or a single recommended set

Consistent with analysis quantifying and never ranking. The player orders by looking.

## 6. Demand expansion — scope, within the existing drift line

LP record §11.3 locks the module's boundary:

    does       expand a named schematic or assembly phase into item quantities
    does not   choose which schematics to unlock
    does not   sequence or prioritise them
    does not   decide rates

**That line is not relaxed here, and it constrains how the scope widens.** The
demand set grows from Project Assembly alone to Project Assembly *plus* schematic
and MAM research costs *plus* construction parts for a declared building set — but
the **caller names the scope**. A progression cluster is a legitimate thing for a
caller to name, since the clusters are canonical; the module must not select the
band itself. A module that picked its own band would be choosing which schematics
matter, which is precisely what §11.3 forbids.

Output remains a bill of quantities, not rates. Previously justified because
conversion needs a horizon the scheduler owns; now also because quantities are the
form the game states and rates are the derived one.

## 7. Consumer

Demand expansion gains a second consumer alongside the §10 scheduler: a **site
capacity allocator** that, given a site's supply and its candidate outputs, splits
capacity in proportion to what the declared scope consumes. This is the "how much of
each" question — a steel site can make beams, pipes, frames and motors from one
supply, and the split is driven by downstream demand rather than by a date.

Architectural note: a site capacity commitment needs node purity, miner tier,
logistics throughput and recipe rates simultaneously. Extraction is recorded as
*outside* the production solve, belonging to the world layer
(`docs/decisions/resource_authority.md`, `extraction_wiring_and_provenance_stamp.md`).
This object does not breach that boundary — it consumes both sides — which places it
above both.

### 7.1 Withdrawn: the CLI refusal-string defect

The first draft recorded a defect in `tools/production_cli.py`, claiming its
`--by` / `--deadline` refusals named a phase that would not implement them. Checked:

    REFUSALS = {
        "by": "scheduling is Phase 2 — nothing in this model knows what time is",
        "deadline": "scheduling is Phase 2 — nothing in this model knows what time is",
        ...
    }

Phase 2 does own scheduling, per plan §10 and §17. The string is accurate. **No
defect. Claim withdrawn.**

## 8. What is canonical and what is declared

Canonical, verified present in `planning_data/game/reference/`:

    project_assembly_requirements.csv   elevator quantities, 5 phases, 15 line items
    schematic_costs.csv                 milestone + MAM research costs
    logistics_capabilities.csv          belt / lift / pipeline / miner by Mk + unlock
    progression_clusters.csv            the six progression bands
    extraction_rates.csv                node purity x miner tier
    recipe_io.csv, recipes.csv          recipe rates and parts lists

Known defect carried forward (§17.5): `resource_totals.csv` does not join to
`resources.csv` for fluids, so anything deriving fluid capacity silently takes a
default. Relevant here — pipeline Mk.2 at Tier 6 is a design-tier gate for any
fluid-fed site.

Declared parameters, each to be carried where the caller can see it:

### 8.1 Design-tier lookahead — RESOLVED: declared

    declared constant  in units of progression clusters (5.2)   ADOPTED, default
    derived            from demand durability: count of downstream
                       recipes consuming the item and the cluster
                       span across which they appear             REPORTABLE, never default

Both pass the narrow test — counting consumers prices nothing, so the derived form
is admissible under the standing guardrails. The wider test decides it. A derived
lookahead makes the tool decide how long a site should stay the marginal supplier,
and that is a playstyle judgement: a run that designs every site to terminal
logistics is not committing an error the tool is entitled to correct.

The lookahead is therefore **declared by the caller, in progression clusters**. The
derived figure may be reported alongside as a quantified observation — consistent
with analysis quantifying and never ranking — but is never substituted for the
declaration, never sorted, and never presented as a recommended value.

Recorded as the general form, since it settled a second question in this document
the same way (4.1): where two admissible constructions differ only in whether the
tool acquires an opinion, the one without the opinion is the default and the other
is reportable.

### 8.2 Construction overhead — RESOLVED: a geometric rule, not a scalar

Machine parts are derivable: the solve returns machine counts, and their costs are
canonical. What has no canonical source is how much *supporting* structure a build
carries. A proportional factor would hide exactly the thing that varies. The adopted
rule derives it geometrically from `buildings.csv`, which carries `width_m`,
`length_m`, `height_m` and connection counts:

    foundation             8m x 8m
    foundations / machine  ceil(width_m / 8) x ceil(length_m / 8)
    belt or pipe           length_m per machine, at the site's tier Mk
                           deliberately generous — machines are short relative
                           to real runs, and the slack covers splitters and mergers
    power                  1 pole + cable of length_m per machine

Per machine, not per connection. Worked: Smelter rounds to 1 x 2 foundations.

The rule is mix-invariant in the sense of 4.2 — it converts whatever machines a solve
returns into area and trunk length, so a recipe swap re-runs it rather than
invalidating a reservation.

**The five missing footprint rows — sourced 2026-09-19, pending review.**
`buildings.csv` covered ten buildings and omitted five of the eleven producers in
`production_buildings.csv`. Sourced from satisfactory.wiki.gg on 2026-09-19, matching
the existing schema and its `source_url` / `verified_on` provenance columns:

    building              w x l x h        conv i/o   pipe i/o   unlock
    Smelter               5 x 10 x 8.5      1 / 1      0 / 0     T0 HUB Upgrade 2
    Packager              8 x  8 x 12       1 / 1      1 / 1     T5 Fluid Packaging
    Converter            16 x 16 x 18       2 / 1      0 / 1     T9 Matter Conversion
    Particle Accelerator 24 x 38 x 32       2 / 1      1 / 0     T8 Particle Enrichment
    Quantum Encoder      22 x 50 x 18       3 / 1      1 / 1     T9 Quantum Encoding

`power_mw` is left **blank** for Converter, Particle Accelerator and Quantum Encoder.
All three are `power_model: variable` in `production_buildings.csv` with
`base_power_mw: 0`, and their real ranges live in `recipe_variable_power.csv`. A
scalar in `buildings.csv` would assert a figure the power model contradicts. Blank
follows the `space_elevator` precedent in the same table; this is the first variable-
power row, so the precedent is set here deliberately.

Footprints under the rule:

    Smelter                1 x 2 =  2 foundations
    Packager               1 x 1 =  1
    Converter              2 x 2 =  4
    Particle Accelerator   3 x 5 = 15
    Quantum Encoder        3 x 7 = 21

Smelter at 1 x 2 matches the independent call made in conversation before the
dimensions were fetched — weak but real corroboration of both rule and data.

The 8m foundation constant is a declared assumption, named here rather than compiled
in.

### 8.3 Away interval — DELETED

Previously a declared parameter. Removed: see section 9. The tool takes no
player-time input at all.

### 8.4 Phase assignment — RESOLVED

The object splits, and the split is what makes the assignment answerable:

    module sequencing logic     depends only on unlocks and demand, both
                                canonical                          PHASE 2
    spatial realization         footprint, local nodes, room, siting
                                depends on world data              WORLD INTEGRATION

The first works standalone; the second enhances it. So the phased-module idea stays
inside Phase 2 as plan §10 already scopes it, and nothing in Phase 2 acquires a
dependency on the world or pathing layers. No phases are renumbered.

## 9. Player time is a residual — RESOLVED

Earlier drafts treated exploration as either instrumental (a toll paid for hard
drives, so away-time could be minimized) or terminal (wanted for itself, so away-time
is a declared input). **Both are wrong for this project.** Build time and away time
are *residuals* of how the run is played: build fast and there is more time to
explore, build slow and there is less. Neither is planned, so neither is an input.

    the tool takes     no build-time parameter
                       no away-interval parameter
    the tool reports   fill time = sink capacity / production rate  (4.1)
    the player does    the comparison against their own pace, by eye

This removes 8.3 entirely and leaves **the first module with zero player-time
parameters**. It is the fourth question in this document to settle the same way as
8.1's general form: where the tool would have to acquire an opinion, it reports and
declines.

The supporting observation, which is also why no point estimate would have worked:
build time is not per-machine but stepwise — site setup, plus cheap marginal machines
within a block, plus a large rework term whenever a revision moves the block. Greg's
figures: 2–5 min per machine when the layout is right first time, 5–10 min including
logistics and rearranging, and a ten-machine rubber build that took at least 60
minutes with false starts. A range that wide, further widened by cosmetic detours and
by a single bad traverse on the way home, is not a number a tool should accept.

## 9a. What this does not settle

- Whether the Modular Frame figures in section 3 survive re-derivation through a
  path that does not breach the oracle's ambiguity guard, and through `scenario.py`
  rather than this session's implementation of the multiplier rule.
- The five missing footprint rows (8.2).
- `canonical_mw`: re-evaluate or re-solve (handoff #10) — untouched here.

## 10. Pathing dependency, recorded because it recurred

Three pulls toward the pathing track surfaced independently while deriving this
record, each from the progression side and each at Phase 2 rather than Phase 5:

1. **Travel duration** — away-interval, if derived rather than declared, comes from
   an expedition route.
2. **Siting** — "if layout and logistics were obvious" is a build-site question.
3. **Footprint reservation** — what prevents teardown is space reserved for modules
   2..n before module 1 is placed, which is spatial.

**All three defer, and the record over-weighted them.** Pull 1 dissolved when
away-time stopped being a parameter (section 9). Pulls 2 and 3 fall on the spatial
side of 8.4's split, which is deferred to world integration. Phase 2 as scoped here
acquires **no pathing dependency**.

What survives is the observation itself, kept because it was genuine: the progression
work reached toward the pathing track three times from different directions in one
sitting. That is weak evidence the two tracks meet earlier than the plan's ordering
implies, and worth revisiting when spatial realization is specified. It is not a
reason to move the pathing backlog's trigger now, and this record does not move it.

## 11. Evidence and its quality

    repo, read 2026-09-19        plan §10 and §17; LP record §11; production_cli.py;
                                 nine reference tables incl. buildings.csv and
                                 production_buildings.csv
    computation, this session    sections 3 and 3.2; breaches the oracle's
                                 ambiguity guard (3.1) and does not use
                                 scenario.py (3.2)
    conversation, 2026-09-19     the reasoning in sections 4-9
    one play observation         plastic line / container fill, unmeasured
    one secondary source         a video summary on production sizing, supplied by
                                 Greg; used as evidence about how players decide,
                                 not as game fact

Attribution, since it bears on what can be relied on.

Greg's positions: *build small to explore*; *sites are superseded rather than
scaled*; *design to the near unlock, not to saturation*; *look backwards from
demand*; the two site judgements in 5.3; *the phased approach is gated by recipe
acquisition as well as tier* (5.4); *build and away time are both residuals* (9); the
construction-overhead geometry in 8.2 including the 8m foundation and the per-machine
trunk length; the scenario of record.

Derived in session and untested against play: the partition in section 3, the
three-commitment split in section 4, the area-and-throughput correction in 4.2, the
sink bound in 4.1, the cluster-as-lookahead unit in 5.2, the
report-never-order constraint in 5.5, and the demand-durability construction in 8.1.

### 11.1 Decisions closed from the 2026-09-18 handoff

    #5   game data in the public repo — CLOSED, no action. It stays.
    #13  --pool as CLI default — YES, with the obtainable-not-held statement
         required on every response (5.4).
    #14  tools/progression/ as the home for demand expansion — CLOSED,
         deliberate, as written.

Out of scope, recorded so it is not re-litigated: **single-player**. Multiplayer is
low priority and none of this assumes concurrency — build and away time are one
person's.

## 12. Exit condition

Satisfied when the demand expansion module is specified against the wider declared
scope of section 6, with section 8's parameters named in its signature and its
§11.3 drift line asserted by test.

The cheap first test proposed in the first draft — sum canonical lifetime demand for
one mid-tier item and divide by a community rate target — **has been run, corrected,
and bounded**; see 3, 3.1 and 3.2. At 1x, T is 1.5 to 2.4 hours against a target the
community treats as a factory goal; under the scenario of record the lower bound is
5.1 hours. The test holds at both ends of its own uncertainty, and it discriminates
between scenarios, which was the point.

Remaining before the spec:

    1  implement rounding in the transform layer (3.2.5). Decided; the work
       is moving the multiplier from rates to per-cycle amounts.
    2  add a named Scenario constant MARGINAL_PEAK_DEBOTTLENECK for
       1.25 / 2.0 / 2.0 (3.3.1)
    3  observe a fluid recipe at 1.25x once one is unlocked, to confirm m3
       rounds the same way (3.2.4)

None blocks writing the module's signature, which sections 6 and 8 between them now
fully determine. The Modular Frame figures are quotable as game quantities; figures
at sub-1x settings, and for fluid-heavy targets, are not yet.

`buildings.csv` and `game_builds.csv` were applied to the repo on 2026-09-19, so
8.2's footprint rule can run on all eleven producers.
