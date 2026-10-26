# Rail routing with 5-degree headings and curve limits (provenance)

Prototype from the 2026-10-24 chat session, following
`research/rail_slope_reach`. Kept for provenance; not wired into any tool and
not covered by a decision. Greg, 2026-10-24: the ramp-class approach should
become tooling once turn radius is included; long-distance rail is usually
built from blueprints with 5-degree turns, so fewer radius options is better;
take real-world rail limits as the basis for radius and grade versus speed;
be conservative on grade until verified (4:8 dropped).

## What it does

    lattice.py         Hybrid A* per hub link. Pose = position + heading in
                       5-degree steps; moves = straights (4, 8, 16, 48, 96 m)
                       and arcs; each move is one constant-grade deck between
                       the ground at its ends. Cost = travel time, both
                       directions averaged. One run per main-line minimum
                       radius (R1111 ... R124) plus 'any'.
    page.py            Builds out/rail-curve-sweep.html: all links on one
                       map, from two sweeps whose closed-set grids are offset
                       by half a cell, with earlier work as overlays (reach
                       and slope rasters redrawn in ink/brown; 2:8 and 4:8
                       grid paths; corridors, rail tool, site picks and
                       neighborhoods read from the Phase 4 page).
    page_template.html The page with its data slot empty.
    links.json         The 2:8 ramp-class network's seven links.

Run from the repo root (needs `research/rail_slope_reach` run first, and
`network.py` there for the comparison paths):

    uv run --with numba python research/rail_lattice/lattice.py --out sweep_off0.json
    uv run --with numba python research/rail_lattice/lattice.py --key-off-m 2 --out sweep_off2.json
    uv run --with pillow python research/rail_lattice/page.py

page.py also reads research/phase4_rail_hubs/out/phase4-rail-hubs.html (from
build.py there, or the published Phase 4 artifact saved to that path). Note:
that page's prose says the rail tool returned seven routes at 30%; its data
holds six, and this page counts from the data.

Numba is a research-only dependency (`--with`), not added to the dev group.

## Declared assumptions (constants in POLICY; carried into a tool, each becomes a declared input)

    grade        max 25% (2:8). 4:8 dropped: the wiki says a 4 m ramp
                 cannot carry rail, confirmed in game by Greg 2026-10-24.
                 The wiki's other maxima (about 30-44% depending on
                 supports) are not yet verified; 25% stays until they are.
    curves       v = sqrt(a * R), a = 1.0 m/s2 unbalanced lateral
                 acceleration (no superelevation in game; upper end of
                 real-world cant-deficiency practice). 120 km/h needs
                 R = 1111 m: one 5-degree step per 97 m, about one 100 m
                 segment.
    climbs       power-limited, v = K / (grade + 0.002), K set so a train
                 holds 54 km/h on 25% (wiki: "at least 54 km/h" uphill if not
                 overloaded). Downhill limited only by curves.
    deck         at most 2 m under the ground (no cut), at most 16 m above
                 it (tallest span accepted in the ramp-class session);
                 over 4 m counts as viaduct at 1.5x time. No water crossings.
    throat       any radius within 300 m of a hub.
    vertical     not modelled (moves follow the ground every 4-96 m, so a
                 vertical-curve limit on these profiles measures that, not
                 the line).

## Measured 2026-10-24 (container, 2 cores; branch claude/rail-lattice from 3867107)

Minutes per link (km in the page). Main-line minimum radius per column;
throats free. Best of two 4 m-pruned runs offset by 2 m; * = runs differ >5%.

    link    2:8 grid  R1111  R625  R400   R278  R201   R124  any
    S2-C2   1.24 km   0.57   0.57  0.57   0.57  0.57   0.57  0.57
    C1-C2   4.18 km   --     --    --     --    3.44*  2.47  2.39
    C1-C3   4.73 km   --     --    --     --    2.99   2.79  2.66
    C3-W3   3.56 km   --     --    --     3.97  2.54   2.43  2.27
    C1-S1   3.86 km   --     --    2.61*  2.31  2.31   2.02  1.91
    W2-W1   2.39 km   --     --    --     3.23  3.10   1.99  1.53
    W1-S1   5.54 km   --     --    --     3.56  3.42   3.29  3.03

Speeds per radius at a = 1.0: 1111 m 120, 625 m 90, 400 m 72, 278 m 60,
201 m 51, 124 m 40 km/h; 46 m (26 km/h) only in 'any' and throats.

What changed on the way, all measured the same day:
- 8 m pruning: C1-C2 'any' 3.05 km vs 2.15 km at 4 m; R278 found on three
  links at 4 m that 8 m missed. Default moved to 4 m.
- Unbounded viaducts reached 219 m deck height (W1-S1); capped at 16 m.
- Exact single radius: route/no-route flipped between 4 m and 2 m pruning
  and when 4/8 m straights were added; replaced by a minimum radius.
- 'any' is stable: C1-S1 1.94 min (4 m) vs 1.91 (2 m), same box; the two
  offset sweeps agree within 2% on every 'any' result.
- Rechecked against the raw 1 m heightfield: 0 straights off a 5-degree
  heading; decks cut >2 m into ground on 27-367 m per route (>5 m on up to
  181 m) and stand up to 75 m over gullies the 8 m means smooth. Known
  defect, documented in lattice.py; next step is a 1 m deck check.

5 degrees per foundation (lattice.py --profile bp5; Greg, 2026-10-24: a
curve blueprint turns 5 degrees from one 8 m foundation to the next, so the
radius is fixed at 4 / sin(2.5 deg) = 91.7 m, 34 km/h at a = 1.0, with no
other radius anywhere, hubs included). Moves: 1, 2, 6, 12 straight
foundations or one rotated 5 degrees. Minutes, best of two 4 m runs:

    link    BP5    (4 m runs)    2 m check (offset 0 / 1 m)
    S2-C2   0.62   0.62 / 0.62
    C1-C2   2.83   2.83 / 2.84
    C1-C3   3.06   3.06 / 3.08
    C3-W3   2.65   2.65 / 2.65
    C1-S1   2.31   2.31 / 2.53   2.27 / 2.22  (margin 1100 m)
    W2-W1   2.14   3.33 / 2.14   2.13 / 2.14  (margin 1100 m)
    W1-S1   3.93   3.97 / 3.93
    total   17.5 min, 21.1 km; 'any' 14.4 min, 19.5 km

All seven links route at 5 degrees per foundation, where no blueprint family
gentler than 201 m does. The radius is set by the foundations, not the rail
(Greg, 2026-10-24): each foundation turns 5 degrees from the last and the
rail is attached to them, so a rail spanning 2 or 20 foundations follows
the same 92 m circle. The 12 m minimum rail length limits how rails are cut
along the foundation chain, not the alignment; the search's 8 m moves are
foundation placements, not rail pieces.

What limits the routes (measured 2026-10-24, same container; one 4 m run
each unless noted, so single figures carry the pruning noise above):

    time split, BP5 network 17.5 min: straight-line distance at 120 km/h
    5.9, detour 4.7, curve speed 5.0, climbing 1.1, viaduct penalty 0.8.

    relaxing one rule at a time (C1-C2, C1-C3, W1-S1 at R1111/R625/R278):
      deck cap 16 -> 100 m   unlocks C1-C3 and W1-S1 at 278 m only
      grade 25 -> 50%        C1-C2 routes even at 1111 m: 1.7 km, 1.75 min
                             (BP5 at 25%: 3.6 km, 2.83 min); W1-S1 at 625 m
      both                   C1-C3 at 278 m: 2.0 km, 2.04 min
      C1-C3 never routed at 1111 m (C3 sits in a pocket).
    50% is beyond every wiki figure: a sensitivity test, not a proposal.

    BP5 at the wiki's grade figures (train power unchanged):
      25%  17.5 min  21.1 km   (best of two runs)
      30%  15.8 min  19.7 km   (foundation-ended, 1:3.375)
      37%  14.6 min  18.3 km   (ramp-ended, 1:2.7)

Grade is the binding rule: it forces the detours, and the detours are what
make the 92 m curves expensive. lattice.py takes --max-grade and
--max-pillar-m for these runs.

In-game measurements (Greg, 2026-10-24) and what they fit:

    4:8 ramp           rail cannot be placed on it.
    freehand 90 deg    one rail from a straight on the edge of an 8x8
                       foundation grid (tangent length 64 m assumed): the
                       rail crosses the third diagonal foundation 1-1.5 m
                       along its edge from the near corner, so the midpoint
                       is 23.3-23.7 m from the corner (a circle: 26.5 m).
                       Fits a cubic Bezier with handles 0.64 x the tangent
                       length: radius 106-113 m at the ends, 48-50 m in the
                       middle (25 km/h at a = 1.0), plan length ~103 m.
                       That exceeds the 100 m segment limit, so the tangent
                       length is probably a little under 64 m; unresolved.
                       Greg is unsure the measurement was taken at the
                       exact corner, so treat the 0.64 ratio as rough.
                       Circles are possible but players force them by
                       setting tangents (roundabouts).
    6x6 climb          curved in plan, one end raised 22 m before "too
                       steep". Same Bezier ratio: ~77 m long, 28.5%
                       average. Matches the wiki's flat-ended 28 / 94.5 m
                       (29.6% average); with both ends level a cubic ease
                       peaks at 1.5x the average (43-44%), which matches the
                       wiki's 1:2.25 beam figure. Hypothesis, not confirmed:
                       the game limits the steepest local grade (~44%), and
                       a rail with level ends can therefore average ~30%.
                       The search's 25% per-move cap is below this.

Throughput: about 100-115 k states/s (Numba, one core); 'any' runs take
30-120 s at 4 m. Memory, not speed, bounds resolution: a 2 m full sweep
needs 5-8 GB per link with dense arrays.

## Deck-height search, 2026-10-24/25 (branch claude/rail-deck)

Additive to the ground-following search above, whose tables stay
reproducible with the commands at the top. Decided by Greg, 2026-10-24/25:
grade 25% (manual placement is imprecise); no clipping into terrain, space
under the rail acceptable; curves flat, only straights climb; curve angles a
kit (adopted 1, 2, 4, 10 deg per foundation); height priced, not capped
(adopted H0 = 8 m); hard lid 32 m; a hub is its neighbourhood (350 m zone);
braking = acceleration = 0.3 m/s2; the output is a guide to direction and
shape, adjusted in game, not a placement plan.

    uv run --with numba --with scipy python research/rail_lattice/lattice.py --deck \
        [links] --kit 1,2,4,10 --h0-m 8 [--lid-m 32] [--hub-zone-m 350] [--acc 0.3] [--dense]
    uv run --with numba --with scipy python research/rail_lattice/page_deck.py
    uv run --with numba --with scipy python research/rail_lattice/page_deck.py \
        --only K8,K4 --out rail-kit-routes.html --title "Rail Kit Routes"

page_deck.py builds the Rail Curve Sweep page from the published v4 page's
data (saved to out/rail-curve-sweep-v4.html) plus --deck outputs; see RUNS
there for the output file names.

Model: deck height carried per state (one state per 4 m cell and heading;
height not keyed, so pruning is lossy in height as in position); straights of
1, 2, 6 or 12 foundations try three end heights (lowest unclipped, level,
full climb); curves are one foundation turned N deg (radius 4 / sin(N/2)),
flat. Checks every 1 m against the 1 m heightfield: no ground above the deck
under an 8 m footprint (disc rasters, radius 4 + sqrt(0.5) m); deck at most
the lid over the lowest ground beneath it. Cost: time x (1 + mean height /
H0) plus a per-move speed-change charge (vhi - vlo)^2 / (2 a vhi). Reported
minutes are a speed-profile travel time (forward/backward passes, both
directions, free ends), because braking 120 -> 24 km/h takes ~1.8 km. The
per-move charge over-rewards stepping through angles; a speed-state search
is the open fix. Closed set in an int32 hash table (3/4 load, array heap):
identical to the dense arrays on all 7 links; ~100 M states fit in 7 GB.

Measured 2026-10-24/25, container (2 cores), single 4 m-key runs per link,
zone edge to zone edge (not comparable with the hub-point tables above);
every route rechecked against the 1 m heightfield (exact disc, 0.5 m
samples) with no clipping beyond 0.03 m (the recheck's chord error):

    run                  min    km     mean h  km >8 m  highest
    5 deg, H0 8          16.03  13.43  4.6     2.88     31.6
    kit 1-10, H0 8       13.27  12.77  3.8     1.79     31.9
    kit 1-2-4-10, H0 4   15.16  12.95  2.8     1.31     31.0
    kit 1-2-4-10, H0 8   14.10  13.50  3.4     1.63     30.9
    kit 1-2-4-10, H0 16  13.70  13.11  5.3     3.06     31.9
    kit 1-2-4-10, free   12.76  12.37  15.6    9.10     32.0

    lid sweep, kit 1-2-4-10, H0 8, six links (C1-C3 out of memory at 64 m):
    lid 32 10.23 min, 10.27 km; lid 64 and 128 both 10.21 min, 10.35 km,
    highest 47.4 m: the lid stops binding below 64 m.

Review findings on PR #9 (2026-10-25): blocked cells between 8 m samples is
fixed here (check() and sample_move() sample every 1 m); a tight arc that
starts inside the hub throat but ends outside it stays as is in the
ground-following sweep (superseded by the deck search, which has no throat).
