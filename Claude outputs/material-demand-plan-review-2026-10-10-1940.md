# Material-demand plan (Proposed v1, 2026-10-10) checked against the repository

Design note. Current-state; may be corrected in place. Written against HEAD
`2dc60c3` (master), container, 2026-10-10 19:40 UTC. Suite on this checkout:
**Container: 986 passed, 1 skipped** (`uv run pytest -q`, 9.2 s).

No code was written and nothing was committed. The plan's section 10 lists
decisions to lock first, and several of them are Greg's (AGENTS.md: Greg makes
decisions). This note is the PR 1 "repository assessment and data audit" done for
real, so those decisions can be made on measured facts.

## 1. Verdict in four lines

1. The plan is sound and the repo already carries most of its spec. The proposed
   `tools/material_demand/` is the **LP record §11 "demand expansion" shared
   module** whose name and location are an open item (LP §11.5). Build it as that
   module, under that record's constraints, and the open item closes.
2. One premise is false as written: "one canonical default recipe per item."
   29 items have more than one `is_alternate=false` producer. The record already
   knows this (demand-expansion §3.1.1, §3.1.2, LP §14.5) and locked a curated
   set plus a rule that route pins are **a decision to record, not a derivation**.
3. The Motor question is answerable today, exactly, and independently of every
   open ambiguity: see §4. Those figures are the PR 1 fixtures.
4. The fluid-rounding question the plan says to "retain" is not academic for the
   Thermal Propulsion Rocket: Crude Oil per rocket at 1.25x moves 6.7% between the
   two candidate rules. It needs a declared input, and it can be settled by one
   in-game read (§6, decision C).

## 2. Plan claims, checked

| Plan says | Measured | Standing |
|---|---|---|
| `recipes.csv`, `recipe_io.csv`, `items.csv`, `project_assembly_requirements.csv`, unlock tables exist and are reusable | All present. 291 recipes (181 base, 110 alternate), 920 io rows with `amount_per_cycle` and `unit`, 162 items (13 resources), 15 delivery rows | Holds |
| `scenario.py` rounds per cycle, per input, and that matters | True. Nearest integer, half away from zero, per input (record 3.2.5), observed in game both directions (3.2.4). The **tie case is also observed**: 2.5 → 3 on Cable, 7.5 → 8 on RIP (crossover record Amendment 1, 2026-09-21) | Holds. Note `scenario.py` line 45 still says the tie "is unobserved" — stale docstring, one-line fix |
| Fluid rounding is uncertain and should be kept uncertain | True. `scenario.FLUID_ROUNDING_UNIT` names three variants (m3 / mL / none); the code default is `"m3"`. Unobserved in game. Material for TPR (§5) | Holds, and bites |
| Default mode = one canonical default recipe per item | **False.** 29 items have >1 base producer. Causes: 9 Converter ore-conversion recipes, 12 Unpackage recipes, byproduct outputs (Water from Battery, Dark Matter Residue from six recipes, Heavy Oil Residue from Plastic/Rubber, Silica from Alumina Solution...), and genuine base-vs-base choices (Plastic/Residual Plastic, Rubber/Residual Rubber, Fuel/Residual Fuel, three Ficsite Ingot routes, four Power Shard routes, four Biomass, four Alien Protein) | Needs a declared route table (decision B) |
| Cycles: detect and fail | Under "every base recipe is a producer of every output" the base graph has 3 strongly connected components, one of 52 items spanning the whole oil/aluminium/packaging tier. Under primary-output-only plus no Unpackage plus resources-are-leaves: **0 cycles**, 8 ambiguous items remain (Alien Protein, Biomass, Ficsite Ingot, Fuel, Plastic, Power Shard, Rubber, and the duplicated Turbo Rifle Ammo) | The rules remove the cycles; the plan's "solve closed loops with a linear system" is not needed in v1 if byproducts are not producers |
| Coproducts: keep them, don't assume free | Agreed and already decided: record 3.1.2 calls byproduct feedback "known-invalid" for the oracle. With byproducts as producers, Plastic "contains" Motor through a 10-step chain of alternates and byproducts (Plastic ← Crude Oil ← Unpackage Oil ← ... ← Dark Matter Residue ← Neural-Quantum Processor ← OC Supercomputer ← Cooling Device ← Motor). That is the shape of nonsense a naïve graph produces | Primary-output rule; report coproducts in a separate column, never netted (decision G) |
| Test oracle must be independent of production code | The repo already has this pattern: `tests/_demand_oracle.py` (rates, base recipes, raises `AmbiguousDemand`, deliberately crippled) and `busmodel` (reproduces published tables). The oracle raises on every Space Elevator part from Modular Engine up, on Plastic or Rubber | Holds; keep the oracle as the check, build the engine as the thing checked |
| New package depends on canonical facts and its own models only | Matches LP §11.1 (imports `production_adapter.contracts` for types; adapter never imports it) and the `progression` precedent (contracts, gamedata, scenario permitted; backend, lp_backend, analysis, scipy forbidden). Boundary must be an AST test like `tests/test_progression_import_boundary.py` | Holds, with the constraint named |
| `reference.py` as a "canonical data adapter" | **Must not read CSVs.** One-loader rule: only `gamedata.py` knows filenames and columns. `gamedata.load()` returns per-cycle input amounts with units; outputs only as per-minute rates (per-cycle output = rate ÷ cycles_per_min, exact for these durations). `load()` does **not** read the Project Assembly or unlock tables; `progression/stock.py`, `unlocks.py`, `pool.py` read those directly today, each with a documented refusal | Decision D: extend gamedata or follow the progression carve-out |
| "Every automatable item" | 17 item ids appear in `recipe_io.csv` and not in `items.csv` (rifle ammo, nobelisks, rebar, fireworks, Portable Miner). 25 non-resource items have no base recipe (slugs, remains, leaves, wood, mycelia, FICSMAS, waste, Somersloop, Mercer Sphere, Parachute, Medicinal Inhaler, Dissolved Silica). `gamedata.load()` tolerates all of this silently | Decision F: classification rule |
| Unlock awareness | `schematic_recipe_unlocks.csv` covers all 291 recipes (every base and every alternate has a row). `alternate_choices.csv` covers 107 of 110 alternates (missing: Compacted Coal, Distilled Silica, Polyester Fabric). `alternate_recipe_unlocks.csv` is slug-keyed (`cast_screws`) and does not join to recipe ids; `pool.py` already says so | Use `schematic_recipe_unlocks.csv` through `progression.unlocks.at_tier` or a gamedata loader; don't touch the slug table |
| Phase table keyed by name | True, `item_name` only. All 15 rows resolve to exactly one item (measured again today). `progression.stock.load_project_assembly` already does the refusing join | Reuse the pattern (import rule permitting) |
| Recipe display names are unique | **No.** "Turbo Rifle Ammo" names two recipe ids | Key everything on ids; the storage review's warning stands |
| Power multiplier excluded from material calculation | Consistent with record 3.3 ("power is not material at all") | Holds |
| No optimisation score across alternates | Consistent with record §5.5 ("alternates are reported, never ordered") and LP §16.2 (alternate value is set-valued) | Holds; the single-substitution mode is exactly what §5.5 admits |

## 3. Where the plan collides with repo rules it doesn't mention

- **Manifests.** `tools/` and `docs/` are already in `REPO_MANIFEST.csv` scope, so a
  new `tools/material_demand/` and `docs/material_demand/` need no scope change, but
  every content commit needs its `Regenerate manifests` follow-up.
- **Writers pin LF.** `export.py` falls under `tests/test_writers_emit_lf.py`:
  `lineterminator="\n"`, `newline="\n"`, no defaults.
- **Test collection.** `tools/material_demand/tests` must be added to `testpaths`
  in `pyproject.toml` and needs its own conftest that does not rely on
  `tests/conftest.py`. The six basenames the plan proposes (`test_reference`,
  `test_expansion`, `test_alternates`, `test_scenarios`, `test_progression`,
  `test_cycles`) collide with nothing today. `test_progression.py` is one typo
  away from the `test_progression_*.py` family in `tests/`; a package prefix
  (`test_material_demand_*.py`) is safer.
- **Layers report; they don't choose.** The engine must raise a named error on an
  item with zero or several enabled recipes, exactly as the oracle does. "Pick
  the recipe named after the item" is a choice; it may be the *declared* default
  route table's rule, but the table is the decision, not the code.
- **No new runtime dependency.** Fractions and Decimal suffice; the figures in §4
  were computed with `fractions.Fraction`, no scipy.

## 4. The Motor fixtures, independently derived (PR 1 deliverable)

Default routes, build 502094, computed from `recipe_io.csv` with exact rational
arithmetic in a scratch script (not production code). Hand check of the chain:
Modular Engine = 2 Motor + 15 Rubber + 2 Smart Plating → 1. Thermal Propulsion
Rocket = 5 Modular Engine + 2 Turbo Motor + 6 Cooling System + 2 Fused Modular
Frame → **2**. Turbo Motor = 4 Cooling System + 2 Radio Control Unit + 4 Motor +
24 Rubber → 1. Ballistic Warp Drive carries 1 TPR. Nothing else on the elevator
list contains a Motor under default routes, and Motor's own subtree (Rotor,
Stator, Steel Pipe, Wire, ...) has no ambiguity.

The coefficient is robust to every open route question: the ambiguous items
(Plastic, Rubber, Silica, Ficsite Ingot) sit *beside* Motor in these recipes,
never above it, except via the alternate-plus-byproduct chain in §2, which no
declared configuration will enable.

Motors embedded per unit of target. Recipe multiplier applied per cycle, per
input, nearest integer, half away from zero (the observed rule):

| Target | 1x | 1.25x | 1.5x | 2x |
|---|---|---|---|---|
| Modular Engine | 2 | 3 | 3 | 4 |
| Thermal Propulsion Rocket | 9 | 16.5 | 21 | 36 |
| Ballistic Warp Drive | 9 | 16.5 | 42 | 72 |

Working at 1.25x: ME needs round(2.5)=3 Motor. TPR needs round(6.25)=6 ME and
round(2.5)=3 Turbo Motor per 2 rockets; Turbo Motor needs round(5)=5 Motor. So
(6×3 + 3×5)/2 = 16.5. Two of those four roundings are ties; both rest on the
Cable 2.5 → 3 read of 2026-09-21. At 1.5x the Warp Drive doubles because its
own TPR input rounds 1.5 → 2.

Motors embedded per phase, 1x deliveries, incremental (not cumulative):

| Phase | Delivery carrying Motors | Motors at 1x | at recipe 1.25x | growth vs previous (1x) |
|---|---|---|---|---|
| 1 | none | 0 | 0 | n/a |
| 2 | none | 0 | 0 | n/a |
| 3 | 500 Modular Engine | 1,000 | 1,500 | new demand |
| 4 | 250 Thermal Propulsion Rocket | 2,250 | 4,125 | 2.25x |
| 5 | 200 Ballistic Warp Drive | 1,800 | 3,300 | 0.80x |

Lifetime at 1x: 5,050 Motors; remaining-future after phase 3: 4,050. A 2x Project
Assembly multiplier doubles every cell (12.5 → 13 observed, no fraction arises on
these rows). Whether the engine or the scheduler applies that multiplier is LP
§11.5's open item (decision E).

These are the numbers the plan's test cases "Motor → Modular Engine", "Motor →
Thermal Propulsion Rocket" and "same chain at 1x and 1.25x" should pin. They were
derived here by hand and by a 60-line scratch script; the engine must reproduce
them, not the other way round.

## 5. Fluid rounding on the rocket chain, measured

TPR fully expanded to resources at recipe 1.25x, routes pinned to
`Recipe_Plastic_C` and `Recipe_Rubber_C`, Unpackage excluded, byproducts not
producers. Per rocket:

| Fluid rounding variant | Nitrogen Gas | Water | Crude Oil | Iron Ore |
|---|---|---|---|---|
| `m3` (current code default) | 403.0 | 2,129.4 | 880.5 | 2,462.7 |
| `mL` | 406.25 | 2,087.5 | 825.5 | 2,462.7 |
| none | 406.25 | 2,087.5 | 825.5 | 2,462.7 |
| (1x reference) | 200.0 | 324.5 | 209.25 | 669.75 |

*Corrected 2026-10-10, same day: the first version of this table was 2x on
every cell. The scratch script added each resource twice (once as an input,
once at the leaf). Found when the engine and `_demand_oracle` agreed with each
other and not with it. The ratios, and every Motor figure in §4, were never
affected.*

Solids agree; Crude Oil differs by 6.7% and Water by 2% between the two
candidate rules. Record 3.2.3's "immaterial" finding was for Modular Frame, which
has no fluid on its path. For any oil-tier target the variant must be declared
input, not a module constant, and reports should carry it in their provenance.

The decisive in-game read is one recipe: on the 1.25x save, Plastic (3 m3 Crude
Oil per cycle at 1x) shows **4** under m3-rounding and **3.75** under
mL-rounding. Rubber (3 m3) is the same probe.

## 6. Decisions for Greg before PR 1

A. **Name and placement.** `tools/material_demand/` versus a name matching the
   records (`demand_expansion`). Either closes LP §11.5. Recommend
   `tools/demand_expansion/` so the records, the oracle's docstring and the
   package agree on one term; the plan's "material demand" becomes the report
   name.

B. **The default route table.** Adopt record 3.1.1's curated set (181 − 12
   Unpackage − 9 Converter ore recipes − 3 `is_alternate` defects = 159) plus
   explicit pins for the structural residue: Plastic → `Recipe_Plastic_C`,
   Rubber → `Recipe_Rubber_C`, Silica → `Recipe_Silica_C`, Ficsite Ingot →
   one of three (no default exists; LP §14.5), Compacted Coal and Power Shard
   per 3.1.2. Recorded as a decision, carried as a declared data file the engine
   loads, refused when absent. Note the Converter also produces Ficsite Ingot,
   Dark Matter Residue, Time Crystal and Excited Photonic Matter as base recipes;
   3.1.1 excludes only the 9 ore conversions, not all 23 Converter base recipes.

C. **Fluid rounding.** Make the variant a declared scenario input (the three
   values `scenario.py` already names), default none until observed; and do the
   Plastic read in §5 on the 1.25x save, which settles it.

D. **Loader placement.** Either add `load_project_assembly` / `load_unlocks` to
   `gamedata.py` (one-loader rule, strict) or let the new package follow the
   `progression` carve-out (reads those three tables itself with named
   refusals). Recommend extending `gamedata.py`: two consumers now exist.

E. **Project Assembly multiplier.** Apply in phase aggregation (it scales an
   expansion output) and report it as its own column, separate from the recipe
   multiplier, per record 3.3's non-commensurability. This also answers LP §11.5.

F. **Item classification.** Define "automatable item" by rule: has at least one
   base recipe in the curated set, is listed in `items.csv`, and is not a
   resource. That excludes the 17 unlisted consumables and the 25 collectible or
   waste items by name in a coverage report, not by silence.

G. **Coproducts.** v1 rule: a recipe produces only its primary output for
   expansion purposes; coproduct quantities are reported alongside, never netted
   against demand. The closed-loop linear solve in the plan's §6 is deferred
   until a declared configuration actually needs it (none of the 15 delivery
   rows does under B).

H. **This note.** Gitignored by convention. `git add -f` if it should be on the
   record; otherwise it stays local to this session's checkout.

## 7. What PR 1 then contains

- `docs/material_demand/SPECIFICATION.md`: the four metrics, the primary-output
  rule, the route-table contract, refusal conditions, provenance fields
  (game build id, route-table hash, scenario triple, fluid variant).
- The route table as data, with each pin's reason (B).
- A coverage test that pins today's census: 291/181/110 recipes, 29 multi-producer
  items before curation, 8 after, 0 cycles after, 17 unlisted ids, 25 no-recipe
  items, 15 delivery rows resolving uniquely. The test deletes itself when the
  data changes, like the existing data-gap tests.
- The §4 fixtures as an independent table in `VALIDATION.md`, cited by the PR 2
  tests.
- The package skeleton with its AST boundary test, conftest, `testpaths` entry,
  and nothing that computes.
- The one-line `scenario.py` docstring fix (tie case observed, crossover A1).

## 8. Method

Figures were produced by three scratch scripts in the session scratchpad
(`audit.py`, `audit2.py`, `fluid.py`), reading the reference CSVs directly with
`fractions.Fraction` and `decimal.Decimal`, run with `python -I` on this
checkout. They are scratch, not tools, and are not in the repo. Every count above
was read from their output, not predicted.
