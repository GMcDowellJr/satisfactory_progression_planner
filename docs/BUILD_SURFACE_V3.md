# Build Surface V3 — Elevation Sweep

## Why v3 exists

V1 allowed local terrain continuity to chain up very large total vertical relief. V2 bounded that behavior with aligned vertical bands, but that still modeled terrain-following terraces rather than the original question: **what horizontal foundation platform becomes possible as elevation rises?**

V3 makes horizontal platform elevation the primary state.

## Model

For each requested horizontal resolution:

1. aggregate the 1 m terrain into coarse cells using maximum terrain elevation;
2. optionally raise the obstruction height to known water-surface elevation;
3. choose horizontal platform planes from the configured minimum to maximum at `vertical_step_m` intervals;
4. at each plane mark every cell whose obstruction is at or below the plane as available;
5. label connected available regions;
6. find the largest foundation-equivalent rectangular core in each region;
7. classify Small / Medium / Large / Very Large plus shape; and
8. report terrain-clearance and diagnostic metrics.

The key invariant is monotonicity: if a cell is available at Z, it must remain available at every higher sampled Z.

## Independent controls

`analysis_resolution_m` determines X/Y fidelity. Smaller cells preserve more narrow branches, holes, ridges, and irregular edges.

`vertical_step_m` determines Z sampling cadence. Larger steps skip intermediate platform states but do not alter a state at the same exact Z.

This distinction is important for future map/build changes and for comparing play styles.

## Current validation fixture

A build-502094 run at 16 m horizontal resolution and 16 m vertical step passes the monotonic QA gate. It begins producing Large surfaces at lower sampled elevations and Very Large surfaces once sufficient terrain obstructions have been cleared. At the top of the sampled world, all cells in the current analyzable terrain domain are available; remaining separation reflects source-domain/no-data geometry rather than terrain height.

Threshold/class interpretation remains calibration work rather than a blocker for downstream corridor analysis.
