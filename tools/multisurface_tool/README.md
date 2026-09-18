# Multi-surface terrain prototype

This tool is the planner-side half of the cave/arch fix. It does **not** decode Satisfactory cooked assets.
It consumes world-space triangles exported by the existing SatisfactoryMCP game-asset generator and rasterises
multiple Z surfaces per XY cell instead of folding everything to max-Z.

## Triangle handoff contract

An `.npz` with:

```text
triangles: float32/float64 [T,3,3]
```

Coordinates are planner metres: `X=east`, `Y=north=-gameY`, `Z=up`.

The local terrain heightfield is inserted as one surface sample. Rock/arch/cave triangles are additional
surfaces. Near-vertical triangles are excluded from the surface stack but should later feed an obstacle/wall layer.
Distinct Z intersections are clustered, sorted, and retained (default up to six layers).

## A-D prototype window

The exact user-questioned southern A→D arch/convergence is around `(-2047,-620)`. A useful first extraction
window is:

```cmd
python scripts\build_multisurface_window.py ^
  --triangles data\local\ad_arch_triangles.npz ^
  --terrain-dir planning_data\world\spatial\heightmap_build_502094 ^
  --bounds -2300 -900 -1850 -380 ^
  --step-m 2 ^
  --out data\local\multisurface\ad_arch
```

The SatisfactoryMCP exporter should include placements previously excluded solely because the mesh basename
contains `Arc`, plus the cave/merged-floor mesh set that was excluded from max-Z. It should preserve the existing
owner/oversize safety culls and export transformed **world-space** triangles only for placements intersecting the
requested window.

## Why this is separate from the old heightfield

`height.i16.z` remains the fast single-valued ground query. The multi-surface field answers different questions:
which vertical layers exist here, is there overhead geometry, and what clearance separates a travel layer from the
next surface above it? Routing should choose a layer and preserve layer continuity rather than zeroing grade on an
ambiguous max-Z jump.
