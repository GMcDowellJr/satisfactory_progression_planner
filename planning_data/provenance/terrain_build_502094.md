# Terrain source — Satisfactory build 502094

Generated locally from the user's installed Satisfactory 1.2.4.0 (`++FactoryGame+rel-main-anniversary-2026`, CL 502094).

Grid:
- 7500 × 7500
- 1.0 m spacing
- x0 = -3247.0 m east
- y0 = -3750.0 m game Y
- +X east, +Y south, +Z up

Coverage:
- known: 80.467%
- landscape: 45.448%
- cliff interpolated: 5.832%
- cliff direct: 15.227%
- fill: 13.960%

Validation:
- 625 static resource nodes
- median absolute error: 0.2019 m
- 90%-trimmed RMS: 0.3692 m
- p90: 1.4120 m

Important limitation:
The field is single-valued in Z. The source metadata explicitly identifies caves, arches and overhangs as the main topology failure mode. Use the raw heightfield for ordinary route scoring, but flag cave/overhang areas for later graph/mesh treatment.
