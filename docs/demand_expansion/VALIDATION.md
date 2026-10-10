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
multiplier doubles every cell. Phase aggregation is PR 4; the test pins the
three products directly.

## Table 3 — Thermal Propulsion Rocket resources, per rocket

Fully expanded under the default table. First measured in the plan review
with a scratch script that double-counted resources (every figure there was
2x these); corrected 2026-10-10 against the engine and the oracle.

| Variant | Nitrogen Gas | Water | Crude Oil | Iron Ore |
|---|---|---|---|---|
| 1x | 200 | 324.5 | 209.25 | 669.75 |
| 1.25x, m3 | 403 | 2,129.42 | 880.5 | 2,462.69 |
| 1.25x, mL | 406.25 | 2,087.5 | 825.47 | 2,462.69 |
| 1.25x, none | 406.25 | 2,087.5 | 825.47 | 2,462.69 |

Solids agree across variants; Crude Oil differs by 6.7%. mL and none
coincide because no fluid count on this chain has a fractional millilitre
after scaling.

## Table 4 — Smart Plating, the Phase 0 reconciliation

Per unit at 1x: 23.25 Iron Ore. Recipe cycles per unit: Iron Ingot 23.25,
Iron Rod 14.25, Screw 9.25, Iron Plate 3, Reinforced Iron Plate 1, Rotor 1,
Smart Plating 1. These equal the oracle's machine equivalents at 1/min
times each recipe's cycles per minute, and the oracle's 23.25 raw ore.

## Structure

- Plastic per unit: direct 1.5 Crude Oil; coproduct 0.5 Heavy Oil Residue,
  reported and absent from `embedded`.
- Turbofuel is unproducible under the default table: its only base-flagged
  recipe is the `is_alternate` defect the table excludes.
- Biochemical Sculptor and AI Expansion Server refuse on Ficsite Ingot
  (three enabled Converter recipes, no pin), naming the path.
