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
                 cannot carry rail; its listed maxima are about 30-44%
                 depending on supports. Conservative until verified in game.
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

Throughput: about 100-115 k states/s (Numba, one core); 'any' runs take
30-120 s at 4 m. Memory, not speed, bounds resolution: a 2 m full sweep
needs 5-8 GB per link with dense arrays.
