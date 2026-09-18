# Scripts

Repository-level orchestration wrappers. Tool-specific code lives under `tools/`.

## Primary build-surface analysis

```cmd
python scripts\generate_build_surfaces.py --resolutions 16
```

The v5 default is rectangle-first horizontal-plane fit. Override clearance variants if desired:

```cmd
python scripts\generate_build_surfaces.py --resolutions 8 16 --relief-tolerances 4 8 16 32
```

## Alternate horizontal-platform elevation sweep

```cmd
python scripts\generate_elevation_sweep.py --resolutions 16 --vertical-step 16
```

## 3D world viewer

```cmd
python scripts\world_viewer.py view --resolution 16 --terrain-spacing 24
```

For v5, `;` / `'` cycles plane-clearance tolerances. Concrete qualifying rectangles are drawn at their fitted horizontal platform elevations over subdued placement-center regions.

## Corridors

`generate_corridors.py` derives reusable physical corridor/connectivity geometry. See `tools/corridor_tool/README.md`.

### Build-surface calibration from saves

`extract_foundation_fixture.py` extracts a connected flat standard-foundation component from a local `.sav` using the lightweight-buildable subsystem. `calibrate_foundation_fixture.py` compares that derived deck against the versioned terrain/provenance field. Source saves are not copied into the repository.
