# Satisfactory World Analysis & Progression Planner

This repository is organized around a deliberate boundary between **world extraction**, **world analysis**, and **playthrough planning**. It is not intended to become another machine-count calculator with a different UI.

## Product direction

The foundational question is: **what is this world configuration naturally suited to, given resource placement, terrain, water, build surfaces, and logistics friction?** Progression planning then asks what to build, at what scale, and when. Presentation can later be mobile-first, desktop/web, or an in-game mod without changing the core data model.

## Repository layout

```text
satisfactory_progression_planner/
├─ planning_data/
│  ├─ game/                 # installed-game facts: recipes, items, buildings, unlocks
│  ├─ world/                # versioned world extraction and canonical spatial facts
│  │  ├─ canonical/
│  │  ├─ source_snapshots/
│  │  ├─ spatial/
│  │  └─ manifests/
│  ├─ planning/             # generic planner model, plans, strategies, playthrough state
│  ├─ analysis/             # derived world/plan analyses and QA
│  ├─ provenance/
│  └─ schema/
├─ tools/
│  ├─ satisfactory_route_tool/
│  ├─ build_surface_tool/
│  ├─ corridor_tool/
│  └─ world_viewer/
├─ docs/
└─ scripts/
```

## Current world baseline

Build **502094 / Satisfactory 1.2.4.0** is the current aligned default-world test fixture. Its world package includes terrain/water, 4,446 static collectible rows, 1,764 primary exploration POIs, and 625 resource sockets. Resource placement is split from default resource/purity assignment so a future save reader can materialize altered/randomized worlds without replacing fixed geometry.

See `planning_data/ARCHITECTURE.md` and `planning_data/world/README.md`.

## Build-surface analysis

`tools/build_surface_tool/` now defaults to **rectangle-first horizontal-plane fit** from a versioned world manifest. `scripts/generate_build_surfaces.py` evaluates Small/Medium/Large/Very Large reference footprints at configurable horizontal resolutions and clearance tolerances. Each emitted rectangle has one fitted platform Z, plus footprint-wide/perimeter clearance metrics that describe how closely terrain supports that flat plane. The v4 local-relief and v3 global elevation-sweep analyses remain available for comparison. Build 502094 is a validation fixture rather than a map-specific implementation.

## 3D world visualization

`tools/world_viewer/` is a presentation/QA consumer of the versioned world extraction and derived build-surface artifacts. It provides an interactive VTK desktop view, offscreen PNG snapshots, and portable GLB export. It deliberately does not own buildability logic; changing a surface policy requires regenerating analysis, not changing the viewer. Run it through `scripts/world_viewer.py`.

## Corridor/connectivity analysis

`tools/corridor_tool/` generalizes the earlier point-to-point routing work into reusable terrain topology. It derives a policy-controlled passability field, blocker clearance, centerline skeleton, graph nodes/edges, and chokepoint/constrained/open annotations from the same versioned world extraction. It deliberately remains transport-mode neutral; player, vehicle, belt/lift, pipe, and rail solvers can consume or reinterpret this topology downstream. Run it through `scripts/generate_corridors.py`.
