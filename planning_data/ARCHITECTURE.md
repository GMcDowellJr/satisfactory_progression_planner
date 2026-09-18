# Architecture

The repository now separates four concerns that were previously mixed together.

## 1. Game reference

`game/reference/` contains build-pinned gameplay facts such as items, recipes, buildings, logistics capabilities, unlock graphs, extraction rates, and Project Assembly requirements. These describe game rules, not map placement or player choices.

## 2. World extraction

`world/` contains the versioned physical world substrate.

- `world/source_snapshots/<build>/` preserves first-party/raw extracted artifacts.
- `world/canonical/` contains normalized tables used by tools.
- `world/spatial/` contains terrain/water rasters.
- `world/manifests/` binds the layers into one build-aligned extraction package.

The resource model deliberately separates **socket geometry/identity** from **resource assignment/purity**. `world_resource_sockets.csv` is the stable placement layer; `world_resource_assignments_default.csv` is only the default configuration for build 502094. A save-derived configuration should use the same assignment schema and join by `socket_id`.

World extraction answers **what exists and where**. It does not decide what a site should be used for.

## 3. World analysis

`analysis/` contains derived interpretations and validation. The next major world-analysis capabilities are:

1. buildable / industrial-surface extraction;
2. generalized connection and corridor topology;
3. resource clustering over a materialized world configuration;
4. logistics-friction surfaces for belts/lifts, vehicles, pipes, and later rail;
5. site-use suitability.

Terrain and exploration geometry are comparatively stable within a build. Resource assignment/purity may differ by world/save configuration. Analysis should therefore consume a **materialized world**, not assume the default map assignment is universal.

## 4. Planning

`planning/` is downstream of world analysis.

- `planning/model/` — reusable planning vocabulary.
- `planning/plans/` — geography-specific planning inputs and reference plans.
- `planning/strategies/` — player/build-style preferences.
- `planning/playthroughs/` — mutable run state.
- `planning/templates/` — reusable table shapes.
- `planning/legacy/` — transitional sources retained only to migrate older IDs/assumptions.

A future recommendation should combine game facts + materialized world analysis + strategy + playthrough state. Existing machine solvers may be used as subordinate evaluators; they are not the product center.

## Client boundary

No UI owns planner logic. A future mobile app, web/desktop interface, or Satisfactory mod should consume normalized planner/world-analysis outputs through stable contracts. The routing tool is the first standalone analysis engine following this rule.

## Default-world role

The unmodified build-502094 world is a **test fixture**, not the architecture. It is useful for validating whether the analysis independently discovers plausible resource/logistics relationships. Save-derived resource assignments can later replace the default assignment table while reusing the same terrain and world-socket geometry when build-compatible.

## Derived world analysis

Buildable surfaces are derived from the immutable/versioned world extraction rather than stored as canonical world facts. The primary v5 build-surface tool is rectangle-first: each size class supplies a reference factory footprint, one horizontal platform Z is fitted over each candidate rectangle, and independent clearance thresholds measure how closely terrain supports that plane overall and along its perimeter. Horizontal working resolution controls how much sub-cell terrain detail matters. Connected output regions are only zones of qualifying rectangle centers; `build_surface_rectangles.csv` is the primary planning geometry. V4 local-relief and v3 elevation-sweep analyses are retained as alternate diagnostics.

## Visualization / QA boundary

`tools/world_viewer/` sits downstream of world extraction and derived analysis. It renders terrain, water, canonical resource sockets, and build-surface membership without changing those datasets. Interactive rendering, screenshots, and GLB export are presentation products rather than canonical world facts. This keeps later Three.js/mobile/in-game clients free to consume the same stable artifacts.
