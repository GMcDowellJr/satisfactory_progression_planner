# relief.py -- step-level constraint-relief precompute (scratch; not repo code).
# Decided by Greg 2026-10-28: binding constraint is step-level (changes with phase and unlocks); constraints are
# resources incl. power; machines reported separately; option (a) one alternate per item in the step model.
#
# Per phase k, per segment s of model3 (operating point: all milestones, STRETCH P4/P5 x1.25):
#   t*      = minute in s where the largest raw share (raw draw / world capacity at phase k's extractor mark) peaks
#   d       = the factory's net outflow at t* (production + byproducts - consumption, per item): what it delivers
#             to milestones, PA and stock at that minute. Held fixed across all three solves.
#   base    = LP over standard recipes only (reproduces model3's raw draw at t*: the validation)
#   res     = LP over standard + alternates in reach by s, minimise the binding raw's share (+1e-4 x total raw share)
#   pow     = same recipe set, minimise MW (machines x base MW + extractor MW per unit at phase k's mark)
# Alternate in reach at s: its earliest HUB prerequisite (alternate_recipe_unlocks.csv) is paid by the end of s,
#   and its building is unlocked by then; every input is a modelled item or a raw. Hard drives not scheduled.
# Plant (2026-10-28 19:30): Fuel gens burn Fuel as an ITEM, made by the Fuel recipe (crude), Residual Fuel (HOR) or an alternate.
# Power counts as a resource: consumer MW x P is charged the plant's fuel/water at the phase's newest source
#   (P1 biomass: none, hand-fed; P2 coal; P3-5 Fuel from crude). Whole load at that source, HOR->Residual Fuel ignored.
# Binding raw = largest share of world capacity INCLUDING the plant draw, at t* (t* chosen on factory draw).
import csv, math, sys, json, io, contextlib
from collections import defaultdict, Counter
import numpy as np
from scipy.optimize import linprog
import pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))  # EDIT (a): sibling imports under python -I; outputs into this folder
import model2 as M, run2, model3 as M3

REPO = str(HERE.parents[1]) + '/'  # EDIT (a): was '/home/claude/gmcdowelljr/satisfactory_progression_planner/'
REF = REPO + 'planning_data/game/reference/'
WORLD = REPO + 'planning_data/world/configurations/default_502094/resource_assignments.csv'
NAME = {r['item_id']: M.nm(r['display_name']) for r in csv.DictReader(open(REF + 'items.csv'))}
RATE = {(r['extractor_class'], r['purity']): float(r['nominal_rate_min']) for r in csv.DictReader(open(REF + 'extraction_rates.csv'))}

# ---- world capacity per raw, per phase (normal-purity mix of the default world; all sockets in one site) ----
socks = Counter()
for r in csv.DictReader(open(WORLD)):
    sid, it = r['socket_id'], NAME.get(r['resource_descriptor'])
    if not it or it == 'Water' or 'Geyser' in sid or 'FrackingCore' in sid: continue
    socks[(it, 'well' if 'FrackingSatellite' in sid else 'node', r['purity'])] += 1
MARK = {1: 'Build_MinerMk1_C', 2: 'Build_MinerMk2_C', 3: 'Build_MinerMk2_C', 4: 'Build_MinerMk3_C', 5: 'Build_MinerMk3_C'}
def capacity(k):
    cap = Counter()
    for (it, kind, pur), n in socks.items():
        if kind == 'well':
            if k < 4: continue
            cap[it] += n*RATE[('Build_FrackingExtractor_C', pur)]
        elif it == 'Crude Oil':
            if k < 3: continue
            cap[it] += n*RATE[('Build_OilPump_C', pur)]
        else:
            if it == 'Uranium' and k < 4: continue
            cap[it] += n*min(RATE[(MARK[k], pur)], M.BELT[k][1])
    return cap
# extractor MW per unit at normal purity (model2.extraction rules)
def ext_mw(it, k):
    if it in M.MANUAL or it == 'Water': return 20/120 if it == 'Water' else 0
    if it == 'Crude Oil': return 40/120
    if it == 'Nitrogen Gas': return 150/6/60
    nm_, r, w = M.MINER[k]; return w/r

# ---- power plant draw per consumer MW, newest source per phase (D33; whole load at that source: approximation) ----
_fuel_crude = M.solve({'Fuel': 1})[1]['Crude Oil']
FUEL_CRUDE_PER_MW = 20/250*_fuel_crude
STEPS = json.load(open(HERE / 'steps_all_step2.json'))  # EDIT (a): was '/home/claude/pa/steps_all.json'; renamed copy of Project step2-milestones-power/steps_all.json (model3.py writes its own steps_all.json here)
def coal_cap(P):
    # coal gens are built in P2 and in P3 before Petroleum Power (run2.power_block); at P they scale with demand x P
    mw = max(r['MW'] for r in STEPS if r['phase'] == 2 or (r['phase'] == 3 and r['segment'] == 'Step 1'))
    return 75*math.ceil(mw*P/75 - 1e-9)

# ---- recipes: standard set (model2.RID) + alternates ----
rec = {r['recipe_id']: r for r in csv.DictReader(open(REF + 'recipes.csv'))}
by_disp = {r['display_name']: rid for rid, r in rec.items()}
unl = list(csv.DictReader(open(REF + 'alternate_recipe_unlocks.csv')))
alt_pre = {}; unmapped = []
for u in unl:
    rid = by_disp.get('Alternate: ' + u['recipe_name'])
    if rid: alt_pre[rid] = u['earliest_hub_prerequisite']
    else: unmapped.append(u['recipe_name'])
alts_all = [rid for rid, r in rec.items() if r['is_alternate'] == 'true']
no_pre = [rec[r]['display_name'] for r in alts_all if r not in alt_pre]
ITEMS = set(M.R)
RAWS = {'Iron Ore', 'Copper Ore', 'Limestone', 'Coal', 'Caterium Ore', 'Raw Quartz', 'Sulfur', 'Water', 'Crude Oil', 'Bauxite',
        'Nitrogen Gas', 'Uranium', 'SAM', 'Wood', 'Leaves', 'Mycelia'}   # world-drawn; every other item must net >= its demand (0 if none)
MS_BY_NAME = {t['name']: t['schematic_id'] for t in run2.tags}
def producer_of(rid):
    p = M.prodby.get(rid)
    return sorted(p)[0] if p else None
def mw_machine(rid):
    b = producer_of(rid); return M.PB.get(b, 0) or M.VP.get(rid, 0)
skipped = {}
def alt_ok(rid):
    io_ = M.IO[rid]; b = producer_of(rid)
    if b not in M.BLDG: skipped[rec[rid]['display_name']] = f'producer {b}'; return False
    hand = [i for i in io_['rin'] if i in M.MANUAL or i in ('Biomass', 'Solid Biofuel')]
    if hand:   # hand-gathered inputs are uncapped here, so they would read as free coal (D29: gathering is its own output)
        skipped[rec[rid]['display_name']] = 'hand-gathered input: ' + ', '.join(hand); return False
    return True
ALTS = [rid for rid in alts_all if alt_ok(rid)]   # placement by place.py (docs-regenerated deps + sub-components)
import place as PL

FLUIDS = {'Crude Oil', 'Nitrogen Gas', 'Water'}
HAND = {'Wood', 'Leaves', 'Mycelia'}
def unit(r, k):
    """one full belt (solids) or pipe (fluids) of phase k's best tier: the usage unit for step pressure (Greg 2026-10-29)."""
    return M.PIPE[k][1] if r in FLUIDS else M.BELT[k][1]
TANG = [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.75, 0.9, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0, 10.0, 14.0]
def pressure(raw, k):
    """step pressure = sum over world-drawn raws of usage^2, usage = draw / unit (hand-gathered raws excluded)."""
    return sum((max(v, 0)/unit(r, k))**2 for r, v in raw.items() if r not in HAND)

def lp(d, recipes, k, cap, obj, bind=None, P=1.0, plant=True, src=None):
    """x = machine-equivalents per recipe at 100% clock. net item flow >= d; raws free (drawn)."""
    raws = sorted(RAWS)
    items = sorted({i for rid in recipes for i in list(M.IO[rid]['rin']) + list(M.IO[rid]['rout']) if i not in RAWS} | set(d) | {'Fuel'})
    ii = {x: i for i, x in enumerate(items)}; ri = {x: i for i, x in enumerate(raws)}
    n = len(recipes); A = np.zeros((len(items), n)); Rw = np.zeros((len(raws), n))
    for c, rid in enumerate(recipes):
        io_ = M.IO[rid]
        for it, v in io_['rout'].items():
            if it in ii: A[ii[it], c] += v
            else: Rw[ri[it], c] -= v
        for it, v in io_['rin'].items():
            if it in ii: A[ii[it], c] -= v
            else: Rw[ri[it], c] += v
    mw = (np.array([mw_machine(rid) for rid in recipes]) + Rw.T @ np.array([ext_mw(r, k) for r in raws]))*P
    # plant (carry-forward, D31/D33; dispatch is NOT a choice): mode 'coal' = all load on coal gens (P2, P3 before
    # Petroleum Power); mode 'mixed' = carried coal gens run at a fixed load `coal_load` (constant draw, added after the
    # solve), the excess over it goes to fuel (column m_fuel >= MW - coal_load). P1: biomass, hand-fed, no world draw.
    src = (src or {}) if plant else {}
    mode = src.get('mode'); pc = 1 if mode == 'mixed' else 0
    const = {}
    if mode == 'coal':
        Rw[ri['Coal']] += 15/75*mw; Rw[ri['Water']] += 45/75*mw
    Rw = np.hstack([Rw, np.zeros((len(raws), pc))]); A = np.hstack([A, np.zeros((len(A), pc))])
    if mode == 'mixed':
        A[items.index('Fuel'), n] -= 20/250   # Fuel gens burn 20 Fuel/min per 250 MW
        const = {'Coal': 15/75*src['coal_load'], 'Water': 45/75*src['coal_load']}
    dv = np.array([d.get(x, 0.0) for x in items])
    share = np.array([1/cap[r] if cap.get(r) else 0.0 for r in raws])     # per unit of raw drawn
    mwx = np.concatenate([mw, np.zeros(pc)])
    if obj == 'res':
        c = 1e-4*(Rw.T @ share) + (Rw[ri[bind]]*share[ri[bind]] if bind else 0)
    elif obj == 'pow':
        c = mwx + 1e-6*(Rw.T @ share)
    else:
        c = Rw.T @ share
    # net draw of every world raw >= 0: a byproduct raw (water) may offset its own input, never earn credit
    Aub = np.vstack([-A, -Rw]); bub = np.concatenate([-dv, np.zeros(len(raws))])
    if pc:   # m_fuel >= MW - coal_load
        Aub = np.vstack([Aub, np.concatenate([mw, [-1.0]])]); bub = np.concatenate([bub, [src['coal_load']]])
    nz = 0
    if obj == 'press':
        # min sum_r u_r^2 by tangent cuts: z_r >= 2 u0 u_r - u0^2, u_r = (Rw_r x + const_r) / unit_r   (outer LP approximation)
        prs = [r_ for r_ in raws if r_ not in HAND]; nz = len(prs)
        c = np.concatenate([1e-6*mwx, np.ones(nz)])
        Aub = np.hstack([Aub, np.zeros((len(Aub), nz))]); rows = []; rhs = []
        for zi, r_ in enumerate(prs):
            un = unit(r_, k); cr = const.get(r_, 0.0)
            for u0 in TANG:
                row = np.zeros(n+pc+nz); row[:n+pc] = 2*u0/un*Rw[ri[r_]]; row[n+pc+zi] = -1.0
                rows.append(row); rhs.append(u0*u0 - 2*u0*cr/un)
        Aub = np.vstack([Aub, np.array(rows)]); bub = np.concatenate([bub, rhs])
    res = linprog(c, A_ub=Aub, b_ub=bub, bounds=[(0, None)]*(n+pc+nz), method='highs')
    if res.status != 0:
        print('LP FAIL', obj, k, res.status, res.message); return None
    x = res.x[:n+pc]; raw = {r_: v + const.get(r_, 0) for r_, v in zip(raws, Rw @ x)}
    xw = x[:n] @ mw
    plant_draw = {}
    if mode == 'coal': plant_draw = {'Coal': 15/75*xw, 'Water': 45/75*xw}
    if mode == 'mixed':   # crude attributed to the plant: Fuel-recipe crude x plant share of all Fuel made
        fuel_made = sum(x[c]*M.IO[r_]['rout'].get('Fuel', 0) for c, r_ in enumerate(recipes))
        crude_f = sum(x[c]*M.IO[r_]['rin'].get('Crude Oil', 0) for c, r_ in enumerate(recipes) if M.IO[r_]['rout'].get('Fuel', 0) > 0)
        plant_draw = {**const, 'Crude Oil': crude_f*(20/250*x[n])/fuel_made if fuel_made > 1e-9 else 0.0}
    return dict(x={recipes[c]: x[c] for c in range(n) if x[c] > 1e-7}, raw=raw, mw=float(mw @ x[:n]), mach=float(x[:n].sum()), plant=plant_draw,
                share={r: raw[r]/cap[r] for r in raws if cap.get(r) and raw[r] > 1e-9}, press=pressure(raw, k))

def main():
    with contextlib.redirect_stdout(io.StringIO()):
        res, _ = M3.simulate_steps(run2.SCEN['all'])
    STD = sorted(set(M.RID.values()))
    out = []; checks = []
    for k in M.P:
        cap = capacity(k); r3 = res[k]; sc = r3['sc']
        win_end = {TAGS_name: sc['win'][sid][1] for sid, TAGS_name in [(s, M3.TAGS[s]['name']) for s in sc['win']]}
        paid_before = {t['name'] for t in run2.tags if t['phase'] < k}
        T = sc['T']
        for sg in sc['segs']:
            a_, e_ = int(math.floor(sg['start'])), max(int(math.floor(sg['start']))+1, min(T, int(math.ceil(sg['end']))))
            rawc = r3['rawc']
            def top_share(t):
                return max(((rawc[r][t]/cap[r], r) for r in rawc if r in cap and cap[r] > 0 and rawc[r][t] > 0), default=(0, None))
            ts = max(range(a_, e_), key=lambda t: top_share(t)[0])
            sh, bind = top_share(ts)
            d = {j: r3['prof'][j][ts]+r3['byp'][j][ts]-r3['cons'][j][ts] for j in M.R}
            d = {j: v for j, v in d.items() if abs(v) > 1e-9}   # negative = drawn from stock at t* (kept: same stock use in every solve)
            # in reach by segment end
            paid = paid_before | {n_ for n_, e in win_end.items() if e <= sg['end']+1e-9}
            clk = PL.Clock(k, sc); memo = {}
            reach = [rid for rid in ALTS if PL.alt_time(rid, clk, memo)[0] <= sg['end']+1e-6]
            base = lp(d, STD, k, cap, 'base', plant=False)
            checks.append((k, sg['name'], bind, sh, base['share'].get(bind, 0) if base else None))
            fuel_ok = k >= 4 or (k == 3 and 'Petroleum Power' in paid)   # fuel gens open at 5-5
            for P in PS:
                if k == 1: src = {}
                elif not fuel_ok: src = dict(mode='coal')
                else:
                    b0 = lp(d, STD, k, cap, 'base', P=P, plant=False)
                    src = dict(mode='mixed', coal_load=min(coal_cap(P), b0['mw']), fuel_crude_per_mw=FUEL_CRUDE_PER_MW)
                STDp = STD + (['Recipe_ResidualFuel_C'] if src.get('mode') == 'mixed' else [])
                bp = lp(d, STDp, k, cap, 'base', P=P, src=src)
                bind_p, sh_p = max(bp['share'].items(), key=lambda x: x[1])
                row = dict(phase=k, segment=sg['name'], P=P, minute=ts, bind=bind_p, share=sh_p, reach=len(reach),
                           base=dict(share=sh_p, mw=bp['mw'], mach=bp['mach'], plant_part=plant_part(bp, bind_p, src)))
                for obj in ('res', 'pow'):
                    r_ = lp(d, STDp+reach, k, cap, obj, bind_p, P=P, src=src)
                    used = sorted(rec[rid]['display_name'].replace('Alternate: ', '') for rid in r_['x'] if rid in reach)
                    split = sorted({it for rid in r_['x'] if rid in reach for it, v in M.IO[rid]['rout'].items()
                                    if v > 0 and len([q for q in r_['x'] if M.IO[q]['rout'].get(it, 0) > 0]) > 1})
                    nb = max(r_['share'].items(), key=lambda x: x[1])
                    # leave-one-out: what each picked alternate carries (re-solve without it; same objective)
                    met = (lambda q: q['share'].get(bind_p, 0)) if obj == 'res' else (lambda q: q['mw'])
                    full = met(r_); loo = []
                    for rid in [q for q in r_['x'] if q in reach]:
                        q = lp(d, STDp+[z for z in reach if z != rid], k, cap, obj, bind_p, P=P, src=src)
                        loo.append([rec[rid]['display_name'].replace('Alternate: ', ''), (met(q)-full)/max(met(bp), 1e-12)])
                    loo.sort(key=lambda z: -z[1])
                    row[obj] = dict(alts=used, share=r_['share'].get(bind_p, 0), mw=r_['mw'], mach=r_['mach'], new_bind=nb[0], new_share=nb[1], split=split,
                                    loo=loo, other_share=r_['share'].get(bind_p, 0))
                out.append(row)
    return out, checks

PS = (1.0, 5.0)
def plant_part(r_, raw, src):
    v = r_['plant'].get(raw, 0); tot = r_['raw'][raw]
    return v/tot if tot > 1e-9 else 0

def bldg_paid(rid, paid):
    m = M.recipe_needs(M.BLDG[producer_of(rid)])
    return m is None or M.sch[m]['display_name'] in paid

if __name__ == '__main__':
    out, checks = main()
    print('VALIDATION (binding share: model3 at t* vs base LP)')
    for c in checks: print(f"  P{c[0]} {c[1][:28]:28s} {c[2]:12s} model3 {c[3]:.4f}  LP {c[4]:.4f}")
    json.dump(out, open(HERE / 'relief.json', 'w', newline="\n"), indent=1)  # EDIT (b)(d): LF; was cwd
    print('skipped:', skipped)
    print(f"\nalternates usable: {len(ALTS)}; no prerequisite row: {len(no_pre)}; skipped (outside model): {len(skipped)}; names unmatched: {unmapped}")
