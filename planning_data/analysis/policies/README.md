# Analysis Policies

## `build_surfaces_v3.json` — current

Horizontal-platform elevation-sweep policy. Horizontal analysis resolution and vertical sampling step are independent. Coarse cells retain maximum obstruction height, and connected usable area grows monotonically as the platform plane rises.

## Historical build-surface policies

- `build_surfaces_v2.json` — aligned terrain-elevation-band segmentation experiment.
- `build_surfaces_v1.json` — local terrain-following prototype.

Both remain for provenance/reproducibility but are not the default generator policy.

## `corridors_v1.json`

Current terrain-connectivity/corridor derivation policy.

- `build_surfaces_v8.json` — prior default: save-calibrated horizontal-plane support with recalibrated variable flat-pad families (S>=8, M>=12, L>=20, VL>=32 foundations short-side); 1..64 m clearance variants.

- `build_surfaces_v9.json` — current default: v8 flat-pad semantics plus class-specific footprint-union rasters for reliable exclusive S/M/L/V rendering; safe NaN diagnostics.
