# Architecture migration: v1.14 → v2.0

The refactor makes world extraction a first-class layer instead of mixing map facts into `reference/` and Rocky planning inputs.

| Old location | New location / treatment |
|---|---|
| `planning_data/reference/*` | gameplay facts → `planning_data/game/reference/` |
| `reference/exploration_pois.csv` | `world/canonical/exploration_pois.csv` |
| `reference/spatial/*` | `world/spatial/*` |
| `reference/source_snapshots/*` | `world/source_snapshots/*` |
| `reference/resource_sources.csv` | retained under `planning/legacy/rocky_desert/`; no longer canonical |
| new | `world/canonical/world_resource_sockets.csv` |
| new | `world/configurations/default_502094/resource_assignments.csv` |
| new | `world/manifests/world_502094.json` |
| `planner_model/` | `planning/model/` |
| `plans/` | `planning/plans/` |
| `strategy_profiles/` | `planning/strategies/` |
| `playthroughs/` | `planning/playthroughs/` |
| `templates/` | `planning/templates/` |
| `derived/` | `analysis/derived/` |
| `qa/` | `analysis/qa/` |

The default build-502094 world is a validation fixture. Future save readers should emit additional `world/configurations/<id>/resource_assignments.csv` files using the same `socket_id` join contract.
