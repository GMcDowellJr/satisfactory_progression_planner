# Multi-surface terrain prototype — A↔D arch pilot

## Why this exists

The build-502094 `height.i16.z` artifact is intentionally single-valued in Z. The source sidecar records
1,075 placements excluded solely because the mesh basename contains `Arc`; adding those roofs to a max-Z
field made ordinary ground-height accuracy worse. It also records cave/merged-floor meshes excluded for the
same reason. That is correct for a *ground query* and wrong for routing where two vertical layers may both be
real.

This prototype adds a second product rather than changing `height.i16.z`:

```text
existing 1 m ground field     cooked static-mesh triangles
          │                             │
          └─────────────┬───────────────┘
                        ▼
                multi-surface window
             XY -> sorted Z intersections
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
        travel layer          overhead layer
        continuity              clearance
```

## Pilot window

The user-questioned southern A→D natural arch/convergence is centred near planner coordinate
`(-2047, -620)`. First extraction bounds:

```text
xmin = -2300 m
xmax = -1850 m
ymin =  -900 m
ymax =  -380 m
```

This deliberately covers the route approach, the pale SCIM arch feature, and the extracted cliff geometry
that begins east of the route convergence.

## What is implemented in this repo

`tools/multisurface_tool/`:

- rasterises world-space triangles without max-Z folding;
- inserts the existing terrain field as another surface sample;
- clusters nearly-coplanar Z hits;
- retains up to N ordered surfaces per XY cell;
- derives vertical clearance to the next surface above;
- ignores near-vertical triangles as *surfaces* (future obstacle/wall layer);
- has synthetic regression tests for an under-arch lower travel surface plus upper shell.

`scripts/build_multisurface_window.py` consumes an NPZ triangle handoff and the existing terrain directory.

## Missing local extraction seam

The planner repository does **not** contain SatisfactoryMCP's `tools/gen_world_heightmap.py`,
`core.gameassets.nanite`, or the user's installed cooked game containers. Therefore this environment cannot
truthfully reconstruct the 1,075 excluded `Arc` placements itself.

The SatisfactoryMCP-side change should be narrow: reuse its existing `sweep_levels`, `read_mesh_geometry`,
placement transform, `rotation_matrix`, and `winding_sign` path, but export transformed world-space triangles
intersecting the pilot window **before** the max-Z-specific `Arc` exclusion. Include:

1. placements whose basename contains `Arc`;
2. cave/merged-floor geometry currently excluded only because it has no cooked hull;
3. the ordinary hull-equivalent rock set intersecting the same window, for context.

Keep the existing owner exclusion and >600 m oversize exclusion. No node meshes.

Handoff file:

```text
ad_arch_triangles.npz
  triangles: float32 [T,3,3]
```

Coordinates must already be planner metres: X=east, Y=north=-gameY, Z=up. Export transformed triangles, not
mesh-local vertices + placement records, so the planner prototype stays independent from Unreal package logic.

A useful v2 of the handoff should additionally include corrected world-space face orientation (`triangle_side`
= +1 upward / -1 downward / 0 uncertain) after SatisfactoryMCP's winding correction. That will let the planner
distinguish traversable decks/floors from arch undersides/ceilings rather than treating every Z intersection
as a possible floor.

## Local command once the triangle handoff exists

```cmd
python scripts\build_multisurface_window.py ^
  --triangles data\local\ad_arch_triangles.npz ^
  --terrain-dir planning_data\world\spatial\heightmap_build_502094 ^
  --bounds -2300 -900 -1850 -380 ^
  --step-m 2 ^
  --out data\local\multisurface\ad_arch
```

Outputs:

- `multisurface_window.npz` — ordered Z surfaces per XY cell;
- `multisurface_derived.npz` — layer count and clearance to the next surface;
- `summary.json` — counts/provenance.

## Acceptance checks for the A↔D pilot

The pilot succeeds only if all of these are visible in data, not inferred from the SCIM picture:

1. In the highlighted arch area, some XY cells contain at least two physically separated surfaces.
2. A lower surface remains vertically continuous from the western approach to the eastern exit where the
   in-game route can pass under the arch.
3. The upper arch/deck surface is retained separately rather than replacing the lower route surface.
4. Clearance between the lower travel layer and the nearest overhead surface can be measured.
5. A layered route can stay on the lower surface without zeroing a 150–200 m max-Z jump.
6. If the extracted geometry does *not* provide that continuity, the A↔D short route remains unverified rather
   than being rescued by an ambiguity exception.

## Relationship to the existing heightfield

Do not replace `height.i16.z`. It remains the fast ground field and is well validated for ordinary terrain.
The multi-surface artifact is a local/derived topology layer for caves, arches, bridges and stacked terrain.
If the A↔D pilot succeeds, extend it spatially only where the source extraction indicates multiple surfaces or
where routing crosses vertical-ambiguity provenance.
