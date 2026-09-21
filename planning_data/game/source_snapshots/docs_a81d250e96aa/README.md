# Game Docs snapshot — docs_a81d250e96aa

Raw, unmodified first-party artifact. Mirrors the `world/source_snapshots/<build>/`
convention in `planning_data/ARCHITECTURE.md`.

    file      en-US.json
    bytes     10,640,180
    sha256    a81d250e96aa13db3c0bf8c332c199ad930b2f15323e2c1a069afa4c07f971bb
    encoding  UTF-16 LE with BOM
    origin    <Satisfactory install>/CommunityResources/Docs/en-US.json
    captured  2026-09-18 (file mtime 2026-09-09T22:12:38Z)

Do not edit. Do not reformat, re-encode, or strip the BOM — the sha256 is the pin
that `game_builds.csv` and every derived table's `game_build_id` refer to, and any
byte change breaks that chain.

## Why this is here

The game install is overwritten in place by every patch, so a path alone could not
be relied on. With this copy the reference layer is reproducible from the repo, on a
machine that has never had the game installed.

## Derived from this snapshot

**The list below is a copy. `planning_data/provenance/reference_tables.csv` is the
single declaration** — this file, `tools/check_game_docs_provenance.py` and
`tests/test_game_docs_provenance.py` all read it, and a test asserts this section
matches it exactly. Edit the manifest, not this list.

Derived by hand. **No code in this repo regenerates these fifteen.** They are pinned
by the sha256 above and by the recipe-filter check described below, not by a script
that reproduces them.

    game/reference/recipes.csv
    game/reference/recipe_io.csv
    game/reference/recipe_producers.csv
    game/reference/items.csv
    game/reference/production_buildings.csv
    game/reference/recipe_variable_power.csv
    game/reference/extraction_buildings.csv
    game/reference/extraction_rates.csv
    game/reference/resource_extraction_map.csv
    game/reference/schematics.csv
    game/reference/schematic_costs.csv
    game/reference/schematic_recipe_unlocks.csv
    game/reference/schematic_dependencies.csv
    game/reference/alternate_choices.csv
    game/reference/non_hard_drive_alternate_unlocks.csv

Emitted by `scripts/extract_game_reference.py --emit`, added 2026-09-21:

    game/reference/building_recipes.csv
    game/reference/building_recipe_io.csv
    game/reference/power_buildings.csv
    game/reference/generator_fuels.csv

### Corrected 2026-09-21 — this list was wrong

It named nine tables. **Seven more carry this snapshot's `game_build_id` and were
declared nowhere** — not here, not in the checker, not in the tests: the four
`schematic*`/`schematics` tables, `alternate_choices.csv`,
`non_hard_drive_alternate_unlocks.csv`, and `game_builds.csv` (which is a registry,
not a derived table, and is excluded with that reason recorded in the manifest).

That was not a drift risk but a live defect. At a game patch the checker would have
named nine stale tables and silently omitted the entire schematic layer — the tables
`progression.unlocks` and `progression.pool` read. Found by scanning every reference
CSV for the column rather than by reading any of the three lists.

`game_builds.csv` is the instructive one: it carries `game_build_id` as a key, so a
stamp check would pass today and fail the moment a second build is registered, which
is precisely when a patch lands.

### The recipe filter

`FGRecipe` holds 872 classes; `recipes.csv` holds 291. The rule that reproduces that
set exactly is **keep a recipe when `mProducedIn` names at least one `Build_*`
class**. The other 549 name `BP_BuildGun` and are building construction costs; no
recipe names both, so the sets are disjoint. `extract_game_reference.py --verify`
asserts this against the committed `recipes.csv`, which is what pins the nine
hand-derived tables to a stated rule rather than to memory.

## Checking

    python tools/check_game_docs_provenance.py
    python scripts/extract_game_reference.py --verify

The first verifies this copy, and — when the game is installed here — compares it
against the live install to detect a patch. See
`planning_data/provenance/game_docs_source.csv`. The second checks the recipe filter
against `recipes.csv` and the generator arithmetic against known in-game figures,
and writes nothing.

## Note on language files

`CommunityResources/Docs` ships ~55 localizations of the same structural data. Only
`en-US.json` is pinned; display names in the reference layer are therefore US English
by construction. A different locale would produce identical IDs, rates and power with
different `display_name` values, and would be a different sha256.
