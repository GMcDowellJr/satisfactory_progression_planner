# PA walk-back step planner — scratch drivers (2026-10-27 to 2026-10-31)

Provenance copy of the Project Assembly walk-back "step planner" from the
claude.ai Project "Satisfactory", folder
`progression-optimizer/pa-walkback-2026-10-27/`. It is kept here because it
will be joined to the neighbourhood site locations later.

What it does: it walks the five PA phases back into a phase → step schedule
(required milestones by dependency level, then extras, then the PA run). It
runs a minute-by-minute stockpile sim over that schedule (installed capacity,
raw draw per step), adds a power block (biomass → coal → fuel, carried
forward), and from that produces the per-step raw draws for the site view
(`site_data.json`) and the per-phase node defaults with a world-supply
ceiling (`node_defaults.json`). The alternate-recipe drivers (`model3a`,
`model3b`, `relief`, `alt_run`, `place`, `plan2`) pick per-phase alternate
plans on top of it.

This is NOT tool code. The drivers break repo rules on purpose and stay out of
`tools/` until there is a decision and a test behind them:

- They **read the reference CSVs directly** (`planning_data/game/reference/*.csv`,
  the world `resource_assignments.csv` and the docs snapshot) instead of going
  through `production_adapter.gamedata` (AGENTS.md, "One loader").
- **Hardcoded tier tables**: `nodes.py` copies world node counts, miner, belt,
  pipe, oil and well rates into literals. `model2.py` hardcodes `BELT`, `PIPE`
  and `MINER`, and `run2.py` hardcodes the generator mix and plant figures.
- **Flat sibling imports**: modules import each other by bare name
  (`import model2 as M`, `import run2`) and several run work on import.
  `run2` writes `milestones_tagged.csv` when it is imported. Each file puts its
  own folder on `sys.path` so that `python -I` works (see the edits table).
  Keep them in one folder.
- They make choices the tool layers refuse to make (`min`/`max`/`sorted`
  ranking, defaults such as `STRETCH = {4: 1.25, 5: 1.25}`, `BIND_MIN = 0.10`).
  The dated comments in the files say who decided each one.

Run from a checkout. The repo root is found from the script's own location
(`research/step_planner/` is two levels under it), so the trailing `.` follows
the folder convention and the scripts don't read it. Every output goes into
this folder.

    uv run python -I research/step_planner/model3.py .        # steps_{all,required}.{json,csv}
    uv run python -I research/step_planner/site_data.py .     # site_data.json   (~3 s)
    uv run python -I research/step_planner/nodes.py .         # node_defaults.json
    uv run python -I research/step_planner/relief.py .        # relief.json
    uv run python -I research/step_planner/alt_run.py .       # steps_all_alts.json, alt_plan.json
    uv run python -I research/step_planner/plan2.py .         # plan2.json, plan2_raw.json
    uv run python -I research/step_planner/ppm.py .           # stdout only
    uv run python -I research/step_planner/cap.py .           # stdout only
    uv run python -I research/step_planner/alt_deps.py .      # alt_deps.json (from the docs snapshot)
    uv run python -I research/step_planner/run2.py .          # run2.pkl + stdout; write_outputs() is not called by __main__

`rerun.py` keeps the Project's `sys.argv[1]` = Ficsite Ingot recipe id. Run as a
script it would read `.` as a recipe id, but it is only ever imported (through
`model2`, which sets `sys.argv = ['x']` first, so the default recipe is used).
Only `site_data.json`, `node_defaults.json`, `alt_deps.json`,
`milestones_tagged.csv` and `steps_all_step2.json` are checked in. Other
outputs are regenerated on demand. Delete them before committing, or keep one
with a row added below.

## Files

Project paths are relative to `progression-optimizer/pa-walkback-2026-10-27/`.
All files were fetched from the Project on 2026-11-01.

| File | What it does | Project source |
|---|---|---|
| `p5_walkback.py` | Phase-5 walk-back: recipe matrix and `solve()`. Imported by `rerun` | `p5_walkback.py` |
| `rerun.py` | Replaces `p5_walkback.R` with standard recipes from the reference CSVs. Defines `D` (reference dir) | `rerun.py` |
| `model2.py` | Step 2 model: reference data, recipe set, milestone tagging, stockpile sim, machine sizing, extraction | `step2-milestones-power/model2.py` |
| `run2.py` | Step 2 driver: milestone tags (writes `milestones_tagged.csv` on import), bills, `power_block`, `W_bill`, scenarios | `step2-milestones-power/run2.py` |
| `model3.py` | **Canonical** step model: `schedule`, `simulate_steps`, `evaluate` | `step3-relief/model3.py` |
| `model3a.py` | model3 + one alternate per item (option ii) | `step3-relief/model3a.py` |
| `model3b.py` | model3a + recipes per consumer line | `step3-relief/model3b.py` |
| `relief.py` | Step-level constraint-relief LPs, world capacity, plant draw | `step3-relief/relief.py` |
| `place.py` | Unlock minute of each alternate (HUB deps, building, inputs) | `step3-relief/place.py` |
| `alt_run.py` | Resource-lean alternate pick per phase. `plan2` imports it | `step3-relief/alt_run.py` |
| `plan2.py` | Per-phase recipe plan (binding raw, then line complexity) | `step3-relief/plan2.py` |
| `alt_deps.py` | Regenerates alternate-schematic deps from the docs snapshot | `step3-relief/alt_deps.py` |
| `alt_deps.json` | Output of `alt_deps.py`. Read by `place.py` | `step3-relief/alt_deps.json` (same content; see verification) |
| `site_data.py` | Per-step raw draws (factory + plant) for the canvas site view | `step3-relief/site_data.py` (fixed 2026-11-01) |
| `site_data.json` | Output of `site_data.py` | `step3-relief/site_data.json` (regenerated 2026-11-01) |
| `model3_ppm1029.py` | Session variant 2026-10-29: `FLOOR`, `FLOOR_RATE`, `PPM`, `STOCK_SLOTS` | `step3-relief/ppm-2026-10-29/model3.py` |
| `nodes.py` | Per-phase node defaults + world-supply ceiling | `step3-relief/ppm-2026-10-29/nodes.py` (fixed 2026-11-01) |
| `node_defaults.json` | Output of `nodes.py` | `step3-relief/ppm-2026-10-29/node_defaults.json` (regenerated 2026-11-01) |
| `ppm.py` | PPM sweep: Cu/Fe draw, machines, pasta rate | `step3-relief/ppm-2026-10-29/ppm.py` |
| `cap.py` | Stock-ahead cap sweep (`STOCK_SLOTS`) | `step3-relief/ppm-2026-10-29/cap.py` |
| `model3_ppm1031.py` | Session variant 2026-10-31 (latest): per-item PPM targets (`PPM_ITEM`). No driver here imports it | `step3-relief/ppm-2026-10-31/model3.py` |
| `steps_all_step2.json` | Step-model rows read by `relief.coal_cap` and `alt_run` (reference table) | `step2-milestones-power/steps_all.json` (renamed; see edits) |
| `milestones_tagged.csv` | Written by `run2` on import. Checked in as an output (49 rows) | `step2-milestones-power/milestones_tagged.csv` (see note) |
| `canvas_Main.dc.html` | Design-canvas UI mock-up (phase steps, node defaults, site nodes) | `step3-relief/canvas/Main.dc.html` |
| `model3_ppm1029_plant.py` | `model3_ppm1029.py` plus two read-only additions (2026-11-01): the canonical `segcap` block inside `simulate_steps`, and a cut-down `evaluate()` that makes the same `run2.power_block` calls as canonical `model3.evaluate`. Only changed line: `out[k]` gains `segcap` | new (from `model3_ppm1029.py` + canonical `model3.py`) |
| `plant_resize.py` | Re-sizes the power plant for each `nodes.py` case (1/min, P5 5/min, P5 40/min); checks the 1/min plant against `site_data.json` first and stops on a mismatch → `plant_resize.json` | new, 2026-11-01 |
| `plant_resize.json` | `plant_resize.py` output: per case and phase, factory draw, plant draw, generator counts, peak MW | new, 2026-11-01 |
| `selection_threshold.py` | Draw ÷ best single same-raw neighbourhood (`tools/neighborhoods.py`) per case, phase, raw and declared power set (S0 standard Fuel; S1 HOR + Diluted Fuel; S2 + Turbofuel; S3 + Nitro Rocket Fuel). Radius required. Water not thresholded → `selection_threshold_output.txt` | new, 2026-11-01 |
| `selection_threshold_output.txt` | `selection_threshold.py . --radius 350 1000` output, cited by `site_planner_reframe.md` A12 | new, 2026-11-01 |

Import graph: `p5_walkback` ← `rerun` ← `model2` ← `run2` ← `model3` ←
{`model3a`, `model3b`, `relief`}. Then `place` ← `relief`, `alt_run` ←
{`relief`, `place`, `model3a`}, `plan2` ← `alt_run`, and `site_data` ←
{`relief`, `model3b`, `plan2`}. Separately, `model3_ppm1029` ← {`nodes`,
`ppm`, `cap`}.

`canvas_Main.dc.html` loads its data with `fetch('/_blob/<hash>')` (five
blobs: site data, node defaults, standard steps, alternates/relief/plan,
alternate steps). Those URLs belong to the design-canvas host that produced
it. They are left as they were, and this copy does not show whether the blobs
are snapshots of the JSON files here. On its own the page shows "Loading plan
data…". It also loads `./support.js`, which is not in the Project folder read
here.

## Edits from the Project copies

Only these edit kinds were made. Each edited line carries an `EDIT (a|b|c|d)`
comment. There are no refactors, no behaviour changes and no trimming. Every
`.py` was diffed against the copies in the session scratchpad.

| File | Edit | Why |
|---|---|---|
| all `.py` except `p5_walkback.py`, `model2.py` | (a) one line puts the script's folder on `sys.path` (`pathlib.Path(__file__).resolve().parent`) | `python -I` leaves the script dir off `sys.path` for imported siblings, and drivers import from their own folder |
| `rerun.py` | (a) `D = <repo>/planning_data/game/reference/`, from `__file__` (`parents[1]`) | was `/mnt/user-data/uploads/satisfactory_progression_planner/...`. `model2` overwrites `sys.argv` before importing `rerun`, so argv cannot carry the repo root |
| `relief.py` | (a) `REPO` from `__file__` | was `/home/claude/gmcdowelljr/satisfactory_progression_planner/` |
| `relief.py`, `alt_run.py` | (a) `/home/claude/pa/steps_all.json` → `steps_all_step2.json` beside the script | the session's local copy of Project `step2-milestones-power/steps_all.json`. Renamed because `model3.py` writes its own `steps_all.json` into this folder and would overwrite it |
| `place.py` | (a) `alt_deps.json` read from the script's folder | was cwd-relative |
| `alt_deps.py` | (a) snapshot and `alternate_choices.csv` paths from `__file__` | were `/home/claude/gmcdowelljr/...` |
| `run2.py` | (b) `csv.writer(..., lineterminator="\n")` ×4. (d) `milestones_tagged.csv`, `milestone_bill_by_phase.csv`, `pa2_machines_*.csv`, `power_by_phase.csv`, `run2.pkl` written to the script's folder | `tests/test_writers_emit_lf.py`. Keeps outputs out of the repo root |
| `model3.py` | (b) `json.dump(open(..., newline="\n"))`, csv `lineterminator="\n"`. (d) `steps_*.json/csv` to the script's folder | same |
| `alt_run.py`, `plan2.py`, `relief.py`, `site_data.py`, `nodes.py`, `alt_deps.py` | (b) `open(..., 'w', newline="\n")` on each `json.dump`. (d) output to the script's folder | same. A JSON writer emits no newlines except under `indent=`, so `site_data.json`/`node_defaults.json` bytes are unchanged |
| `nodes.py`, `ppm.py`, `cap.py` | (c) `import model3 as M3` → `import model3_ppm1029 as M3` | in the Project's `ppm-2026-10-29/` folder `model3` means that folder's session variant, not the canonical `step3-relief/model3.py` |
| `model3_ppm1029.py`, `model3_ppm1031.py` | (c) renamed from `model3.py`, plus a two-line header note on the rename | name collision with the canonical `model3.py` |

The step2 `model3.py` (`step2-milestones-power/model3.py`) is not copied. It
is the earlier version of the canonical model (no `prof/cons/byp/rawc` in its
output), and step3 imports the canonical one.

## 2026-11-01 defect fix (fixed in the Project before this copy)

`site_data.py` added the Fuel generators' crude to the plant draw twice.
`run2.power_block` already puts that crude in `pb['raw']`, and `site_data`
added it again, so plant crude was 2×. The fix removed the second add (dated
comment in `site_data.py`). `nodes.py`'s `PLANT` table, which is copied from
`site_data.json` std per-phase max, was corrected to match (P3 25.04, P4
522.28, P5 983.28 crude, dated comment). `site_data.json` and
`node_defaults.json` here are the corrected outputs, regenerated in the
Project on 2026-11-01.

## Verification (cloud container, 2026-11-01, branch `claude/step-planner-threshold` on master 3fcab38)

- `site_data.py` regenerates `site_data.json` byte-identical to the Project's
  2026-11-01 `step3-relief/site_data.json` (10263 B, sha256 `85a89122…7d05`).
- `nodes.py` regenerates `node_defaults.json` byte-identical to the Project's
  2026-11-01 `ppm-2026-10-29/node_defaults.json` (11078 B, sha256 `152a00f5…dbc9`).
- `alt_deps.py` regenerates `alt_deps.json` with the same content as the
  Project file (109 entries, same key order, same bytes up to whitespace). The
  repo file is the regenerated one.
- `milestones_tagged.csv` (LF) differs from the Project's CRLF copy in line
  endings and in one reason cell, Obstacle Clearing. The current `run2`
  labels that recipe `Solid Biofuel (P1 power, PMULT<=1)`, and the Project
  CSV predates that label. Tags and costs are the same in every row checked.
- `steps_all_step2.json` was re-serialised from the Project's
  `steps_all.json` (`json.dumps(indent=1)`, the Project's own format). It is
  internally consistent (d_machines, d_MW, new_lines and line sums all
  re-derive), and its P1–P3 MW match the session's trimmed copy.
- `plant_resize.py`: its own check passes (1/min plant equals `site_data.json`
  std, Coal and Crude Oil, every phase); 0 WARN lines in every case.
- `selection_threshold.py . --radius 350 1000` writes
  `selection_threshold_output.txt` (master `3fcab38`, `tools/neighborhoods.py`
  as merged there). The 1/min S0 rows match the session's scratch run of the
  same day.
