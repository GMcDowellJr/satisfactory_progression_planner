"""Multiplier difficulty ratios — scratch driver, 2026-10-26. NOT repo code.

Reproduces the figures in multiplier-difficulty-design-2026-10-26.md.
Keep out of tools/ until it has a test and a decision behind it (CLAUDE.md).

What it computes, per phase, for one scenario against the 1R/1P/1E baseline:

    anchor   one 100%-clock final machine per Project Assembly part
             A = every part at its one-machine rate simultaneously (peak factory)
             B = bottleneck part at one machine; others sized to finish at the
                 same T (sustained factory). No unlock offsets.
    solve    repo LpBackend.solve, BASE_ONLY recipes, PowerStatistic.MEAN,
             Scenario(..., input_amount_floor=1)
    metrics  machine-equivalents (100% clock), manufacturing MW, extractor MW
             (highest miner mark by phase, uniform purity, x P), solid raw /min

Known gaps: Water Extractor MW absent (no water rate in extraction_rates.csv);
phase 2 uses Mk1 throughout though Mk2 unlocks at 4-1; no node caps; no
generators; milestones/MAM not in the bill; no unlock offsets.

Usage (repo checkout path as first arg):
    python -I multiplier_ratios.py /path/to/satisfactory_progression_planner \\
        --scenarios 1.25:1 1.5:1 1:5 --purity normal
"""
from __future__ import annotations

import argparse
import csv
import sys

PHASE_MINER = {1: "Build_MinerMk1_C", 2: "Build_MinerMk1_C", 3: "Build_MinerMk2_C",
               4: "Build_MinerMk2_C", 5: "Build_MinerMk3_C"}
FLUID_MARKERS = ("Water", "Liquid", "Gas")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--scenarios", nargs="+", default=["1.25:1", "1.5:1", "2:1", "1:5", "1.25:5"],
                    help="R:P pairs")
    ap.add_argument("--purity", default="normal", choices=["impure", "normal", "pure"])
    ap.add_argument("--absolute", action="store_true", help="also print 1/1/1 absolute values")
    a = ap.parse_args()

    repo = a.repo
    sys.path.insert(0, repo + "/tools/production_adapter/src")
    from production_adapter import gamedata
    from production_adapter.contracts import OutputTarget, SolveRequest
    from production_adapter.lp_backend import LpBackend, PowerStatistic
    from production_adapter.scenario import Scenario

    ref = repo + "/planning_data/game/reference/"
    # Scratch only: the repo rule is that gamedata.py is the one CSV loader.
    rows = list(csv.DictReader(open(ref + "project_assembly_requirements.csv")))
    item_by_name = {r["display_name"]: r["item_id"] for r in csv.DictReader(open(ref + "items.csv"))}
    emap = {r["item_id"]: r["extractor_class"] for r in csv.DictReader(open(ref + "resource_extraction_map.csv"))}
    emw = {r["extractor_class"]: float(r["base_power_mw"]) for r in csv.DictReader(open(ref + "extraction_buildings.csv"))}
    erate = {(r["extractor_class"], r["purity"]): float(r["nominal_rate_min"])
             for r in csv.DictReader(open(ref + "extraction_rates.csv"))}

    base = gamedata.load(repo)
    part_rate = {r.outputs[0][0]: r.outputs[0][1] for rid, r in base.recipes.items()
                 if rid.startswith("Recipe_SpaceElevatorPart_")}
    be = LpBackend(power_statistic=PowerStatistic.MEAN)
    unmapped: set[str] = set()

    def run(R: float, P: float, phase: int, mode: str) -> tuple[float, float, float, float, float]:
        data = base if (R, P) == (1, 1) else base.with_scenario(
            Scenario(recipe_input_multiplier=R, machine_power_multiplier=P, input_amount_floor=1))
        parts = [(item_by_name[r["item_name"]], float(r["quantity_default_1x"]))
                 for r in rows if r["phase"] == str(phase)]
        T = max(q / part_rate[i] for i, q in parts)
        targets = {i: part_rate[i] for i, _ in parts} if mode == "A" else {i: q / T for i, q in parts}
        resp = be.solve(SolveRequest(outputs=tuple(OutputTarget(i, r) for i, r in targets.items())), data)
        machines = sum(u.machine_equivalents for u in resp.recipes)
        raw = sum(x.rate_per_min for x in resp.raw_inputs if not any(k in x.item_id for k in FLUID_MARKERS))
        ext = 0.0
        for x in resp.raw_inputs:
            c = emap.get(x.item_id)
            if c and c.startswith("Build_MinerMk"):
                c = PHASE_MINER[phase]
            rate = erate.get((c, a.purity)) or erate.get((c, "normal")) if c else None
            if rate is None:
                unmapped.add(x.item_id)
                continue
            ext += x.rate_per_min / rate * emw[c] * P
        return T / 60, machines, resp.power.scenario_mw, ext, raw

    baseline = {(ph, m): run(1, 1, ph, m) for ph in range(1, 6) for m in "AB"}
    if a.absolute:
        print("1/1/1 absolute: T_h, machines, mfg MW, ext MW, raw/min")
        for k, v in baseline.items():
            print(f"  ph{k[0]} {k[1]}: " + ", ".join(f"{x:,.1f}" for x in v))
    for s in a.scenarios:
        R, P = (float(x) for x in s.split(":"))
        print(f"== R{R:g} P{P:g}  (ratio vs 1/1/1, same anchor mode; purity={a.purity})")
        for ph in range(1, 6):
            cells = []
            for m in "AB":
                v, b = run(R, P, ph, m), baseline[(ph, m)]
                cells.append(f"{m}: mach {v[1]/b[1]:.2f} mfgMW {v[2]/b[2]:.2f} "
                             f"extMW {v[3]/b[3]:.2f} raw {v[4]/b[4]:.2f}")
            print(f"  ph{ph}  " + " | ".join(cells))
    if unmapped:
        print("unmapped raws (no extractor MW):", sorted(unmapped))


if __name__ == "__main__":
    main()
