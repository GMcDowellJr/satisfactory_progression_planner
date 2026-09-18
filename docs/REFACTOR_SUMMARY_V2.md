# Refactor summary — v2.0

## Why

The repository previously centered `reference/` and Rocky planning data. The revised design makes build-versioned world extraction and world analysis first-class, with progression planning downstream. This supports default and save-modified resource configurations without recreating machine-solver tooling.

## Material changes

- Added `game/reference/` for gameplay rules.
- Added `world/` for source snapshots, canonical geometry, world configurations, spatial rasters, and build manifests.
- Added authoritative build-502094 resource socket projection from the supplied first-party JSON.
- Split fixed resource socket identity/geometry from default resource/purity assignment.
- Moved the old Rocky-only `resource_sources.csv` to `planning/legacy/rocky_desert/`.
- Moved planner semantics, plans, strategies, playthroughs, and templates under `planning/`.
- Moved generated outputs and QA under `analysis/`.
- Updated the route tool to consume v2 world/game paths.
- Added `scripts/materialize_world_resources.py` so the socket/configuration projection is repeatable for future builds.

## Validation

- 625 resource sockets projected.
- 625 default assignments projected.
- 118/118 fracking satellites retain a core link.
- Resource, terrain/water, and collectible layers all identify build 502094.
- Route tool unit tests pass under the v2 path layout.

## Next world-analysis work

Buildable/industrial-area extraction is the largest missing physical-world layer. Generalized corridor topology should follow/iterate with it, then resource clustering and site suitability can be evaluated against the default world before save-derived configurations are introduced.

## Build-surface calibration policy

Build-surface analysis now defaults to `analysis/policies/build_surfaces_v3.json`. V3 replaces the terrain-band experiment with a true horizontal-platform elevation sweep: horizontal resolution controls edge detail, vertical step controls Z sampling, maximum terrain/water height defines obstruction, and usable area is monotonic as platform elevation rises. V1/V2 remain historical policies.

## Build-surface analysis update (v4)

The current primary build-surface analysis is `analysis/policies/build_surfaces_v9.json`: rectangle-first horizontal-plane support over recalibrated flat-pad footprint families for Small/Medium/Large/Very Large (short-side anchors 8/12/20/32 foundations; PHM steel deck anchors Medium). Rectangle dimensions are physical foundation dimensions (8 m each) and do not scale with analysis resolution. V7 renders the union of qualifying footprints as contextual suitability coverage and emits the actual chosen rectangle geometry. It retains V6's landscape/fill ground-support provenance, cliff/overhang ambiguity, and PHM save-derived calibration fixture. V6 fixed-footprint, V5 all-top-surface plane fit, v4 local relief, and v3 elevation sweep remain available for comparison/reproducibility.
