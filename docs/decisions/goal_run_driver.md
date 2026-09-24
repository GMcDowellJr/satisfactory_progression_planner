# The goal run — one pass over every layer, choosing nothing

    status    decided 2026-09-23 (Greg accepted the design note's O1-O4 as
              proposed). Immutable; amend forward
    scope     Phase 2 deliverable 5 (the Project Assembly report), first cut
    code      tools/goal_run.py, tests/test_goal_run.py
    replaces  scratchpad/first50_run.py (never in git; pre-A12, so every
              `disposition=` in it is now a TypeError)
    measured  agent container, 2026-09-23, against 08e4126e plus this change.
              Not Greg's machine

## 1. What it is

    solve -> realize(declared lines) -> project_goals -> stock.bill_for

`run()` calls each layer once and returns `GoalRunReport`, which holds each
layer's answer as the SAME object the layer returned. The only value it computes
is `machines`: the realization's lane machines summed per producer class, in
discovery order.

Location: `tools/` root, next to `production_cli.py`, which set the precedent. A
joint above three packages cannot live inside any of them, because none may
import upward.

## 2. Decisions

    O1  the stock pass's machine counts are the realization's lane machines
        (`machines_of`). They follow from the declaration and nothing chooses
        them, so `stock` still derives no count. The report carries the set
        so a reader can see which build the bill costed
    O2  no bill feedback in the same run. Attaching the bill to a line's
        `withdrawal_bill` needs a second realization whose machines differ from
        the ones the bill was summed over, which is A5's loop. A caller who
        wants a bill-sized line runs again with the bill attached. Noted, NOT
        adopted: one bounded second pass would still be a floor, because a
        bill over first-pass counts leaves out the build-material lines' own
        machines
    O3  no binding goal. It is a max over goals, which the comparator guard
        forbids. Left to the reader until D2 gives the goal build a meaning
        for T
    O4  goals are handed in. `goals_for_phases` builds them from the Project
        Assembly table as an optional helper, scaled through the same
        `apply_project_assembly_quantity` the bill's delivery term uses

## 3. Guardrails — structural, asserted from the source

    G1  no call builds a SolveRequest, OutputTarget, BusDeclaration,
        SourceEdge, RealizationRequest, AllowedRecipes or BootstrapSet
    G2  `run` contains no loop, and each layer has exactly one call site
    G3  no min, max, sorted or sort anywhere in the module
    G4  report fields are the layers' own objects (identity, via spies), and
        every layer saw the one ReferenceData

Every guardrail test was confirmed to fail on a mutation that breaks it:

    sorted machine set                  G3
    project_goals inside a loop         G2
    a RealizationRequest built          G1
    a copy of the realization report    G4
    a second realize call               G2 and the once-per-layer count

## 4. Figures — A12's "not pinned" list, now pinned

1 Smart Plating/min, 1x/1x/1x, tier 2, `first50_run.py`'s partition declared
under A12, bootstrap of 1 miner and 1 biomass burner, phase 1 goal:

                        machines (Asm/Con/Sml)   iron ore /min   phase 1 (50 SP)
    storing (default)     17  (3 / 10 / 4)           120.00        2.0/min, 25 min
    storage off            7  (3 /  3 / 1)            23.25        1.0/min, 50 min

These match A12's scratch-driver figures, and 120.0 matches Greg's in-game
reading. They were re-derived by this run rather than copied from A12.
Storing, the Smart Plating line runs at 100% and makes 2/min against a 1/min
target: the rate is GROSS (see project_goals), so the 25 minutes is what the
build makes, not what the target asked for.

## 5. What this does not establish

    not run       the full suite on Greg's machine
    not built     D2 (goal-paced targets), D3 (carry-forward across stages),
                  a rendered text view of the report
    not modelled  build and expedition time; container capacity (A7.3)
    floor         the bill is a floor for stock's reasons, plus one more: a
                  build-material line not yet declared adds none of its own
                  machines

## Amendment 1 — 2026-09-23. `paced_run` (D2)

Appended forward-only. The goal run's decisions stand. `run` is unchanged and
G1-G4 still hold for it.

`paced_run` composes `run` twice, with `progression.schedule` between the two
calls: first the storage-off floor, then the paced build. It is recorded in the
crossover record's amendment 13, which is where D2's decisions live. What
bears on this record:

    G2   `run` is still single-pass. `paced_run` calls it exactly twice and
         never from inside a loop, asserted from the source. Two passes and not
         one is A13.2's floor argument, not iteration
    G1   `paced_run` builds no BusDeclaration or RealizationRequest; it
         `dataclasses.replace`s the caller's, setting only `stores=False`
         (floor) and `storage_per_min` (paced)
    O2   the bill still does not feed back into `withdrawal_bill`. Pacing
         feeds a RATE, into a different field with a different meaning
    refused   a Project Assembly term in the stock declaration (P1), and two
              storing buses of one item, since the item's bill would pace both

## Amendment 2 — 2026-09-23. `on_hand` and `carry_estimate` (D3)

Appended forward-only. Recorded in the crossover record's amendment 14, where
D3's decisions live. What bears on this record:

    G1   paced_run still builds no declaration. It receives a
         `DeclaredOnHand` the caller built
    G2   `run` unchanged; paced_run still calls it exactly twice. Netting sits
         between the calls and is one `stock.net_of` call, not a pass
    O2   still no bill feedback into `withdrawal_bill`
    new  `carry_estimate` is carried to the report and read nowhere else,
         asserted from the source. With nothing declared, nothing nets

## Amendment 3 — 2026-09-23. The per-chain view

Appended forward-only. Greg's item from the 19:25 handoff ("after D3"): the
caller declares which buses share a chain, and the report groups by chain.
A view only; no sizing moves.

    code      tools/chain_view.py, tests/test_chain_view.py (19 tests)
    measured  agent container, against d1181210 plus this change. Not Greg's
              machine

Decided by Greg 2026-09-23, on questions put to him this session:

    C1  OVERLAP ALLOWED. A bus may sit in several chains, and each chain's
        totals include it. Chain totals therefore do not add up to the build:
        the build total is read from the report and printed once, and every
        shared bus is named
    C2  BELT LOAD IS PER BELT plus the chain's BOUNDARY. No figure is summed
        across items. What the chain draws from outside it is listed per
        (item, source bus), which is the feed a separately built chain needs
    C3  a paced run is shown FLOOR | PACED side by side

Made here, not asked:

    C4  a bus is shown with FLOW (its lanes' output at their clocks: the
        average the belt carries) beside NAMEPLATE (`supply_per_min`). The
        handoff's "belt load" did not say which. Supply alone overstates a
        BACK_UP line's flow (storage-off ingot: 23.25 flowing on a 30.00
        nameplate), and flow alone understates what a belt must fit while
        backed-up machines run (A5.2). The boundary draws are lane input
        rates, so they are on the flow basis
    C5  no belt Mk is shown. `Lane.trunk` is the tier's trunk, not what the
        bus needs, and `LaneInput.carrier` is per lane input. A minimum
        sufficient Mk for a bus's output would be a new selection; not built
    C6  buses in no chain are listed as `(unchained)`, never dropped
    C7  chain_view imports realization types only — not goal_run, not
        progression — so the caller passes `paced.floor.realization` and
        `paced.paced.realization` in

Guardrails, from the source and by identity, each confirmed to fail on a
mutation that breaks it:

    V1  calls no layer and no `dataclasses.replace`; imports no goal_run,
        progression, backend or realize
    V2  no min, max, sorted or sort; caller order kept for chains and buses
    V3  a view's buses ARE the report's objects

Figures, A13.5's case (first-50 partition, 1x/1x/1x, tier 2, T = 50,
nothing declared), with Greg's chains mapped onto the partition by this
session. The mapping is an inference — ingot is read as the plate chain's
feed rather than a member, and rotor is placed in the rod chain:

                           machines floor | paced
    smelting                  1 | 4     iron_ingot
    plate_rip                 2 | 3     iron_plate, rip
    rod_rotor_screws_rip      4 | 9     iron_rod, rotor, screws, rip
    smart_plating             1 | 1     smart_plating
    build                     7 | 16    RIP shared, so chains sum to 8 | 17

The pacing grows the smelting and rod chains most. plate_rip draws 31.20
screws/min paced across its boundary from the rod chain.

## Amendment 4 — 2026-09-24. The case of record, and machines standing (D4)

Appended forward-only. The goal run's decisions and amendments 1-3 stand.
Design note: project doc `d4-buildings-standing-design-2026-09-24.md` (a
draft, left as written). Every lock below is Greg's, in chat, 2026-09-24, and
marked by him "for now".

    code      progression/stock.py (StandingBuildings, NetBuildings,
              net_buildings, bill_for(standing=)), tools/goal_run.py
              (StockDeclaration.standing), tests/test_progression_stock.py,
              tests/test_goal_run.py
    measured  agent container, against c1562f2a plus this change. Not Greg's
              machine

### Definitions

    on hand      ITEMS in storage at stage open (DeclaredOnHand). Nets the
                 item bill
    standing     PLACED machines at stage open that the player lets this
                 stage's plan use (StandingBuildings). Nets building demand
                 per producer class. Declared by COMMITMENT, not by run state:
                 an idle, backed-up or storage-full machine on a line the plan
                 needs counts; one the player won't repurpose doesn't, whatever
                 its state
    power        NOT netted per line. Generators are supply in the power
                 ledger, fungible across a connected grid. Standing coal
                 generators do net against the bootstrap's coal-generator
                 count (same producer class); biomass burners have no class to
                 net against and appear only as ledger supply (base or
                 reserve, fed or not). Separate grids are not modelled; a
                 generator on another grid is declared as not supplying

### The case of record

    target      the Mk1 coal step, 2 Miner Mk1 : 4 Coal Generator : 2 Water
                Extractor (what one Mk1 belt carries; the extractors
                underclocked). Replaces 1 miner + 1 biomass burner. The 2:1:1
                minimum stays a valid declaration and is useful as a power
                floor under standing burners
    partition   the first-50 lines plus copper ingot, wire, cable, copper
                sheet and concrete, each build-material line carrying its
                `recipe_id` (P30)
    on hand     10% of each item's whole floor bill (bootstrap + remainder),
                a declared PLACEHOLDER until a real reading. Built by the
                caller from a first run's floor bill, which is independent of
                on hand (asserted)

The A12-A14 fixtures in test_goal_run.py are kept, not replaced: their
figures are still true of their declarations. The record is a new section.

### D4 locks

    (e)  PHASE-SPAN REFRAME. For Project Assembly goals a stage is the phase
         span: phase 2's SP 1000 / VF 1000 / AW 100 share one T, and SP made
         along the way counts through `project_goals`, never by netting.
         A14 (a derived carry never nets) STANDS
    (a)  a machine the player won't let the plan use is declared as not
         standing. No "committed" field
    (b)  standing nets the class's whole demand: bootstrap + lines
    (c)  no default for generators: each standing generator is declared base
         or reserve, and fed or not
    (d)  generator fuel and water appear in the power ledger only, not in the
         solve
    P1-P7 as proposed in the note, with the above and the two resolutions
    below

### Resolved this session

    S1  LINES NET FIRST. P3 said standing nets with no order; P4 costs the
        owed machines, and the bill's two halves (bootstrap, remainder) need
        an order to split them. Greg's call: standing covers the class's
        LINES first and the rest covers the bootstrap. What is left over is
        surplus, reported. Conservation per class, asserted:
            owed_lines + owed_bootstrap + standing
                == lines + bootstrap + surplus
    S2  POWER LEDGER BASIS: extractors at NAMEPLATE (100%), labelled so.
        Demand is then overstated, so base - demand is the conservative
        figure. A declared clock can be added later without changing that
        label's meaning

### What was built

    stock      `StandingBuildings` (pairs, caller order, a class twice
               refused, negatives refused, zero allowed); `net_buildings`
               (two sign tests per class, no min/max/sort/round, asserted);
               `bill_for(standing=None)` costs each half over its OWED
               machines and carries `StockPass.standing_net`. Unresolved
               costs follow the owed sets, so a fully standing miner no
               longer reports the Portable Miner gap
    BootstrapSet   docstring defect fixed at the site: it said coal power is
               "at least 1 coal generator, 1 water extractor, 1 miner", a
               minimum with 1 miner where Greg revised to 2 on 2026-09-23.
               It now names the set a TARGET. The non-empty invariant stays
    goal_run   `StockDeclaration.standing`, default None. `run` and
               `paced_run` are otherwise unchanged: G1 (builds no
               BootstrapSet), G2 (one call per layer; two `run` calls),
               G3 (no ranking) still hold, asserted by the existing tests.
               Both passes of a paced run net the same reading

Mutations confirmed to fail the new tests: the bootstrap netted before the
lines; a `max` in `net_buildings`; the standing reading not passed through
`run`.

### Figures

1 Smart Plating/min, T = 50, 1x/1x/1x, tier 2, `schematics_in_tiers(2)`, the
record's partition and target. Paced pass; power is production lines only.

                            floor   paced (Asm/Con/Sml)   Fe / Cu / Ls ore /min       MW
    record                   12     27 (3/18/6)   148.62 / 19.88 / 43.20      107.81
    record + 10% on hand     12     26 (3/17/6)   136.083 / 17.892 / 38.88     97.90
    record, coal standing    12     22 (3/14/5)   110.52 / 15.88 / 42.00       75.69

The first two re-derive the 08:35 handoff's scratch figures (which printed
136.08 / 17.89). Floor bill, record (whole units): Cable 656, Concrete 720,
Copper Sheet 40, RIP 188, Plate 1120, Rod 710, Screw 1000, Rotor 122,
Wire 516. With the coal step standing, the bootstrap half is zero on every
item and Copper Sheet leaves the bill (only the water extractors bill it),
so its line stores nothing.

### Known looseness, recorded

    miners   ore extraction is outside the solve, so ore miners are in no
             line's demand. A standing miner on an iron node therefore nets
             the bootstrap's coal miners. The bill stays a floor (looser);
             the declaration rule is the (a) rule: declare only miners the
             bootstrap may use
    extras   standing machines beyond the FLOOR build's lines are surplus
             even when the paced build could use them: the bill is summed
             over the floor (A13.2), so there is nothing for them to net

### Not built

    PowerLedger (P5, S2). Open: how bootstrap generators still OWED (not yet
    standing) are shown, since (c) gives no default and they cannot be read
    several goals on one T over a phase span (P6), scheduler side, outside
    goal_run (G1); the A7.3 storage-fill report (P7)

## Amendment 5 — 2026-09-24. The power ledger (D4 P5)

Appended forward-only. Amendment 4 stands; this builds what it left as "not
built" for the ledger.

    code      progression/power.py, tests/test_progression_power.py (17),
              tests/test_goal_run.py (+2), tests/test_progression_import_
              boundary.py (power.py added to the scanned set)
    measured  agent container, against e8b02d3 plus this change. Not Greg's
              machine

Decided by Greg 2026-09-24, on the question amendment 4 left open:

    L1  bootstrap generators still OWED are PLANNED supply: their own line,
        at nameplate, `fed` left unset (None) because an unbuilt generator
        cannot be read. Never summed into base or reserve

Made here, not asked:

    L2  the ledger takes the production draw as a NUMBER (the realization's
        `total_power_mw`), so `progression` gains no realization import and
        `stock` stays the one module touching `realization.contracts`
    L3  generator readings are a second declaration beside
        `StandingBuildings`, and must agree with it: per generator class, the
        readings' counts sum to the standing count, or the ledger refuses. A
        coal generator read but not declared standing would supply without
        netting the bootstrap, then be planned again. So burners are declared
        standing too; they ride as surplus in the netting and change no bill
    L4  demand counts the bootstrap TARGET's extractors (standing or owed) at
        nameplate. With S2 this overstates demand twice over while the step
        is unbuilt; both errors are in the conservative direction
    L5  three balances, all BEFORE ore extraction (unknown): base, base +
        reserve, base + planned. The third is a separate figure, not base
        widened: it reads "once the bootstrap stands, if every planned
        generator is fed"
    L6  fuel and supplemental draw per fed reading when its fuel is declared;
        unknown (None) when not, rather than guessing among the class's fuels.
        Variable-output generators (geothermal) are refused, not reported
        with an invented nameplate

Guardrails, from the source, each confirmed to fail on a mutation: no field
of the report is a bool (no verdict); no min, max, sort or round; no layer
called (bill_for, net_buildings, net_of, cost_of, solve, realize, run,
paced_run). Mutations checked: reserve summed into base; zero-count planned
lines; standing generators not cross-checked against readings.

Figures, the case of record (T = 50, paced pass):

    nothing standing          base 0, planned 300 (4 coal), demand 157.81
                              (107.81 lines + 10 miners + 40 water, nameplate)
                              base + planned - demand = 142.19
    coal step standing,       base 300, reserve 120, planned 0,
    4 burners fed as reserve  demand 125.69 (75.69 + 50); base - demand
                              = 174.31; coal 60/min, water 180 m3/min

goal_run itself is unchanged: the ledger is built by the caller from a
report, so G1-G3 and the once-per-layer count are untouched.

### Not built

    several goals on one T over a phase span (P6); the A7.3 storage-fill
    report (P7)
