# Corridor Tool

Derives reusable physical connectivity geometry from the versioned world terrain/water package. It does **not** solve a route between requested endpoints and it does not encode a tractor, rail, belt, or player preference.

## v1 method

1. Resample the canonical terrain/water/provenance rasters to the configured analysis step.
2. Build a permissive physical passability mask using policy-defined hard grade/water constraints.
3. Compute distance-to-blocker (clearance) across traversable terrain.
4. Skeletonize traversable space to obtain persistent connectivity centerlines.
5. Convert the skeleton to graph nodes (ends/junctions) and edges.
6. Annotate edges with length, clearance and grade; classify narrow edges as chokepoint/constrained and broad-space skeleton edges as open.

This is a first topology substrate. Mode-specific route costs remain downstream in `satisfactory_route_tool`.

## Run

From repository root:

```cmd
python scripts\generate_corridors.py
```

Override the coarse world-analysis resolution during calibration:

```cmd
python scripts\generate_corridors.py --step-m 32
```
