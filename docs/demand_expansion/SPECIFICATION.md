# Demand expansion — specification

The contract for `tools/demand_expansion/`. Decided by Greg, 2026-10-10
(`docs/decisions/demand_expansion_scope_and_site_capacity.md`, Amendment 1),
on the plan review of the same date. The package is the LP record §11 shared
module; §11.3's drift line binds it:

    does       expand a declared target into item quantities, per unit
    does not   choose a recipe, choose a scope, sequence, prioritise, or rate

## 1. The four metrics

| Metric | Definition | Where |
|---|---|---|
| Direct coefficient | units of A consumed by B's own recipe, per unit of B, after scenario rounding | `Expansion.direct` |
| Embedded coefficient | units of A on every path below one unit of B, summed; kept for **every** intermediate part and every resource | `Expansion.embedded` |
| Phase requirement | embedded coefficient × a Project Assembly delivery quantity, summed per phase | PR 4 (not built) |
| Growth factor | a later phase requirement ÷ an earlier one; "new demand" when the earlier is zero; n/a when both are | PR 4 (not built) |

Quantities are exact rationals (`fractions.Fraction`). There is no time in the
module: no rates, no horizon, no machine count. `recipe_cycles` reports cycles
per unit of target so a consumer with a horizon can derive machines.

## 2. The three structural rules

These follow from what the data is and live in `graph.build`. They are not
declarations and carry no reason field, because they are not choices.

1. **Primary output.** A recipe produces, for expansion, only the output the
   game lists first. Every other output is a coproduct: reported in
   `Expansion.coproducts`, never netted against demand, never a producer.
   On this build, wherever a recipe's display name names one of its outputs,
   that output is first (`Census.name_match_is_first_output`), so "first" is
   the data's ordering and not a second reading.
2. **Resource leaf.** A resource (`items.csv` category `resource`) is never
   expanded, and no recipe whose primary output is a resource is enabled.
   This is record 3.1.1's Converter exclusion as a rule: 20 base recipes on
   this build, 17 ore conversions and the 3 Unpackage reversals of Water,
   Oil and Nitrogen.
3. **Alternates off.** `is_alternate=true` recipes are never enabled by this
   module. A run that holds one pins it, which is a recorded choice.

## 3. Declarations: the route table

Everything that is a choice is a `RouteTable`: named exclusions of base
recipes and pins of one recipe for an item that has several, each with a
reason. `declarations.DEFAULT_ROUTES` (`default-2026-10-10`) carries:

- the 12 Unpackage recipes (record 3.1.1: reversals, not routes);
- the 2 remaining `is_alternate` defects (record 3.1.1; the third is an
  Unpackage recipe and is carried once);
- pins: Plastic → `Recipe_Plastic_C`, Rubber → `Recipe_Rubber_C` (LP §14.5).

A stale declaration is refused by `graph.build`: an exclusion naming a
missing or alternate-flagged recipe, a pin that resolves nothing (Silica,
under rule 1), a pin naming a recipe that is not an enabled candidate.
Unpinned residue on this build: Alien Protein, Biomass, Ficsite Ingot, Fuel,
Power Shard, Turbo Rifle Ammo. A target that reaches one is refused by name
(`AmbiguousRoute`, with the path). Biochemical Sculptor and AI Expansion
Server reach Ficsite Ingot; the other thirteen delivery rows expand.

## 4. Scenario

`Scenario.recipe_input_multiplier` is applied by `ReferenceData.with_scenario`
to per-cycle input counts, nearest integer, half away from zero, per input
(record 3.2.5; observed in game including ties, crossover A1). Outputs never
scale. Rounding happens before the division by the output count, so the
multiplier compounds unevenly through a chain.

**Fluid rounding: observed, 2026-10-10 (Amendment 2).** The Plastic recipe on
a 1.25x save shows 3.75 Crude Oil per cycle, so fluids are not rounded to
whole m3. The default is `"mL"`; `None` cannot differ from it on this build
(every fluid count is a multiple of 0.5 m3, every multiplier of 0.25); `"m3"`
is selectable only to reproduce figures computed before the read, and
overstated Crude Oil per Thermal Propulsion Rocket at 1.25x by 6.7%. Until
the read the engine refused a non-1x multiplier without a declaration
(Amendment 1); `FluidRoundingUndeclared` now fires only on an unknown value.

The Project Assembly multiplier is not applied here. It scales delivery
quantities and belongs to phase aggregation (PR 4), reported as its own
column; power multipliers are not material (record 3.3).

## 5. Refusals

| Error | When |
|---|---|
| `AmbiguousRoute` | an item on the path has several enabled producers and no pin |
| `UnproducibleItem` | a non-resource item on the path has no enabled producer |
| `CycleDetected` | the chosen routes loop (impossible under the default table; a pin set could do it) |
| `FluidRoundingUndeclared` | `fluid_rounding` is not `"mL"`, `None` or `"m3"` |
| `NotExpandable` | the target is a resource |
| `DeclarationError` | a stale or malformed route table |

## 6. Provenance of a result

An `Expansion` carries the target, the route table's name, the recipe
multiplier and the fluid variant. The game build is the `ReferenceData`'s
`game_build_id`. A reference-output writer (PR 5) adds the route table's
content hash and the build's sha256 from `game_builds.csv`.

## 7. Coverage: what "automatable item" means here

An item is in scope when it is listed in `items.csv`, is not a resource, and
has at least one enabled recipe under the route table in force. The census
names the rest rather than silently dropping it: 17 ids used by recipes that
`items.csv` does not list (ammunition, nobelisks, rebar, fireworks, the
Portable Miner) and 25 listed items no base recipe makes (collectibles,
creature remains, slugs, FICSMAS, nuclear waste, Dissolved Silica).

## 8. Boundaries

Imports `production_adapter.contracts`, `.gamedata`, `.scenario` only; never
`progression`, `realization`, `busmodel`, `scipy`, `csv`; opens no file.
`tools/demand_expansion/tests/test_demand_expansion_import_boundary.py`
asserts this from both sides. `progression` may import this package.

## 9. Not in v1

Phase aggregation and growth factors (PR 4), reference outputs and a CLI
(PR 5), alternate sensitivity (PR 3: a `RouteTable` with an alternate pinned
is the mechanism, once rule 3 admits a declared alternate), closed-loop
material balance, any optimisation.
