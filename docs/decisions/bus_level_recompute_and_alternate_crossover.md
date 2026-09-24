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

## Amendment 6 — 2026-09-22. The peak stops sizing, and A5.3's cascade is computed

Appended forward-only. **Amendment 5 changed no code and said so**; this is the
code change, and it moves one published conclusion between columns. Nothing
above is edited.

Every figure below was computed in an agent container on 2026-09-22 from
`tools/busmodel` at the scenario of record (1.25x inputs, 2.0x Project
Assembly), against `declarations.worked_case_A4`. Each is pinned by
`tools/busmodel/tests/test_published_tables.py` section 7, so the table is a
regression target rather than a run nobody can repeat.

### A6.1 `presents_peak_draw` is removed, not renamed, and `SizingBasis.PEAK` is refused

A5.2 says the field "loses its reason to exist as a SIZING switch". Reading it
again against its only call site says something stronger:

    presents_peak_draw=(build_plate_disposition is Disposition.BACK_UP)

It was DERIVED FROM THE DISPOSITION at the declaration site. It was never a
declaration — it was a rule written out by hand at the one place that needed
it. So it is removed rather than demoted to a report-only field: a declaration
nothing reads lets a caller state a preference that silently does not apply,
and a caller who still passes the keyword now gets a `TypeError`, which is the
loud break a rename would have been.

`SizingBasis.PEAK` is kept as a value and **refused by `solve`**, naming A5.2
and naming the three fields that carry the peak instead. Deleting the member
would answer a caller with an `AttributeError`, which says nothing about why.
`--basis peak` still reaches that refusal on purpose.

`SizingBasis.USAGE` is a NEW value rather than a redefinition of `AVERAGE` —
the same forward-only rule `WithdrawalBasis` follows. `AVERAGE`'s docstring is
corrected to say what it always computed and does not claim to be right:

    AVERAGE   THE BASIS OF RECORD. A MIXTURE and not an average — a WITHDRAWN
              consumer draws its NAMEPLATE, everything else draws its usage.
              A5.2 says that split is an artefact of the observation window
              rather than a model. It stays because the published tables were
              computed on it and reproducing them is this package's first job
    USAGE     A5.2's basis. Every consumer draws its usage, in every state

Collapsing `AVERAGE` into usage was measured before it was rejected: it breaks
seven of the published reproductions, which is the oracle losing its first job
to gain a better name.

### A6.2 A4.2's central comparison is RE-BASED, not retracted

This is the conclusion that moves, and it is the reason this amendment exists
rather than a commit message.

A4.2 concluded that a full-rate Iron Plate build line "does not merely cost
more power, it costs a smelter producing plates nobody consumes." That
conclusion was computed on the peak basis. On the usage basis it does not hold,
and A5.2 predicts exactly that — the states do not differ in what a line costs
its source bus on average.

    computed 2026-09-22, MATCHED build line vs full-rate BACK_UP, one field
    changed and everything else held:

                            MATCHED      full-rate     delta
    ingot demand /min        204.00        204.00       0.00   was 36.00
    ingot machines                7             7          0   was +1
    ingot PEAK demand /min   204.00        240.00      36.00
    peak shortfall /min        0.00         30.00      30.00

**The 36/min did not disappear. It changed columns.** It was always a peak
figure; the model was sizing against it and reporting it as a demand.

**And the finding survives, sharper.** The full-rate line asks the ingot bus
for 240/min against a supply of 210 while it refills — 30/min it cannot have.
Splitters round-robin and do not prioritise, so that shortfall is paid by Wire,
Iron Plate and Iron Rod, which hold 98% of the bus between them; the build line
itself holds 2.0%. A4.2's answer to "what does the full-rate line cost" becomes
*it starves its neighbours during a refill* instead of *it costs a smelter*.

    NOT ANSWERED   how much that costs. The duration is capacity/slack and no
                   container capacity reaches this layer, so the shortfall is
                   reported as a rate and its duration is not guessed
    SUPERSEDED     A4.2's "+1 SMELTER" line, in provenance. The comparison is
                   restated in `test_amendment_4_iron_plate_build_line`, whose
                   docstring names what it stopped asserting

### A6.3 A5.3's cascade, computed

A5.3 derived the direction from two rows and said "NOT COMPUTED — the full
cascade." This is it. Same declaration, same scenario, one claim changed: a
WITHDRAWN consumer draws its usage rather than its nameplate.

    bus                 AVERAGE                 USAGE
                        m   demand   residual   m   demand   residual
    smart_plating       1     2.00       0.00   1     2.00       0.00
    rip                 1     4.00       1.62   1     4.00       1.62
    rotor               1     4.00       0.00   1     4.00       0.00
    screws              4   124.00      36.00   4   124.00      36.00
    wire_iron           3    46.88      20.62   2    33.33      11.67
    wire_copper         1    14.00      16.00   1    14.00      16.00
    cable               1     3.00      27.00   1     3.00      27.00
    concrete            1     6.00       9.00   1     6.00       9.00
    iron_plate          2    24.38      15.62   1    17.33       2.67
    iron_plate_build    1     2.00       0.00   1     2.00       0.00
    iron_rod            5    64.00      11.00   4    55.00       5.00
    iron_ingot          7   204.00       6.00   4   115.89       4.11
    copper_ingot        1    15.00      15.00   1     7.00      23.00

    TOTAL              29  machines,           23  machines,
                       21.747 continuous       16.989 continuous

    out-of-scope Iron Ore   210.00/min          115.89/min

**A5.3's consequence holds, and is stronger than its prediction.** Six machines
come off, and NONE of them is a build line: Cable, Concrete and the Iron Plate
build line are one machine on both bases, held there by the machine floor.
Every machine removed comes off Iron Ingot (7 → 4), Iron Rod (5 → 4), Iron
Plate (2 → 1) and Wire_iron (3 → 2), which are production buses. Sizing for
usage shrinks the production chain, not the build lines.

    NOT A CORRECTION OF A3.5   A3.5 stands as written and is still not a
                               regression target, for the reason A4.1 already
                               gives: its withdrawal column sits inside the
                               demand sum on two rows and outside it on four.
                               This is a NEW table over `worked_case_A4`, which
                               is the topology with that defect removed
    A5.3's own arithmetic      predicted Iron Rod demand "about 43" against
                               the 55.00 computed here. The gap is A3.5's
                               Rotor row at 50% utilisation, which
                               `worked_case_A4` does not reproduce because its
                               withdrawal is inside Rotor's own demand. The
                               DIRECTION was right and the figure was on the
                               older topology

### A6.4 What the peak reports now, and the guardrail that keeps it there

The peak is computed on every solve, under either basis, and it is REPORTED:

    ConsumerShare.peak_per_min        one consumer's nameplate on this bus,
                                      equal to its average under MATCHED
    BusSolution.peak_demand_per_min   external + every consumer's peak + the
                                      declared withdrawal
    BusSolution.peak_shortfall_per_min    max(0, peak demand − supply)

Wire_copper is the sharpest row and was invisible before: Cable draws 3.00/min
on average and 90.00/min at nameplate, so the peak asks 95.00/min of a bus
supplying 30.00 — a shortfall of 65.00/min. Under the old peak basis that sized
Wire_copper at four Constructors and the transient vanished into a machine
count. It now sizes at one on both bases and the 65.00 is reported.

**A peak that can move a machine count is `presents_peak_draw` again under a
new name**, so the guardrail is structural rather than a note: the sizing reads
`demand_per_min` alone, and a test re-solves a declaration whose peaks differ
by a factor of ten and asserts that every machine count, every residual and
every clock is unchanged.

### What this amendment does not establish

    not decided    whether `USAGE` should become the default. `AVERAGE` stays
                   the default only because the published tables were computed
                   on it; that is a reproduction argument, not a modelling one,
                   and the two will have to be separated
    not changed    the realization layer. A5.2's third consequence — that
                   `realization.buses` computes a consumer's draw as
                   `machines × per-machine rate`, which is the peak — is
                   untouched here. `busmodel` and the bodies it checks now
                   disagree on this, by design and not by accident, and the
                   oracle is the one that moved
    not modelled   the transient's DURATION. capacity/slack needs a container
                   capacity, and none reaches this layer
    unverified     idle power draw ≈ 0, unchanged from A5. A5.2's claim that
                   the states differ in power but not in average draw still
                   assumes an idling machine costs nothing
    not recomputed the storage review's sections 5, 6.1 and 7 under `USAGE`.
                   They reproduce on `AVERAGE` and were not re-run on the new
                   basis; what they would say is unknown rather than unchanged

## Amendment 7 — 2026-09-22. Three in-game reads, and the transient acquires a duration

Appended forward-only. Nothing above is edited, including amendment 6, which
was written earlier the same day and is corrected forward at A7.4.

    source   Greg, in session 2026-09-22, game settings menu and in-game
             reads. Three of the five outstanding game observations named by
             the 10:30 handoff; the fluid-unit read is still outstanding

This is amendment 1's document type rather than amendment 5's: it records
observations and what they close, not a change of framing.

### A7.1 An idle machine draws no power. The assumption is discharged

    stated   "when a machine is idle it draws no power"

Every amendment since A5 has carried `idle power draw ≈ 0, unverified` in its
own "does not establish", and A6 inherited it unchanged. It is now observed.

It does more than remove a caveat: it is what makes the POWER half of A5.2
correct rather than merely assumed. `_lane_power` treats backpressure as a DUTY
CYCLE and prices it linearly, and a set clock as convex at `power_exponent`
1.321929. Linear-from-zero is exactly right when the idle end of the duty cycle
costs nothing, and it is wrong by a constant if idling costs anything at all.

    CONSEQUENCE  MATCHED is strictly cheaper in power than BACK_UP at the same
                 average throughput, for every utilisation below 1. That was
                 the model's behaviour already; it is now the model's behaviour
                 for a reason
    CLOSED       the `unverified` line carried by A5 and A6

### A7.2 The Power Shard ceiling is known, and A5.4's gap closes

    stated   1 shard -> 150%, 2 -> 200%, 3 -> 250%. Shard CRAFTING follows the
             recipe multiplier — a 2x run needs 2 blue slugs per shard against
             1 at 1x — while the MAM unlock does not: 1 blue slug at both

A5.4 recorded that "the shard → clock ceiling is NOT in
planning_data/game/reference: the only clock columns there are
extraction_rates.csv's nominal/max_250 pair", and concluded that a shard's
supply chain was representable while what it buys was not. The ceiling is
`100 + 50 × shards`, capped at three shards, and 250% agrees with the
`max_250` column already carried for extractors.

**Overclocking is therefore now fully representable**: the shard supply chain
(already), the clock ceiling (now), and the power cost (already, through
`power_exponent`).

    FLAGGED, NOT WIRED   representable is not the same as wired to an
                         objective. A layer that can price "overclock this
                         machine versus add another" is answering a build
                         question, which is the drift the standing guardrail
                         exists to prevent. A5.4 listed overclocking under
                         OPTIONS rather than under the model, and this
                         amendment does not move it
    SECOND READING       the crafting/unlock split is evidence for a modelling
                         choice already made: `unlock_cost` reads
                         `schematic_costs.csv` and is not scenario-scaled,
                         while recipe inputs are. One MAM node is evidence for
                         Milestone costs, not proof, and MAM schematics are
                         excluded from `schematics_at_tier` in any case

### A7.3 Container capacity reaches the model. The time constant is computable

    stated   Storage Container 24 slots, Industrial Storage Container 48 slots.
             Fluid Buffer 400 m3, Industrial Fluid Buffer 2400 m3. No change
             with tier or with any multiplier

The missing half was only ever the slot count. The other half has been in the
repo all along: `items.csv` carries `cached_stack_size` per item — SS_ONE 1,
SS_SMALL 50, SS_MEDIUM 100, SS_BIG 200, SS_HUGE 500 — and items.csv is the sole
resource authority. So

    capacity(container, item) = slots x cached_stack_size(item)

and it is CANONICAL and SCENARIO-INVARIANT, which puts it alongside building
construction cost rather than alongside a recipe amount.

A5.1's time constant, computed at last, over `worked_case_A4` under
`SizingBasis.USAGE`, scenario of record, one Storage Container per bus:

    bus             item          stack       R/min    capacity   saturates in
    screws          Screws          500       36.00      12,000        333 min
    cable           Cable           200       27.00       4,800        178 min
    copper_ingot    Copper Ingot    100       23.00       2,400        104 min
    wire_copper     Wire            500       16.00      12,000         12.5 h
    concrete        Concrete        500        9.00      12,000         22.2 h
    iron_plate      Iron Plate      200        2.67       4,800         30.0 h
    smart_plating   Smart Plating    50        0.00       1,200          never
    rotor           Rotor           100        0.00       2,400          never

**Saturation time is a property of SCALE, not of the container.** It is
capacity over slack, and slack grows with the factory while a container does
not, so a bigger line saturates its container faster. The hours above are a
consequence of `worked_case_A4` being four machines wide at its widest. This
reconciles the record with the standing observation that storage fills quickly
in a real factory: both are the same formula at different scales.

**Three buses never saturate at all**, because their residual is zero by design
(A3.4). For those, A4.2's post-saturation regime never arrives and the
BACK_UP/MATCHED distinction has nothing to bite on.

### A7.4 The refill transient is not brief, and A6.2's phrasing is corrected

A6.2 concluded that a full-rate build line "starves its neighbours for the
duration of a refill" and reported the shortfall as a rate because the duration
was not modelled. The duration is now bounded, and the phrasing was too kind:
the transient is hours, not a spike.

Worked, the Cable line against Wire_copper, same solve as above:

    Cable container, Mk1                                     4,800 units
    refill from empty at NAMEPLATE 30/min                        160 min
    wire Cable needs at nameplate                                90/min
    wire_copper supplies                                         30/min
    Cable is therefore throttled to                     8.33 - 10.00/min
    refill from empty, actual                              480 - 576 min

The range is whether the player keeps taking their 5/min withdrawal from
Wire_copper during the refill; splitters round-robin and do not prioritise, so
both ends are reachable and neither is chosen here.

**The refilling line is throttled by the very bus it is starving.** That is a
feedback loop, and the demand pass is a single reverse-topological traversal
that refuses loops for the reason recorded in
`toggle_propagation_and_demand_pass.md` §5. So the model reports the shortfall
as a rate and a capacity-derived bound, and does not iterate to the true
figure.

    SUPERSEDED   A6.2's "for the duration of a refill", in implication rather
                 than in substance. The shortfall and the 98/2 split of who
                 pays it stand exactly as computed
    NOT TAKEN    solving the transient. It is a fixed point, and acquiring one
                 here would put in the stock/flow layers exactly what §5 keeps
                 out of them

### What this amendment does not establish

    still open   the fluid unit. `items.csv` gives SS_FLUID a
                 `cached_stack_size` of 50000 with no unit named, while the
                 buffer capacities above are read in m3. Reconciling them is
                 the same read as the outstanding "observe a fluid recipe at
                 1.25x and read the UNIT", which now has a second consumer
    not modelled the player's drawdown. A6.4 reported a shortfall rate; A7.4
                 adds a capacity-derived bound on its duration. How much a
                 player actually pulls is not a modelled quantity and no
                 amendment here makes it one
    not wired    container capacity. It is computable as of this amendment and
                 nothing reads it — no type carries a container, and the
                 saturation column above was produced by a script, not by the
                 model
    not taken    fluid buffers as storage. Greg's own reading is that they are
                 not: a full buffer stops the machines feeding it and clears
                 only by manual flush or by downstream consumption, so a fluid
                 line has no WITHDRAWN analogue. Recorded, not modelled
    unchanged    the AWESOME Sink, the somersloop axis, and every parked item
                 A6 carried forward

## Amendment 8 — 2026-09-23. The realization layer follows A5.2, and `external` was basis-coupled

Appended forward-only. Nothing above is edited. Discharges A5.2's third
consequence, which A6 declined in its own "does not establish" ("not changed —
the realization layer"). `busmodel` and `realization.buses` now size on the same
basis, so the oracle's second job — checking the realization bodies against
something that is not themselves — is available again on this axis.

    decided   Greg, in session 2026-09-23: option A of three — size on usage,
              report the peak, and add a fixture that can tell them apart
    measured  agent container, 2026-09-23, against `0d8d7d7c`. Not Greg's
              machine, and not the full suite

### A8.1 What the bodies computed, and what they compute now

    before   every consumer drew `machines × per-machine input` — nameplate,
             in every disposition. Not busmodel's `AVERAGE` (which is
             nameplate on WITHDRAWN only) but the basis busmodel's `solve` now
             REFUSES as `SizingBasis.PEAK`. A peak could move a machine count
             in this layer, which is what A6.4's guardrail forbids in the other
    after    `draw_per_min` = consumer demand × per-machine input / consumer
             rate — busmodel's `USAGE`. Nameplate is reported as the new
             `ConsumerShare.peak_per_min`, equal to usage under MATCHED and on
             a withdrawal, the same two rules busmodel follows

`USAGE` rather than `AVERAGE` because this layer has no published table to
reproduce. `AVERAGE` exists for the oracle's first job; action 2's question
(whether it stays busmodel's default) is not decided by this and does not need
to be.

The body's docstring said the signature admitted only nameplate because "no
consumer's settled demand is available here". It was: `_demand` is already
reached through the same cached recursion `_machines` uses. No signature
changed.

### A8.2 `external` subtracted a peak from an average

`_demand` derives out-of-scope demand on a solved bus as
`max(0, machine_equivalents × rate − automated)`. The solve's figure is
continuous; `automated` was nameplate. So genuine out-of-scope demand up to the
consumers' integrality slack read as ZERO and was absorbed into the sizing
without being reported. Measured, worked case at the scenario of record, the
solve asking 132 screws/min against 92 of in-scope usage:

    peak basis    external = max(0, 132 − 199) = 0     5 machines
    usage basis   external = 132 − 92 = 40             4 machines

It erred conservative — no bus was undersized by it — but the figure it
reported was wrong. **This is what made the three outcomes of the 07:35 handoff
unequal**: declining to follow busmodel would have left this subtraction in
place and needed its own repair. On a usage basis the term is coherent without
any change to its own line.

### A8.3 The suite could not discriminate the bases

A usage-basis body passed all 215 realization tests unchanged. `worked_response`
gives RIP and Rotor 1.0 machine-equivalents, `external` lifts each consumer to
one whole machine, and usage equals nameplate on every bus. Two tests claimed
to assert the peak basis and could not fail for that reason. Both are kept and
now assert both fields while claiming neither basis.

A continuous response of the same chain (RIP 0.4, Rotor 0.5, screws 2.3
equivalents) is the fixture that discriminates. On it:

    screw bus        peak basis        usage basis
    draws            75 + 124 = 199    30 + 62 = 92
    machines         5                 3
    residual /min    1.0               28.0

Seven tests added, each confirmed to fail against a body with the old rule put
back: draws and peaks on the continuous fixture, the screw bus's size, the
`external` case above, the MATCHED rule, and two `feasibility` cases below. The
guardrail is the busmodel one restated for this layer: nine extra Rotor
Assemblers multiply Rotor's peak by ten and no machine count, supply, residual
or clock on the screw bus moves.

### A8.4 `feasibility` reads the peak, and that is not sizing

Two of its checks were reading `draw_per_min` and would have changed meaning
silently under the switch:

    branch capacity   a belt carries what the machine draws while it runs.
                      Rotor at 50% averages 62/min and still needs 124/min of
                      branch — usage would pass a belt that starves it
    connectivity      a consumer held at the machine floor with no demand has
                      usage zero and is connected. "Draws nothing" is a PEAK of
                      zero — a recipe that consumes nothing the bus carries

Both now read `peak_per_min`. Neither moves a machine count; they report.

### What this amendment does not establish

    not measured  the full suite on Greg's machine. The container ran the
                  realization, busmodel, adapter and progression suites and
                  the stock-to-realization joint; 442 pass and the one failure
                  is `__main__.py` not being staged into the container
    not added     a bus-level peak. busmodel carries
                  `BusSolution.peak_demand_per_min` and
                  `peak_shortfall_per_min`; `realization.Bus` carries neither.
                  The per-consumer peaks are there to sum; the shortfall also
                  needs `external`, which `Bus` does not carry
    not re-run    A6.3's table through the realization layer. The two layers
                  now share a basis; whether they agree row for row on
                  `worked_case_A4` is the oracle's second job, and it has not
                  been done
    unchanged     `realize`'s 0% clock warning. The machine past the ceil is
                  still reported as buying nothing

## Amendment 9 — 2026-09-23. The oracle's second job, run: the layers agree on every row

Appended forward-only. Amendment 8 listed "not re-run — A6.3's table through
the realization layer" in its own "does not establish". This is that run.

    measured  agent container, 2026-09-23, against `8d64a2f0` plus the change
              recorded at A9.2. Pinned by
              `tests/test_oracle_against_realization.py`

### A9.1 Thirteen buses, one disagreement in definition and none in substance

`worked_case_A4`, scenario of record, busmodel under `SizingBasis.USAGE` against
`realization.buses_from_response` on a translated request:

    agree   machine count, automated demand and withdrawal on all 13 buses.
            23 machines on both sides — A6.3's USAGE total. Iron Ingot 115.89
            on 4 Smelters, both sides
    agree   every consumer's usage AND peak on every bus, including the MATCHED
            Iron Plate build line, whose peak equals its usage in both layers
    agree   supply on every non-MATCHED bus. On the MATCHED bus busmodel's
            clocked supply equals realization's lanes at their clock
    differ  the residual, BY DEFINITION and on the record: busmodel's is
            supply − (automated + withdrawal + external); realization's is
            supply − automated, leaving withdrawal to `coverage_for` and
            external out of scope. Every difference on the table is exactly a
            withdrawal or the root's external. Not compared as a number

The translation is where a false agreement or disagreement could come from, so
it is pinned separately: the response carries ONE `RecipeUse` (the root, at
busmodel's declared external over its rate) and every other bus is DECLARED,
which makes realization's derived external zero by absence — what busmodel
declares for those buses.

Every test was confirmed to fail against a body with its rule reverted — the
usage draw, the MATCHED peak rule, and A9.2 below.

### A9.2 Two DECLARED buses on one recipe are admitted

The run could not start as the bodies stood: `worked_case_A4` puts the Iron
Plate production bus and its build line on one recipe, and `_attribute` refused
two buses on one recipe "whatever their provenance". Neither of its reasons
holds when both are DECLARED — both carry `machine_equivalents=None`, so
nothing is double-counted, and `_check_partition` walks `response.recipes`,
which holds neither. The refusal is NARROWED to recipes the solve ran.

    BEHAVIOUR CHANGE   a declaration previously refused is now sized
    unchanged          the SOLVED case — a build line beside a production bus
                       the solve runs on the same recipe — is still refused by
                       name, and still needs bus identity beyond
                       (item, sources, recipe) to close

### What this amendment does not establish

    not shown   agreement on any declaration but `worked_case_A4`. The storage
                review's cases are busmodel reproductions on `AVERAGE`, which
                realization does not implement
    not shown   agreement where the solve runs a non-root bus. Every non-root
                bus here is DECLARED, so `external` on a SOLVED intermediate —
                A8.2's case — is covered by `test_buses.py` and not by the
                oracle

## Amendment 10 — 2026-09-23. `USAGE` is the default; the record is named

Appended forward-only. Amendment 6 recorded "not decided — whether `USAGE`
should become the default. `AVERAGE` stays the default only because the
published tables were computed on it; that is a reproduction argument, not a
modelling one, and the two will have to be separated." This separates them.

    decided   Greg, in session 2026-09-23: option 2 of three — `USAGE` becomes
              the default, every reproduction names `AVERAGE`, and the CLI
              keeps `--basis` as the override. Chosen over keeping `AVERAGE`
              (casual calls answer on a retracted basis, silently) and over
              removing the default (every unnamed call breaks)

### A10.1 What moved and what did not

    moved       `solve()`'s default, and the CLI's `--basis` default, from
                `average` to `usage`
    named       every reproduction in `test_published_tables.py` passes
                `sizing_basis=RECORD`, a module constant bound to `AVERAGE`.
                No published figure moved, and none could: each call now says
                which basis it reproduces instead of inheriting one
    widened     the two peak guardrails in `test_refusals.py` ran on the
                default alone. They now run on both bases, so the default
                moving did not silently change which basis they guard
    pinned      the default itself, on `solve` and on the CLI; and that the
                default and the record disagree on `worked_case_A4` (23
                against 29), which is what lets the pin fail
    unchanged   `AVERAGE` as a value and its meaning. Realization, which sizes
                on usage unconditionally (A8.1)

Every new or widened test was confirmed to fail with the old default put back.
Container 2026-09-23: busmodel's suite collected 64 before and 69 after.

### What this amendment does not establish

    not re-run   the storage review's sections 5, 6.1 and 7 under `USAGE`.
                 Still unknown rather than unchanged

## Amendment 11 — 2026-09-23. The storage review under `USAGE`: sections 5 and 7 have no demand to size

Appended forward-only. Amendment 6 recorded "not recomputed — the storage
review's sections 5, 6.1 and 7 under `USAGE`. What they would say is unknown
rather than unchanged." This is the recompute. Nothing above is edited, and the
storage review (`storage-model-bundle-review-2026-09-21.md`, rev 4) is not
edited either; where this contradicts it, this is newer.

    measured  agent container, 2026-09-23, against `2aef8e58`. Pinned by
              `test_published_tables.py` section 8. The reproductions on
              `AVERAGE` (sections 1-3 there) are unchanged and still pass

### A11.1 Section 5: every machine above the floor is the review's 100%-clock assumption

The storage review's declarations have zero external demand (the recovered
rule, section 1), no declared withdrawal, and every line WITHDRAWN. On `USAGE`
that is a factory with NO demand in it: every bus sits at the one-machine
floor, continuous machines 0.000, whole output as residual.

    table              AVERAGE (record)   USAGE
    T1-2 @1x           15 machines         9 — one per line, the floor
    T1-2 @1.25x        18 machines         9
    base RIP @1x       16 machines         9

So every above-floor machine in section 5 — and therefore the 12.5x Iron Plate
notch and Screws' 0.00 → 26.00/min — is a floor machine at a demand-less root
drawing its nameplate, propagated upstream. The review stated this assumption
itself (§9: "every modelled line runs at 100% clock"); A5.2 is what makes it an
assumption rather than a model.

    STANDS      the sawtooth. Overflow = ceil(d/r)·r − d is arithmetic and
                is non-monotonic in anything that moves d. `worked_case_A4`
                shows it under real demand
    DOES NOT    section 5's INSTANCE. Its magnitudes are properties of the
    TRANSFER    100%-clock assumption on a declaration with no demand, not of
                rounding under demand
    NOT         AVERAGE's 15/18 against USAGE's 9. Under the feasibility guard
    COMPARABLE  these are not a basis comparison: the two runs answer different
                questions (what the lines draw at full rate; what the declared
                demand requires, which is nothing). Reported side by side, not
                differenced

A5.3 asked whether its cascade is a property of `worked_case_A4` or of every
table. **The storage review cannot answer it** — A5.3's cascade is integrality
slack shrinking under a real demand, and there is no demand here to shrink.

### A11.2 Section 7: the alternate delta is one RIP machine's footprint

On `RECORD` the review's alternate report reads Stitched against base RIP as
15 against 16 machines, iron ingot 100 against 155/min, copper 60 against 30.
On `USAGE` the two regimes are identical: 9 floor machines each, zero
out-of-scope draw. RIP is a root with no demand, so its recipe moves nothing.

    what the record measured   the upstream draw of ONE Reinforced Iron Plate
                               machine at 100% under each recipe. A real and
                               useful per-machine figure
    what it did not measure    what either regime costs a phase, because the
                               phase declares no RIP demand

Giving the roots the config's own declared demand does not rescue it: only
Rotor qualifies (2/min — RIP's one in-file consumer, Modular Frame, is declared
at 0), and the two regimes are still both 9 machines with identical draws.

    STANDS      section 7's REPORT SHAPE — deltas, no ordering, an alternate as
                a re-wiring event. The shape was the finding
    DOES NOT    its figures, as a statement about the phase
    TRANSFER

### A11.3 Section 6.1 has no basis; its usage analogue loses four of six negatives at 1x

Section 6.1 does not call `solve`. Its draw is every line at 100% of the
config's INSTALLED CAPACITY, which is nameplate by construction, and it
reproduces unchanged on any default. There is no `USAGE` re-run of it as
written.

Its usage analogue draws each consumer at the config's OWN DECLARED DEMAND — a
consistency check of the demand column against itself:

                     at capacity (record)          at declared demand
    T1-2 @1x         Screws −50, Wire −18.5,       none
                     Rod −3
    T3-4 @1x         Screws −50, Wire −37.3,       Wire −17.10
                     Rod −6
    T1-2 @1.25x      Screws −74, Wire −30.9,       Screws −12.00
                     Rod −8.5, Plate −5.6
    T3-4 @1.25x      Screws −74, Wire −53.7,       Screws −12.00, Wire −26.98
                     Rod −13, RIP −0.5

Screws at 1x goes from −50 to 0: Rotor is declared at 2/min, half its machine,
so it draws 50 screws and the config declares 50. At 1.25x the multiplier
raises that to 62, and the −12 is the scenario, not the config.

**This contradicts the storage review's §9**, which says "§6.1's negative deltas
are robust to [the 100%-clock assumption]: an underclocked line would show a
positive delta." An underclocked consumer draws less, so every delta moves
positive — which is the direction that REMOVES negatives. Four of the six at
1x do not survive. The one that does, T3-4 Wire, is a real inconsistency in the
config's demand column on its own terms.

    CONSEQUENCE   the review's settle-first item 4 ("correct the three negative
                  deltas") was stated against capacity-basis deltas. On the
                  demand column's own terms there is one at 1x, not three

### What this amendment does not establish

    not decided   whether section 5 and 7's record tests keep their current
                  docstrings. They reproduce the record, correctly, and a
                  reproduction does not have to endorse what it reproduces;
                  amendment 11 is where the reading lives
    not re-run    the storage review's §3 table, which used the config's
                  declared demand directly rather than the section 5 rule. It
                  was never a regression target
    not modelled  what the config's author meant the roots' demand to be. The
                  declared-demand column is A2.1's derived column; A11.3 uses
                  it only against itself

## Amendment 12 — 2026-09-23. The storage toggle sets the sizing basis, per line

Appended forward-only. Nothing above is edited. Supersedes, in provenance,
A5.2's reading that "WITHDRAWN draws nameplate" is an artefact of the
observation window, and A10's default. Neither is retracted as arithmetic:
A5.2's trajectory still describes a line whose storage saturates, and `USAGE`
still computes what it always computed.

    decided   Greg, in session 2026-09-23 (D1): the storage toggle sets the
              sizing basis, per line
      ON (default)  the line runs at 100%. Its consumers take exactly what they
                    need through an exact splitter/merger setup; the RESIDUAL
                    goes to storage. It draws its NAMEPLATE from its sources
      OFF           the line clocks down to what its consumers need and draws
                    its USAGE. Example: iron wire on the wire lanes
      no residual   a storing line whose output is exactly consumed has nothing
                    to store. The remedy — overclock, somersloop, or add a
                    machine — is the player's; the tool REPORTS it, never picks
    decided   Greg, same session, on the questions the body step raised:
      Q1  the toggle is an EXPLICIT per-line flag, `stores: bool = True`, and
          the disposition is DERIVED from it — A5.2's consequence 1 literally
      Q2  a storing line draws what it PRODUCES: nameplate while it runs at
          100%, a target clock's output once D2 sets one. Stated so D2 does
          not have to supersede D1
      Q3  stores=True -> WITHDRAWN; stores=False with a withdrawal -> MATCHED;
          stores=False otherwise -> BACK_UP (realization's `clock_mode` sets
          any clock)
      Q4  `disposition=` is a TypeError, A6.1's precedent
      Q5  the record path, below
    noted     Greg, same session: time to completion must eventually be
              overridable; until then T defaults to the goal-build derivation
              (D2). Recorded here because it bounds what D2 may assume
    measured  agent container, 2026-09-23, against `de700c05` plus the change
              below. Not Greg's machine

### A12.1 The record's AVERAGE was D1 under older names

`AVERAGE` draws nameplate for a WITHDRAWN consumer and usage for everything
else. WITHDRAWN is "drained continuously, producers at 100%" — storage ON.
BACK_UP (the record's need basis) and MATCHED draw usage — storage OFF. So
`AVERAGE` was D1 wherever a line's disposition had been chosen to mean its
storage state, and A10 had moved the default to `USAGE`, which is storage off
everywhere.

    new value   `SizingBasis.STORAGE`, THE DEFAULT (solve and CLI). A storing
                consumer draws its supply at its clock; a non-storing one draws
                its usage. A new value rather than a re-pointed `AVERAGE`, per
                A6.1's rule that a value's meaning is fixed when it is added
    equal       `STORAGE` equals `AVERAGE` on every declaration today, BY
                CONSTRUCTION: a storing line is WITHDRAWN and runs at 100%.
                They part when D2 gives a storing line a target clock. Pinned
                as an equality so that day is visible
    kept        `AVERAGE` as the record; `USAGE` as storage off everywhere

### A12.2 The record path

Q3's table cannot state two things the record declares. `worked_case_A4`'s
Cable and Concrete lines are BACK_UP WITH a withdrawal — a storing line
measured after its container saturated — which the toggle derives as MATCHED
(off) or WITHDRAWN (on), and either moves A6.3's reproduced AVERAGE column.
And SUNK is not derivable from a bool, so its refusal would be unreachable.

    field      `recorded_disposition: Disposition | None = None` on both
               `BusSpec` and `BusDeclaration`. Taken as given; refused only
               where it CONTRADICTS the toggle (recorded WITHDRAWN with
               stores=False; recorded BACK_UP or MATCHED with stores=True)
    where      `busmodel/declarations.py` alone under `tools/*/src`, through
               `_recorded`, which emits the toggle alone wherever the toggle
               derives the record's disposition. Asserted by inspection in
               `test_refusals.py`. Tests may use it
    result     every reproduction in `test_published_tables.py` passes
               unchanged; the SUNK refusal is still reached and tested

### A12.3 What moved

    busmodel      `BusSpec.stores` replaces `disposition` (was WITHDRAWN by
                  default; unchanged in effect). `STORAGE` is the default basis.
                  `BusSolution.stores_nothing` reports D1's no-residual case and
                  the rendered table lists those lines. `out_of_scope_draw`
                  mirrors the new branch
    realization   `BusDeclaration.stores` replaces `disposition`, whose default
                  was BACK_UP — storage OFF, contradicting D1 and busmodel.
                  `_draw` sizes a storing consumer on what it produces; it now
                  returns (draw, peak, usage). `Bus.stores_nothing` added
    both          `derive_disposition` in `realization.contracts` is the one
                  table; busmodel imports it as it already imports `Disposition`

    worked_case_A4, scenario of record, busmodel and realization agreeing
                             machines   iron ingot demand   iron ore /min
    STORAGE (as declared)       29          204.00            210.00
    storage off everywhere      23          115.89            115.89
    storing, nothing to store: smart_plating, rotor

A6.3's AVERAGE and USAGE columns respectively. The oracle comparison (A9) now
runs on both states and agrees on machines, automated demand, withdrawal,
every consumer's draw and peak, and supply.

### A12.4 Two things D1 exposed

**A8.2's defect would have come back through the storing path.** `_demand`
derived `external` as the solve's continuous figure less `automated`. With a
storing consumer drawing what it produces, `automated` carries the integrality
slack again. `external` now subtracts the consumers' USAGE, kept separately
from the draw. Continuous worked fixture, 132 screws/min asked against 92 of
usage: 6 machines (239/min); subtracting the draw gives 5.

**Realization's MATCHED clock starved consumers.** It clocked to
`withdrawal_per_min` alone, which was right for A4.1's Iron Plate build line —
the only MATCHED line any case declared, with no consumers. Q3 now derives
MATCHED for any storage-off line with a withdrawal, and D1 says such a line
"clocks down to what its consumers need". RIP with storage off, feeding Smart
Plating 2/min and withdrawn at 2/min, ran at 2/min. The clock is now the
line's whole demand over nameplate — busmodel's rule — and is the same number
wherever a MATCHED line has no consumers.

    BEHAVIOUR CHANGE   a MATCHED line with in-scope consumers or external demand
                       clocks higher. `test_rate_is_derived_from_machines_at_the_lane_clock`
                       moved from 1/min on one Assembler to 3/min on two at 75%
    NOT A PRIOR        A9 recorded MATCHED supply agreeing between the layers;
    CONCLUSION         it did, on the one MATCHED bus it had. Recorded here
    CHANGED            because the rule changed, not because A9 was wrong

**The zero-clock contradiction dissolves for a storing bill line.** The
concrete bill line in `test_stock_to_realization.py` stores by default now, so
it runs at 100% and produces the 15/min `projected_coverage` divides by; no 0%
warning. The contradiction is still pinned, on the same line with storage off.

### A12.5 Tests

Every new or changed assertion was confirmed to fail with its rule reverted:
the storing draw, `external` on usage, the STORAGE branch, both defaults, the
realization default, the MATCHED clock, the out-of-scope mirror, both
`stores_nothing`, the record-path contradiction check, the CLI default, and the
rendered report line. The peak guardrail runs on NON-storing consumers in
realization: a storing consumer's nameplate is its draw, and nine more storing
Rotor Assemblers do draw ten times the screws.

    counts   container, collected: busmodel 75 -> 82, realization 224 -> 240,
             tests/ (staged subset) 228 -> 234. 584 pass across the staged
             suites. One run of ten showed one failure whose name was not
             captured; nine runs after it were clean. Not reproduced

### What this amendment does not establish

    not run       the full suite on Greg's machine
    not pinned    the 1 Smart Plating/min figures (17 machines and 120.0 iron
                  ore/min storing; 7 and 23.25 storage off). They came from a
                  scratch driver, and 120.0 is Greg's in-game figure
    not modelled  the exact split D1 assumes. With plain splitters the residual
                  does not reach storage in ratio (hand calculation, 2026-09-23)
    not wired     container capacity. D1's nameplate draw holds for capacity /
                  residual (A7.3). That window has a consumer again
    not built     D2 (goal-paced targets, the time-to-completion override) and
                  D3 (carry-forward across declared stages)
    unreachable   BACK_UP with a withdrawal and SUNK, except by the record path.
                  A future routing value (storage / sink / off) would replace
                  the bool; not decided

## Amendment 13 — 2026-09-23. Goal-paced targets (D2): a storing line clocked to its bill over T

Appended forward-only. Nothing above is edited. Carries D2 out of A12's "not
built" list. A12.1's expectation that STORAGE and AVERAGE "part when D2 gives a
storing line a target clock" did not happen, and A13.3 says why.

    decided   Greg, in session 2026-09-23, on the D2 design note (project doc
              d2-goal-paced-targets-design-2026-09-23.md):
      T   T = anchor goal total / anchor target rate (50 SP at 1/min = 50 min).
          The default derivation; an override is a different number passed to
          the same parameter
      P1  the paced bill = this build's machines + the NEXT tier's bootstrap +
          the unlocks DECLARED for this stage, NOT the cumulative tier set. The
          Project Assembly delivery term is excluded, because the goal item
          already reaches its line as the solve's target
      P2  a new field, `storage_per_min`, on BusDeclaration and BusSpec.
          `withdrawal_per_min` keeps its meaning (A6.1)
      P3  a new derived disposition, PACED (stores=True plus a rate). WITHDRAWN
          keeps "producers at 100%"
      P4  PACED and storage-off MATCHED at one rate compute the same numbers.
          Both are kept, since they state different intent, and the
          equality is pinned
      P5  a paced line with nothing to pace clocks to usage and reports
          `stores_nothing`
      --  two passes: storage off (the floor), then paced. No iteration
    measured  agent container, 2026-09-23. Not Greg's machine

### A13.1 Where the division lives

Realization keeps §9, so no player time enters it. It receives a RATE and
never T. `stock` keeps "never a rate, a horizon". The division is in a new
`progression.schedule`, which divides and nothing else. It is asserted from its
source: the only arithmetic is addition and division, it has no min, max, sort
or rounding, and it imports adapter contract types only.

### A13.2 The loop, and the floor that closes it

The bill needs machine counts (the goal run's O1), and the paced counts need
the bill. That is A5's loop. `goal_run.paced_run` runs:

    floor   every line storage OFF -> bill over those machines
    pace    rate_i = bill_i / T
    paced   storing lines PACED at their item's rate

The paced demand is usage plus a non-negative rate, so every paced line has at
least the floor's machines (asserted per line). The bill is therefore a floor
of the paced build's bill, and Greg's standing position is that a floor
suffices. Two `run` calls and no loop around either, asserted from the source.

### A13.3 STORAGE and AVERAGE do not part

With PACED a separate value, AVERAGE's record rule — a WITHDRAWN consumer draws
nameplate — never reaches a paced consumer. Under STORAGE a paced consumer's
supply at its clock is its demand, which is usage. So all three bases size a
paced line identically, and the basis question does not arise for it. The
A12.1 equality test is unchanged and still true on everything it covers. The
new pin is `test_every_basis_sizes_a_paced_declaration_the_same`.

    NOT A PRIOR CONCLUSION CHANGED  A12.1's equality held and holds. What moved
                                    is only its forecast of where it would fail

### A13.4 What moved

    realization   Disposition.PACED, ClockCause.PACED;
                  BusDeclaration.storage_per_min (refused with stores=False,
                  with a withdrawal rate or bill, on the record path, and
                  below zero). `_demand` adds it; `clock_for` clocks PACED to
                  demand / nameplate; `_draw` reads a paced consumer's supply
                  at its clock (A12 Q2's rule, not a second one);
                  `draw_is_stable` includes PACED; `Bus.storage_per_min`;
                  `stores_nothing` reads the rate on a paced line
    busmodel      the mirror: `BusSpec.storage_per_min`, PACED supply = demand,
                  `BusSolution.storage_per_min`, `stores_nothing`
    progression   `schedule.py`: `horizon_from_anchor`, `storage_rates`
    tools         `goal_run.paced_run`, `PacedRunReport`, `PacedRunError`

### A13.5 First figures

Phase 1, 1x/1x/1x, tier 2, the first-50 partition. The bootstrap is 1 miner and
1 biomass burner. The unlocks declared for the stage are the five milestones
`schematics.csv` places at tech tier 2. T = 50.

                        machines (Asm/Con/Sml)   iron ore /min   phase 1
    storage off (floor)    7  (3 / 3 / 1)             23.25        50 min
    PACED                 16  (3 / 9 / 4)            109.55        50 min
    flat out (A12, D1)    17  (3 / 10 / 4)           120.00        25 min

    rates  plate 22.50, screw 20.00, rod 14.40, RIP 1.60, rotor 1.24 /min
    stores nothing  smart_plating (P1 excludes its delivery term), iron_ingot
                    (no building costs it)

**Finding, which is why P1 was needed.** The design-note prototype paced the
cumulative tier 0-2 unlock set: 1680 plates into 50 minutes, 19 machines and
137.2 ore/min. That is more than running flat out, because tiers 0 and 1 were
bought before the stage opened. P1 exists because of that result.

One oddity in the data, noted where it was found: `Schematic_3-2_C` carries
`tech_tier` 2 and is one of the five. Not investigated.

### A13.6 Tests

Every rule was confirmed to fail with it reverted: storage in realization's
demand, the paced consumer's draw, storage in busmodel's demand, the PA
refusal, a third `run` pass, and the floor pass keeping storage on. The oracle
comparison (A9) runs on a third state, paced. `test_contracts_construction`'s
enum test names the fifth state, as its docstring asked.

    counts   container, collected: busmodel 82 -> 89, realization 240 -> 253,
             tests/ (staged subset) 186 -> 212. 554 pass together, five
             runs clean

### What this amendment does not establish

    not run       the full suite on Greg's machine
    not built     D3 (carry-forward across stages: stock made before a stage
                  opens should reduce what it must make); the T override as
                  a UI; several goals sharing one T, which is the scheduler
                  building OutputTargets
    not modelled  container capacity against a paced fill (A7.3). A bill of
                  rate x T must fit somewhere
    open          which schematics a stage buys is the caller's declaration.
                  Nothing derives it, and deriving it is D3's question

## Amendment 14 — 2026-09-23. Carry-forward (D3): a declared inventory nets the bill

Appended forward-only. Nothing above is edited. Carries D3 out of A13's "not
built" list and settles A13's "open" line on which schematics a stage buys.

    decided   Greg, in session 2026-09-23, on the D3 design note (project doc
              d3-carry-forward-design-2026-09-23.md):
      P1  carry is DECLARED: the inventory the player reads at stage open. A
          modelled estimate (prior rate x gap) may be SHOWN beside it and
          NEVER nets, including when nothing is declared. Greg chose "both,
          declared wins" over the note's "declared only"; the no-declaration
          case was then asked separately and answered "never nets"
      P2  netting lives in `stock` (`net_of` -> `NetStock`: owed, surplus),
          reported and never clamped silently
      P3  against the item's whole bill, not a half
      P4  `schedule` gains a sibling `rates_of`; `storage_rates` unchanged
      P5  an item the holding covers paces to 0.0 and reports stores_nothing
      P6  which schematics a stage buys stays DECLARED. Optional helper
          `unlocks.schematics_in_tiers`; stage -> tiers is declared too
      P7  build and expedition time have no sizing consumer once carry is
          declared. Wall clock per stage is a report with no consumer; not
          built
      P8  `paced_run(on_hand=None, carry_estimate=None)`; the default is A13
      P2-P5 and P8 were accepted as proposed ("build as proposed")
    measured  agent container, 2026-09-23. Not Greg's machine

### A14.1 Why only a declared inventory nets

A13.2's floor is `bill <= true_bill`. Netting gives `bill - carry`, and for
that to stay below `true_bill - true_carry` it suffices that
`carry >= true_carry`. **Once carry is subtracted, the floor needs carry to be
a CEILING**, the opposite of every other term. A read inventory is a
measurement. A modelled carry understates whenever lines ran faster than paced
— the way the pre-Smart-Plating window is played — and so breaks the floor.

The guard is structural: `stock.net_of` refuses any argument that is not a
`DeclaredOnHand`, and `schedule.CarryEstimate` is a separate type with no
`units` pairs. `paced_run` names `carry_estimate` exactly once, in the report
constructor, asserted from the source.

### A14.2 Where the arithmetic lives

    stock      DeclaredOnHand, NetStock, net_of. A sign test splits each
               difference into owed or surplus; no min, max, sort or round,
               asserted. Conservation per item: owed + on_hand == bill +
               surplus. An on-hand item no bill names is surplus, not dropped
    schedule   rates_of (divides). carry_estimate: rate x gap, the one
               multiplication in the module, admitted by the amended
               arithmetic test only inside that function. It is the inverse
               of the module's job and its result cannot be netted
    unlocks    schematics_in_tiers: tech_tier IN the declared set, the same
               three types. A filter; returns ids
    goal_run   paced_run nets the FLOOR bill between the two passes when
               on_hand is given. Still two `run` calls, no loop; G1 holds

The floor pass never sees the inventory, so its build and bill are unchanged
by netting (asserted). The paced rate is non-negative after netting, so
A13.2's per-line `paced >= floor` still holds (asserted).

### A14.3 First figures

Phase 1, 1x/1x/1x, tier 2, first-50 partition, T = 50, A13's declaration.
The inventory is INVENTED for the test, not a reading of Greg's save:
500 Iron Plate, 62 Rotor, 40 Wire.

                            machines (Asm/Con/Sml)   iron ore /min
    PACED, nothing declared    16  (3 / 9 / 4)            109.55   A13.5
    PACED, netted              13  (3 / 7 / 3)             80.60

    rates  plate 22.50 -> 12.50, rotor 1.24 -> 0 (stores_nothing);
           RIP, rod, screw unchanged
    wire   billed (tier-2 unlocks) but no declared bus makes it; the 40 held
           net against it and pace nothing

Each unit held lowers its item's rate by 1/T. A13.5's figures therefore
overstate paced rates by exactly on_hand_i / T per item; a real reading is
what closes that.

### A14.4 The Schematic_3-2_C oddity, resolved by inference only

`3-2_C` (Logistics Mk.2) reads tech_tier 2, `4-2_C` reads 3, `5-3_C` reads 4.
The class names look like pre-1.0 numbering with a correct 1.0 tier, and the
tier-2 set matches the 1.0 tier 2 as recalled. INFERENCE, not measured. P6's
helper is only as right as the column; an in-game read of tier 2 settles it.

### A14.5 Tests

Every guard was confirmed to fail with it reverted: net_of accepting a
non-declaration, an estimate moving the rates, `on_hand` ignored, and a
multiplication outside `carry_estimate`.

    counts   container, staged subset (tests/ and tools/realization/tests):
             135 relevant before -> 168; 194 pass together, six runs clean

### What this amendment does not establish

    not run       the full suite on Greg's machine
    not read      a real inventory; every netted figure above uses an
                  invented one
    not modelled  container capacity against a paced fill or against a gap
                  (A7.3); the estimate ignores saturation and says so
    not built     wall clock per stage (P7); a stage sequence of any kind —
                  carry_estimate takes the prior rates and the gap as handed
                  in and does not know what a stage is

## Amendment 15 — 2026-09-24. Several goals on one T (D4 P6), and the fill over T (D4 P7)

Appended forward-only. A13 and A14 stand. The D4 locks, including (e), the
phase-span reframe, are recorded in goal_run_driver.md amendment 4; this
amendment builds the two parts D4 placed on the scheduler side.

    code      progression/schedule.py (PhaseRates, phase_rates),
              tools/storage_view.py, tests/test_progression_schedule.py (+7),
              tests/test_goal_run.py (+1), tests/test_storage_view.py (8)
    measured  agent container, against e8b02d3 plus goal run A5 plus this
              change. Not Greg's machine

### A15.1 One horizon for a phase's goals — anchored on a goal the caller names

Decided by Greg 2026-09-24: T is anchored on a NAMED goal. With several goals
on one T, a max over goals would pick a binding goal, which the comparator
guard forbids (goal run O3). So the caller names the anchor and its rate;
`horizon_from_anchor` gives T as before; every goal's rate is its total / T.

    phase 2, SP anchored at 1/min    T = 1000 min; SP 1.0, VF 1.0, AW 0.1 /min
    AW anchored at 0.2/min           T = 500;      every rate doubles

"Smart Plating trickles in the background" is expressed by which goal the
caller names and at what rate, not chosen here.

Refused: an anchor that names no goal; a goal id twice; an item twice (its
targets would add); a non-positive total. `phase_rates` builds no
`OutputTarget` — the caller does, outside goal_run (G1). Its arithmetic is
division only, so A13's inspection test (add and divide; one multiplication,
in `carry_estimate`) holds unamended. The import test admits `dataclasses`,
a standard-library record type, for `PhaseRates`.

Not built: a phase-2 run. VF and AW need tier-3/4 lines (steel, modular
frames, stators) and a partition no one has declared yet.

### A15.2 The fill over T, against A7.3 capacity — a view, reported

`tools/storage_view.py`, beside `chain_view.py` and under the same rules
(it calls no layer, ranks nothing, rows carry the report's own buses, no
bool field). Per bus, in report order:

    fill        storage_per_min x T. On a paced line this equals the item's
                owed bill by construction (asserted)
    capacity    A7.3: slots x cached_stack_size (items.csv) x containers,
                with slots and count DECLARED per bus by the caller. The
                24 / 48 slot figures are exposed as constants, not defaults
    reported    minutes to fill (inf when nothing is stored: A7.3's
                "never"), fill as a fraction of capacity. Over 1.0 is a
                number, not a refusal

A13.5's case, one Storage Container per bus:

    T = 50      screws 1000 of 12,000 (600 min to fill); plate 1125 of 4,800
    T = 1000    plate 22,500 units: 4.69 containers' worth

That second line is the standing observation ("storage fills quickly") as a
figure: the phase-span T multiplies every paced rate. Nothing here says what
to build about it.

### What this amendment does not establish

    not run       the full suite on Greg's machine
    not built     a phase-2 partition and run; wall clock per stage
    not modelled  saturation feeding back into anything: the view is read by
                  nothing
