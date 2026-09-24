# Goal-run driver — design note (proposal), 2026-09-23

    status    PROPOSAL. Nothing here is decided until Greg says so; the parts
              he locks go into a decision record, and this note stays a draft
    baseline  08e4126e (HEAD = origin/master, read from .git this session)
    scope     Phase 2 deliverable 5 (the Project Assembly report), first cut.
              Replaces scratchpad/first50_run.py, which is pre-A12: every
              `disposition=` in it is now a TypeError (A12 Q4)

## 1. What it is

One function that runs the existing layers in order and returns everything
each layer returned, side by side:

    LP solve -> declared lines -> realization -> project_goals -> stock pass

It adds no arithmetic of its own. Every number in its report comes from a
layer that already computes it.

## 2. Where it lives — PROPOSED: `tools/goal_run.py`

The same precedent as `production_cli.py`: a joint that imports more than one
package lives at `tools/` root as a standalone module that sets up `sys.path`
itself. None of the three packages may import the others upward, so the joint
cannot live inside any of them. Tested from `tests/`, the only conftest that
puts all src trees on the path (the same reason `test_stock_to_realization.py`
lives there).

    alternative   a fourth package `tools/goal_run/src/goal_run` with its own
                  import-boundary test. More ceremony, and it would be the
                  first package whose job is to import every other package.
                  Not recommended for a first cut

## 3. Inputs — everything is handed in

    data           ReferenceData, scenario ALREADY APPLIED by the caller. One
                   instance feeds every layer (the rule in
                   test_stock_to_realization.py's docstring)
    solve          SolveRequest — the rate anchor (e.g. 1 Smart Plating/min)
                   and the allowed recipes (the caller runs `at_tier`)
    realization    RealizationRequest — the DECLARED partition, the design tier
                   and the nodes. The driver never builds a BusDeclaration
    goals          (goal_id, item_id, total) triples, passed to project_goals
                   unchanged
    stock          BootstrapSet, unlock tier, phases. Passed to bill_for

## 4. Output — `GoalRunReport`, a frozen dataclass

    solve          the SolveResponse, as returned
    realization    the RealizationReport, as returned
    goals          project_goals' tuple, in caller order
    stock          the StockPass, as returned
    machines       the (producer_class, count) set handed to bill_for, so a
                   reader can see which counts the bill was summed over

No sorting and no score. Nothing returns a single variant. A `render()` text
view comes later and is a view only.

## 5. Guardrails — structural, asserted by inspection in a test

    G1  goal_run.py contains no `BusDeclaration(`, `SourceEdge(`,
        `OutputTarget(` or `SolveRequest(` call. It cannot choose a recipe,
        a partition or a target, so it cannot become a planner
    G2  no loop over layers. Each layer is called once per run. Asserted as a
        count of call sites, not left to review
    G3  no `min(`, `max(`, `sorted(` or `.sort(` over goals or buses — the
        comparator guard
    G4  every field in GoalRunReport is the identical object a layer returned
        (identity checks in the test), so the driver cannot restate a number

## 6. Open — needs Greg

    O1  WHERE THE STOCK PASS'S MACHINE COUNTS COME FROM. bill_for needs settled
        counts. Two readings:
          (a) the realization's lane machines, summed per producer class, as
              first50_run.py did. Derived from the declaration, not chosen,
              so stock still derives nothing. RECOMMENDED
          (b) a separate declared build, handed in like BOOTSTRAP
        Either way the counts are reported in `machines` (section 4)

    O2  BILL FEEDBACK. The handoff's order puts the stock pass LAST, so a bill
        is reported and NOT attached to a line's `withdrawal_bill` in the same
        run. Attaching it means a second realization whose machine counts
        differ from the ones the bill was summed over — A5's loop of machines
        that build machines. Proposed: no feedback in this deliverable. A
        caller who wants a bill-sized line runs again with the bill attached,
        which is visible in the caller's code. (A bill summed over the
        first-pass counts omits the build-material lines' own machines, so a
        single bounded second pass would still be a floor — noted so the
        option is not lost, NOT proposed)

    O3  BINDING GOAL. project_goals' docstring says the binding item is argmax
        T, and nothing computes it. Reporting it is a fact about the build, but
        it is a max over goals, which G3 forbids. Proposed: leave it to the
        reader for now; revisit with D2, where the goal build sets T

    O4  GOAL TOTALS FROM THE PHASES. The Project Assembly table is canonical
        and exact, so goals could be derived from `phases` rather than handed
        in. Proposed: handed in for the first cut (smallest surface), with a
        helper that builds the triples from load_project_assembly as a
        separate function the caller may use

## 7. First tests (proposed)

    - the 1 Smart Plating/min case at 1x/1x/1x: re-derive, don't re-quote, the
      figures A12 calls "not pinned" (17 machines and 120.0 ore/min storing; 7
      and 23.25 with storage off) and pin whatever the run produces, with
      provenance
    - G1-G4 by inspection
    - a goal no declared bus makes: rate 0.0 and inf minutes pass through
    - scenario identity: the report's layers all saw the same ReferenceData
