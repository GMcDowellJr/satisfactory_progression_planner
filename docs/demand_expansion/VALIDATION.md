# Demand expansion — validation fixtures

Independently derived, 2026-10-10, before the engine existed: by hand from
`recipe_io.csv` and by three scratch scripts over the CSVs using exact
rationals (plan review, `Claude outputs/material-demand-plan-review-2026-10-10-1940.md`).
`tools/demand_expansion/tests/test_demand_expansion_expand.py` pins them;
`tests/test_demand_expansion_oracle_check.py` checks the engine against
`tests/_demand_oracle.py` on the chains the oracle resolves. Build 502094,
`game_builds.csv` docs_a81d250e96aa. Route table `default-2026-10-10`.

## The chain

    Modular Engine             2 Motor + 15 Rubber + 2 Smart Plating          -> 1
    Turbo Motor                4 Cooling System + 2 Radio Control Unit
                               + 4 Motor + 24 Rubber                          -> 1
    Thermal Propulsion Rocket  5 Modular Engine + 2 Turbo Motor
                               + 6 Cooling System + 2 Fused Modular Frame     -> 2
    Ballistic Warp Drive       1 Thermal Propulsion Rocket + ...              -> 1

Nothing else on the delivery list contains a Motor under default routes.
Motor's own subtree (Rotor, Stator, Steel Pipe, Wire, ...) has no ambiguity,
and the ambiguous items on these chains (Plastic, Rubber) sit beside Motor,
not above it.

## Table 1 — Motors embedded per unit of target

Recipe multiplier per cycle, per input, nearest integer, half away from zero.

| Target | 1x | 1.25x | 1.5x | 2x |
|---|---|---|---|---|
| Modular Engine | 2 | 3 | 3 | 4 |
| Thermal Propulsion Rocket | 9 | 16.5 | 21 | 36 |
| Ballistic Warp Drive | 9 | 16.5 | 42 | 72 |

1.25x working: ME needs round(2.5)=3 Motor. TPR needs round(6.25)=6 ME and
round(2.5)=3 Turbo Motor per 2 rockets; Turbo Motor needs round(5)=5 Motor;
(6×3 + 3×5)/2 = 16.5. Both ties rest on the Cable 2.5 → 3 read (crossover
A1, 2026-09-21). At 1.5x the Warp Drive doubles because its own TPR input
rounds 1.5 → 2. The Motor coefficient is identical under all three fluid
variants.

## Table 2 — Motors embedded per phase, 1x deliveries, incremental

| Phase | Delivery carrying Motors | Motors at 1x | at recipe 1.25x | growth (1x) |
|---|---|---|---|---|
| 1 | none | 0 | 0 | n/a |
| 2 | none | 0 | 0 | n/a |
| 3 | 500 Modular Engine | 1,000 | 1,500 | new demand |
| 4 | 250 Thermal Propulsion Rocket | 2,250 | 4,125 | 2.25x |
| 5 | 200 Ballistic Warp Drive | 1,800 | 3,300 | 0.80x |

Lifetime at 1x 5,050; remaining after phase 3, 4,050. A 2x Project Assembly
multiplier doubles every cell. Pinned by `test_demand_expansion_aggregate.py`
through `aggregate`, which also marks phase 5 incomplete: Biochemical
Sculptor and AI Expansion Server refuse on Ficsite Ingot, so every sum that
includes phase 5 is a lower bound.

## Table 2a — the self-count rule, Modular Engine and Smart Plating

| Phase | Modular Engine | Smart Plating |
|---|---|---|
| 1 | 0 | 50 (delivered) |
| 2 | 0 | 1,000 (delivered) |
| 3 | 500 (delivered) | 1,000 (2 per Modular Engine) |
| 4 | 625 (2.5 per rocket) | 1,250 (5 per rocket) |
| 5 | 500 (2.5 per warp drive) | 1,000 (5 per warp drive) |

At a 0.25x Project Assembly multiplier phase 1's 50 Smart Plating is 13
(12.5 → 13, observed 2026-09-22) and the series is 13 / 250 / 250 / 315 /
250. Under the scenario of record's shape (1.25x recipes, 2x deliveries)
Motors are 0 / 0 / 3,000 / 8,250 / 6,600.

## Table 3 — Thermal Propulsion Rocket resources, per rocket

Fully expanded under the default table. First measured in the plan review
with a scratch script that double-counted resources (every figure there was
2x these); corrected 2026-10-10 against the engine and the oracle.

| Variant | Nitrogen Gas | Water | Crude Oil | Iron Ore |
|---|---|---|---|---|
| 1x | 200 | 324.5 | 209.25 | 669.75 |
| 1.25x, mL (observed rule, default) | 406.25 | 2,087.5 | 825.47 | 2,462.69 |
| 1.25x, none (identical on this build) | 406.25 | 2,087.5 | 825.47 | 2,462.69 |
| 1.25x, m3 (ruled out 2026-10-10) | 403 | 2,129.42 | 880.5 | 2,462.69 |

Solids agree across variants; Crude Oil differs by 6.7%. mL and none
coincide because every fluid count is a multiple of 0.5 m3 and every
multiplier of 0.25, so no scaled fluid has a fractional millilitre.

## Table 3a — the read that settled it

Greg, 2026-10-10, 1.25x save, game 1.2.4.0 CL#502094, Plastic recipe:
3.75 Crude Oil per cycle (3 at 1x), 20 Plastic and 10 Heavy Oil Residue per
minute, unchanged. 3.75 is what mL and none predict; m3 predicted 4. The
outputs confirm the yield does not scale. Per unit of Plastic: 1.875 Crude
Oil, 0.5 HOR coproduct, half a cycle.

## Table 4 — Smart Plating, the Phase 0 reconciliation

Per unit at 1x: 23.25 Iron Ore. Recipe cycles per unit: Iron Ingot 23.25,
Iron Rod 14.25, Screw 9.25, Iron Plate 3, Reinforced Iron Plate 1, Rotor 1,
Smart Plating 1. These equal the oracle's machine equivalents at 1/min
times each recipe's cycles per minute, and the oracle's 23.25 raw ore.

## Reference outputs

`python tools/demand_expansion_cli.py generate` at 1x on this build: 119
targets in scope, 804 coefficient rows, 74 items × 5 phases in dataset B
(the two refused deliveries count as themselves), phase 5 incomplete, 44
unresolved rows;
unresolved lists the two refused deliveries and every in-scope target that
reaches an unpinned item. Two runs produce byte-identical CSVs and report.

## Table 5 — alternate sensitivity, hand-derived

Steeled Frame (`Recipe_Alternate_ModularFrame_C`, T4): 2 Reinforced Iron
Plate + 10 Steel Pipe → 3 Modular Frame, against the default 3 RIP + 12 Iron
Rod → 2. A RIP is 12 Iron Ingot (6 plates at 1.5, 12 screws at 0.25); a
Steel Pipe is 1.5 Steel Ingot, each 1 Iron Ore + 1 Coal.

| Source → Modular Frame | Default | Steeled Frame | Change |
|---|---|---|---|
| Iron Ore | 24 | 13 | 0.542x |
| Iron Ingot | 24 | 8 | 0.333x |
| Coal | 0 | 5 | new |
| Iron Rod | 21/2 | 2 | 0.190x (the RIPs still take screws) |
| Steel Pipe | 0 | 10/3 | new |

Iron Wire (`Recipe_Alternate_Wire_1_C`, T1): 5 Iron Ingot → 9 Wire against
1 Copper Ingot → 2. Cable takes 2 Wire: Copper Ore 1 → 0 (removed), Iron Ore
0 → 10/9 (new).

Sweep on this build at 1x: 110 alternates, 6,187 changed pairs, 5
inapplicable by name (Automated Miner: unlisted output; Charcoal, Biocoal:
make Coal; Recycled Plastic, Recycled Rubber: conflict with the base pins).
Heavy Oil Residue has no primary producer under the default table, so
"Alternate: Heavy Oil Residue" newly resolves 4 targets and "Alternate:
Tempered Caterium Ingot" (through Petroleum Coke) newly refuses 9.

## Structure

- Plastic per unit: direct 1.5 Crude Oil; coproduct 0.5 Heavy Oil Residue,
  reported and absent from `embedded`.
- Turbofuel is unproducible under the default table: its only base-flagged
  recipe is the `is_alternate` defect the table excludes.
- Biochemical Sculptor and AI Expansion Server refuse on Ficsite Ingot
  (three enabled Converter recipes, no pin), naming the path.
