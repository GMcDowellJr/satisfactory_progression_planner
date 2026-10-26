"""Milestone vs Project Assembly load per phase, and the serial E time
multiplier — scratch driver, 2026-10-26. NOT repo code (CLAUDE.md: keep out of
tools/ until it has a test and a decision behind it).

Decided by Greg, 2026-10-26 (design note D17, D18):
    D17  milestones are paid SERIALLY from factory capacity: machine-minutes
         are treated as fungible on one factory, so
             T multiplier(E) = (E * W_PA + W_ms) / (W_PA + W_ms)
    D18  Mycelia is a HAND-SUPPLIED input: a leaf with no extractor and no
         machine-minutes. Biomass and Fabric are still made by machines.

Measure: W = sum of LP machine-equivalents to make the whole bill (BASE_ONLY,
100% clock, floor 1 per stated unit). Solved at bill/1000 per minute and
rescaled, because LpBackend's ACTIVITY_UPPER_BOUND (1e6) binds at bill scale
(2R phase 5) and reports Infeasible.

Scratch shortcuts that break repo rules, named: reads project_assembly_
requirements.csv and items.csv directly (gamedata.py is the one loader), and
widens ReferenceData.resource_items with dataclasses.replace to make Mycelia a
leaf (in the repo that would be a declared input, refused when undeclared).

Usage: python -I milestone_load.py <repo> [R ...]
"""
import sys, csv, pathlib, dataclasses
repo = pathlib.Path(sys.argv[1]); Rs = [float(x) for x in sys.argv[2:]] or [1.0]
for p in ("production_adapter", "progression"):
    sys.path.insert(0, str(repo / f"tools/{p}/src"))
from production_adapter import gamedata
from production_adapter.contracts import OutputTarget, SolveRequest
from production_adapter.lp_backend import LpBackend, PowerStatistic, Infeasible
from production_adapter.scenario import Scenario
from progression import unlocks

HAND_SUPPLIED = frozenset({"Desc_Mycelia_C"})                     # D18
WINDOW = {1: (0, 1, 2), 2: (3, 4), 3: (5, 6), 4: (7, 8), 5: (9,)}   # D16
E_SETTINGS = (0.25, 0.5, 0.75, 1, 2, 5, 10, 25, 50, 100)            # record §3.2.1
K = 1e-3

ref = repo / "planning_data/game/reference"
pa = list(csv.DictReader(open(ref / "project_assembly_requirements.csv")))
item_by_name = {r["display_name"]: r["item_id"] for r in csv.DictReader(open(ref / "items.csv"))}
costs = unlocks.schematic_costs(repo)
base = gamedata.load(repo)
base = dataclasses.replace(base, resource_items=base.resource_items | HAND_SUPPLIED)
be = LpBackend(power_statistic=PowerStatistic.MEAN)


def work(data, bill):
    """(machine-minutes, hand-supplied units) for the whole bill."""
    bill = {i: q for i, q in bill.items() if q > 0}
    if not bill:
        return 0.0, {}
    r = be.solve(SolveRequest(outputs=tuple(OutputTarget(i, q * K) for i, q in bill.items())), data)
    hand = {x.item_id: x.rate_per_min / K for x in r.raw_inputs if x.item_id in HAND_SUPPLIED}
    return sum(u.machine_equivalents for u in r.recipes) / K, hand


def bills(ph):
    pab = {item_by_name[r["item_name"]]: float(r["quantity_default_1x"]) for r in pa if r["phase"] == str(ph)}
    msb, skipped = {}, set()
    for s in unlocks.schematics_in_tiers(repo, WINDOW[ph]):
        for i, q in costs.get(s, ()):
            if i not in base.items:
                skipped.add(i); continue
            try:
                be.solve(SolveRequest(outputs=(OutputTarget(i, 1.0),)), base)
            except Infeasible:
                skipped.add(f"{i}x{q:g}@{s}"); continue
            msb[i] = msb.get(i, 0) + q
    return pab, msb, skipped


for R in Rs:
    data = base if R == 1 else dataclasses.replace(
        base.with_scenario(Scenario(recipe_input_multiplier=R, input_amount_floor=1)),
        resource_items=base.resource_items)
    print(f"== R{R:g}  W_PA | W_ms | ms share | serial T multiplier at E = " + " ".join(f"{e:g}" for e in E_SETTINGS))
    for ph in WINDOW:
        pab, msb, skipped = bills(ph)
        (wpa, _), (wms, hand) = work(data, pab), work(data, msb)
        tm = [(e * wpa + wms) / (wpa + wms) for e in E_SETTINGS]
        extra = (f"  hand {({k: round(v) for k, v in hand.items()})}" if hand else "") + \
                (f"  skipped {sorted(skipped)}" if skipped else "")
        print(f"  ph{ph} {wpa:11,.0f} | {wms:9,.0f} | {wms/(wpa+wms):5.1%} | " + " ".join(f"{t:6.2f}" for t in tm) + extra)
