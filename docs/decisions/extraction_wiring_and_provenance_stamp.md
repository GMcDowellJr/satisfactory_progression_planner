# Extraction Wiring (P2) and Game-Patch Provenance Stamp

- Date: 2026-09-18
- Follows: `production_building_power_model.md` (P1)
- Primary source: the same sha256-pinned `en-US.json`, `docs_a81d250e96aa`

## State

    locked:   extractor inventory + power, extraction rates, resource -> extractor map
    locked:   provenance stamp and drift checker, exercised in all three states
    open:     P3 resources.csv join — unchanged, but now easier (see section 4)
    open:     nitrogen resource wells absent from the world layer (section 3)
    pending:  whether a repo-local copy of en-US.json is wanted alongside the stamp

## 1. Extraction power is not on the extractor

Same failure shape as P1's variable power, different location.

    Build_FrackingExtractor_C   Resource Well Extractor       0 MW
    Build_FrackingSmasher_C     Resource Well Pressurizer   150 MW

The extractors on a resource well draw nothing. The Pressurizer carries 150 MW for
the whole well regardless of how many satellite extractors sit on it. A table keyed
"extractor -> power" records resource wells as free.

`extraction_buildings.csv` therefore carries a `role` column — `extractor` or
`activator` — and `resource_extraction_map.csv` carries `requires_activator`, which
names `Build_FrackingSmasher_C` for the three well-extracted resources. Power for a
well is `150 MW per well`, not per extractor; the adapter has to count wells, not
machines, for that one case.

## 2. What was produced

    extraction_buildings.csv      7 rows   3 miner tiers, Oil Extractor, Water Extractor,
                                           Resource Well Extractor, Resource Well Pressurizer
    extraction_rates.csv         16 rows   extractor x purity, Docs-derived
    resource_extraction_map.csv  35 rows   resource item_id -> extractor_class

Rates, at 100% clock:

    Build_MinerMk1_C        1 item / 1.00 s      impure 30    normal 60    pure 120   items/min
    Build_MinerMk2_C        1 item / 0.50 s      impure 60    normal 120   pure 240   items/min
    Build_MinerMk3_C        1 item / 0.25 s      impure 120   normal 240   pure 480   items/min
    Build_OilPump_C         2000 cm3 / 1.00 s    impure 60    normal 120   pure 240   m3/min
    Build_FrackingExtractor_C  1000 cm3 / 1.00 s impure 30    normal 60    pure 120   m3/min
    Build_WaterPump_C       2000 cm3 / 1.00 s    no purity    120                     m3/min

Node purity multipliers (0.5 / 1.0 / 2.0) are not in Docs. They are inferred, and
independently corroborated: the existing wiki-sourced `miner_extraction_rates.csv`
reconciles against `Docs base rate x multiplier` with **0 mismatches across 9 rows
and both rate columns**. Two sources, one answer.

The Water Extractor is deliberately a single row with `purity = none`. It is placed
on water surfaces rather than graded nodes, so a three-row purity spread would imply
a 60–240 range that does not exist. Corroborated by the world layer:
`resource_totals.csv` grades solid nodes, oil nodes and resource wells, and lists no
water nodes at all.

`max_250_rate_min` is nominal x 2.5 throughout, matching the existing table. Note
this is the *rate* at 250% clock; power at that clock is governed by the 1.321929
exponent from P1, not by 2.5.

## 3. Reconciliation and a world-layer gap

`miner_extraction_rates.csv` is confirmed correct against the game's own data. It is
now redundant with `extraction_rates.csv`, which is keyed by `Build_*_C` rather than
the `Mk.1` display string and covers fluids as well. Retiring it is a call for you,
not something done here — nothing was modified.

Separately, `resource_totals.csv` grades `crude_oil_wells` and `geyser` but has no
row for nitrogen resource wells, even though `Build_FrackingExtractor_C` extracts
nitrogen gas and `Desc_NitrogenGas_C` is a canonical resource item. Either nitrogen
wells are folded into another row or the world layer is short one resource. Out of
scope here; flagged because Phase 5 district planning will trip over it.

## 4. Effect on P3

`resource_extraction_map.csv` keys on `item_id` from `items.csv`, so it does not
depend on `resources.csv` at all. That makes the P3 decision cleaner: `items.csv`
can simply become the sole resource authority, and `resources.csv` either gains an
`item_id` column or is retired. The only thing still keyed on the human slugs is the
world layer (`resource_totals.csv`, `resource_assignments.csv`), which is a separate
join and a separate decision.

## 5. Provenance stamp

The reference layer is derived from a file inside the Steam install, which the store
overwrites in place on every patch. Nothing in the repo could see that happen.

    planning_data/provenance/game_docs_source.csv    the pin: path, bytes, sha256,
                                                     encoding, mtime, capture date
    tools/check_game_docs_provenance.py              the drift check
    tests/test_game_docs_provenance.py               stamp validity + build-id
                                                     consistency across derived tables

The checker re-hashes the live file and exits:

    0  MATCH    derived tables are current
    1  DRIFT    game patched; names every table that is now stale
    2  MISSING  file not readable here (different machine or library folder)
    3  STAMP    the stamp itself is malformed

Path resolution is `--path` > `$SATISFACTORY_DOCS` > the stamped path, so it works on
a machine with a different Steam library. `--restamp` records a new pin after you have
re-derived — it deliberately does not re-derive anything itself, and it says so.

All three states were exercised: MATCH against the real file, DRIFT against a
one-byte-modified copy, MISSING against a bad path.

The pytest side also asserts that every stamped table carries the *same*
`game_build_id` as the stamp — so a partial re-derivation after a patch fails loudly
instead of leaving a half-updated reference layer. The live-file check skips cleanly
when the game is not installed, so this stays green off your machine.

Suite: 25 tests, 24 passed, 1 skipped (the live-file check, in this container).

## 6. Not done

A repo-local copy of `en-US.json` would make the reference layer self-contained and
reproducible without the game installed. It is 10.6 MB of UTF-16 JSON, which is a real
decision about repo weight and about shipping game assets, so the stamp records the
path rather than the bytes. Say if you want the copy; the stamp already has a
`source_kind` column to distinguish `game_install` from a vendored copy.
