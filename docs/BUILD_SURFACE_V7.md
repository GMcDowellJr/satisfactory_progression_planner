# Build Surface V7 — Variable Footprint Families

V7 addresses two calibration problems discovered while comparing the viewer with known in-game factories:

1. a size class cannot be represented by one square/reference rectangle; real factories may be long and relatively narrow;
2. footprint visualization must remain in physical foundation units and must not scale with terrain-analysis resolution.

## Geometry contract

A Satisfactory foundation is treated as 8 m x 8 m in plan. `analysis_resolution_m` controls only terrain sampling and candidate-center spacing.

Each size class contains a parameterized `footprint_family_foundations`. The analyzer tests all configured shapes at the supported orientations. A center qualifies for a class if any family member passes the horizontal-plane support tests. Within a class, the largest qualifying area is retained; support clearance breaks ties.

The default Small family deliberately includes `12 x 26`, close to the PHM steel-deck outer proportions, without reclassifying that calibration deck as Medium. Medium and larger classes continue to require broader footprints.

## Viewer contract

`build_surface_rectangles.csv` is authoritative for concrete candidate geometry. The viewer computes physical dimensions as:

`metres = foundations * foundation_size_m`

with 8 m as the backward-compatible default.

The membership NPZ retains two spatial concepts:

- `labels`: connected regions of qualifying **centers**;
- `coverage_labels`: union of the actual physical footprints associated with those centers.

The viewer fills from `coverage_labels`, which makes the colored suitability envelope spatially consistent with the white candidate rectangles.
