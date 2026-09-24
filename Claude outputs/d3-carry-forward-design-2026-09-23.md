# D3 — carry-forward across stages, design note (proposal), 2026-09-23

    status    PROPOSAL. The parts Greg locks go into a decision record
              (crossover record, next amendment); this stays a draft
    baseline  e12ebeb6, read from .git/logs/HEAD on Greg's machine this
              session. Code read: progression/schedule.py, stock.py,
              unlocks.py, tools/goal_run.py; A7.3 and A13 of the crossover
              record; goal_run_driver.md incl. amendment 1
    measured  nothing run. The arithmetic in §4 was re-derived in the agent
              container from schematic_costs.csv, not from a pipeline run
    bounded by, already decided:
      A13 P1  paced bill = this build's machines + next tier's bootstrap +
              the unlocks DECLARED for this stage; PA delivery excluded
      A13.2   bill over the storage-off pass is a FLOOR of the paced bill,
              and a floor suffices
      stock   quantities only — "never a rate, a horizon"
      schedule  divides and nothing else; no min, max, sort, rounding
      memory  "stock already accumulated before a stage starts ... should
              reduce what the stage must make"; build and expedition time
              "treated as real"

## 1. The three questions D3 carries

    C1  stock on hand at stage open reduces the stage's bill. Where does
        that quantity come from, and where is it subtracted?
    C2  which schematics a stage buys: derive, or leave declared?
    C3  build and expedition time: carry as a floor, or settle?

## 2. Finding that decides C1 — netting inverts the floor's sensitivity

A13.2's floor: `bill <= true_bill`. Netting gives `net = bill - carry`.
For `net <= true_net` it is sufficient that

    carry >= true_carry

So once carry is subtracted, **the floor survives only if carry is a CEILING**.
That is the opposite direction from every other term, which is safe when
understated.

Two sources for carry:

    DECLARED   the player reads inventory at stage open. A measurement, so
               carry == true_carry and the floor holds
    DERIVED    modelled from the prior stage. A paced prior stage finishes
               its bill exactly at T_(k-1) by construction (A13.5's round
               trip: coverage reads T), so its derived surplus is zero. The
               only derivable carry is what lines make AFTER T: rate x gap,
               where gap is build/expedition time before the next stage's
               lines start. Greg's play runs the pre-SP window flat out, not
               paced, so rate x gap UNDERSTATES true carry -> net overstates
               -> the floor breaks

**Derived carry cannot keep A13.2's floor; declared carry can.** That is the
basis for the P1 recommendation below, not a preference.

A second reason, tool gravity: deriving carry means modelling the prior stage's
production, which means a stage sequence, which is a progression simulator — a
broader and more authoritative answer than "what does this stage owe". A
declared inventory keeps the model answering the narrow question.

## 3. Consequence for C3 — build and expedition time lose their sizing consumer

T is the production window (anchor total / anchor rate), not wall clock. Rates
are bill / T and never see build time. Build and expedition time touch sizing
through one path only: lines running on during the gap produce carry. With carry
DECLARED, that effect is already inside the measurement.

    so    build/expedition time has no consumer in sizing once C1 is declared
    left  wall clock (build + T per stage) as a REPORT. No consumer yet, so
          not built. It stays "real" in the sense Greg meant — it is in the
          inventory he reads — without the model estimating it

A7.3 ties in here and is left to next action 3: a gap long enough to saturate a
container caps carry, and A7.3 already computes saturation as capacity / slack.
Declared carry makes that cap observed rather than modelled, too.

## 4. What carry moves — illustrative, phase 1, 1x, T = 50

A13.5's paced rates re-derived from the bill terms (tier-2 unlocks from
schematic_costs.csv; machine and bootstrap terms from A13's prototype split):

    item    unlock t2  machines  bootstrap  bill   /T = rate  (A13.5)
    plate      1100        0        25      1125   22.50      22.50
    screw      1000        0         0      1000   20.00      20.00
    rod         700        5        15       720   14.40      14.40
    RIP          50       30         0        80    1.60       1.60
    rotor        50       12         0        62    1.24       1.24

The unlock term is 98% of plate's bill and 100% of screw's. Each unit on hand
lowers its item's rate by 1/T, i.e. 500 plates on hand -> 12.50/min. The
figures of record are therefore an upper bound on paced rates by exactly
on_hand_i / T per item. No count is predicted here: machine counts move by
ceil and need a run.

Pre-stage context, same table: tiers 0-1 cost plate 555, rod 475, screw 300,
wire 720, cable 70, concrete 280 (+2 coupons). That is what the ~60 min before
Smart Plating SPENT, not what it left over. Carry is production minus that,
which only the inventory knows.

## 5. Proposals — needs Greg

    P1  CARRY IS DECLARED. `on_hand: Mapping[ItemId, float]`, quantities at
        stage open, handed in like the bootstrap set. Nothing derives it.
        RECOMMENDED, by §2. Rejected alternative: derived rate x gap; noted,
        not adopted, because it breaks the floor in the direction Greg plays

    P2  NETTING LIVES IN `stock`, NOT `schedule`. It is quantity arithmetic,
        and `schedule` must stay "divides, nothing else". New
        `stock.net_of(bills, on_hand) -> NetStock`:
            owed      per item, bill total - on_hand, where positive
            surplus   per item, on_hand - bill total, where positive —
                      including on-hand items no bill names
        REPORTED, never clamped silently. A sign test is a branch, not a
        ranking; no min/max. `WithdrawalBill` objects are untouched (their
        basis stays DERIVED_WHOLE_GAME_FLOOR); NetStock is a separate object

    P3  NET AGAINST THE ITEM'S WHOLE BILL, not per half. `schedule` already
        sums bootstrap + remainder; choosing which half on-hand stock pays
        first would be an ordering the model has no basis for

    P4  `schedule` GAINS NOTHING BUT AN INPUT SHAPE. Either storage_rates
        accepts NetStock.owed (a Mapping[ItemId, float]) through a sibling
        function, or NetStock exposes the same attributes. Recommended:
        sibling `rates_of(quantities, T)`, so storage_rates keeps its
        signature and its tests. Still add and divide only

    P5  AN ITEM NETTED TO ZERO IS A13 P5's CASE. Its storing line clocks to
        usage and reports stores_nothing. No new disposition

    P6  WHICH SCHEMATICS: STAY DECLARED, WITH AN OPTIONAL HELPER (the O4
        pattern). `unlocks.schematics_in_tiers(repo, tiers)` — tech_tier IN
        the declared set, same three types as `_reached_at_tier`, a filter
        and not a bill. Stage -> tiers stays declared: the PA table's
        `delivery_unlocks` is prose, the same reason phases are declared.
        "Already bought" is caller state; the caller passes the set it
        still owes

    P7  BUILD/EXPEDITION TIME: SETTLED AS NO SIZING CONSUMER (§3). Wall
        clock per stage is a report with no consumer; not built

    P8  paced_run gets `on_hand` as an optional parameter, default empty,
        so every existing figure is unchanged. Netting sits between the
        floor pass and schedule. Still two `run` calls, no loop; G1 still
        holds (paced_run builds no declaration)

## 6. Data oddity, resolved by inference — needs an in-game read

`Schematic_3-2_C` (Logistics Mk.2) carries tech_tier 2; so do `4-2_C` at 3 and
`5-3_C` at 4. The class names look like pre-1.0 numbering, and the tier-2 set
here (Part Assembly, Obstacle Clearing, Jump Pads, Resource Sink Bonus Program,
Logistics Mk.2) matches the 1.0 tier 2 as I recall it. **Inference, not
measured.** It matters to P6: a tech_tier filter is only as right as the column.
A read of the tier 2 milestone list in game settles it.

## 7. Tests proposed

    - net_of: owed + on_hand - surplus == bill total, per item (conservation)
    - net_of reports surplus for an on-hand item with no bill; drops nothing
    - net_of source by inspection: no min, max, sort, round
    - paced_run with on_hand={} reproduces A13.5 exactly (P8 default)
    - on_hand_i = bill_i -> that line reports stores_nothing (P5)
    - pass 2 machines >= pass 1 machines still holds with netting
    - schedule by inspection: unchanged guardrail, plus rates_of
    - schematics_in_tiers({2}) == the five A13.5 declared; a filter only
      (returns ids, never quantities)

## 8. Not in D3

    per-chain report view (after D3, Greg 2026-09-23); container capacity vs
    a paced fill (A7.3); several goals on one T; the T override UI
