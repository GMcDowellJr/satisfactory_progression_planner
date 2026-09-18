# Build surface v6 — flat-plane support with vertical-layer ambiguity

v6 keeps the rectangle-first, single-horizontal-plane model from v5 but changes what counts as ground support.

The 502094 heightfield is a 2.5D top surface. In the PHM steel district, a natural bridge is represented by cliff geometry roughly 30 m above an existing flat foundation deck. Treating every heightfield sample as floor terrain therefore creates false penetration/floating conclusions.

v6 uses provenance-aware support:

- landscape (`1`) and fill (`3`) are ground-support samples;
- cliff (`4`) and cliff-direct (`5`) are reported as vertical-layer ambiguity rather than automatically raising the fitted plane;
- footprints must retain sufficient known ground support (85% overall, 75% perimeter by default);
- the fitted platform is the lowest no-penetration horizontal plane over known ground;
- mean, edge-mean, and maximum known-ground clearance are policy-controlled;
- with the default 4 m tolerance, maximum known-ground clearance is also capped at 4 m.

## PHM calibration fixture

`planning_data/analysis/calibration/PHM_steel_deck_502094/` contains 221 connected standard 8x4 foundations on one flat transform plane.

Observed against the 502094 heightfield at foundation centers:

- transform origin Z: -5 m;
- assumed top of a centered 4 m foundation: -3 m;
- known landscape/fill centers: 179 / 221 (~81%);
- cliff/overhead top-surface centers: 42 / 221;
- known-ground terrain relief: ~2.3 m;
- known-ground top clearance median: ~3.0 m;
- known-ground top clearance p95: ~3.8 m;
- known-ground edge p95: ~3.8 m;
- no known-ground center protrudes above the deck top.

This is calibration evidence, not a claim that every cliff sample is overhead. Cliff-only areas remain explicitly ambiguous until a multi-surface terrain representation exists.
