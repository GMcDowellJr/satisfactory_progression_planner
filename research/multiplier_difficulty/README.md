# Multiplier difficulty — scratch drivers (2026-10-25/26)

Provenance for `Claude outputs/multiplier-difficulty-design-2026-10-26.md`.
This is NOT tool code. These drivers break repo rules on purpose and say so
in their docstrings: they read reference CSVs directly instead of through
`gamedata`, and they widen `ReferenceData.resource_items` to add hand-supplied
pickups. They stay out of `tools/` until there's a decision and a test behind
them. Open item before promotion: record §3.3's "never priced against each
other" line against this tool's ×1/1/1 framing (design note §7).

All figures in the note came from a cloud container at master 4a32faa. Run
from a checkout with the repo path as the first argument, e.g.
`uv run python -I research/multiplier_difficulty/work_axis.py . 1.25:5:1`.

| File | What it measures | Note section |
|---|---|---|
| `lab_rounding_check.py` | Reproduces the external lab's ceil-rounding defect | above the fold |
| `multiplier_ratios.py` | Per-phase anchor ratios, machines / MW / raw | §5 |
| `milestone_load.py` | Milestone vs PA machine-minutes; serial E multiplier | §5.1 |
| `mam_bill.py` | MAM placement by earliest-producible phase; MAM bill | §5.3 |
| `power_axis.py` | Energy demand; net MW per generator; parasitic load | §5.5 |
| `work_axis.py` | Full work multiplier with extractors and power plant | §5.6 |
| `work_axis_output.txt` | Output of `work_axis.py` for the §5.6 scenarios | §5.6 |
| `card_numbers.py` | Factory-only figures for the mock-up cards | §5.7 |
| `common_baseline.py` | Everything × the 1/1/1 factory before power (D26) | §5.7 |
| `grid.py` | The R×P grid (48 pairs × 5 phases) → `grid.json` | §5.8 |
| `biomass_routes.py` | Patches `grid.json` with the D30 gathering-mix biomass routes | §5.9 |
| `grid.json` | The page's data: `grid.py` output, patched by `biomass_routes.py` | §5.8–5.9 |
| `node_ceiling.py` | Node ceiling k on the default world (and all-normal); sole-source power | §5.10 |
| `node_ceiling.json`, `node_ceiling_all_normal.json` | `node_ceiling.py --grid` output (k per cell) | §5.10 |
| `mockup_page.dc.html` | Source of the design-canvas mock-up (phone, R/P/E selector), `grid.json` embedded | §5.7–5.9 |

The scripts chain by exec: `power_axis` loads `mam_bill`, `work_axis` loads
`power_axis`, and `card_numbers`, `common_baseline`, `grid` and `node_ceiling` load
`work_axis`. Keep them in one folder.
