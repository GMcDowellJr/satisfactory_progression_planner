"""Node ceiling on the default world — scratch driver, 2026-10-26 (action 3).
NOT repo code. Reuses work_axis.py (exec'd from beside this), so it inherits
the same bills, pricing recipes, pickups and scenario data as grid.py.

Question (Greg, 2026-10-26): use nodes by their proportion in the world, not
all-normal; some R/P combinations may be impossible on default nodes, before
power shards, somersloops or alien power augmenters.

    world      planning_data/world/configurations/default_502094/
               resource_assignments.csv, per socket. Nodes: miners / oil
               extractors. Wells: satellites only (cores are activators).
               Geysers left out (geothermal is not in GENS). Water: pumped
               from open water, uncapped (well water is not used).
    extractor  per socket kind, the highest mark open at the phase's top tier
               (D12), 100 % clock, no shards. Solids capped at the best belt
               open at the top tier (logistics_capabilities.csv). At the top
               tier the belt never binds (Mk1 pure 120 on Mk2 120, Mk2 pure
               240 on Mk3 270, Mk3 pure 480 on Mk5 780); it would bind earlier
               in a window, which D12's top-tier convention does not model.
    wells      charged as pressurizers: 150 MW x cores of that resource,
               spread over its satellites' total rate (an average; a real
               well's satellites share one core). Open from 8-2.
    pickups    hand-supplied (D21), capped at 1e7/min: not node-bound. Dropped
               from the bill itself (D29 counts them separately).
    bill       the whole phase bill, PA x E + milestones + MAM (as grid.py),
               divided by T_ref: the bill per minute at the reference pace.
               Raws named directly in the bill (MAM costs) pass through a
               zero-power pseudo recipe (`with_ship`).
    solve      LpBackend.solve_portfolio, one site, stage 1 = max scale under
               the caps, which is k directly. T_min = T_ref / k: the shortest
               the phase can take on every default node at once.
               Conditioning: an earlier version solved the raw bill per
               minute (scale ~1e-5) with pickups at 1e9; HiGHS then returned
               scale 0 for 1.5R/5P ph5 Coal and a short scale for Biomass at
               5P. Normalising made both regular.
    modes      factory: caps only, power outside the solve (P cannot matter).
               <generator>: sole source (D27), one shared grid row, extractors
               charged by their draw x P (A4, A7), water pumped. Biomass burns
               Leaves, a pickup, so it is gathering-bound, not node-bound.
    pace       T_ref = T_anchor_PA x W_total / W_PA at 1/1/1: the anchor-B
               factory (§3.3) paying milestones and MAM serially (D17).
               k = T_ref / T_min: how many 1/1/1-pace factories the world
               feeds. k < 1 means the "same pace" endpoint (D19) is not
               reachable on default nodes; the "same factory" endpoint always
               is, it just takes longer.

Usage: python -I node_ceiling.py <repo> [R:P:E ...]   (default: a short set)
       python -I node_ceiling.py <repo> --grid           (R x P x E{1,10})
       add --all-normal to rerun with every socket's purity set to normal
       (same counts): the "assume all normal" baseline the question replaces;
       --purity=impure|normal|pure sets every socket to that purity
"""
import sys, pathlib, json, time
here = pathlib.Path(__file__).parent
args = sys.argv[2:]
PURITY = next((a.split("=")[1] for a in args if a.startswith("--purity=")), None)
if "--all-normal" in args:
    PURITY = "normal"           # same socket counts, every one normal (comparison)
args = [a for a in args if a != "--all-normal" and not a.startswith("--purity=")]
sys.argv = [str(here / "work_axis.py"), sys.argv[1]]
src = open(here / "work_axis.py").read().split("base_w = {ph")[0]
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(src, "work_axis", "exec"))

from production_adapter.contracts import (PortfolioRequest, PortfolioSite, ResourceCap,
                                          ExtractionSegment, PowerBalance)

WORLD = repo / "planning_data/world/configurations/default_502094/resource_assignments.csv"
PICKUP_CAP = 1.0e7    # hand-supplied; ~50x the most any cell draws (Leaves), kept modest for conditioning
WATER = "Desc_Water_C"
WELL = "Build_FrackingExtractor_C"
SMASHER_MW = BASE_MW["Build_FrackingSmasher_C"]

# ---- world: (item, kind, purity) -> socket count; cores per well resource ----
world, cores = collections.Counter(), collections.Counter()
for r in csv.DictReader(open(WORLD)):
    sid, item = r["socket_id"], r["resource_descriptor"]
    if "Geyser" in sid or item == "Desc_Geyser_C":
        continue
    if "FrackingCore" in sid:
        cores[item] += 1
    elif "FrackingSatellite" in sid:
        world[(item, "well", r["purity"])] += 1
    else:
        world[(item, "node", r["purity"])] += 1

# ---- belts by tech tier ----
BELT = []
for r in rows("logistics_capabilities.csv"):
    if r["capability_type"] == "belt":
        BELT.append((int(r["unlock"].split()[1]), float(r["capacity_per_min"])))


def belt_at(tier):
    return max(c for t, c in BELT if t <= tier)


def segments(ph, P):
    """(segments, caps) for every raw at the phase's top tier, default world."""
    open_cls = unlocks.extractors_open_at_tier(repo, TOP[ph])
    belt = belt_at(TOP[ph])
    segs, caps = [], collections.Counter()
    for (item, kind, purity), n in sorted(world.items()):
        if item == WATER:
            continue
        if PURITY:
            purity = PURITY
        avail = set(open_cls.get(item, ())) & set(EMAP.get(item, ()))
        if kind == "well":
            if WELL not in avail:
                continue
            cls = WELL
            rate = RATE[(cls, purity)]
            sat_rate = sum(RATE[(WELL, p)] * c for (i, k, p), c in world.items() if i == item and k == "well")
            mw = SMASHER_MW * cores[item] / sat_rate
        else:
            cls = next((c for c in MARK if c in avail and c != "Build_WaterPump_C"), None)
            if cls is None:
                continue
            rate = RATE[(cls, purity)]
            if cls.startswith("Build_Miner"):
                rate = min(rate, belt)
            mw = BASE_MW[cls] / RATE[(cls, purity)]
        segs.append(ExtractionSegment(item, n * rate, mw * P, n * BASE_MW[cls] * P if cls != WELL else 0.0,
                                      source=f"{n} x {cls} on {purity}"))
        caps[item] += n * rate
    return segs, caps


def with_ship(data, raws):
    """Scratch: a zero-power pass-through recipe per raw the bill names
    directly (MAM costs Coal, Caterium Ore, ...), raw -> 'Ship_<raw>' token,
    because a portfolio bill item cannot also be a capped raw. Stage 1 only
    reads the scale, so the pseudo recipe's machine count is never used."""
    r0 = next(iter(data.recipes.values()))
    rec, items = dict(data.recipes), dict(data.items)
    for i in raws:
        tok = "Ship_" + i
        rec["Recipe_" + tok] = dataclasses.replace(
            r0, recipe_id="Recipe_" + tok, display_name=tok, is_alternate=False, duration_sec=60.0,
            inputs=((i, 1.0),), outputs=((tok, 1.0),), power=gamedata.PowerRange(0.0, 0.0),
            input_amounts=((i, 1.0, "items"),), output_amounts=((tok, 1.0, "items"),))
        items[tok] = dataclasses.replace(data.items[i], item_id=tok, display_name=tok, is_resource=False)
    return dataclasses.replace(data, recipes=rec, items=items)


def phase_bill(data, ph, E):
    """(bill tuple, data, allowed) — pickups dropped (hand-supplied, D29),
    raws shipped through `with_ship`."""
    pab, msb, mmb = bills(ph)
    bill = collections.Counter()
    for i, q in pab.items(): bill[i] += E * q
    for b in (msb, mmb):
        for i, q in b.items(): bill[i] += q
    bill = {i: q for i, q in bill.items() if q > 0 and i in names and i not in PICKUPS}
    raws = sorted(i for i in bill if i in data.resource_items)
    data = with_ship(data, raws)
    for i in raws:
        bill["Ship_" + i] = bill.pop(i)
    allowed = AllowedRecipes(mode=RecipeMode.EXPLICIT, recipe_ids=tuple(sorted(
        set(priced_recipes(ph).recipe_ids) | {"Recipe_Ship_" + i for i in raws})))
    # per minute at the reference pace, so the solved scale IS k (O(1));
    # the raw bill made HiGHS return 0 or a short scale at scale ~1e-5
    return tuple((i, q / T_REF[ph]) for i, q in sorted(bill.items())), data, allowed


def request(data, ph, P, E, gen=None):
    bill, data, allowed = phase_bill(data, ph, E)
    segs, caps = segments(ph, P)
    raws = sorted(data.resource_items)
    if gen is None:
        rc = [ResourceCap(i, PICKUP_CAP if (i in PICKUPS or i == WATER) else float(caps.get(i, 0.0))) for i in raws]
        site = PortfolioSite("world", tuple(rc))
        power = None
    else:
        segs = list(segs)
        segs.append(ExtractionSegment(WATER, None, BASE_MW["Build_WaterPump_C"] / RATE[("Build_WaterPump_C", "none")] * P,
                                      None, source="pumped"))
        rc = [ResourceCap(i, None if i == WATER else (PICKUP_CAP if i in PICKUPS else float(caps.get(i, 0.0))))
              for i in raws]
        site = PortfolioSite("world", tuple(rc), tuple(segs))
        power = PowerBalance(generators=(gen,))
    return PortfolioRequest(sites=(site,), bill=bill, allowed_recipes=allowed, power=power), data


def ceiling(R, P, E, ph, gen=None):
    """(k, binding raws): k = bill copies per T_ref the world sustains."""
    req, data = request(scenario_data(R, P), ph, P, E, gen)
    r = be.solve_portfolio(req, data)
    # Binding read from the plan (agrees with SitePlan.binding once the bill
    # is normalised). "grid" = the power row binds and no raw is at its cap:
    # the cheap sockets are full and the rest are not worth working. Checked
    # once (2R/5P ph3 Fuel): doubling the pure oil sockets lifts k 1.69x,
    # doubling the impure ones 1.00x, doubling every oil socket 2.00x.
    caps = {c.item_id: c.rate_per_min for c in req.sites[0].resource_caps}
    bind = sorted(names.get(x.item_id, x.item_id) for x in r.sites[0].plan.raw_inputs
                  if x.item_id not in PICKUPS and caps.get(x.item_id) is not None
                  and x.rate_per_min >= caps[x.item_id] * (1 - 1e-4))
    if not bind and r.power is not None and r.power.binding:
        bind = ["grid"]
    return r.scale, bind


# ---- reference pace at 1/1/1 ----
def t_anchor_pa(ph):
    pab = bills(ph)[0]
    allowed = set(priced_recipes(ph).recipe_ids)
    t = 0.0
    for i, q in pab.items():
        rates = [rate for rid in allowed if not base.recipes[rid].is_alternate
                 for it, rate in base.recipes[rid].outputs if it == i]
        t = max(t, q / max(rates))
    return t


T_REF = {}
for ph in TOP:
    data = scenario_data(1.0, 1.0)
    pab, msb, mmb = bills(ph)
    w_pa = solve_full(data, pab, ph, 1.0)[0]
    w_tot = w_pa + solve_full(data, msb, ph, 1.0)[0] + solve_full(data, mmb, ph, 1.0)[0]
    T_REF[ph] = t_anchor_pa(ph) * w_tot / w_pa


def gens_open(ph):
    return [GENS[c] for c in unlocks.generators_open_at_tier(repo, TOP[ph], tuple(GENS))]


def gname(g):
    return g.generator_class.split("_")[1].replace("Generator", "")


def row(R, P, E, ph):
    out = {}
    s, b = ceiling(R, P, E, ph)
    out["factory"] = (s, b)
    for g in gens_open(ph):
        out[gname(g)] = ceiling(R, P, E, ph, g)
    return out


def fmt(s, b):
    if s <= 0:
        return "unreachable [" + ", ".join(b) + "]"
    return f"T_min {T_REF_PH/s/60:8.2f} h  k {s:7.2f}" + (f"  [{', '.join(b)}]" if b else "")


print("world sockets used:", {f"{names.get(i, i)} {k} {p}": n for (i, k, p), n in sorted(world.items())})
print("well cores:", dict(cores))
print("T_anchor_PA h (§3.3 check):", {ph: round(t_anchor_pa(ph) / 60, 2) for ph in TOP})
print("T_ref h (1/1/1 anchor pace, serial):", {ph: round(t / 60, 2) for ph, t in T_REF.items()})

if args == ["--grid"]:
    Rs = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]
    Ps = [0.25, 0.5, 0.75, 1, 2, 5]
    out, t0 = {}, time.time()
    for R in Rs:
        for E in (1, 10):
            for ph in TOP:
                s, b = ceiling(float(R), 1.0, float(E), ph)
                out[f"{R}|*|{E}|{ph}|factory"] = [round(s, 4), b]
        for P in Ps:
            for E in (1, 10):
                for ph in TOP:
                    for g in gens_open(ph):
                        s, b = ceiling(float(R), float(P), float(E), ph, g)
                        out[f"{R}|{P}|{E}|{ph}|{gname(g)}"] = [round(s, 4), b]
        print(f"R{R} done {time.time()-t0:.0f}s", flush=True)
    json.dump({"t_ref_min": T_REF, "cells_are": "k", "cells": out}, open(here / (f"node_ceiling_all_{PURITY}.json" if PURITY else "node_ceiling.json"), "w", newline="\n"),
              separators=(",", ":"))
    print("written", len(out))
else:
    scen = [tuple(float(x) for x in a.split(":")) for a in args] or [
        (1, 1, 1), (1.25, 1, 1), (2, 1, 1), (1, 5, 1), (1.25, 5, 1), (2, 5, 1), (1, 1, 10)]
    for R, P, E in scen:
        print(f"== R{R:g} P{P:g} E{E:g}   T_min = whole phase bill on every default node; k = T_ref / T_min")
        for ph in TOP:
            T_REF_PH = T_REF[ph]
            cells = row(R, P, E, ph)
            print(f"  ph{ph}")
            for mode, (s, b) in cells.items():
                print(f"     {mode:8s} {fmt(s, b)}")
