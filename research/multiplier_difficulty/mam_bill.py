"""MAM bill by earliest-producible phase, and the work multiplier with MAM —
scratch driver, 2026-10-26. NOT repo code.

Rules (design note D10, D16, D17, D18):
    window     phase p is produced on tiers <= TOP[p] (ph1 2, ph2 4, ph3 6,
               ph4 8, ph5 9); MAM building opens at 1-3, inside phase 1
    recipes    tier-granted base recipes (unlocks.at_tier) + recipes unlocked by
               MAM nodes already placed (closure, iterated to a fixed point
               within the phase)
    resources  extractables with an extractor open at TOP[p], plus PICKUPS
    PICKUPS    hand-supplied leaves: items.csv items with no producing recipe
               that are not resources, minus wastes/FICSMAS/crafted equipment.
               Extends D18 from Mycelia to every pickup — PENDING GREG.
               Hard Drive (not in items.csv) is a pickup too.
    placement  a node lands in the first phase where every resolvable cost
               item is producible. MAM tree order is NOT enforced: the
               reference data carries no MAM dependency rows. Recipe-unlock
               dependencies are enforced by the closure.
    excluded   'Discontinued - ' nodes and the FICSMAS tree (Research_XMas_*),
               named in the output
    unpriced   costs not in items.csv (Nobelisk, Rebar, Cartridge, Object
               Scanner): named per node, not priced, not used for placement
    work       machine-minutes as milestone_load.py, pickups as leaves,
               bill/1000 rescaled. Priced on base recipes PLUS the recipes the
               MAM nodes placed at or before the phase unlock (some are
               alternate-flagged: Compacted Coal is reachable only that way).
               Placement is tier-gated; pricing is not (same gap as §5.1).

Usage: python -I mam_bill.py <repo> [R ...]
"""
import sys, csv, pathlib, dataclasses, collections
repo = pathlib.Path(sys.argv[1]); Rs = [float(x) for x in sys.argv[2:]] or [1.0]
for p in ("production_adapter", "progression"):
    sys.path.insert(0, str(repo / f"tools/{p}/src"))
from production_adapter import gamedata
from production_adapter.contracts import OutputTarget, SolveRequest, AllowedRecipes, RecipeMode
from production_adapter.lp_backend import LpBackend, PowerStatistic, Infeasible
from production_adapter.scenario import Scenario
from progression import unlocks

TOP = {1: 2, 2: 4, 3: 6, 4: 8, 5: 9}
WINDOW = {1: (0, 1, 2), 2: (3, 4), 3: (5, 6), 4: (7, 8), 5: (9,)}
HARD_DRIVE = "Desc_HardDrive_C"
NOT_PICKUP = {"Desc_NuclearWaste_C", "Desc_PlutoniumWaste_C", "Desc_Medkit_C", "Desc_Parachute_C", "Desc_Gift_C"}
K = 1e-3

ref = repo / "planning_data/game/reference"
rows = lambda f: list(csv.DictReader(open(ref / f)))          # scratch: breaks one-loader rule
sch = {r["schematic_id"]: r for r in rows("schematics.csv")}
outs = {r["item_id"] for r in rows("recipe_io.csv") if r["direction"] == "output"}
res = {r["item_id"] for r in rows("resources.csv")}
names = {r["item_id"]: r["display_name"] for r in rows("items.csv")}
PICKUPS = frozenset(i for i in names if i not in outs and i not in res and i not in NOT_PICKUP
                    and not i.startswith("Desc_XmasDataCartridge"))
mam_unlocks = collections.defaultdict(set)
for r in rows("schematic_recipe_unlocks.csv"):
    if sch.get(r["schematic_id"], {}).get("schematic_type") == "EST_MAM":
        mam_unlocks[r["schematic_id"]].add(r["recipe_id"])
costs = unlocks.schematic_costs(repo)
mam = sorted(k for k, v in sch.items() if v["schematic_type"] == "EST_MAM")
excluded = [m for m in mam if sch[m]["display_name"].startswith("Discontinued") or m.startswith("Research_XMas")]
active = [m for m in mam if m not in excluded]

base = gamedata.load(repo)
all_recipes = set(base.recipes)
be = LpBackend(power_statistic=PowerStatistic.MEAN)
feas_cache = {}


def producible(item, recipes, resources):
    if item in resources:
        return True
    key = (item, recipes, resources)
    if key not in feas_cache:
        data = dataclasses.replace(base, resource_items=resources)
        try:
            be.solve(SolveRequest(outputs=(OutputTarget(item, 1.0),),
                                  allowed_recipes=AllowedRecipes(mode=RecipeMode.EXPLICIT,
                                                                 recipe_ids=tuple(sorted(recipes)))), data)
            feas_cache[key] = True
        except Infeasible:
            feas_cache[key] = False
    return feas_cache[key]


# ---- placement ----
placed, unpriced = {}, collections.defaultdict(list)
for m in active:
    for i, q in costs.get(m, ()):
        if i not in names and i != HARD_DRIVE:
            unpriced[m].append(f"{i} x{q:g}")
researched: set[str] = set()
for ph in TOP:
    tier_recipes = set(unlocks.at_tier(repo, TOP[ph]).recipe_ids)
    open_res = set(unlocks.extractors_open_at_tier(repo, TOP[ph])) & res
    resources = frozenset((open_res & set(base.resource_items)) | PICKUPS)
    while True:
        recipes = frozenset((tier_recipes | {r for n in researched for r in mam_unlocks[n]}) & all_recipes)
        new = [m for m in active if m not in placed and all(
            producible(i, recipes, resources) for i, _ in costs.get(m, ()) if i in names)]
        if not new:
            break
        for m in new:
            placed[m] = ph; researched.add(m)

never = [m for m in active if m not in placed]
by_phase = collections.defaultdict(list)
for m, ph in placed.items():
    by_phase[ph].append(m)
print(f"MAM nodes: {len(mam)}; excluded {len(excluded)} (Discontinued + FICSMAS); placed {len(placed)}; never {len(never)}")
alt_via_mam = sorted(r for m in active for r in mam_unlocks[m] if r in all_recipes and base.recipes[r].is_alternate)
print("alternate-flagged recipes unlocked by MAM:", alt_via_mam)
print("pickups (hand-supplied):", ", ".join(sorted(names[i] for i in PICKUPS)))
for ph in TOP:
    print(f"  ph{ph}: {len(by_phase[ph])} nodes: " + "; ".join(sch[m]["display_name"] or m for m in sorted(by_phase[ph])))
if never:
    print("  never placed:", "; ".join(f'{sch[m]["display_name"]} ({m})' for m in never))
if unpriced:
    print("  unpriced costs:", "; ".join(f'{sch[m]["display_name"]}: {", ".join(v)}' for m, v in sorted(unpriced.items())))

# ---- work ----
pa = rows("project_assembly_requirements.csv")
item_by_name = {v: k for k, v in names.items()}
pricing = dataclasses.replace(base, resource_items=base.resource_items | PICKUPS)


def priced_recipes(ph):
    s = {r for r in all_recipes if not base.recipes[r].is_alternate}
    s |= {r for m, p in placed.items() if p <= ph for r in mam_unlocks[m]} & all_recipes
    return AllowedRecipes(mode=RecipeMode.EXPLICIT, recipe_ids=tuple(sorted(s)))


def work(data, bill, ph):
    bill = {i: q for i, q in bill.items() if q > 0 and i in names}
    if not bill:
        return 0.0, {}
    r = be.solve(SolveRequest(outputs=tuple(OutputTarget(i, q * K) for i, q in bill.items()),
                              allowed_recipes=priced_recipes(ph)), data)
    hand = {x.item_id: x.rate_per_min / K for x in r.raw_inputs if x.item_id in PICKUPS}
    return sum(u.machine_equivalents for u in r.recipes) / K, hand


def bills(ph):
    pab = {item_by_name[r["item_name"]]: float(r["quantity_default_1x"]) for r in pa if r["phase"] == str(ph)}
    msb, mmb = collections.Counter(), collections.Counter()
    for s in unlocks.schematics_in_tiers(repo, WINDOW[ph]):
        for i, q in costs.get(s, ()):
            msb[i] += q
    for m in by_phase[ph]:
        for i, q in costs.get(m, ()):
            mmb[i] += q
    return pab, msb, mmb


W = {}
for R in [1.0] + [r for r in Rs if r != 1.0]:
    data = pricing if R == 1 else dataclasses.replace(
        base.with_scenario(Scenario(recipe_input_multiplier=R, input_amount_floor=1)),
        resource_items=pricing.resource_items)
    for ph in TOP:
        pab, msb, mmb = bills(ph)
        W[(R, ph)] = (work(data, pab, ph)[0], work(data, msb, ph)[0], *work(data, mmb, ph))
print("\nW in machine-minutes: PA | milestones | MAM ; MAM share ; work multiplier vs 1/1/1 (E=1) with MAM [without]")
for R in Rs:
    print(f"== R{R:g}")
    for ph in TOP:
        pa_, ms, mm, hand = W[(R, ph)]
        b = W[(1.0, ph)]
        tot, tot1 = pa_ + ms + mm, b[0] + b[1] + b[2]
        print(f"  ph{ph} {pa_:11,.0f} | {ms:9,.0f} | {mm:9,.0f} ; {mm/tot:5.1%} ; {tot/tot1:6.2f} [{(pa_+ms)/(b[0]+b[1]):6.2f}]"
              + (f"  hand-MAM {({names[k]: round(v) for k, v in hand.items()})}" if hand else ""))
