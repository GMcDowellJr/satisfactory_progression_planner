# Planning Data

This directory holds the data contracts for the Satisfactory world-analysis and progression-planning project.

## Read order

1. `ARCHITECTURE.md`
2. `world/README.md`
3. `world/manifests/world_502094.json`
4. `schema/schema_v2.json`
5. `planning/README.md`

## Layer rules

**Game reference** is build-pinned gameplay truth. **World extraction** is build-pinned placement/geometry truth. **World analysis** is regenerable interpretation of a materialized world. **Planning** applies progression, strategy, and playthrough state to those analyses.

The default world is one configuration. Do not encode resource type or purity into fixed socket geometry. Do not encode Rocky Desert district decisions into world extraction or site-suitability logic.

The current build-502094 extraction is aligned across resources, terrain/water, and collectibles/POIs. Buildable-area extraction remains the next major missing world layer.
