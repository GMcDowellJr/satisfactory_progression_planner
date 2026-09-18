# Foot Exploration Data Pipeline

## Separation of concerns

The fixed world is expensive to understand and cheap to reinterpret. The pipeline therefore keeps canonical spatial facts separate from runtime player policy.

### Canonical / static facts

1. `vertical_intervals.npz`
2. detailed `surface_graph`
3. structural foot topology from `build_travel_topology.py`
4. `topology_gateways.csv` containing every detailed crossing retained between contracted topology nodes
5. POI geometric snap products from `build_foot_exploration_data.py`

Canonical outputs do **not** contain expedition weights, safety labels, ramp counts, or POI-to-POI weighted distance matrices.

### Runtime interpretation

Runtime profiles may decide how to treat:

- grade and climb
- clearance
- deep water
- Alpha hostiles
- gas / spore flowers
- uranium / nuclear hogs
- ramps
- Blade Runners
- jetpack / hoverpack

An example runtime-only profile lives at `planning_data/analysis/policies/exploration_runtime_profile.example.json`.

## Rebuild scope

No game/MCP extraction or detailed surface-graph rebuild is required for this schema revision. Re-run only the contracted topology derivation and POI exploration-data derivation.

## Commands

```cmd
python scripts\build_travel_topology.py ^
  --planner planning_data ^
  --build 502094 ^
  --surface-graph data\local\spatial\surface_graph ^
  --intervals data\local\spatial\multisurface\vertical_intervals.npz ^
  --mode foot ^
  --sector-m 128 ^
  --write-component-maps ^
  --out planning_data\analysis\derived\world_foot_topology
```

Then:

```cmd
python scripts\build_foot_exploration_data.py ^
  --topology-dir planning_data\analysis\derived\world_foot_topology ^
  --out planning_data\analysis\derived\foot_exploration_data
```

The second command can also pass `--build-topology` when the revised topology products are absent.

## Important structural caveat

The contracted topology is still explicitly a **foot structural topology**. Its contraction uses the selected foot profile's hard feasibility rules. That is different from embedding expedition weights: it establishes the structural graph family. Runtime exploration policy is applied afterward.

If future requirements need a single locomotion-neutral topology shared by foot, jetpack, and vehicles, that is a separate topology-design change rather than a world-data re-extraction.
