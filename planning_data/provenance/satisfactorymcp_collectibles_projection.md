# SatisfactoryMCP world_collectibles projection

Pinned source:
- repository: `lukszi/SatisfactoryMCP`
- commit: `ade73e6c4736937eb49cc54364def7d6b30873d6`
- file: `data/world_collectibles.json`
- blob SHA: `8dd9da40b164e8bd3d88131567959cbe38b0dea3`
- game build: `++FactoryGame+rel-main-1.2.0-CL-495413`

## Canonical fields to retain

From each primary route POI row:
- `instance` -> source_object_id
- `cell` -> source cell identifier
- `category` -> mapped planner poi_type
- `class` -> source class
- `x` -> east_m = x / 100
- `y` -> north_m = -y / 100
- `z` -> elevation_m = z / 100
- static `unlock_cost` -> crash-site requirement table
- static/inferred `hazard` -> hazard context table, explicitly marked inferred

## Fields NOT to ingest as canonical world state

The source file includes `state`, `looted`, and save-observation metadata from its author's saves.
These are useful evidence about the schema but are NOT this user's playthrough state and must not
be copied into `planning/playthroughs/`.

## Primary route categories

- crashed_drop_pod
- power_slug_blue
- power_slug_yellow
- power_slug_purple
- mercer_sphere
- somersloop

Shrines are supporting geometry, not extra collectibles. Loot caches are a supporting exploration
layer and should be associated spatially with crash sites/camps rather than ranked as equal POIs.
