# Phase 4 Rail Hubs map page (provenance)

Rebuilds the "Phase 4 Rail Hubs" artifact from the 2026-10-24 chat session.
Kept for provenance, like `research/v020_site_mapper`; not wired into any tool
and not covered by a decision. The session's scratch steps are consolidated in
`build.py`; `page_template.html` is the final page with its data slot empty.

## Run

Needs the spur-pruning fix in `corridor_tool` (PR #7), corridors generated,
and `research/rail_slope_reach` run first:

    python scripts/generate_corridors.py
    uv run --with pandas python research/rail_slope_reach/slope_reach.py
    uv run python research/rail_slope_reach/bridges.py
    uv run --with scipy python research/rail_slope_reach/network.py
    uv run --with pandas --with scikit-image --with pillow --with matplotlib \
        python research/phase4_rail_hubs/build.py

Output: `out/phase4-rail-hubs.html` (gitignored), self-contained. Stages can
be run alone by name: expand, hubs, corridors, rail, ramp, slope, page. The
rail stage calls satisfactory_route_tool 8-16 times and is the slow one.

## Choices that are opinion, not repo policy

- Role screen (ROLES in build.py): which resources make a role and how they
  are weighted; purity weights impure 0.5, normal 1, pure 2; a fracking
  satellite counts as a node; top 6 per role, 800 m apart; hubs grouped
  within 750 m.
- HUB_TABLE: names, core/extension tiers, and merging groups 5 and 7 into
  C3. EXPECT guards group order; a changed input fails rather than renaming.
- LINKS: the network was picked from a corridor-length spanning tree plus
  the C1-C2 loop, in chat.
- Rail stage hard grade 30% (route_constraints.csv's figure), not the
  repo profile's 8%; the two sources disagree and this is not resolved.
- Ramp stage: 2 m per 8 m foundation (25%), from player guidance.

## Measured 2026-10-24 (container, master 237cafe data + PR #7 fix)

The rebuilt page's data and markup are identical to the published artifact
(compared after parsing the embedded data). Phase 4 default-recipe raw
needs at 1x: iron 505k, copper 462k, oil 314k, coal 228k, limestone 122k,
water 100k, caterium 68k, bauxite 61k, quartz 56k, nitrogen 53k; no sulfur
or uranium in the chain.
