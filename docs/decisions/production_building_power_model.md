# Production Building Power Model — P1

- Date: 2026-09-18
- Supersedes: the power clause of the plan's section 6 validation invariant.
- Primary source: `en-US.json` shipped in the game's `CommunityResources/Docs`, sha256-verified.

## State

    locked:   producer inventory (11), power model per producer, per-recipe variable power (43)
    locked:   provenance of recipes / recipe_io / recipe_producers / items against the pinned build
    open:     is_alternate classification for 2 recipes (section 6)
    open:     P2 extraction wiring, P3 resources.csv join — not started
    pending:  whether underclock power scaling (exponent 1.321929) is modelled or ignored

## 1. Provenance

The file at `C:\Program Files (x86)\Steam\steamapps\common\Satisfactory\CommunityResources\Docs\en-US.json`
hashes to:

    a81d250e96aa13db3c0bf8c332c199ad930b2f15323e2c1a069afa4c07f971bb

which is byte-for-byte the value already pinned in `game_builds.csv` as `docs_a81d250e96aa`. The
reference layer's declared provenance is therefore verified, not assumed. 10,640,180 bytes, UTF-16 LE
with BOM, mtime 2026-09-09T22:12:38Z.

Note the gap this exposes: the sha256 pins a file that lives outside the repo, in a game install that
Steam will overwrite on the next patch. Nothing currently detects that. Worth considering a
provenance-stamped copy inside the repo, or at minimum a recorded path.

## 2. The invariant was wrong

Plan section 6 asserts `every recipe producer -> known base power`. That holds for 8 of 11 producers
and is false for the other 3.

The game splits manufacturers across two native classes:

    FGBuildableManufacturer                 8 producers, fixed power on the building
    FGBuildableManufacturerVariablePower    3 producers, mPowerConsumption = 0.000000

For the second group, power lives on the **recipe** as `mVariablePowerConsumptionConstant` and
`mVariablePowerConsumptionFactor`, giving a range of `const` to `const + factor`. A single scalar
keyed by building cannot represent it.

Revised invariant, now enforced by `tests/test_production_building_invariant.py`:

    every recipe producer
        -> exactly one canonical production-building record
        -> either a fixed base power, or a declared variable-power producer
        -> for variable-power producers, every recipe under that producer
           carries const + factor, and effective power is a (producer, recipe)
           function, not a producer constant

## 3. The trap

Three recipes on **fixed**-power producers also carry non-default variable-power fields:

    Recipe_SpaceElevatorPart_10_C  Biochemical Sculptor   Blender        const 500  factor 1000
    Recipe_SpaceElevatorPart_11_C  Ballistic Warp Drive   Manufacturer   const 500  factor 1000
    Recipe_SingularityCell_C       Singularity Cell       Manufacturer   const 0    factor 0

The game ignores these, because `FGBuildableManufacturer` has no variable-power behaviour. A rule of
the form "if the recipe has variable-power fields, use them" would give Ballistic Warp Drive
500–1500 MW on a 55 MW Manufacturer — a ~20x overstatement on a Phase 5 part.

**Variable power is gated on the producer's native class, never on the recipe's fields.** This is an
inference from the class hierarchy rather than a documented rule, but it is corroborated: Candidate C's
`docs.py` gates on membership in a `variable_buildings` set derived the same way, and Candidate B
carries `FGBuildableManufacturerVariablePower` as a distinct import in every version file it supports.

A further 245 recipes on fixed producers carry the harmless default `(const 0, factor 1)`. Filtering
only on "non-zero factor" would sweep all of those in too.

## 4. What was produced

Three new tables in `planning_data/game/reference/`. No existing file was modified.

    production_buildings.csv    11 rows, keyed by producer_class (Build_*_C) — the same key
                                recipe_producers.csv uses. Columns: display_name, native_class,
                                power_model, base_power_mw, power_exponent, provenance.
    recipe_variable_power.csv   43 rows, one per recipe on a variable-power producer.
                                vp_const_mw, vp_factor_mw, power_min_mw, power_max_mw, power_mean_mw.
    extraction_buildings.csv     6 rows — 3 miner tiers, Oil Extractor, Water Extractor, Resource
                                Well Extractor. P2 groundwork; free to produce, discard if unwanted.

Producer power, from the primary source:

    fixed       Constructor 4   Smelter 4    Assembler 15   Foundry 16
                Packager 10     Refinery 30  Manufacturer 55  Blender 75
    variable    Particle Accelerator   250-750 or 500-1500 depending on recipe
                Converter              100-400 on all 18 of its recipes
                Quantum Encoder        0-2000 on all 6 of its recipes

This closes the 73-recipe (25.1%) power hole. Smelter was the most consequential: it was absent from
`buildings.csv` entirely, which is why the benchmark reported Iron Plate 20/min at 9.63 MW with the
Smelter contributing nothing.

Note the Quantum Encoder's floor of 0 MW. Mean draw for those six recipes is 1000 MW, but a
minimum-power objective will see a floor of zero. Any Pareto axis on power needs to declare which
statistic it optimises — min, mean or max — before Phase 3.

## 5. Provenance reconciliation of the existing layer

Re-derived from the pinned Docs and diffed against the committed CSVs. Read-only; nothing rewritten.

    recipe_producers.csv   291 / 291 rows.  0 mismatches. 0 recipes produced in >1 factory building.
    recipes.csv            291 / 291 rows.  0 duration mismatches. 0 display_name mismatches.
    recipe_io.csv          919 / 919 rows.  0 recipes differ — every ingredient, product, per-cycle
                           amount and per-minute rate matches, fluid m3 conversion included.
    items.csv              162 rows.        0 items absent from Docs. 0 sink_points mismatches.

That is a clean bill for the solver-relevant layer. The 573 `Desc_*` classes in Docs that are absent
from `items.csv` are building and decoration descriptors — a deliberate ingest filter, not a gap.

**One open item.** My `is_alternate` check used a class-name heuristic and disagreed with the repo on
two rows:

    Recipe_PureAluminumIngot_C    repo: true    class name has no "Alternate"
    Recipe_Alternate_Turbofuel_C  repo: false   class name has "Alternate"

Docs carries no `is_alternate` field, so the heuristic is the weaker signal and the repo is probably
right on both. But the authoritative test is which schematic unlocks the recipe, and that lives in
`schematic_recipe_unlocks.csv`, which I did not reconcile. Worth confirming before Phase 3, since
alternate classification is what gates the candidate recipe set.

## 6. Adapter consequence

This does **not** add a fifth fork delta to the vendored Candidate A solver. That solver reads power as
`gameData.buildings[recipeInfo.producedIn].power`, so the adapter can synthesise one pseudo-building
per (recipe, producer) pair for variable-power producers only. 43 extra building records, one branch in
`to_solver_gamedata()`, no solver change. Fork delta F3 (extraction power hardcoding) still stands.

## 7. Side finding, not acted on

Every producer carries `mPowerConsumptionExponent = 1.321929`. Power does not scale linearly with clock
speed. The plan's section 15 policy allows underclocking and presents "2 Assemblers at 68.5% each" —
those draw `0.685 ^ 1.321929 = 0.60` of base, not 0.685. Roughly a 12% error in the wrong direction on
any underclocked build. Presentation-layer concern, flagged for whenever section 15 gets implemented.
