"""Comparison-lab defect reproduction — scratch, 2026-10-25. NOT repo code.

The external "Multiplier Comparison Lab" (satisfactory_multiplier_comparison_lab.html,
2026-10-10 payload) reported phase-1 iron at R=1.25 as 13.247x the R=1 figure.
This hand-expands Smart Plating (default recipes) under two rounding rules.
CEIL reproduces the lab at all seven R values; nearest-half-away-from-zero with
floor 1 (the in-game-observed rule) gives 1.441x at R=1.25. The lab is wrong.
"""
import math


def ore_per_smart_plating(rnd, r: float) -> float:
    q = lambda n: max(1, rnd(n * r))
    ingot = q(1)                    # 1 ore -> 1 ingot
    rod = q(1) * ingot              # 1 ingot -> 1 rod
    screw = q(1) * rod / 4          # 1 rod -> 4 screws
    plate = q(3) * ingot / 2        # 3 ingot -> 2 plate
    rip = q(6) * plate + q(12) * screw
    rotor = q(5) * rod + q(25) * screw
    return q(1) * rip + q(1) * rotor


nearest = lambda x: math.floor(x + 0.5)   # half away from zero for x >= 0
lab = {0.25: 0.237, 0.5: 0.462, 0.75: 0.796, 1.25: 13.247, 1.5: 16.258, 1.75: 19.957, 2: 22.366}
b = ore_per_smart_plating(nearest, 1)
for r, v in lab.items():
    print(f"R{r}: lab {v}  ceil {ore_per_smart_plating(math.ceil, r)/b:.3f}  "
          f"nearest {ore_per_smart_plating(nearest, r)/b:.3f}")
