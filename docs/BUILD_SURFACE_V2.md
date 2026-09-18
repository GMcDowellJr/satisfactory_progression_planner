# Build Surface Segmentation v2

## Why v2 exists

The first build-surface prototype used a local elevation rule. At 16 m horizontal resolution, neighboring cells could each pass an 8 m local step test and still chain up a long hillside. One observed connected surface accumulated about 200 m of total relief. The viewer correctly exposed the region, but the region was not a coherent industrial terrace.

## V2 parameter separation

V2 treats these as independent policy controls:

- `working_resolutions_m`: horizontal analysis cell size;
- `cell_relief_tolerance_m`: allowable terrain relief inside a cell;
- `max_neighbor_step_m`: allowable representative-elevation discontinuity between neighboring cells;
- `region_vertical_spans_m`: total aligned vertical envelope used to segment coherent connected surfaces.

The default Z-span variants are 2, 4, 8, and 16 m.

## Deterministic aligned bands

For each horizontal resolution, usable cells are assigned to elevation bands using one shared origin. The configured spans are aligned so the 2 m bands nest into 4 m, then 8 m, then 16 m. This gives calibration behavior that is easy to reason about:

```text
smaller Z span  -> more / smaller terraces
larger Z span   -> progressively merged terraces
```

This is intentionally simpler than fitting arbitrary sloping planes. It gives us a stable first definition of terrain-supported surface coherence that can be validated in-game.

## Validation fixture: build 502094, 16 m horizontal resolution

The initial v2 smoke run produced the following raw candidate-region counts:

| Region vertical span | Candidate regions | Maximum observed region relief |
|---:|---:|---:|
| 2 m | 2,943 | ~1.95 m |
| 4 m | 2,883 | ~3.95 m |
| 8 m | 1,984 | ~7.95 m |
| 16 m | 1,373 | ~15.95 m |

The classified Small+ surface count is not expected to decrease monotonically: when small terraces merge, a region that was previously below the Small footprint threshold can become classifiable.

## Viewer

The world viewer reads the v2 membership variants directly. Use `--region-span` to choose one at startup, or `;` / `'` in the interactive viewer to cycle the active Z span. Surface outlines, selection, isolation, and metrics remain presentation-only; segmentation stays in `build_surface_tool`.
