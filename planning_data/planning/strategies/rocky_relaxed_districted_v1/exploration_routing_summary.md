# Exploration-aware routing dataset v1

This package adds the data model needed to enrich planner routes with exploration value.

## What is ready now

- Generic POI types and accessibility requirements.
- Route detour/value score components.
- Rocky exploration priority profile.
- Rocky acceptable-detour defaults.
- Initial district-to-district exploration route requests.
- Empty playthrough state tables for collected/opened POIs.
- Canonical build-502094 exploration POIs populated in `world/canonical/exploration_pois.csv` (1,764 primary POIs).

## Important source boundary

The installed game Docs JSON (`a81d250e96aa`) does not contain the static world placement of crash sites, slugs, Mercer Spheres, or Somersloops. Fields that look spatial are class/building defaults or offsets, not map-instance coordinates.

A separate static-world source is required. SCIM-format map data exposes marker `x`, `y`, and `z`, so it can supply elevation as well as plan coordinates once a current build is pinned and ingested.

## Current ingest status

Static-world POIs are populated and build-aligned with the build-502094 terrain/water and resource-socket extraction. Route/POI analysis can consume the canonical world package directly. Buildable-area extraction and generalized corridor topology are the next missing world-analysis layers.


## Static collectible source inspection — v1.8

Pinned SatisfactoryMCP build 495413 reports 1,764 primary route POIs:
118 crash sites, 1,242 power slugs, 298 Mercer Spheres, and 106 Somersloops.
It also reports 703 loot caches as a useful supporting exploration layer.

The source contains X/Y/Z in centimetres (+X east, -Y north, +Z up), crash-site unlock costs,
and hazard context. Save-derived `state`/`looted` values belong to the source author's
playthrough and are deliberately excluded from this planner's playthrough state.
