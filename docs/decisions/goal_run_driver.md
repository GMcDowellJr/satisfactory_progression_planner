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
