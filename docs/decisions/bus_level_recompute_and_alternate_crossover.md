# Bus-level recompute of the storage review, and the alternate crossover scale

- Date: 2026-09-21
- Kind: **decision record.** Immutable. Supersessions recorded forward.
- Governs: the status of every overflow figure in
  `storage-model-bundle-review-2026-09-21.md`, and the scale-dependence claim at
  `bus_allocation_backpressure_and_residual.md` §8.
- Discharges: handoff open items 2 (bus-level recompute) and 3 (alternate
  crossover scale). Both were named "live, and both move numbers."
- Source: computed first-hand this session against
  `planning_data/game/reference/` and the bundle config recovered at
  `scratchpad/satisfactory_storage_model_bundle/`, at the scenario of record
  (1.25x parts, game 1.2.4.0 CL#502094). Every figure below was **run**, not
  composed from a prior figure plus a delta.

## 1. The engine was validated before it was believed

The recompute is only worth its conclusions if it reproduces the documents it
revises. It does, on all four, without fitting:

    storage review §5, 1x and 1.25x      10 of 10 cells      machines and overflow
    storage review §6.1 balance deltas   all rows            both phases
    storage review §7 alternate table     8 of  8 cells      both regimes
    bus record §4 screw-bus table        199/min, 37.7/62.3, R = 1.0/min at 5
    bus record §8 regime comparison      19.02 -> 20, 15.79 -> 19

Reproducing §5 and §7 required recovering two rules the review applies but does
not state, and they are load-bearing:

    external demand = 0        §9 says "external demand held constant across
                               scenarios." It was constant at ZERO. The
                               assumption is therefore vacuous as written, not
                               wrong — but it is not what the sentence conveys.
    min one machine per        every declared line gets a machine floor. This
    declared line              is what gives Cable 30.00 and Concrete 15.00
                               overflow in §3 against zero automated demand.

Both are recorded here because a figure that cannot be reproduced without
guessing its rules cannot be carried forward by anyone else.

## 2. §6.1's balance check was computed at 1x, and the scenario of record is worse

The review's three negative deltas reproduce **exactly, and only, at 1x**. Run
at the scenario of record they are larger, and there is a fourth.

    phase T1-2        review (1x)      at 1.25x      change
    Screws              -50.0            -74.0       +48%
    Wire                -18.5            -30.9       +67%
    Iron Rod             -3.0             -8.5       +183%
    Iron Plate            —               -5.6       NEW

    phase T3-4        review (1x)      at 1.25x
    Screws              -50.0            -74.0
    Wire                -37.3            -53.7
    Iron Rod             -6.0            -13.0
    Reinforced Iron       —               -0.5       NEW
    Plate

**The fourth phase-1 delta is Iron Plate, which §3 named as the binding item of
the phase.** The one item whose coverage the review singles out as the thing to
fix is also an item whose demand the review understates at the multiplier the
save actually runs at.

    SUPERSEDED   storage review §6.1's "three internal balance inconsistencies"
                 and §8 settle-first item 4, "correct the three negative
                 deltas." At the scenario of record there are FOUR in phase 1
                 and four in phase 2. The item stays open; its cardinality and
                 its magnitudes change.

This is the process note's shape in a new place. Nothing was composed wrongly —
the arithmetic is right. A check was run at one scenario and its results carried
into a document whose other tables run at another.

## 3. The review's figures were already bus-level. The predicted movement does not occur

Handoff §11.4 and storage review rev 4 both record that lane decomposition
"MULTIPLIES the round-ups — one block of 8 rounds once, two lanes of 4 round
twice — so every overflow figure in §3 and §5 of this note is single-lane and
WILL move."

**It does not, and the bus record is what retires it.** Two independent reasons:

1. The review's demand figures already sum *every in-config consumer* of each
   item. Verified by reproduction: Wire's 97.50/min demand at 1x is 37.50
   (Stitched RIP) + 60.00 (Cable). That is a bus total, not a lane total.
2. Bus record §1 makes the producer set the primitive and puts lane
   decomposition *inside* it. A bus of five screw constructors feeding two belts
   is five constructors. The ceil happens once, against total bus demand.
   Splitting producers across belts is a topology choice and adds no round-up.

    SUPERSEDED   handoff §11.4's lane-multiplication consequence, and the
                 storage review rev-4 note carrying it. The mechanism described
                 belongs to the vertical-slice model that bus record §1 declares
                 void. It does not survive the slice model's retirement.

The figures do move. They move for a different reason, and it is §4.

## 4. The propagation basis is the real correction, and it is structural

The review propagates demand upstream at **100% of installed capacity**: a
declared line draws its nameplate input rate. Bus record §2 and §4 say otherwise
— a consumer that is satisfied backs up, the splitter stops offering it items,
and producers idle at utilisation `demand / supply`. Under backpressure the
steady-state draw is **actual need**, not nameplate.

Recomputed on the need basis, at 1.25x, with the config's `automated_demand`
column read as the external root its own `_notes` define it to be:

    phase T1-2           rate     ext  in-scope   demand  mach  supply   R(bus)  withdraw
    Cable               30.00    0.00      0.00     0.00     1   30.00    30.00      3.00
    Concrete            15.00    0.00      0.00     0.00     1   15.00    15.00      6.00
    Iron Plate          20.00   18.75     11.70    30.45     2   40.00     9.55      2.00
    Iron Rod            15.00   23.00     12.00    35.00     3   45.00    10.00      2.00
    Modular Frame        2.00    0.00      0.00     0.00     1    2.00     2.00      0.50
    Reinforced Iron Pl.  5.62    2.70      0.00     2.70     1    5.62     2.92      2.00
    Rotor                4.00    2.00      0.00     2.00     1    4.00     2.00      2.00
    Screws              50.00   50.00     62.00   112.00     3  150.00    38.00      0.00
    Wire                30.00   25.00     22.50    47.50     2   60.00    12.50      5.00
    TOTAL MACHINES 15

    phase T3-4           rate     ext  in-scope   demand  mach  supply   R(bus)  withdraw
    Cable               30.00    4.00      0.00     4.00     1   30.00    26.00      3.09
    Concrete            15.00    1.20      0.00     1.20     1   15.00    13.80      5.79
    Copper Sheet        10.00    0.00      0.00     0.00     1   10.00    10.00      1.14
    Encased Ind. Beam    4.00    0.00      0.00     0.00     1    4.00     4.00      0.20
    Iron Plate          20.00   37.35     23.94    61.29     4   80.00    18.71      1.47
    Iron Rod            15.00   26.00     19.50    45.50     4   60.00    14.50      1.24
    Modular Frame        2.00    1.00      0.00     1.00     1    2.00     1.00      1.00
    Reinforced Iron Pl.  5.62    3.52      2.00     5.53     1    5.62     0.10      2.00
    Rotor                4.00    2.00      0.00     2.00     1    4.00     2.00      1.30
    Screws              50.00   50.00     62.00   112.00     3  150.00    38.00      0.00
    Steel Beam          15.00   12.00      0.00    12.00     1   15.00     3.00      1.11
    Steel Pipe          20.00    9.60      0.00     9.60     1   20.00    10.40      1.20
    Wire                30.00   14.40     58.04    72.44     3   90.00    17.56      9.13
    TOTAL MACHINES 23

Against the review's 1.25x cap-basis solve of phase 1 (18 machines), the bus
recompute is **15**. Screws residual is 38.00/min, neither the review's 26.00
nor its 0.00.

**The sharper result is what the need basis does with the review's own basis.**
Set external demand to zero — the review's actual §5 and §7 assumption from §1 —
and solve on the need basis: the declared scope has **zero throughput**. Nothing
demands anything, every line idles, every residual is its full nameplate.

    FINDING   the overflow figures in storage review §§3, 5 and 7 exist only
              because of the 100%-capacity basis combined with the min-one-
              machine floor. They are not residuals of a demand-driven solve.
              Under the mechanism the bus record establishes, that configuration
              produces no flow at all.

This is not a defect in the review's arithmetic. It is the cost of a basis that
was reasonable before backpressure was on the record and is not after.

### 4.1 The config's demand column has no consistent reading

The recompute above reads `automated_demand_per_min` as external demand, per the
config's own `_notes`: "direct factory/Project Assembly consumption that does
not pass through storage." §6.1's negative deltas prove the column is *also*
carrying in-config draw. It cannot be both without double-counting.

    OPEN      the storage config cannot be solved at the bus until its demand
              column is split into external demand and in-scope draw. §6.1
              recorded this as three wrong numbers. At the bus it is a column
              with two meanings, which is the stronger statement and the one
              that blocks.

## 5. §7's alternate-stockpile finding is scale-specific and inverts

Storage review §7 reports that the base RIP recipe accumulates 40 screws/min
that nothing wants, while Stitched accumulates 22.5 wire/min "which does feed
both RIP and Cable" — offered as the quantified form of "improves the topology
of the next expansion." Both figures reproduce exactly at the review's basis.

At the bus record's own scenario (5 RIP/min + 4 Rotor/min, need basis, 1.25x)
the comparison **inverts**:

                        review basis (1x, cap)      bus basis (1.25x, need)
    base RIP            Screws  4 mach, R 40.00     Screws  5 mach, R  1.00
    Stitched            Screws  2 mach, R  0.00     Screws  4 mach, R 36.00

The involuntary screw stockpile the review attributes to the base recipe belongs
to the alternate at the other scale and basis, by a factor of 36.

    SUPERSEDED   storage review §7's characterisation of which regime moves the
                 involuntary stockpile where. The report SHAPE stands — deltas,
                 no ordering, no score, and it still requires nothing to be
                 ranked. The direction of the specific deltas does not.

## 6. The alternate crossover: there is no crossover

Bus record §8 records that Stitched + Iron Wire is 17% leaner in continuous
machine-equivalents (19.02 vs 15.79) and saves exactly one machine after
round-up (20 vs 19), that "the integrality tax eats almost all of it at that
scale," and that "the crossover scale is computable and is not computed here."

Computed. Targets held at RIP:Rotor = 5:4, scale `s` multiplying both, 1.25x,
need basis, both regimes solved to whole machines:

    s      A cont   A ceil   B cont   B ceil   saved   cont saved   tax
    0.1      1.90        6     1.58        7      -1         0.32   1.32
    0.2      3.80        7     3.16        7       0         0.64   0.64
    0.5      9.51       12     7.90       11       1         1.61   0.61
    0.9     17.12       19    14.21       16       3         2.90  -0.10
    1.0     19.02       20    15.79       19       1         3.22   2.22
    1.1     20.92       25    17.37       22       3         3.55   0.55
    1.6     30.43       33    25.27       27       6         5.15  -0.85
    2.0     38.03       39    31.59       35       4         6.44   2.44
    5.0     95.08       96    78.97       83      13        16.11   3.11
   10      190.17      192   157.94      160      32        32.22   0.22
   30      570.50      572   473.83      476      96        96.67   0.67
  100     1901.67     1903  1579.44     1582     321       322.22   1.22

**The integrality tax does not grow with scale.** Over s = 0.1 to 100 it
oscillates in a band of roughly [-1, +3] machines and never trends. That is not
an empirical accident: the tax is a sum of fractional parts over a *fixed number
of buses* — seven in regime B, six in regime A — so it is bounded by the bus
count and is O(1) in scale, while the continuous advantage is O(s).

    DECIDED   "the crossover scale" does not exist as posed. The question
              assumed a penalty that scales against an advantage that scales.
              The penalty is bounded by the bus count. Regime B is ahead from
              s = 0.5 upward and does not reverse through s = 100. Regime A wins
              only at s = 0.1 — below one assembler of output — and ties at
              s = 0.2 to 0.4.

### 6.1 s = 1.0 is a local minimum of the saving

    s = 0.9   saved 3
    s = 1.0   saved 1     <- the measurement point in bus record §8
    s = 1.1   saved 3
    s = 1.5   saved 4
    s = 1.6   saved 6

Bus record §8 measured at the single worst scale in its own neighbourhood. Its
conclusion — "at one assembler of each the alternate barely pays" — is a
**sawtooth artifact of that measurement point**, not a property of the alternate
at small scale.

    SUPERSEDED   bus record §8's "the integrality tax eats almost all of it at
                 that scale" as a general statement about small scale. It is
                 true at s = 1.0 and false at s = 0.9 and s = 1.1.
    SUPERSEDED   bus record §10's "not shown: the crossover scale at which an
                 alternate's leanness beats its integrality tax." Shown, and the
                 framing is retired rather than answered.

This generalises past this pair, and that is the reason it is on the record
rather than in a note: **any single-point measurement of an alternate's machine
saving is a sample of a sawtooth.** The comparison is only meaningful over a
neighbourhood. A tool that reports one scale reports noise.

## 7. Exposure to the unobserved rounding rule

Two of the figures this record rests on sit on `§3.2.5`'s half-away-from-zero
rule, which storage review §11.2 records as **still unobserved at a tie**:

    base RIP      6 Iron Plate x 1.25 = 7.5    tie -> 8 assumed
    Stitched     10 Iron Plate x 1.25 = 12.5   tie -> 13 assumed

Under half-to-even, 7.5 -> 8 (unchanged) but 12.5 -> 12, which lowers Stitched's
plate draw. **The two regimes are not equally exposed**, so §6's crossover
result is sensitive to a rule nobody has read. The screw-bus figures are safe:
12 x 1.25 = 15 and 25 x 1.25 = 31.25 are not ties, so 199/min, 37.7/62.3 and the
§5 inversion do not move.

    OPEN      storage review §11.2's replacement tie probe (Cable 2 Wire ->
              2.5; RIP 6 Iron Plate -> 7.5 against its own 12 Screw -> 15
              control) is now load-bearing for §6 of this record, not only for
              §3.2.5. One build-menu read settles it.

## 8. Evidence and its quality

    first-hand, this session   every table above. The reference layer was read
                               directly; the bundle config was recovered from
                               scratchpad/ and parsed; all five validation
                               reproductions in §1 were run, not inspected
    stated, not verified       bus record §9's five game mechanics, on which
                               §4's need basis depends entirely. If backpressure
                               does not work as stated, §4 falls and the review's
                               capacity basis is correct after all
    assumption, stated         §3.2.5's half-away-from-zero at a tie. §7 names
                               the exposure
    assumption, stated         §4's external root reads the config's demand
                               column per its own _notes. §4.1 records that the
                               column does not support that reading cleanly
    not run                    the test suite. No shell on the machine this
                               session, so no pytest and no git. The 330-pass
                               figure of 2026-09-21 is NOT re-quoted here

## 9. What this does not establish

    not shown   whether the bus-count bound on the integrality tax generalises
                beyond this recipe pair. Argued structurally, computed once
    not shown   the same sweep for the other §11 alternates (handoff open
                item 6). §6.1's sawtooth warning applies to them untested
    not shown   idle power draw, unchanged from bus record §10. §4's need basis
                makes idle draw load-bearing for the power column, since it puts
                more machines in the idling state than the capacity basis did
    not done    the storage config's demand column is not split (§4.1). Until
                it is, §4's tables are the best available reading and not a
                measurement of the author's intent

---

## Amendment 1 — 2026-09-21. The tie probe was read in game

Appended forward-only. Nothing in §§1–9 is edited.

§7 recorded the half-away-from-zero assumption as an open exposure and named the
probe as load-bearing for §6's crossover result. **The probe was read.**

    source     Greg, in session 2026-09-21, save at recipe 1.25x,
               game 1.2.4.0 CL#502094. Crafting-recipe ingredient reads.

    recipe                  input          1x        1.25x      output
    Reinforced Iron Plate   Iron Plate      6 (30/min)   8 (40/min)   5 RIP/min
    Reinforced Iron Plate   Screws         12 (60/min)  15 (75/min)  unchanged
    Cable                   Wire            2 (60/min)   3 (90/min)  30 Cable/min

All six cells match the model's prediction exactly, including both output rates.

    CONFIRMED  §3.2.5's "nearest integer, ties away from zero." Adopted without
               ever observing a tie; two ties are now observed and both round up.
               7.5 -> 8 rules out half-down. 2.5 -> 3 rules out half-to-even AND
               half-down. The prior §3.2.4 read of 1.25 -> 1 rules out ceil.
               15.00 -> 15 was carried as the in-recipe control and held.
    CLOSED     §7 of this record. The exposure is discharged, not mitigated.
    CLOSED     storage review §11.2's replacement tie probe. Its count of 109
               base-recipe inputs landing on an exact half at 1.25x is now a
               census of confirmed behaviour rather than a measure of exposure.

**No figure in §§1–6 moves.** This record was computed under half-away
throughout, which is the observed rule. The 16.9% leanness, 19.02 -> 20,
15.79 -> 19, the s = 0.1 to 100 sweep and the §6.1 local-minimum result all
stand as originally computed, and are now resting on an observed rule rather
than an assumed one.

### A1.1 Correction to the probe's method, recorded so it is not repeated

Storage review §11.2 specified these as **"build-menu reads."** That is the
wrong surface: §11.1 established that Build Gun recipes do not scale, so the
build menu displays 1x amounts and settles nothing. The reads that closed this
were of *crafting* recipes in their producers' recipe UI — a Constructor for
Cable, an Assembler for Reinforced Iron Plate.

The probe's *design* was sound and worked exactly as intended: two reads chosen
in advance to discriminate three candidate rules, plus a control in the same
recipe. Only the surface was misnamed. This is the second time naming the
discriminating observation in advance has settled a question in one glance
(§11.1 was the first), and it is worth keeping as a pattern — with the surface
named alongside the observation.

### A1.2 Residual ambiguity, immaterial and not an open item

Half-away-from-zero and half-up are identical on positive values, and every
recipe input amount is positive. No recipe input can distinguish them. The
distinction cannot arise in this domain and is recorded as closed rather than
carried.

---

## Amendment 2 — 2026-09-21. §4 over-generalised, and §4.1 is resolved

Appended forward-only. Nothing in §§1–9 or amendment 1 is edited. This amendment
**retracts a conclusion of §4** and records what replaces it.

    source   Greg, in session 2026-09-21, correcting two things this record
             got wrong about his own intent.

### A2.1 `automated_demand_per_min` is derived, not declared. §4.1 dissolves

    stated   "automated demand is what downstream consumers use in the
             production lane -- use the numbers we're getting in our work here.
             Mistake in the storage work."

The column is **in-scope draw**, which the model computes. The config's declared
figures are a mistake and are discarded rather than repaired.

    SUPERSEDED   §4.1's open item, "the config cannot be solved at the bus until
                 its demand column is split." There is nothing to split. The
                 column is derived and the declared values are void.
    SUPERSEDED   the same item as carried in the handoff as the live block.

§4.1's *diagnosis* stands and is why the correction was findable — the column
demonstrably held three different quantities, including Screws' 50.00/min which
was its own installed capacity. It was a wrong column, not an ambiguous one.

**What this does not fix.** With the demand column derived, the config's
remaining declaration is its machine counts, and those do not survive contact
either: §2 counted nine rows below one machine (Encased Industrial Beam 0.05,
Copper Sheet 0.11, Cable 0.24). Rounding those up to whole machines — the
locked rule — manufactures draw the author never intended. Cable at a floored
one machine draws 90 Wire/min at 1.25x against a declared intent of roughly
a tenth of that, which alone drives Wire's derived draw to 136.88/min and the
line 111.88/min short.

    OPEN, replacing §4.1   the storage config still cannot be solved, now for a
                           simpler reason: it does not consistently state what
                           the factory IS. A machine-count declaration in whole
                           machines is the missing input. Nothing derivable
                           substitutes for it.

### A2.2 §4's basis conclusion is retracted. Both bases are right, for different steady states

    stated   "the point of that was to ask if the residual was enough to get me
             to the next set of milestones/tiers, or if I'd need to ramp up."

§4 concluded that the need basis is "the real correction" and that the review's
100%-of-capacity basis produces artifacts. **That over-generalised, and the
error is visible in the bus record's own §5.**

The bus record enumerates three steady states. Which basis is correct is a
property of *which state the question is about*, and this record picked one basis
for all questions:

    BACK UP     no drain. Producers idle at demand/supply. The NEED basis is
                correct here. §4's "zero throughput" result is not a reductio on
                the review — it is a correct description of an unattended
                factory with no terminal demand.
    WITHDRAWN   the player drains the containers, so producers run at 100% while
                there is room. The CAPACITY basis is correct here.
    SUNK        producers never stop. Capacity basis, constant draw.

**Greg's question is about the withdrawn state.** "Is the residual enough to
reach the next tier" presupposes a player actively drawing the stock down, which
is exactly the condition under which a producer does not back up.

    RETRACTED   §4's claim that the propagation basis is "the real correction"
                and that §§3, 5 and 7 of the storage review are "artifacts of
                the capacity basis." The review chose the correct state for its
                own question. Its defect is that it does not SAY which state it
                is modelling — not that it chose wrongly.
    STANDS      §4's need-basis tables, as the unattended/BACK-UP case. 15
                machines in phase 1 is a correct figure for a factory nobody is
                drawing from. It is not the figure that answers the storage
                question.
    STANDS      §§2, 3, 5, 6 and both amendments, none of which depend on the
                basis choice. §2's 1x/1.25x defect, §3's lane retraction, §5's
                alternate inversion and §6's crossover result are unaffected.

**Consequence for the record's shape, and it is the durable part:** a residual
figure is meaningless without naming its steady state, and neither the storage
review nor this record named one until now. Two documents computed R under
different states and neither declared it, which is how §4 mistook a state
difference for an error.

    DECIDED   any emitted residual names the steady state it was computed
              under. This is the §9-style provenance rule applied to a derived
              quantity rather than to a source table, and it is testable: a
              residual without a state label is a defect.

### A2.3 The bootstrap is not partial. The correction to open item 3

    stated   "by partial I mean beyond the bootstrap."

The handoff logged this as "partial bootstrap appears to be acceptable." Wrong.
The **bootstrap must be covered** — that is the whole point of holding stock
across a tier boundary, so that next-tier construction can start without waiting.
What may be partial is the remainder of the tier *beyond* the bootstrap.

    coverage criterion, corrected
      current-tier remaining bill    + bootstrap    MUST be covered
      beyond-bootstrap next tier                    MAY be partial

So `max_i T_i` is a threshold after all, taken over the bootstrap-inclusive bill
only. The beyond-bootstrap remainder is the part that is reported rather than
required, and the binding item over *that* set is a sequencing signal. The
record had this inverted in the handoff and it is corrected here rather than in
place.

---

## Amendment 3 — 2026-09-21. Buses partition by declaration, and steady state is per-bus

Appended forward-only. Nothing above is edited. This amendment **contradicts bus
record §1**, **withdraws A2.1's second half**, and re-scopes A2.2's decision.

    source   Greg, in session 2026-09-21, describing the topology he actually
             builds. Game-mechanics and design-practice statements, flagged as
             such per bus record §9.

### A3.1 The same item can run on several isolated buses, by choice

    stated   "wire in that chain was Iron Wire for Stitched Iron Plate -- wire
             for building comes from the copper branch in this case."

Bus record §1 states: *"Whether a bus can stay isolated is a property of its
consumer set, not a design choice: one consumer can be isolated, two or more
must merge."*

**That is false.** Wire has three consumers here — Stitched Iron Plate, Cable,
and player withdrawal for construction — and is deliberately run as **two
unconnected buses**: Iron Wire from Iron Ingot feeding Stitched, and ordinary
Wire from Copper Ingot feeding Cable and the build stock. Two consumers merge
only if something physically connects them, and whether to connect them is
exactly a design choice.

Measured, root Smart Plating 2/min, Stitched, 1.25x, both computed this session:

                      supply     draw       R        consumers
    Wire_iron          67.50    46.88   20.62/min    Stitched RIP
    Wire_copper        90.00    90.00    0.00/min    Cable
    ---- merged into one bus per item ----
    Wire              150.00   136.88   13.12/min    both
    machines: split 31, merged 30

    SUPERSEDED   bus record §1's derivation of isolation from consumer count.
                 The consumer set does not determine the partition. The
                 PARTITION IS PART OF THE DECLARATION, and the consumer set is
                 what a declared partition must cover, not what induces it.
    CONSEQUENCE  the primitive is not (item, producers, consumers). It is
                 (item, producers, consumers, PARTITION ID). Two buses of the
                 same item are different objects and their residuals do not
                 pool.

**This invalidates a figure in §5 of this record and one in amendment A2.2's
tables**, both of which merged Wire by assuming one bus per item. The merged
number is not wrong arithmetic; it describes a factory nobody built.

### A3.2 Steady state is a property of the bus, not of the factory

A2.2 decided that any emitted residual names its steady state. Correct, and
**scoped too coarsely** — it implied one state per report. Different buses in
the same factory sit in different states at the same time:

    production chain      Smart Plating and everything feeding it. Drains
                          continuously, so producers run at 100%. WITHDRAWN
                          state. Residual is rounding slop -- small, sawtoothed,
                          often exactly zero
    build-material line   Concrete, Cable, build stock. One whole machine fills
                          a container and PAUSES. BACK UP state. Its average
                          draw is the withdrawal rate, not nameplate. Nameplate
                          draw never reaches the upstream bus

    SUPERSEDED   A2.2's decision, re-scoped: the steady state is declared PER
                 BUS and a residual is meaningless without its own bus's state.
                 Bus record §5's three states are per-bus, not per-factory.

### A3.3 A2.1's machine-count criticism is withdrawn

    stated   "concrete, plates, wire, cable etc. not specified by machines was
             estimated based on machine size ... added 1 additional 8m
             foundation on the short axis so it rests on something longer than
             it, to account for movement, splitters etc. This is definitely a
             floor."

A2.1 said the config's fractional figures were unusable machine counts, and
reported that flooring Cable's "0.10 machines" to one whole machine drives Wire's
derived draw to 136.88/min and the line 111.88/min short.

**That cascade was my artifact, not a property of the config.** Those fields are
not machine counts at all — they are **withdrawal estimates from §8.2's
geometric overhead rule**, footprint-derived, with one extra 8m foundation on the
short axis for movement and splitters, and **stated as a floor**. Dividing a
withdrawal estimate by a machine rate and then running the result at nameplate
produces a demand figure nobody declared.

    WITHDRAWN    A2.1's "the config does not state what the factory IS" and its
                 Cable/Wire cascade. The config states a build-material
                 withdrawal, correctly, in the units §8.2 prescribes.
    STANDS       A2.1's first half: the demand column is derived, not declared.
                 Unaffected.
    STANDS       §2's defect that `installed_capacity` on eleven rows is
                 back-solved as (automated + withdrawal). That is a real defect
                 and a different one.
    NEW, minor   the geometric estimate is declared by its author as a FLOOR.
                 Any coverage verdict computed against it is therefore
                 optimistic by an unmeasured amount, and should say so rather
                 than present the comparison as tight.

### A3.4 The zero residuals were intentional design

The previous turn reported "Iron Plate and Wire yield exactly zero residual" as a
failure of the mechanism. Two thirds of that is wrong:

    Wire = 0      INTENTIONAL. Iron Wire is dedicated to Stitched RIP and is
                  meant to be fully consumed. Build wire is a different bus.
                  A dedicated intermediate having zero residual is the design
                  working, not failing
    Screws = 1    INTENTIONAL, and not a storage item. "Screws are so rarely
                  needed I can just steal them from the machine." No dedicated
                  storage required [stated, Greg]
    Iron Plate    NOT addressed, so it remains open as a question rather than a
                  finding. Its zero is structural at 1.25x -- Stitched draws
                  exactly 40 plate/min, exactly two Constructors -- and it does
                  not move with the root

### A3.5 The corrected model, and it covers

Split Wire buses, production chain continuous, build-material draw at its average
rate, root Smart Plating 2/min, Stitched RIP, 1.25x:

    bus             rate     draw  mach   supply    R/min   withdraw   verdict
    Screws         40.00   124.00     4   160.00    36.00       0.00   ok
    Wire_iron      22.50    46.88     3    67.50    20.62       0.00   ok
    Wire_copper    30.00    14.00     1    30.00    16.00       0.00   ok
    IronPlate      20.00    24.38     2    40.00    15.62       2.00   ok
    CopperIngot    30.00    15.00     1    30.00    15.00       0.00   ok
    IronRod        15.00    64.00     5    75.00    11.00       2.00   ok
    IronIngot      30.00   200.00     7   210.00    10.00       0.00   ok
    Concrete       15.00     0.00     1    15.00     9.00       0.00   ok
    RIP             5.62     2.00     1     5.62     3.62       2.00   ok
    Rotor           4.00     2.00     1     4.00     2.00       2.00   ok
    SmartPlating    2.00     0.00     1     2.00     0.00       0.00   ok
    TOTAL MACHINES 27

Wire_copper carries Cable at its average 9/min plus 5/min of build wire against
one Constructor's 30/min. Concrete carries 6/min against 15/min. **Everything
covers**, which is the answer the storage question was asking for and the first
time this record has produced it under a topology that matches what gets built.

Subject to A3.3's floor caveat: the withdrawal figures are a declared
underestimate, so "covers" here means "covers the floor."

---

## Amendment 4 — 2026-09-21. Iron Plate closed, and a fourth steady state

Appended forward-only. Closes A3.4's one remaining open question.

    stated   "the Iron Plate is likely just a miss -- we'd want some Iron Plate
             going to storage even if that means an entire Constructor's worth,
             or some underclocked amount."

### A4.1 Iron Plate is a declared build line, not a residual item

Its zero residual is not a defect and not a design intent — it is a **missing
declaration**. Build plates belong on their own line, exactly like Concrete and
Cable, and the structural zero (Stitched draws 40 plate/min = exactly two
Constructors at 1.25x) is simply irrelevant once the build line is declared
separately.

    CLOSED   A3.4's open Iron Plate question. The item joins the
             build-material class. The §5/§6 residual figures for Iron Plate
             describe the production bus only and were never the build supply.

One Constructor at 1.25x makes 20 plate/min and draws 40 Iron Ingot/min, against
a geometric withdrawal estimate of 2.00/min — a 10x overshoot, which is why the
declaration matters rather than being a rounding detail:

    option                          plate/min   ingot draw   clock   power MW
    full Constructor, 100%              20.00        40.00    100%       4.00
    underclocked to 10/min              10.00        20.00     50%       1.60
    underclocked to 5/min                5.00        10.00     25%       0.64
    underclocked to withdrawal           2.00         4.00     10%       0.19

The ingot cost is the real figure, not the plate: a full-rate build line adds
1.33 smelters of upstream draw for plates nobody is consuming yet.

### A4.2 A fourth steady state: MATCHED

Bus record §5 lists three states and says only SUNK gives a constant power draw,
gating that on the AWESOME Sink's absence. There is a fourth, and it needs
nothing that is missing from the reference layer:

    MATCHED   underclock the line to its average withdrawal rate. Production
              equals average consumption, so nothing overflows and nothing
              pauses. Power is CONSTANT. The container buffers the burstiness
              of the withdrawal (twenty foundations at once) rather than
              buffering an overflow.

For the Iron Plate build line that is 0.19 MW constant against 4.00 MW
oscillating, and 4/min of ingot draw against 40/min peak. It is strictly better
than the intermittent build for a line whose consumer is a bursty player:
BACK UP presents a 40/min peak draw and a 4 MW peak that the upstream bus must
either carry or dip under, for the same average output.

    CONSEQUENCE   handoff open item 7 is narrowed, not closed. The AWESOME Sink
                  still gates constant power for a line with genuine OVERFLOW
                  to dispose of. It does not gate constant power for a
                  build-material line, because that line can be matched to its
                  draw instead of overproducing into a sink.
    CONSEQUENCE   respec §4's clock toggle acquires a second, non-exceptional
                  use. Underclocking is not only the exactness lever of §4.5 --
                  it is the ordinary way a build-material line is sized, and on
                  this line it is a 20x power reduction.

Recorded as derived rather than stated: Greg named underclocking as an option;
the constant-power consequence and the comparison against BACK UP are computed
here, resting on the §4 convexity (exponent 1.321929) already on the record.

---

## Amendment 5 — 2026-09-21. The two BACK_UP readings are one mechanism, and a line is sized to usage

Appended forward-only. **Unifies A2.2 and A4.2 rather than superseding either.**
Neither was wrong about its own case; the reading that they were two
specifications was.

    stated   "both can be true — a line that first backs up (A2) to overflow
             into adjacent lanes will, eventually, fill up its storage (unless
             manually pulled from or overflow sent to sink) and cause draw
             oscillations (A4.2) — don't size for storage, size for usage (both
             known downstream in lane as well as computed but variable current
             and next tier bootleg needs)"

### A5.1 A2.2 and A4.2 are one line at two points on one trajectory

The bridge was already on the record, in `realization.contracts.Disposition`'s
own docstring, and was not read as one:

> A storage container draws no power and is a finite buffer, so "producers at
> 100% with stock accumulating and nothing withdrawing" is a transient of
> duration capacity/residual and is not a state the tool reports.

That sentence is A2.2 → A4.2. One mechanism, with a time constant of
capacity / slack. What differs between the two amendments is the buffer and
therefore the observation window:

    A2.2's window   the buffer is the belt. It saturates in seconds, so the
                    observed steady draw is the NEED. That is the basis 19.02
                    and 15.79 were computed on, and it is correct there
    A4.2's window   the buffer is a container. Saturation takes capacity/slack
                    minutes, after which the draw oscillates between nameplate
                    and zero. That is correct there

    RETRACTED   the framing carried by the 2026-09-21 16:57 handoff finding 1
                and the busmodel note finding 1 — "the two amendments specify
                BACK_UP differently and the recompute has to pick." There is
                nothing to pick. Both are the same state, observed before and
                after the buffer saturates

### A5.2 Average draw is usage in every state. Nameplate is the peak

Backpressure is a DUTY CYCLE, not a clock. A bus at utilisation u draws
u × nameplate **on average** whether a clock set it or the belts idled it — the
two differ in power, not in average throughput. Therefore:

    average draw   = usage. In every state, including BACK_UP and WITHDRAWN
    peak draw      = nameplate, for capacity/slack after a drawdown
    the states     differ in POWER (convex in clock, linear in duty cycle) and
                   in peak DURATION. They do not differ in what a line costs
                   its source bus on average

    CONSEQUENCE    disposition is DERIVED, not declared. It is a consequence of
                   (supply − usage) and of where the slack goes. WITHDRAWN vs
                   MATCHED is only whether the excess is zero by integer luck or
                   zero by clock; BACK_UP vs SUNK is only slack routing. What a
                   caller declares is the usage estimate and the slack routing
    CONSEQUENCE    `busmodel.BusSpec.presents_peak_draw` loses its reason to
                   exist as a SIZING switch, and `SizingBasis.PEAK` becomes a
                   REPORT mode rather than a solve mode. The peak is still worth
                   reporting, but for a different question: what a refill
                   transient costs the PRODUCTION consumers that share the
                   source bus, since splitters round-robin and do not prioritise
    CONSEQUENCE    the realization layer's bodies, written 2026-09-21, compute a
                   consumer's draw as `machines × per-machine rate`. That is the
                   peak. Correct for a saturated consumer, an overstatement for
                   a slack one

### A5.3 A3.5's draw column is pre-saturation, and uniformly

Derived, not stated, and **not computed** — this is arithmetic on two of A3.5's
own rows, not a recompute.

A3.5's IronRod draw of 64.00 is Rotor's 24.00 plus four screw machines at 10.00
each. But Rotor is one machine, supply 4.00 against draw 2.00 — 50% utilisation,
so its steady rod draw is 12.00, not 24.00. The screw bus is 160.00 against
124.00 — 77.5%, so its steady rod draw is 31.00, not 40.00. Rod demand becomes
about 43 and the bus is 3 machines rather than 5. The cascade continues: Rotor
at 50% draws 62 screws rather than 124, which is 2 screw machines rather than 4.

    CONSEQUENCE   size-for-usage does not merely trim the build lines. It
                  shrinks the PRODUCTION CHAIN. A3.5's 27 machines is a
                  transient figure — what the factory draws before its
                  containers saturate, not what it settles at
    NOT COMPUTED  the full cascade. `worked_case_A4` under a usage basis is what
                  the recompute now has to produce, and it is no longer a
                  question of which amendment to follow

### A5.4 A4.1's four options are one continuum on one bus

A4.1's table reads as a line-level choice between dispositions. It is not: build
supply is a machine-count-and-clock decision on the same bus, and a separate
line is one option among several rather than the framing.

    add a machine at any clock   fully representable today
    overclock an existing one    power is priced — `power_exponent` 1.321929 on
                                 all eleven rows of production_buildings.csv.
                                 The shard → clock ceiling is NOT in
                                 planning_data/game/reference: the only clock
                                 columns there are extraction_rates.csv's
                                 nominal/max_250 pair, checked 2026-09-21. Power
                                 Shard is a real item with four recipes, so its
                                 supply chain is representable; what it buys is
                                 not
    somersloop                   parked. Same gap shape as respec §10.6

### A5.5 The withdrawal figure becomes a derived floor, and the floor is what makes one pass legal

A whole-game build-material bill closes a loop: machine counts → construction
bill → build-line sizing → more machines → bigger bill. That feedback is exactly
what the demand pass forbids (single reverse-topological traversal, no fixed
point — see `toggle_propagation_and_demand_pass.md` §5).

It converges, and fast: one Constructor costs 8 Cable and 2 Reinforced Iron
Plate and produces 20 plate/min, so the map is a hard contraction. But
converging is not the same as permitted.

**Omitting the second-order term — the machines needed to build the machines
that make the build materials — leaves the bill BELOW the truth, and below the
truth is the basis the coverage criterion is already stated against (A3.3).** So
a single pass is legitimate precisely because it under-counts. The floor is not
a tolerated imprecision; it is the form of this number that fits the pass.

    stated        "if we considered the entire production cycle from start to
                  end of game, possibly based on site selection and logistics
                  between, we should be able to back into those numbers as a
                  floor (and floor is sufficient)"
    CONSEQUENCE   §8.2's geometric estimate is not corrected — it is superseded
                  in PROVENANCE. A derived whole-game floor and a declared
                  footprint floor are different bases with different error
                  characteristics, not better and worse instances of one basis.
                  `WithdrawalBasis` has one value today; it needs a second, and
                  `Coverage.basis` has no default precisely so the distinction
                  cannot be dropped on the way out
    CONSEQUENCE   the bill is a STOCK pass, computed from settled machine counts
                  and kept out of the flow traversal. Folding it in is how the
                  loop gets smuggled into a pass that refuses loops

Decomposition of the bill, and which half is computable when, is recorded
separately — it changes what §8.2 is for rather than correcting a figure.

### What this amendment does not establish

    not computed   `worked_case_A4` under a usage basis. A5.3 is two rows of
                   arithmetic, not a solve
    not changed    no code, no declaration and no published table moves on
                   account of this amendment. `presents_peak_draw` still sizes,
                   the realization bodies still compute nameplate, and A3.5
                   stands as written
    unverified     idle power draw ≈ 0, unchanged. A5.2's claim that the states
                   differ in power but not in average draw assumes an idling
                   machine costs nothing
