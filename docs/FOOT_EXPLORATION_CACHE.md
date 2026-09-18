# Foot exploration cache

`build_foot_exploration_cache.py` turns the static world/POI data into a terrain-aware lookup layer for the exploration planner.

## First run with the current repo

The checked-in repo contains the 1 m heightmap, canonical POIs, and POI hazard records, but not the generated local layered-surface graph. The script can bootstrap a base-terrain-only 8 m foot graph without another game-data extraction:

```cmd
python scripts\build_foot_exploration_cache.py --bootstrap-base-only --build-topology
```

That command:

1. copies the checked-in heightmap into `data/local/spatial/heightmap`;
2. creates an empty layered-surface interval table at 8 m (base terrain only);
3. runs `build_surface_graph.py`;
4. runs `build_travel_topology.py --mode foot`;
5. snaps all exploration POIs to the foot topology;
6. merges POI hazard metadata; and
7. precomputes shortest-path costs only between topology nodes actually used by POIs.

The generated local geometry products remain under `data/local/` and are gitignored. The planner-facing outputs are written to:

`planning_data/analysis/derived/foot_exploration_cache/`

## Outputs

- `poi_topology_snap.csv` — one row per POI with snapped topology node, local XY/Z mismatch, estimated 4 m ramp count, connector cost, component IDs, and hazard flags.
- `poi_topology_snap.json` — same records as JSON.
- `poi_snap_validation_candidates.csv` — 50 most vertically difficult/suspicious snaps for manual QA.
- `foot_topology_distance_cache.npz` — `topology_node_ids` plus a dense distance matrix between only the topology nodes used by POIs.
- `manifest.json` — run inputs and summary counts.

A POI-to-POI terrain-aware cost is:

`connector_cost(A) + cached_topology_distance(nodeA,nodeB) + connector_cost(B)`

This avoids running a detailed A* for every POI pair.

## When the richer layered graph is available

If `data/local/spatial/multisurface/vertical_intervals.npz` and `data/local/spatial/surface_graph/` already exist from the full world-spatial pipeline, do not use `--bootstrap-base-only`. Build/consume the richer foot topology instead:

```cmd
python scripts\build_foot_exploration_cache.py --build-topology
```

That retains caves, stacked surfaces, and other layered geometry represented by the local spatial artifacts.

## Important limitation of base-only bootstrap

The base-only mode is terrain-aware, not fully 3D-world-aware. It sees the checked-in terrain/cliff heightfield and POI elevation, and it charges ramp cost for local vertical mismatch. It does not reconstruct cave floors, bridges, or vertically stacked walkable surfaces that only exist in `vertical_intervals.npz`. Use `poi_snap_validation_candidates.csv` to review the hardest tower/cliff cases before making the cache authoritative.
