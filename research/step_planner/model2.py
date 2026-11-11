# model2.py -- PA walk-back step 2: milestones (tagged) + per-phase power block.
# Exploration script, not repo code. Reads repo reference CSVs (read-only) from D.
# Factory model = stockpile_midhigh policy (HYB on), extended recipe set, bill = PA + milestones.
# Power block = steady-state per phase, generator mix per Greg 2026-10-27, iterated to fixed point.
import csv, math, sys, io, contextlib
import numpy as np
from collections import defaultdict
sys.argv = ['x']
with contextlib.redirect_stdout(io.StringIO()):
    import rerun
D = rerun.D
nm = lambda s: 'Screw' if s == 'Screws' else s
EXP = 1.321929

# ---------------- reference data ----------------
rec = {r['recipe_id']: r for r in csv.DictReader(open(D+'recipes.csv'))}
IO = defaultdict(lambda: {'in': {}, 'out': {}, 'rin': {}, 'rout': {}})
for r in csv.DictReader(open(D+'recipe_io.csv')):
    d = 'in' if r['direction'] == 'input' else 'out'
    IO[r['recipe_id']][d][nm(r['item_name'])] = float(r['amount_per_cycle'])
    IO[r['recipe_id']]['r'+d][nm(r['item_name'])] = float(r['rate_per_min'])
prodby = defaultdict(set)
for r in csv.DictReader(open(D+'recipe_producers.csv')): prodby[r['recipe_id']].add(r['producer_name'])
form = {nm(r['display_name']): r['form'] for r in csv.DictReader(open(D+'items.csv'))}
stack = {nm(r['display_name']): float(r['cached_stack_size'] or 0) for r in csv.DictReader(open(D+'items.csv'))}
PB = {r['display_name']: float(r['base_power_mw']) for r in csv.DictReader(open(D+'production_buildings.csv'))}
VP = {r['recipe_id']: float(r['power_mean_mw']) for r in csv.DictReader(open(D+'recipe_variable_power.csv'))}
sch = {r['schematic_id']: r for r in csv.DictReader(open(D+'schematics.csv'))}
cost = defaultdict(dict)
for r in csv.DictReader(open(D+'schematic_costs.csv')): cost[r['schematic_id']][nm(r['item_name'])] = float(r['amount'])
unl_by_rec = defaultdict(list); unl_by_sch = defaultdict(list)
for r in csv.DictReader(open(D+'schematic_recipe_unlocks.csv')):
    unl_by_rec[r['recipe_id']].append(r['schematic_id']); unl_by_sch[r['schematic_id']].append(r['recipe_id'])
GEN = {}
for r in csv.DictReader(open(D+'generator_fuels.csv')): GEN[(r['generator_class'], r['fuel_item_name'])] = r

# ---------------- recipe set ----------------
def pick_base(p):          # same rule as rerun.py
    if p == 'Ficsite Ingot': return 'Recipe_FicsiteIngot_AL_C'
    c = [rid for rid, x in IO.items() if p in x['out'] and rec.get(rid, {}).get('is_alternate') == 'false' and (p == 'Excited Photonic Matter' or x['in'])]
    if len(c) > 1: c = [r for r in c if rec[r]['display_name'].startswith(p)]
    assert len(c) == 1, (p, c); return c[0]
RID = {p: pick_base(p) for p in rerun.R}
EXTRA = {'Gas Filter': 'Recipe_FilterGasMask_C', 'Fabric': 'Recipe_Fabric_C', 'SAM Fluctuator': 'Recipe_SAMFluctuator_C',
         'Solid Biofuel': 'Recipe_Biofuel_C', 'Biomass': 'Recipe_Biomass_Wood_C', 'Fuel': 'Recipe_LiquidFuel_C',
         'Encased Uranium Cell': 'Recipe_UraniumCell_C', 'Sulfuric Acid': 'Recipe_SulfuricAcid_C',
         'Uranium Fuel Rod': 'Recipe_NuclearFuelRod_C'}
RID.update(EXTRA)
R = {}
for p, rid in RID.items():
    x = IO[rid]; o = x['out'][p]
    ins = dict(x['in']); by = {k: v for k, v in x['out'].items() if k != p}
    for k in list(by):                       # net same-item in/out (Encased Uranium Cell: Sulfuric Acid 8 in / 2 out)
        if k in ins: ins[k] -= by.pop(k)
    R[p] = (o, ins, by)
ITEMS = list(R); IDX = {k: i for i, k in enumerate(ITEMS)}
A = np.zeros((len(ITEMS), len(ITEMS)))
for j, p in enumerate(ITEMS):
    o, ins, by = R[p]; A[IDX[p], j] += o
    for k, v in list(ins.items()) + [(k, -v) for k, v in by.items()]:
        if k in IDX: A[IDX[k], j] -= v
def solve(dem):
    d = np.zeros(len(ITEMS))
    for k, v in dem.items(): d[IDX[k]] += v
    x = np.linalg.solve(A, d)
    prod = {ITEMS[j]: x[j]*R[ITEMS[j]][0] for j in range(len(ITEMS)) if abs(x[j]) > 1e-12}
    raw = defaultdict(float)
    for j, p in enumerate(ITEMS):
        o, ins, by = R[p]
        for k, v in ins.items():
            if k not in IDX: raw[k] += x[j]*v
        for k, v in by.items():
            if k not in IDX: raw[k] -= x[j]*v
    return prod, raw
def producer(p): return sorted(prodby[RID[p]])[0]
def mrate(p): return IO[RID[p]]['rout'][p]
def mw_per_machine(p, clock_pct):
    b = producer(p); base = PB.get(b, 0) or VP.get(RID[p], 0)
    return base*(clock_pct/100.0)**EXP

# ---------------- milestones ----------------
def tier_phase(t): return 1 if t <= 2 else 2 if t <= 4 else 3 if t <= 6 else 4 if t <= 8 else 5
MIL = [s for s in sch.values() if s['schematic_type'] in ('EST_Milestone', 'EST_Tutorial')]
def owner(sid):            # schematic that must be purchased to get this unlock; None = free (MAM/start/tutorial-free)
    s = sch.get(sid)
    if s is None: return 'UNKNOWN'
    t = s['schematic_type']
    if t in ('EST_Milestone', 'EST_Tutorial'): return sid
    if t == 'EST_Custom':
        parts = sid.replace('Schematic_', '').replace('_C', '').split('-')
        if len(parts) == 3:                    # Schematic_5-1-1_C -> Schematic_5-1_C (id-convention inference)
            par = f"Schematic_{parts[0]}-{parts[1]}_C"
            if par in sch: return par
        return None                            # starting blueprints / cosmetic
    return None                                # MAM treated as available (handoff assumption)
def recipe_needs(rid):     # milestone required for a recipe, or None if any free source exists
    owners = [owner(s) for s in unl_by_rec[rid]]
    if not owners or any(o is None for o in owners): return None
    return sorted(owners, key=lambda s: int(sch[s]['tech_tier']))[0]
BLDG = {'Constructor': 'Recipe_ConstructorMk1_C', 'Smelter': 'Recipe_SmelterBasicMk1_C', 'Assembler': 'Recipe_AssemblerMk1_C',
        'Foundry': 'Recipe_SmelterMk1_C', 'Refinery': 'Recipe_OilRefinery_C', 'Manufacturer': 'Recipe_ManufacturerMk1_C',
        'Blender': 'Recipe_Blender_C', 'Particle Accelerator': 'Recipe_HadronCollider_C', 'Converter': 'Recipe_Converter_C',
        'Quantum Encoder': 'Recipe_QuantumEncoder_C', 'Packager': 'Recipe_Packager_C'}

def tag_milestones(used_items, power_bldgs, practical_bldgs):
    """required: unlocks a recipe/building the plan cannot run without (closure over required bills).
       practical: belts/lifts/splitters/storage/miner upgrades -- plan runs without them, worse.
       optional: everything else."""
    req = {}; prac = {}
    def add_rec(rid, why, tgt):
        m = recipe_needs(rid)
        if m: tgt.setdefault(m, set()).add(why)
    changed = True; items = set(used_items)
    while changed:
        changed = False
        for p in sorted(items):
            if p in RID:
                add_rec(RID[p], f"recipe {p}", req); add_rec(BLDG[producer(p)], f"building {producer(p)}", req)
        for b, why in power_bldgs: add_rec(b, why, req)
        # closure: items in required milestone bills must themselves be makeable
        for m in list(req):
            for it in cost[m]:
                if it not in items: items.add(it); changed = True
    for b, why in practical_bldgs: add_rec(b, why, prac)
    out = []
    for s in sorted(MIL, key=lambda s: (int(s['tech_tier']), s['schematic_id'])):
        sid = s['schematic_id']
        if s['schematic_type'] == 'EST_Tutorial': tag, why = 'required', {'HUB tutorial chain (Space Elevator gate)'}
        elif sid in req: tag, why = 'required', req[sid]
        elif sid in prac: tag, why = 'practical', prac[sid]
        else: tag, why = 'optional', set()
        out.append(dict(schematic_id=sid, name=s['display_name'], tier=int(s['tech_tier']),
                        phase=tier_phase(int(s['tech_tier'])), tag=tag, reason='; '.join(sorted(why)),
                        cost=cost[sid]))
    return out, items

# ---------------- factory stockpile sim (stockpile_midhigh policy, HYB on) ----------------
PA = {}
for r in csv.DictReader(open(D+'project_assembly_requirements.csv')): PA.setdefault(int(r['phase']), {})[r['item_name']] = float(r['quantity_default_1x'])
P = sorted(PA)
HIGH = {'Assembler', 'Manufacturer', 'Particle Accelerator', 'Quantum Encoder', 'Converter', 'Blender'}
def topo():
    edges = defaultdict(set)
    for p, (o, ins, by) in R.items():
        for i in list(ins) + list(by):
            if i in R: edges[p].add(i)
    order = []; seen = set()
    def visit(n):
        if n in seen: return
        seen.add(n)
        for m in edges[n]: visit(m)
        order.append(n)
    for n in R: visit(n)
    return order[::-1]
ORDER = topo()
def simulate(bills, T_over=None):
    """bills[k] = {item: qty delivered by end of phase k}; PA finals carry the >=1/min floor.
    T_over[k] (optional, minutes): phase horizon, e.g. the stretched base time. The PA-final floor stays on
    the PA-only time T_PA (PA lines keep their PA-only rate; the extra time goes to milestones).
    PA quota is delivered at the last minute (as stockpile_midhigh). Non-PA quota (milestones) is drawn
    uniformly over the phase -- delivering it in the last minute would size JIT lines for the whole bill in 1 min."""
    STOCK = {j for j in R if set(prodby[RID[j]]) & HIGH}
    LIFE = defaultdict(float)
    for k in P:
        prod, _ = solve(bills[k])
        for j, v in prod.items(): LIFE[j] += max(v, 0)
    C = defaultdict(float); S = defaultdict(float); made = defaultdict(float); hist = {}
    for k in P:
        Q = bills[k]; FQ = PA[k]; T_PA = int(max(FQ.values()))
        T = int(round(T_over[k])) if T_over else T_PA
        cons = {j: np.zeros(T) for j in R}; byp = {j: np.zeros(T) for j in R}
        rawc = defaultdict(lambda: np.zeros(T)); prof = {}; newC = {}
        t = np.arange(1, T+1)
        for j in ORDER:
            need = (cons[j]-byp[j]).copy(); need[-1] += FQ.get(j, 0); need += (Q.get(j, 0)-FQ.get(j, 0))/T
            cum = np.cumsum(need)-S[j]
            req = max(0, (cum/t).max()) if cum.max() > 1e-9 else 0
            fut = LIFE[j]-made[j]-Q.get(j, 0)
            floor = (1.0 if fut > 1e-6 else FQ[j]/T_PA) if j in FQ else 0
            r = max(C[j], req, floor)
            rem = max(LIFE[j]-made[j], (np.cumsum(need)-S[j]).max())
            if j in STOCK:
                cp = np.minimum(r*t, rem)
            else:
                jit = np.maximum(need, 0)
                pr0 = np.diff(np.concatenate([[0], np.maximum(np.cumsum(jit)-S[j], 0)]))
                r = max(C[j], pr0.max()); cp = np.cumsum(pr0)
            m_ = (S[j]+cp-np.cumsum(need)).min()
            if m_ < -1e-6: print("WARN", k, j, round(m_, 3))
            pr = np.diff(np.concatenate([[0], cp])); prof[j] = pr; newC[j] = r
            o, ins, by = R[j]
            for i, v in ins.items(): (cons[i] if i in R else rawc[i])[:] += pr/o*v
            for b, v in by.items():
                if b in R: byp[b] += pr/o*v
                else: rawc[b] -= pr/o*v
        for j in R:
            made[j] += prof[j].sum(); S[j] += prof[j].sum()+byp[j].sum()-cons[j].sum()-Q.get(j, 0)
        hist[k] = dict(T=T, C=newC, S={j: S[j] for j in R},
                       raw_peak={i: v.max() for i, v in rawc.items()},
                       raw_avg={i: v.sum()/T for i, v in rawc.items()},
                       made={j: prof[j].sum() for j in R if prof[j].sum() > 1e-9})   # units made in this phase (for machine-minutes)
        C = defaultdict(float, newC)
    return hist, STOCK

# ---------------- machines (machines.py rules) ----------------
BELT = {1: ('Mk.2', 120), 2: ('Mk.3', 270), 3: ('Mk.4', 480), 4: ('Mk.5', 780), 5: ('Mk.6', 1200)}
PIPE = {1: ('Pipe Mk.1', 300), 2: ('Pipe Mk.1', 300), 3: ('Pipe Mk.2', 600), 4: ('Pipe Mk.2', 600), 5: ('Pipe Mk.2', 600)}
def size(p, cap, k):
    mr = mrate(p); scale = cap/mr; rr = IO[RID[p]]
    flows = [(v*scale, form.get(i, 'solid')) for d in ('rin', 'rout') for i, v in rr[d].items()]
    need = [1]
    s = [f for f, fm in flows if fm == 'solid']; fl = [f for f, fm in flows if fm != 'solid']
    if s: need.append(math.ceil(max(s)/BELT[k][1]-1e-9))
    if fl: need.append(math.ceil(max(fl)/PIPE[k][1]-1e-9))
    lines = max(need); per = cap/lines; n = math.ceil(per/mr-1e-9)
    clock = math.ceil(per/(n*mr)*1e6)/1e4
    return lines, n, clock, lines*n, lines*n*mw_per_machine(p, clock)

# ---------------- extraction (assumption: normal nodes, 100% clock) ----------------
MINER = {1: ('Miner Mk.1', 60, 5), 2: ('Miner Mk.2', 120, 15), 3: ('Miner Mk.2', 120, 15), 4: ('Miner Mk.3', 240, 45), 5: ('Miner Mk.3', 240, 45)}
MANUAL = {'Wood', 'Mycelia', 'Leaves'}
def extraction(rates, k):
    out = {}; mw = 0
    for res, v in rates.items():
        if v <= 1e-9 or res in MANUAL or res == 'Heavy Oil Residue': continue
        if res == 'Water': n = math.ceil(v/120-1e-9); e = ('Water Extractor', n, 20*n)
        elif res == 'Crude Oil': n = math.ceil(v/120-1e-9); e = ('Oil Extractor', n, 40*n)
        elif res == 'Nitrogen Gas':
            n = math.ceil(v/60-1e-9); pz = math.ceil(n/6); e = (f'Well Extractor (+{pz} Pressurizer)', n, 150*pz)
        else:
            nmn, r, w = MINER[k]; n = math.ceil(v/r-1e-9); e = (nmn, n, w*n)
        out[res] = e; mw += e[2]
    return out, mw
