# Rail reach by standard ramp class (provenance)

Prototype from the 2026-10-24 chat session on Phase 4 rail hubs. Kept for
provenance, like `research/v020_site_mapper`. Not wired into any tool and not
covered by a decision. Greg, 2026-10-24: the approach holds and should become
part of the tooling once turn radius is included.

## What it does

    slope_reach.py   8 m cells (one foundation), each the mean of the 1 m
                     heightfield. Track steps to any of 8 neighbours if the
                     rise is within the class: 1:8, 2:8, 4:8 (12.5, 25, 50%).
                     Blocked: no-data; water > 3 m deep or of unknown depth.
                     Writes components per class, hub snaps, hub-pair path
                     lengths, and a reach raster (first class that connects a
                     cell to C1).
    bridges.py       Spans joining a cut-off component to C1's: a straight
                     deck at the class grade, kept only if the 8 m ground
                     never rises more than 2 m above it (no cut or tunnel).
                     Ranked by length + 2 x tallest pillar; top 3 per gap.
    network.py       Minimum spanning tree over the hubs per class (2:8, 4:8)
                     on the class graph plus the spans (span cost 1.5 x
                     length), with path geometry.
    hubs.json        The eight candidate hubs from the same session's
                     Phase 4 screen. Their role scores were a weighting chosen
                     in chat, not a repo policy.

Run from the repo root, in order; output goes to `out/` (gitignored):

    uv run --with pandas python research/rail_slope_reach/slope_reach.py
    uv run python research/rail_slope_reach/bridges.py
    uv run --with scipy python research/rail_slope_reach/network.py

## Policy choices that are currently constants

Cell size 8 m; classes 1/2/4 m per 8 m; deep water 3 m; the 0.5 valid-fraction
and 0.5 wet-fraction cell rules; deck tolerance 2 m; span search radius 600 m;
span ranking (length + 2 x pillar) and routing cost (1.5 x); hub snap search
160 m preferring the largest component. Carried into a tool, each becomes a
declared input (AGENTS.md "Layers report; they don't choose").

## Known limits

- No turn radius: paths may turn at every 8 m cell, so lengths are lower
  bounds and some zigzags are not buildable. The radius to declare is open:
  route_constraints.csv says 17 m (90-degree, centreline); a player report
  says 3 foundations.
- Spans are searched only to join cut-off components, never as shortcuts.
- Steeper than 4:8 is not modelled; whether rail allows it is unconfirmed.

## Measured 2026-10-24 (container, master 237cafe world data)

No bridges, which hubs share C1's component:

    1:8   none (only C2-S2, together)
    2:8   C1 C2 C3 S2 W3; S1 apart; W1 W2 on a 3.66 km2 island
    4:8   adds S1; W1 W2 on a 4.10 km2 island

With spans: 2:8 MST 25.5 km using a 34 m (1 m high) and an 80 m (16 m high)
span; 4:8 MST 20.4 km using a 32 m (8 m high) span. Re-running these scripts
from this folder reproduced the session's bridges.json and network.json
exactly.
