# Build Surface v5 — horizontal plane fit

v5 makes the proposed factory rectangle the primary object.

For each Small/Medium/Large/Very Large reference footprint and each candidate center, the tool fits **one horizontal platform plane**. At the working resolution the plane Z is the highest representative terrain cell in the rectangle, so representative terrain does not protrude through the platform.

The working-cell terrain elevation is policy-driven. The v5 calibration default is the **median of the underlying 1 m samples**. At 16 m resolution this deliberately ignores small sub-cell rocks/spikes; use a finer working resolution if those details should matter.

A clearance tolerance describes how closely terrain supports the plane rather than total end-to-end terrain relief. A candidate qualifies when:

- footprint mean clearance <= tolerance;
- perimeter mean clearance <= tolerance;
- maximum clearance <= `max_clearance_factor × tolerance` (3× by default).

The perimeter test is intended to detect the practical transition where a flat foundation field begins visibly floating along an edge. The maximum allowance prevents one deep local pocket from being ignored entirely while not requiring every terrain sample to sit within one foundation height.

`build_surface_rectangles.csv` records the actual candidate rectangles and fitted platform Z values. The irregular membership regions are only connected zones of qualifying rectangle centers and should be treated as context.

Important calibration parameters are all in `planning_data/analysis/policies/build_surfaces_v5.json`:

- `working_resolutions_m`
- `clearance_tolerances_m`
- `cell_surface_percentile`
- `max_mean_clearance_factor`
- `max_edge_mean_clearance_factor`
- `max_clearance_factor`
- size-class reference footprints

v4 local-relief and v3 elevation-sweep analyses are retained for comparison/reproducibility.
