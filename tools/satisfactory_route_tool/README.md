# Satisfactory Route Tool

> Planner package v2: terrain/POI inputs now live under `world/` and gameplay requirements under `game/reference/`.

A standalone routing toolkit for the planning package developed in the Satisfactory project.

It separates three jobs:

1. **Visual-road preprocessing**  
   Convert a SCIM screenshot with the Roads layer visible into a coarse road-prior raster aligned
   to the locally extracted Satisfactory terrain grid.

2. **Mode-aware routing**  
   Solve Foot / Tractor / Truck / Rail routes using the local heightfield, water plane,
   terrain provenance, and optional road prior.

3. **Exploration scoring**  
   Rank nearby Hard Drives, Power Slugs, Mercer Spheres and Somersloops as detours from a solved
   route using a foot-oriented access model.

The solver deliberately treats roads as a **preference**, not as permission to cross impossible
terrain. Local game-derived terrain and water are evaluated inside the route search.

## Input package

The tool accepts either:

- an unpacked `satisfactory_planning_data_v1_x/` directory, or
- the planner `.zip` directly.

Expected spatial inputs:

```text
world/spatial/heightmap_build_502094/
  height.i16.z
  prov.u8.z
  water.i16.z
  waterq.u8.z
  meta.json

world/canonical/exploration_pois.csv
game/reference/crash_site_requirements.csv
```

The raster format is the one produced by SatisfactoryMCP's local heightmap generator:
int16 height/water values are decimetres encoded as row-delta + zlib; uint8 planes are plain zlib.

## Install

From this folder:

```cmd
py -m pip install -e .
```

or with `uv`:

```cmd
uv pip install -e .
```

## 1. Extract a SCIM visual road prior

Take a north-up screenshot that contains the full square SCIM map with **Roads** enabled.

```cmd
satisfactory-route extract-scim ^
  --planner "C:\path\satisfactory_planning_data_v1_14.zip" ^
  --image "C:\path\scim_roads.png" ^
  --out "C:\path\spatial\scim_roads"
```

Outputs:

```text
scim_road_prior_5m.npz
scim_road_prior_meta.json
scim_road_segmentation.png
```

The `.npz` is aligned to the planner world extent at 5 m resolution by default.

This is coarse cartographic interpretation of the visible overlay, not underlying SCIM source data.

## 2. Solve a route

Example: Rocky Desert A -> D / Oil, Truck, no bridge:

```cmd
satisfactory-route solve ^
  --planner "C:\path\satisfactory_planning_data_v1_14.zip" ^
  --roads "C:\path\spatial\scim_roads\scim_road_prior_5m.npz" ^
  --origin -2650.2936 370.0145 ^
  --destination -2540.9607 -740.4848 ^
  --mode truck ^
  --bridge-policy forbid ^
  --out "C:\path\routes\a_to_d"
```

Outputs:

```text
route_points.csv
route_summary.json
route_validation.csv
route_map.png
```

### Bridge policy

- `forbid` — deep water is blocked; shallow water is expensive.
- `allow` — deep-water crossings are permitted but very expensive and reported as construction
  requirements.

The route solver does **not** automatically decide that a bridge is strategically worthwhile.
It only exposes the cost/requirement.

## 3. Score exploration detours

```cmd
satisfactory-route score-pois ^
  --planner "C:\path\satisfactory_planning_data_v1_14.zip" ^
  --route "C:\path\routes\a_to_d\route_points.csv" ^
  --trip-type first_trip ^
  --out "C:\path\routes\a_to_d\exploration"
```

This uses an intentionally looser foot model:

- horizontal distance dominates,
- vertical difference is a soft penalty,
- natural-road preference is ignored,
- route POIs are classified as `near_free`, `strong_detour`, `purposeful_detour`,
  `optional_detour`, or `defer`.

## Default movement profiles

These are planning defaults, **not claims about exact in-game vehicle physics**.

| Mode | Road preference | >100% edge grade | 50-100% grade | Deep water |
|---|---|---|---|---|
| Foot | none | allowed/high cost | moderate | high cost |
| Tractor | strong | blocked | very high cost | blocked unless bridge allowed |
| Truck | strong | blocked | very high cost | blocked unless bridge allowed |
| Rail | moderate | blocked much earlier | high construction cost | bridge construction |

The defaults live in `movement_profiles.json` and can be copied/edited without changing code.

## Design principles

- Validation is **inside** routing, not merely post-hoc.
- Screenshot roads are a **corridor prior**.
- Local water/terrain are the authoritative physical layers.
- Movement modes are distinct.
- Corridor-level accuracy is sufficient; this is not turn-by-turn GPS.
- Solver outputs remain machine-readable so ChatGPT or another planner can interpret them.


## Grade handling

The solver does not use raw 5 m neighbor-to-neighbor height differences directly as its only
grade signal. The local heightfield can contain sharp raster/topology discontinuities around
cliffs, caves and overhangs. Grade cost therefore uses a locally smoothed elevation surface while
the raw terrain elevation is still retained in route output and validation.

The movement-profile hard-grade values remain planning policy rather than a claim about exact
vehicle physics. Tune them in `movement_profiles.json` as play validation improves the model.

## Current scope

Version 0.1.0 is intentionally a **corridor solver**, not an autonomous road builder. It can:

- read the planner package directly from ZIP or an unpacked directory;
- create a 5 m road-prior raster from a SCIM screenshot;
- solve mode-specific terrain/water-aware routes;
- expose bridge-policy decisions;
- emit validation and route points;
- score nearby exploration POIs.

Known future improvements:

- explicit corridor-width / vehicle-clearance tests;
- route alternatives rather than one best A* path;
- bridge segment grouping and construction estimates;
- cave/pass graph integration;
- rail curvature constraints;
- play-validated movement thresholds.
