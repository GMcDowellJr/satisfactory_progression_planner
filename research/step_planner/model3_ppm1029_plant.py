# model3_ppm1029_plant.py -- model3_ppm1029.py plus two read-only ADDITIONS (2026-11-01), for plant_resize.py:
#   segcap (per-segment capacity, ported verbatim from canonical model3.py) inside simulate_steps, and a cut-down
#   evaluate() that makes the same run2.power_block calls as canonical model3.evaluate. No existing line changed.
# model3.py -- SESSION VARIANT 2026-10-29 (not canonical). Base: project step3-relief/model3.py (schedule + simulate_steps), segcap/evaluate omitted.
# Adds: FLOOR (qt switch), FLOOR_RATE, PPM (per-phase ppm target + next-phase carry-forward floor), STOCK_SLOTS (stock-ahead cap).
# Defaults (FLOOR=base, PPM={}, STOCK_SLOTS=0) reproduce the canonical numbers (P4 Cu 422/1148/1557, P5 1893, Fe 746).
# Session-only addition: FLOOR switch, default 'base' = canonical behaviour.
#   'base' : PA final floor >=1/min when fut > 0, else Q/T_PA (canonical)
#   'qt'   : PA final floor = Q/T_PA always (no carry-forward floor)
# REPO COPY: saved as model3_ppm1029.py (Project path step3-relief/ppm-2026-10-29/model3.py); nodes.py / ppm.py / cap.py
#   import it as `import model3_ppm1029 as M3` (EDIT (c)).
import math
import numpy as np
from collections import defaultdict
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # EDIT (a): sibling imports under python -I
import model2 as M
import run2
P = M.P
TAGS = {t['schematic_id']: t for t in run2.tags}
PACING = 'paced'
STRETCH = {4: 1.25, 5: 1.25}
FLOOR = 'base'
TRACE = {}
FLOOR_RATE = None   # callable item -> carry-forward floor rate; None = 1.0/min (canonical)
def fr_(p): return FLOOR_RATE(p) if FLOOR_RATE else 1.0
STOCK_SLOTS = 0   # >0: stock carried past this phase's own need is capped at slots x stack size (24 = Storage Container, 48 = Industrial)
PPM = {}   # per-phase parts-per-minute target; absent = 1.0 (canonical)
def nxt_(k, p):
    # carry-forward floor: ppm of the next phase whose PA bill uses p (FLOOR_RATE overrides when set)
    if FLOOR_RATE: return FLOOR_RATE(p)
    for kk in sorted(M.PA):
        if kk > k and p in M.PA[kk]: return PPM.get(kk, 1.0)
    return 1.0
def qt_(p): return FLOOR == 'qt' or (isinstance(FLOOR, (set, frozenset)) and p in FLOOR)

def gate(item):
    out = set()
    if item not in M.RID: return out
    prod, _ = M.solve({item: 1})
    for j, v in prod.items():
        if v > 1e-12:
            for rid in (M.RID[j], M.BLDG[M.producer(j)]):
                m = M.recipe_needs(rid)
                if m: out.add(m)
    return out
def own_gate(j):
    return {m for m in (M.recipe_needs(M.RID[j]), M.recipe_needs(M.BLDG[M.producer(j)])) if m}

def schedule(k, sel):
    ms = [t for t in run2.tags if t['phase'] == k and t['tier'] > 0 and sel(t)]
    ids = {t['schematic_id'] for t in ms}
    pre = {s: (set().union(*[gate(i) for i in TAGS[s]['cost']]) & ids) - {s} for s in ids}
    lvl = {}
    def L(s):
        if s not in lvl:
            lvl[s] = 0; lvl[s] = 1+max([L(p) for p in pre[s]], default=-1)
        return lvl[s]
    for s in ids: L(s)
    req = sorted([s for s in ids if TAGS[s]['tag'] == 'required'], key=lambda s: (lvl[s], TAGS[s]['tier'], s))
    ext = sorted([s for s in ids if TAGS[s]['tag'] != 'required'], key=lambda s: (lvl[s], TAGS[s]['tier'], s))
    tut = [t['schematic_id'] for t in run2.tags if t['phase'] == k and t['tier'] == 0 and sel(t)]
    T_PA = max(M.PA[k].values())/PPM.get(k, 1.0); Wpa = run2.W_bill(M.PA[k]); Rf = Wpa/T_PA
    W_ms = sum(run2.W_bill(TAGS[s]['cost']) for s in list(ids)+tut)
    base_T = T_PA*(Wpa+W_ms)/Wpa*STRETCH.get(k, 1.0)
    later = {p for kk in P if kk > k for p in M.PA[kk]}
    rate = {p: (max(nxt_(k, p), q/T_PA) if (p in later and not qt_(p)) else q/T_PA) for p, q in M.PA[k].items()}
    dl = {s: base_T for s in req+tut}
    for p, q in M.PA[k].items():
        for m in gate(p):
            if m in dl: dl[m] = min(dl[m], base_T-q/rate[p])
    req = sorted(req, key=lambda s: (lvl[s], dl[s], TAGS[s]['tier'], s))
    for i in range(len(req)-2, -1, -1):
        dl[req[i]] = min(dl[req[i]], dl[req[i+1]]) if lvl[req[i]] < lvl[req[i+1]] else dl[req[i]]
    for s in ext: dl[s] = base_T
    seq = tut+req+ext; cum = 0.0; Rm = 0.0
    for s in seq:
        cum += run2.W_bill(TAGS[s]['cost']); Rm = max(Rm, cum/max(dl[s], 1e-9))
    if PACING == 'serial': Rm = Rf
    t = 0.0; win = {}; segs = []
    def add_seg(name, members, rate_):
        nonlocal t
        if not members: return
        s0 = t
        for s in members:
            d = run2.W_bill(TAGS[s]['cost'])/rate_; win[s] = (t, t+d); t += d
        segs.append(dict(name=name, start=s0, end=t, members=members))
    add_seg('HUB upgrades', tut, Rm)
    for L_ in sorted({lvl[s] for s in req}):
        add_seg(f'Step {L_+1}', [s for s in req if lvl[s] == L_], Rm)
    add_seg('Extras (practical/optional)', ext, Rm)
    segs.append(dict(name='Project Assembly run', start=t, end=max(base_T, t), members=[]))
    return dict(segs=segs, win=win, lvl=lvl, ids=ids|set(tut), T=int(math.ceil(max(base_T, t))), base_T=base_T, Rf=Rf, T_PA=T_PA)

def simulate_steps(sel):
    bills, mb = run2.bills_for(sel)
    STOCK = {j for j in M.R if set(M.prodby[M.RID[j]]) & M.HIGH}
    LIFE = defaultdict(float)
    for k in P:
        prod, _ = M.solve(bills[k])
        for j, v in prod.items(): LIFE[j] += max(v, 0)
    C = defaultdict(float); S = defaultdict(float); made = defaultdict(float)
    paid = set(); out = {}
    for k in P:
        sc = schedule(k, sel); T = sc['T']; FQ = M.PA[k]; T_PA = sc['T_PA']
        t = np.arange(1, T+1)
        avail = {}
        for j in M.R:
            a = 0.0
            for m in own_gate(j):
                if m in sc['win']: a = max(a, sc['win'][m][1])
                elif m not in paid: a = math.inf
            avail[j] = a
        mdem = defaultdict(lambda: np.zeros(T))
        for s, (a0, a1) in sc['win'].items():
            i0, i1 = int(math.floor(a0)), min(T, max(int(math.ceil(a1)), int(math.floor(a0))+1))
            idx = np.arange(i0, i1)
            ov = np.clip(np.minimum(idx+1, a1)-np.maximum(idx, a0), 0, None) if a1 > a0 else (idx == i0).astype(float)
            ov = ov/ov.sum()
            for it, q in TAGS[s]['cost'].items(): mdem[it][i0:i1] += q*ov
        cons = {j: np.zeros(T) for j in M.R}; byp = {j: np.zeros(T) for j in M.R}
        rawc = defaultdict(lambda: np.zeros(T)); prof = {}; newC = {}
        for j in M.ORDER:
            need = (cons[j]-byp[j]).copy(); need[-1] += FQ.get(j, 0); need += mdem[j]
            a = avail[j]
            cum = np.cumsum(need)-S[j]
            if cum.max() > 1e-9 and math.isinf(a): print('WARN unavailable', k, j); a = 0
            span = np.maximum(t-a, 1e-9)
            ok = t > a+1e-9
            req = max(0, (cum[ok]/span[ok]).max()) if (cum.max() > 1e-9 and ok.any()) else 0
            fut = LIFE[j]-made[j]-bills[k].get(j, 0)
            if not qt_(j):
                floor = (max(nxt_(k, j), FQ[j]/T_PA) if fut > 1e-6 else FQ[j]/T_PA) if j in FQ else 0
            else:
                floor = FQ[j]/T_PA if j in FQ else 0
            r = max(C[j], req, floor) if (cum.max() > 1e-9 or j in FQ) else C[j]
            if j in FQ: TRACE[(k, j)] = dict(fut=fut, LIFE=LIFE[j], made=made[j], bill=bills[k].get(j, 0), C=C[j], req=req, floor=floor, r=r, S=S[j], avail=a)
            rem = max(LIFE[j]-made[j], (np.cumsum(need)-S[j]).max())
            if STOCK_SLOTS and j in STOCK: rem = min(rem, max((np.cumsum(need)-S[j]).max(), 0) + STOCK_SLOTS*M.stack.get(j, 0))
            if j in STOCK:
                cp = np.minimum(r*np.maximum(t-a, 0), rem)
            else:
                jit = np.maximum(need, 0)
                cp = np.maximum(np.cumsum(jit)-S[j], 0)
            m_ = (S[j]+cp-np.cumsum(need)).min()
            if m_ < -1e-6: print("WARN short", k, j, round(m_, 3))
            pr = np.diff(np.concatenate([[0], cp])); prof[j] = pr; newC[j] = max(C[j], pr.max() if len(pr) else 0) if j not in STOCK else (r if pr.max() > 1e-9 else C[j])
            o, ins, by = M.R[j]
            for i, v in ins.items(): (cons[i] if i in M.R else rawc[i])[:] += pr/o*v
            for b, v in by.items():
                if b in M.R: byp[b] += pr/o*v
                else: rawc[b] -= pr/o*v
        for j in M.R:
            made[j] += prof[j].sum(); S[j] += prof[j].sum()+byp[j].sum()-cons[j].sum()-bills[k].get(j, 0)
        paid |= sc['ids']
        # ADDED 2026-11-01: segcap block ported verbatim from canonical step3-relief/model3.py (read-only addition)
        segcap = []
        for sg in sc['segs']:
            e = min(T, max(1, int(math.ceil(sg['end']))))
            cap = {}
            for j in M.R:
                v = prof[j][:e].max() if e > 0 else 0
                if j in STOCK and v > 1e-9: v = newC[j]
                cap[j] = max(C[j], v)
            raw = {i: max(v[:e].max(), 0) for i, v in rawc.items()}
            hor = max(0, -rawc['Heavy Oil Residue'][:e].sum()/e) if 'Heavy Oil Residue' in rawc else 0
            a_, b_ = int(math.floor(sg['start'])), max(int(math.floor(sg['start']))+1, e)
            own = {j: prof[j][a_:b_].max() for j in M.R if prof[j][a_:b_].size and prof[j][a_:b_].max() > 1e-6}
            segcap.append(dict(seg=sg, cap=cap, raw=raw, hor=hor, own=own))
        out[k] = dict(sc=sc, S={j: S[j] for j in M.R}, prof=prof, cons=cons, byp=byp, rawc=dict(rawc), avail=avail, segcap=segcap)  # ADDED 2026-11-01: segcap
        C = defaultdict(float, {j: (max(C[j], prof[j].max()) if j not in STOCK else newC[j]) for j in M.R})
    return out, mb, bills, LIFE


# ADDED 2026-11-01: evaluate() power-block driver ported from canonical step3-relief/model3.py,
# reduced to the fields needed for the plant draw (machines, MW, gens, power_block calls). Same call sequence.
def evaluate(sel):
    res = simulate_steps(sel)[0]
    st = {}; rawcap = defaultdict(float); rows = []
    for k in P:
        sc = res[k]['sc']
        for sgc in res[k]['segcap']:
            sg = sgc['seg']
            mach = 0; mw = 0
            for j, c in sgc['cap'].items():
                if c > 1e-6:
                    l, n, cl, tot, w_ = M.size(j, c, k); mach += tot; mw += w_
            for r_, v in sgc['raw'].items(): rawcap[r_] = max(rawcap[r_], v)
            ext, emw = M.extraction(dict(rawcap), k)
            fuel_ok = k >= 4 or (k == 3 and any(TAGS.get(s, {}).get('name') == 'Petroleum Power' and sc['win'][s][1] <= sg['end']+1e-9 for s in sc['win']))
            pb = run2.power_block(k, mw+emw, sgc['hor'], st, 'A', fuel_ok=fuel_ok)
            if k >= 3 and fuel_ok: st['fuel'] = st.get('_fuel_now', 0)
            rows.append(dict(phase=k, segment=sg['name'], machines=mach, fac_mw=mw, ext_mw=emw, MW=pb['D_total'], gens=dict(pb['gens'])))
    return rows
