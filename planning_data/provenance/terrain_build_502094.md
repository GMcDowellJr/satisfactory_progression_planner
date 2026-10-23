# Terrain source — Satisfactory build 502094

Generated locally from the user's installed Satisfactory 1.2.4.0 (`++FactoryGame+rel-main-anniversary-2026`, CL 502094).

Grid:
- 7500 × 7500
- 1.0 m spacing
- x0 = -3247.0 m east
- y0 = -3750.0 m game Y
- +X east, +Y south, +Z up

Coverage:
- known: 80.467%
- landscape: 45.448%
- cliff interpolated: 5.832%
- cliff direct: 15.227%
- fill: 13.960%

Validation:
- 625 static resource nodes
- median absolute error: 0.2019 m
- 90%-trimmed RMS: 0.3692 m
- p90: 1.4120 m

Important limitation:
The field is single-valued in Z. The source metadata explicitly identifies caves, arches and overhangs as the main topology failure mode. Use the raw heightfield for ordinary route scoring, but flag cave/overhang areas for later graph/mesh treatment.

## In this repository — recorded 2026-10-23

- The raster directory `planning_data/world/spatial/heightmap_build_502094/` is
  committed to this repository (git-tracked, listed in `planning_data/manifest.csv`).
- Its `meta.json` was written by SatisfactoryMCP's `tools/gen_world_heightmap.py`
  (lukszi/SatisfactoryMCP; Greg 2026-10-23 16:14) and is kept as generated. Its
  `description` ("no terrain raster is ever committed to this repository") and
  `sources.game.licence` ("Not committed, not redistributed") describe the
  generator's own repository and practice, not this one. The generator is not in
  this repository (checked: `git ls-files` on claude/picker 99b16c8;
  `docs/MULTISURFACE_TERRAIN_PROTOTYPE.md` says the same).
- Decided by Greg, 2026-10-23 16:21: keep the raster in this repository.
- Derived from it: `tools/site_planner_web/precomputed/basemap_502094.png`, the
  site planner picker's base map (every 7th vertex, 1072 px; Greg 2026-10-23
  16:14: a small version is fine in the repository), cut by
  `tools/site_planner_web/basemap.py`.
