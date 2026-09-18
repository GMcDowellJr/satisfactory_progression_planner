# Resource Authority (P3)

- Date: 2026-09-18
- Closes: P3, open since `production_solver_selection.md` section 7.

## State

    locked:  items.csv is the sole authority for what a resource IS
    locked:  resources.csv is a crosswalk, not a second authority
    open:    the world layer's third vocabulary (see below)

## Problem

Three tables described resources in three vocabularies with no join:

    game/reference/items.csv          Desc_OreIron_C     13 rows, category='resource'
    game/reference/resources.csv      iron               14 rows, human slugs, no item_id
    world/.../resource_totals.csv     iron, crude_oil_nodes, crude_oil_wells, geyser

The adapter needs canonical item ids. The world layer keys on slugs. Retiring
`resources.csv` outright would have broken the world layer's vocabulary.

## Decision

`items.csv WHERE category='resource'` is the authority for resource identity.
`resources.csv` keeps its slugs and gains an `item_id` column, making it the
explicit crosswalk between the world layer and the game reference layer.

The mapping was not invented. `world/configurations/default_502094/resource_assignments.csv`
already carries both `resource_id` (slug) and `resource_descriptor` (`Desc_*_C`)
on all 625 rows, derived from the installed world default. Extracted from there:

    14 slugs, 0 ambiguous (no slug maps to two descriptors)
    13 map 1:1 onto exactly the 13 resource items in items.csv
    0 resource items uncovered, 0 descriptors without an item
    geothermal_geyser maps to nothing — it is a power site, not an item

## Still open

`resource_totals.csv` uses a *third* vocabulary: it splits `crude_oil` into
`crude_oil_nodes` and `crude_oil_wells`, and renames `geothermal_geyser` to
`geyser`. That is a world-layer modelling distinction (node versus resource well)
rather than a naming inconsistency, and it matters — the two are extracted by
different buildings at different rates, per `resource_extraction_map.csv`. Left
alone; it belongs to the Phase 5 world integration, not to P3.
