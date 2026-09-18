# Static world map-data ingest contract

The installed CommunityResources/Docs `en-US.json` is **not** a static world-placement file.
It describes game classes, recipes, schematics, buildings, and related defaults.

Exploration routing requires a separate static-world source containing object instances with X/Y/Z.

## Required POI layers

- Blue / Yellow / Purple Power Slugs
- Mercer Spheres
- Somersloops
- Crash Sites / Drop Pods / Hard Drives

## Coordinate normalization

Source coordinates are expected in Unreal/save centimeters:
- east_m = x / 100
- north_m = -y / 100
- elevation_m = z / 100

Keep the original source object/path ID and source build/hash.

## Validation

Before promotion to canonical:
1. Pin source retrieval date, advertised game/map build if available, and SHA-256.
2. Verify global counts against the current map source.
3. Cross-check a sample against known resource-node coordinates already used by the Rocky plan.
4. Do not merge POI records from different map builds without marking the mismatch.
