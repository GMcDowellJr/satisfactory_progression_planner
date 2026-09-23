# busmodel — the bus-level recompute

Written 2026-09-21. Replaces `scratchpad/recompute_model/`, which produced every
figure in `docs/decisions/bus_level_recompute_and_alternate_crossover.md` and its
four amendments and could not be committed.

## What it is for

This package is the **oracle**. Two jobs, and they are not the same job:

    reproduce   every bus figure the decision records publish is recomputable
                from the repo, so a published table is a regression test rather
                than a one-off validation nobody can re-run
    check       the realization layer's bodies get something to be checked
                against that is not themselves

The second is why the import boundary forbids `realization.buses`,
`realization.residual` and `realization.realize`. An oracle that can reach the
code it validates is not an oracle.

## Why the scratch model could not be committed

`busmodel.py` and `split_bus.py` read `recipes.csv`, `recipe_io.csv` and
`recipe_producers.csv` directly. That violates `gamedata.py`'s locked claim to be
the only place in the repo that knows CSV column names — the same constraint that
forced the realization layer's import tripwire from the inclusion form to the
exclusion form. Committing them as-is would have put a second loader in the repo,
which is exactly what that lock exists to prevent.

Nothing here opens a file. `tests/test_busmodel_import_boundary.py` asserts it,
rather than the docstring asking for it.

Three other things the scratch model did not have, each of which cost something:

    no driver        A3.5 was not reproducible from the code that produced it.
                     `python -m busmodel <case>` is the driver
    no saved         every declaration lived in an ad-hoc call that was not
    declaration      kept. `declarations.py` is the declarations, each naming
                     its primary source
    no state         it could not express a MATCHED line at all, so amendment
    awareness        4's central comparison was derived by hand

## Layout

    src/busmodel/model.py          the solve
    src/busmodel/declarations.py   the saved declarations
    src/busmodel/report.py         rendering, out-of-scope draw roll-up
    src/busmodel/cli.py            the driver
    tests/test_published_tables.py the five reproductions, plus amendment 4
    tests/test_refusals.py         four refusals, each with a site
    tests/test_busmodel_import_boundary.py   the structural tripwire

## The model

**The primitive is `(item, producers, consumers, PARTITION)`**, and the partition
is DECLARED. `BusSpec.sources` is where it lives: each bus names, per input item,
which bus it draws that input from. Iron Wire feeding Stitched Iron Plate is a
different bus from copper Wire feeding Cable and the build stock, and their
residuals do not pool.

**Steady state is per bus, not per factory.** Several run at once:

    WITHDRAWN   drained continuously, producers at 100%. Residual is rounding
                slop
    BACK_UP     producers idle at utilisation demand/supply
    MATCHED     clocked to the average withdrawal. Supply equals demand, so the
                residual is zero and the draw is constant
    SUNK        refused by name — the AWESOME Sink is absent from the reference
                layer

**A5.2, 2026-09-22: the states do not differ in what a line costs its source
bus on average.** Average draw is USAGE in every state — backpressure is a duty
cycle, not a clock, so a bus at utilisation u draws u × nameplate whether a
clock set it or the belts idled it. What differs is POWER (convex in a clock,
linear in a duty cycle) and peak DURATION. The peak is nameplate for any state
whose supply exceeds its demand, and equals the average under MATCHED.

**Two recovered rules**, neither stated by the documents this reproduces, both
named options rather than compiled into the arithmetic:

    external demand = 0        the storage review's "held constant" was constant
                               at ZERO
    machine floor = 1          every declared line gets a machine floor. This is
                               what gives Cable 30.00/min and Concrete 15.00/min
                               of overflow against zero automated demand

## Running it

    python -m busmodel --repo . worked_case_A4 --multiplier 1.25
    python -m busmodel --repo . storage_review_T1-2 --multiplier 1.0 --basis average
    python -m busmodel --repo . crossover_B --multiplier 1.25 --basis average

`--basis` takes `usage` (the default) or `average` (the override that
reproduces the record). The same default applies to `solve()`. Every rendered
table prints its basis in its header.

    usage     THE DEFAULT since 2026-09-23 (amendment 10). A5.2's basis:
              every consumer draws its usage, in every state
    average   THE BASIS OF RECORD. A MIXTURE, not an average: a WITHDRAWN
              consumer draws its nameplate and everything else draws its
              usage. Every published table was computed on it, which is the
              only reason it is still here — so reproducing a table means
              passing `--basis average`, or `sizing_basis=SizingBasis.AVERAGE`
              in code, and the tests do exactly that
    peak      REFUSED as of 2026-09-22. It was a sizing mode and is not one any
              more; `solve` raises and names where the peak went. `--basis peak`
              still reaches that refusal on purpose, because argparse's
              "invalid choice" explains nothing

**The peak is reported on every solve, under either basis**, as
`ConsumerShare.peak_per_min`, `BusSolution.peak_demand_per_min` and
`BusSolution.peak_shortfall_per_min`. Nothing sizes against it — the machine
count reads `demand_per_min` alone, and `tests/test_refusals.py` asserts that a
run whose peaks differ wildly moves no machine count, no residual and no clock.
The shortfall answers A5.2's question: splitters round-robin and do not
prioritise, so a refill transient is paid by the PRODUCTION consumers sharing
the bus. Its DURATION is capacity/slack and is not modelled, because no
container capacity reaches this layer.

## What it does NOT assert, and why

A3.5's 27-machine table is **not** a regression target, and did not become one
on 2026-09-22. Its withdrawal column sits inside the demand sum on Concrete and
Wire_copper and outside it on four other rows, under one verdict column, so
`supply − draw = R` reconciles on nine of its eleven rows and fails on two.
`worked_case_A4` is the same topology with every withdrawal inside its own
bus's demand — the uniformity A4.1 buys structurally — and it is therefore NOT
byte-identical to A3.5 and is not meant to be.

**`worked_case_A4` under `--basis usage` IS a target**, as of 2026-09-22:
23 machines against the average basis's 29, with all six removed machines
coming off production buses and none off a build line. Amendment 6 publishes
that table; `test_published_tables.py` section 7 pins it.

## One contradiction between the two declared cases, carried rather than resolved

The bundle config declares Screws as `Alternate: Cast Screws` (50/min). A3.5's
screw bus runs at 40.00/min, which is the base Screw recipe, and its Iron Rod bus
draws 64.00/min — Rotor's 24.00 plus four screw machines at 10 rod/min each. Cast
Screws draws iron ingot and no rod at all, so no Cast Screws configuration
produces 64.00.

Both are declared, as two cases. The bundle config is the older artifact and is
not corrected here: forward-only.
