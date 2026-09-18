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

    game/reference/recipes.csv
    game/reference/recipe_io.csv
    game/reference/recipe_producers.csv
    game/reference/items.csv
    game/reference/production_buildings.csv
    game/reference/recipe_variable_power.csv
    game/reference/extraction_buildings.csv
    game/reference/extraction_rates.csv
    game/reference/resource_extraction_map.csv

## Checking

    python tools/check_game_docs_provenance.py

Verifies this copy, and — when the game is installed here — compares it against the
live install to detect a patch. See `planning_data/provenance/game_docs_source.csv`.

## Note on language files

`CommunityResources/Docs` ships ~55 localizations of the same structural data. Only
`en-US.json` is pinned; display names in the reference layer are therefore US English
by construction. A different locale would produce identical IDs, rates and power with
different `display_name` values, and would be a different sha256.
