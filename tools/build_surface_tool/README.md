# Satisfactory Build Surface Tool

Repeatable terrain-derived factory-site analysis for versioned Satisfactory world extracts.

## Primary v9 model: recalibrated flat-pad footprint plane fit

V8 treats the **actual flat foundation rectangle** as the primary object and separates flat-pad size from later district-capacity aggregation. A size class is no longer one required square. Each class owns an editable family of rectangular footprints in foundation units; the analyzer tests those shapes and retains the largest qualifying footprint at each candidate center.

The default bands are now Small short side >=8 foundations, Medium >=12, Large >=20, and Very Large >=32. The PHM steel deck (~12 x 26 foundations in outer extent) is the Medium calibration anchor. Edit `planning_data/analysis/policies/build_surfaces_v9.json` to revise the families without changing code.

Three independent concepts drive the result:

1. **horizontal working resolution** — how finely terrain is sampled for analysis;
2. **physical footprint family** — candidate width/length in 8 m foundations;
3. **clearance tolerance** — how far the ground may fall below the fitted flat plane while still reading as terrain-supported.

Rectangle geometry is always physical: `width_foundations * 8 m` by `length_foundations * 8 m`. It never scales with analysis resolution. Thus an 8x8 footprint is 64x64 m at 8 m, 16 m, or any other working resolution.

For every candidate rectangle:

- `platform_elevation_m` is the highest representative known-ground cell in the footprint;
- landscape/fill provenance defines known ground support;
- cliff-only top surfaces are vertical-layer ambiguity and do not automatically lift the platform;
- mean and perimeter clearance measure how grounded the flat plane remains;
- maximum clearance catches deep local drops;
- among multiple qualifying shapes in one class, larger footprint area wins, then lower perimeter/overall clearance breaks ties.

## Outputs

- `build_surfaces.csv` — connected regions of qualifying centers and the best concrete footprint associated with each region.
- `build_surface_rectangles.csv` — primary planning geometry: actual qualifying width/length, fitted platform Z, and support metrics.
- `build_surface_membership_*_clearance_*.npz`
  - `labels` = qualifying-center region identity;
  - `coverage_labels` = union of the physical footprints represented by those qualifying centers;
  - `class_rank` = highest qualifying size class at each center.
- `summary.json`
- `qa.json`

The viewer uses `coverage_labels` for the contextual suitability fill so the concrete white rectangles are contained by the displayed footprint envelope rather than being compared to a center-only mask.

## Run

From the repo root:

```cmd
python scripts\generate_build_surfaces.py --resolutions 16
```

Override clearance variants:

```cmd
python scripts\generate_build_surfaces.py --resolutions 16 --clearance-tolerances 1 2 4 8 16 32 64
```

V7 previous size bands, V6 fixed-reference plane support, V5 all-top-surface plane fit, V4 local relief, and V3 global elevation sweep remain available for comparison/reproducibility.

## Save-derived calibration fixtures

Known in-game foundation decks can be used as empirical calibration fixtures without committing the source save. The repository includes `planning_data/analysis/calibration/PHM_steel_deck_502094/`, extracted from a supplied build-502094 save.

```cmd
python scripts\extract_foundation_fixture.py path\to\save.sav --z-m -5 --output-dir planning_data\analysis\calibration\my_fixture
python scripts\calibrate_foundation_fixture.py planning_data\analysis\calibration\my_fixture\foundations.csv
```

The PHM fixture remains a support/overhang calibration case and now also anchors the Medium flat-pad scale. Because the real deck is irregular, the fixture validates support behavior directly on its placed foundations rather than asserting that its entire outer bounding rectangle must qualify.
