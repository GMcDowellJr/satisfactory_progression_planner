# model3.py -- step-level PA walk-back (phase -> step). Exploration script, not repo code.
# Builds on model2 (recipes, solve, sizing, extraction) and run2 (tags, bills, power_block, W_bill).
# Decisions used: option (a) 2026-10-27 14:32 -- PA lines keep their PA-only rate; phase length = base time.
#
# Per phase k:
#   R_f   = W_bill(PA_k) / T_PA_k                    machine-minute rate of the PA-only factory
#   order = required milestones by dependency level, then tier; then practical/optional ("extras")
#   each milestone takes W_bill(cost)/R_f minutes, paid serially; its bill is drawn uniformly over that window
#   step  = one dependency level of required milestones; extras = one segment; then the PA run to base time
#   an item can be produced only after the milestone unlocking its recipe and building is paid (availability a_j)
#   PA quota delivered at phase end; PA-final floor as model2 (>=1/min with later use, else Q/T_PA)
#   installed capacity at time t = max(capacity carried in, running max of the production rate up to t)
#
# 2026-10-27 15:05 changes (Greg approved 15:00):
#   - milestone bill binned by exact minute overlap with its window (was floor(start): demand could land
#     before an item's unlock, inflating required rates; non-monotone stretch response)
#   - STRETCH: per-phase multiplier on base time; operating point P4 x1.25, P5 x1.25
#   - reuse_floor reported per segment (not a model rule): per building type, running peak within the phase of the
#     machines needed for each segment's own rates; lower bound assuming free reassignment within building type;
#     capacity carried in from earlier phases excluded
import csv, math
import numpy as np
from collections import defaultdict
import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))  # EDIT (a): sibling imports under python -I; outputs into this folder
import model2 as M
import run2
P = M.P
TAGS = {t['schematic_id']: t for t in run2.tags}
PACING = 'paced'   # 'paced': required milestones at the slowest rate meeting PA deadlines, extras spread to phase end; 'serial': all at the PA-factory rate R_f
STRETCH = {4: 1.25, 5: 1.25}   # base-time multiplier per phase (Greg 2026-10-27 15:00); absent = 1.0

def gate(item):
    """Milestones that must be paid before `item` can be made (its whole standard chain)."""
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
    tut = [t['schematic_id'] for t in run2.tags if t['phase'] == k and t['tier'] == 0 and sel(t)]   # HUB tutorials: P1, first
    T_PA = max(M.PA[k].values()); Wpa = run2.W_bill(M.PA[k]); Rf = Wpa/T_PA
    W_ms = sum(run2.W_bill(TAGS[s]['cost']) for s in list(ids)+tut)
    base_T = T_PA*(Wpa+W_ms)/Wpa*STRETCH.get(k, 1.0)
    later = {p for kk in P if kk > k for p in M.PA[kk]}
    rate = {p: (1.0 if p in later else q/T_PA) for p, q in M.PA[k].items()}
    # deadline per milestone: latest finish that still lets every PA part it gates finish by base_T at its rate
    dl = {s: base_T for s in req+tut}
    for p, q in M.PA[k].items():
        for m in gate(p):
            if m in dl: dl[m] = min(dl[m], base_T-q/rate[p])
    req = sorted(req, key=lambda s: (lvl[s], dl[s], TAGS[s]['tier'], s))
    for i in range(len(req)-2, -1, -1):                 # a milestone must finish before anything after it that it precedes
        dl[req[i]] = min(dl[req[i]], dl[req[i+1]]) if lvl[req[i]] < lvl[req[i+1]] else dl[req[i]]
    for s in ext: dl[s] = base_T                        # extras gate no PA part; due by phase end
    seq = tut+req+ext; cum = 0.0; Rm = 0.0
    for s in seq:                                       # PACED: slowest single constant rate meeting every deadline
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
    add_seg('Extras (practical/optional)', ext, Rm)    # paid after the required steps, same rate
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
        # availability: minute index from which an item can be produced
        avail = {}
        for j in M.R:
            a = 0.0
            for m in own_gate(j):
                if m in sc['win']: a = max(a, sc['win'][m][1])
                elif m not in paid: a = math.inf
            avail[j] = a
        # milestone demand profile
        mdem = defaultdict(lambda: np.zeros(T))
        for s, (a0, a1) in sc['win'].items():
            # minute index i covers [i, i+1); draw = overlap with [a0, a1) / window length (exact; no draw before a0)
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
            floor = (1.0 if fut > 1e-6 else FQ[j]/T_PA) if j in FQ else 0
            r = max(C[j], req, floor) if (cum.max() > 1e-9 or j in FQ) else C[j]
            rem = max(LIFE[j]-made[j], (np.cumsum(need)-S[j]).max())
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
        # installed capacity at each segment end
        segcap = []
        for sg in sc['segs']:
            e = min(T, max(1, int(math.ceil(sg['end']))))
            cap = {}
            for j in M.R:
                v = prof[j][:e].max() if e > 0 else 0
                if j in STOCK and v > 1e-9: v = newC[j]          # stockpile lines run at their capacity once started
                cap[j] = max(C[j], v)
            raw = {i: max(v[:e].max(), 0) for i, v in rawc.items()}
            hor = max(0, -rawc['Heavy Oil Residue'][:e].sum()/e) if 'Heavy Oil Residue' in rawc else 0
            # segment's own rates (reuse floor input): peak production rate inside this segment's minutes
            a_, b_ = int(math.floor(sg['start'])), max(int(math.floor(sg['start']))+1, e)
            own = {j: prof[j][a_:b_].max() for j in M.R if prof[j][a_:b_].size and prof[j][a_:b_].max() > 1e-6}
            segcap.append(dict(seg=sg, cap=cap, raw=raw, hor=hor, own=own))
        for j in M.R:
            made[j] += prof[j].sum(); S[j] += prof[j].sum()+byp[j].sum()-cons[j].sum()-bills[k].get(j, 0)
        paid |= sc['ids']
        out[k] = dict(sc=sc, segcap=segcap, S={j: S[j] for j in M.R}, prof=prof, cons=cons, byp=byp, rawc=dict(rawc), avail=avail)
        C = defaultdict(float, {j: segcap[-1]['cap'][j] for j in M.R})
    return out, mb

def evaluate(sel):
    res, mb = simulate_steps(sel)
    st = {}; rawcap = defaultdict(float); rows = []; prev = None
    for k in P:
        sc = res[k]['sc']; floor_by = defaultdict(int)
        for sgc in res[k]['segcap']:
            sg = sgc['seg']
            mach = 0; mw = 0; lines = {}
            for j, c in sgc['cap'].items():
                if c > 1e-6:
                    l, n, cl, tot, w_ = M.size(j, c, k); mach += tot; mw += w_; lines[j] = tot
            own_by = defaultdict(int)
            for j, c in sgc['own'].items(): own_by[M.producer(j)] += M.size(j, c, k)[3]
            for b, v in own_by.items(): floor_by[b] = max(floor_by[b], v)
            for r_, v in sgc['raw'].items(): rawcap[r_] = max(rawcap[r_], v)
            ext, emw = M.extraction(dict(rawcap), k)
            fuel_ok = k >= 4 or (k == 3 and any(TAGS.get(s, {}).get('name') == 'Petroleum Power' and sc['win'][s][1] <= sg['end']+1e-9 for s in sc['win']))
            pb = run2.power_block(k, mw+emw, sgc['hor'], st, 'A', fuel_ok=fuel_ok)
            if k >= 3 and fuel_ok: st['fuel'] = st.get('_fuel_now', 0)
            g = pb['gens']
            row = dict(phase=k, segment=sg['name'], start_h=sg['start']/60, end_h=sg['end']/60,
                       milestones=[TAGS[s]['name']+f" [{TAGS[s]['tag']}]" for s in sg['members']],
                       pay={}, machines=mach, reuse_floor=sum(floor_by.values()), MW=pb['D_total'], gens=dict(g), lines=lines,
                       ore={r_: v for r_, v in rawcap.items() if v > 1e-6 and r_ != 'Heavy Oil Residue'},
                       pa_start=[p for p in M.PA[k] if max([sc['win'][m][1] for m in gate(p) if m in sc['win']], default=0) <= sg['end']+1e-9
                                 and max([sc['win'][m][1] for m in gate(p) if m in sc['win']], default=0) > sg['start']+1e-9*(sg['start']>0)-1e-9*(sg['start']==0) and sg['name'] != 'Project Assembly run'])
            for s in sg['members']:
                for it, q in TAGS[s]['cost'].items(): row['pay'][it] = row['pay'].get(it, 0)+q
            row['new_lines'] = {j: n for j, n in lines.items() if n > (prev['lines'].get(j, 0) if prev else 0)}
            row['d_machines'] = mach-(prev['machines'] if prev else 0)
            row['d_MW'] = row['MW']-(prev['MW'] if prev else 0)
            rows.append(row); prev = row
    return rows

if __name__ == '__main__':
    import json, sys
    for name in ('all', 'required'):
        rows = evaluate(run2.SCEN[name])
        json.dump(rows, open(HERE / f'steps_{name}.json', 'w', newline="\n"), indent=1, default=float)  # EDIT (b)(d): LF; was cwd
        with open(HERE / f'steps_{name}.csv', 'w', newline='') as f:  # EDIT (d)
            w = csv.writer(f, lineterminator="\n"); w.writerow(['phase', 'segment', 'start_h', 'end_h', 'milestones', 'machines', 'd_machines', 'reuse_floor', 'MW', 'd_MW', 'generators', 'new_or_grown_lines', 'PA_parts_unlocked'])  # EDIT (b)
            for r in rows:
                w.writerow([r['phase'], r['segment'], round(r['start_h'], 2), round(r['end_h'], 2), '; '.join(r['milestones']), r['machines'], r['d_machines'], r['reuse_floor'],
                            round(r['MW'], 1), round(r['d_MW'], 1), '; '.join(f'{a} {b}' for a, b in r['gens'].items()),
                            '; '.join(f'{a} {b}' for a, b in r['new_lines'].items()), '; '.join(r['pa_start'])])
        print(f'\n===== {name}')
        for r in rows:
            print(f"P{r['phase']} {r['segment'][:28]:28s} {r['start_h']:6.2f}-{r['end_h']:6.2f} h | mach {r['machines']:4d} (+{r['d_machines']:3d}) floor {r['reuse_floor']:4d} | MW {r['MW']:8.1f} | {r['gens']} | PA+ {r['pa_start']}")
