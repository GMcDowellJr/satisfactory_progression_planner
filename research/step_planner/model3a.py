# model3a.py -- model3 with alternates, option (ii) (Greg 2026-10-28 19:16). Scratch; model3.py untouched.
# PLAN[k] = {item: (alt_recipe_id, t_on_minutes)}: in phase k, `item` is made by the alternate from minute t_on (its unlock,
#   place.py), by its standard recipe before. At most one alternate per item (option (a), Greg 2026-10-28 12:13).
# Differences from model3.simulate_steps, all needed for alternates and inert with an empty PLAN (checked: reproduces model3):
#   - consumption, byproducts and raw draw are split by recipe mask (std before t_on, alt from t_on)
#   - recipe loops (Recycled Plastic <-> Recycled Rubber) are solved by Gauss-Seidel passes over ORDER until consumption settles
#   - capacity is tracked per (item, recipe): a standard line and its alternate are different lines; carried lines stay installed
# Future enhancement, option (i): swap each item's recipe from the step its alternate is picked (time-varying picks within a
#   phase), not one set per phase.
import math
import numpy as np
from collections import defaultdict
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # EDIT (a): sibling imports under python -I
import model2 as M, run2, model3 as M3
P = M.P; TAGS = M3.TAGS
STOCK = {j for j in M.R if set(M.prodby[M.RID[j]]) & M.HIGH}

def flows(j, rid):
    """(out per cycle, inputs, byproducts) of `rid` for product j, in model2.R's shape (same-item in/out netted)."""
    if rid == M.RID[j]: return M.R[j]
    x = M.IO[rid]; o = x['out'][j]; ins = dict(x['in']); by = {k: v for k, v in x['out'].items() if k != j}
    for k in list(by):
        if k in ins: ins[k] -= by.pop(k)
    return o, ins, by

def size_r(j, rid, cap, k):
    """model2.size for an arbitrary recipe of j (lines by belt/pipe tier, machines, clock, MW)."""
    rr = M.IO[rid]; mr = rr['rout'][j]; scale = cap/mr
    flows_ = [(v*scale, M.form.get(i, 'solid')) for d in ('rin', 'rout') for i, v in rr[d].items()]
    need = [1]
    s = [f for f, fm in flows_ if fm == 'solid']; fl = [f for f, fm in flows_ if fm != 'solid']
    if s: need.append(math.ceil(max(s)/M.BELT[k][1]-1e-9))
    if fl: need.append(math.ceil(max(fl)/M.PIPE[k][1]-1e-9))
    lines = max(need); per = cap/lines; n = math.ceil(per/mr-1e-9)
    clock = math.ceil(per/(n*mr)*1e6)/1e4
    b = sorted(M.prodby[rid])[0]; base = M.PB.get(b, 0) or M.VP.get(rid, 0)
    return lines, n, clock, lines*n, lines*n*base*(clock/100.0)**M.EXP

def simulate_steps(sel, PLAN, NIT=30):
    bills, mb = run2.bills_for(sel)
    LIFE = defaultdict(float)
    for k in P:
        prod, _ = M.solve(bills[k])
        for j, v in prod.items(): LIFE[j] += max(v, 0)
    C = defaultdict(float)            # (item, recipe) -> installed rate
    S = defaultdict(float); made = defaultdict(float)
    paid = set(); out = {}
    for k in P:
        sc = M3.schedule(k, sel); T = sc['T']; FQ = M.PA[k]; T_PA = sc['T_PA']
        t = np.arange(1, T+1); plan = PLAN.get(k, {})
        avail = {}
        for j in M.R:
            a = 0.0
            for m in M3.own_gate(j):
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
        # per-item recipe masks: alt from minute t_on (minute index i covers [i, i+1); active when i >= t_on)
        mask = {}
        for j in M.R:
            if j in plan:
                rid, ton = plan[j]; on = (np.arange(T) >= ton).astype(float)
                mask[j] = [(M.RID[j], 1-on), (rid, on)]
            else:
                mask[j] = [(M.RID[j], np.ones(T))]
        contrib = {}                    # consumer j -> (cons dict, byp dict, raw dict) of arrays
        prof = {}; rr_ = {}
        for it_ in range(NIT):
            delta = 0.0
            for j in M.ORDER:
                cons_j = sum((c[0].get(j, 0) for c in contrib.values()), np.zeros(T))
                byp_j = sum((c[1].get(j, 0) for c in contrib.values()), np.zeros(T))
                need = (cons_j-byp_j).copy(); need[-1] += FQ.get(j, 0); need += mdem[j]
                a = avail[j]
                cum = np.cumsum(need)-S[j]
                if cum.max() > 1e-9 and math.isinf(a): a = 0
                span = np.maximum(t-a, 1e-9); ok = t > a+1e-9
                req = max(0, (cum[ok]/span[ok]).max()) if (cum.max() > 1e-9 and ok.any()) else 0
                fut = LIFE[j]-made[j]-bills[k].get(j, 0)
                floor = (1.0 if fut > 1e-6 else FQ[j]/T_PA) if j in FQ else 0
                Cj = max([C[(j, r)] for r, _ in mask[j]] + [0.0])
                r = max(Cj, req, floor) if (cum.max() > 1e-9 or j in FQ) else Cj
                rem = max(LIFE[j]-made[j], (np.cumsum(need)-S[j]).max())
                if j in STOCK:
                    cp = np.minimum(r*np.maximum(t-a, 0), rem)
                else:
                    cp = np.maximum(np.cumsum(np.maximum(need, 0))-S[j], 0)
                pr = np.diff(np.concatenate([[0], cp]))
                old = prof.get(j); delta = max(delta, 0 if old is None else float(np.abs(old-pr).max()))
                prof[j] = pr; rr_[j] = r
                cdict = defaultdict(lambda: np.zeros(T)); bdict = defaultdict(lambda: np.zeros(T)); rdict = defaultdict(lambda: np.zeros(T))
                for rid, mk in mask[j]:
                    o, ins, by = flows(j, rid); prm = pr*mk
                    for i, v in ins.items(): (cdict if i in M.R else rdict)[i] += prm/o*v
                    for b, v in by.items():
                        if b in M.R: bdict[b] += prm/o*v
                        else: rdict[b] -= prm/o*v
                contrib[j] = (dict(cdict), dict(bdict), dict(rdict))
            if it_ > 0 and delta < 1e-7: break
        iters = it_+1
        cons = {j: sum((c[0].get(j, 0) for c in contrib.values()), np.zeros(T)) for j in M.R}
        byp = {j: sum((c[1].get(j, 0) for c in contrib.values()), np.zeros(T)) for j in M.R}
        rawc = defaultdict(lambda: np.zeros(T))
        for c in contrib.values():
            for i, v in c[2].items(): rawc[i] += v
        newC = {}
        for j in M.R:
            for rid, mk in mask[j]:
                p_ = prof[j]*mk
                if j in STOCK: newC[(j, rid)] = rr_[j] if p_.max() > 1e-9 else C[(j, rid)]
                else: newC[(j, rid)] = max(C[(j, rid)], p_.max() if len(p_) else 0)
        segcap = []
        for sg in sc['segs']:
            e = min(T, max(1, int(math.ceil(sg['end']))))
            cap = {}
            for j in M.R:
                for rid, mk in mask[j]:
                    p_ = (prof[j]*mk)[:e]; v = p_.max() if e > 0 else 0
                    if j in STOCK and v > 1e-9: v = newC[(j, rid)]
                    cap[(j, rid)] = max(C[(j, rid)], v)
            for key, v in C.items():         # carried lines of recipes no longer active stay installed
                if key not in cap and v > 1e-9: cap[key] = v
            raw = {i: max(v[:e].max(), 0) for i, v in rawc.items()}
            hor = max(0, -rawc['Heavy Oil Residue'][:e].sum()/e) if 'Heavy Oil Residue' in rawc else 0
            a_, b_ = int(math.floor(sg['start'])), max(int(math.floor(sg['start']))+1, e)
            own = {}
            for j in M.R:
                for rid, mk in mask[j]:
                    p_ = (prof[j]*mk)[a_:b_]
                    if p_.size and p_.max() > 1e-6: own[(j, rid)] = p_.max()
            segcap.append(dict(seg=sg, cap=cap, raw=raw, hor=hor, own=own, masks=mask))
        for j in M.R:
            made[j] += prof[j].sum(); S[j] += prof[j].sum()+byp[j].sum()-cons[j].sum()-bills[k].get(j, 0)
        paid |= sc['ids']
        out[k] = dict(sc=sc, segcap=segcap, S={j: S[j] for j in M.R}, prof=prof, cons=cons, byp=byp, rawc=dict(rawc), avail=avail, iters=iters)
        C = defaultdict(float, {key: v for key, v in segcap[-1]['cap'].items()})
    return out, mb

def label(j, rid):
    return j if rid == M.RID[j] else f"{j} ({M.rec[rid]['display_name'].replace('Alternate: ', '')})"

def evaluate(sel, PLAN):
    res, mb = simulate_steps(sel, PLAN)
    st = {}; rawcap = defaultdict(float); rows = []; prev = None
    for k in P:
        sc = res[k]['sc']; floor_by = defaultdict(int)
        for sgc in res[k]['segcap']:
            sg = sgc['seg']
            # lines per (item, building): a recipe swap on the same building re-uses its machines (largest need of
            # the recipes it has run); a swap to another building leaves the old machines installed but idle.
            # MW only from the recipe running at the segment end (idle machines draw no power).
            e = min(sc['T'], max(1, int(math.ceil(sg['end'])))) - 1
            active = {j: next((rid for rid, mk in sgc['masks'][j][::-1] if mk[e] > 0.5), M.RID[j]) for j in sgc['masks']}
            grp = defaultdict(list)
            for (j, rid), c in sgc['cap'].items():
                if c > 1e-6: grp[(j, sorted(M.prodby[rid])[0])].append((rid, c))
            mach = 0; mw = 0; lines = {}
            for (j, b), lst in grp.items():
                sizes = {rid: size_r(j, rid, c, k) for rid, c in lst}
                n = max(z[3] for z in sizes.values()); mach += n
                run_rid = active.get(j, M.RID[j]); lab_rid = run_rid if run_rid in sizes else max(sizes, key=lambda r_: sizes[r_][3])
                if run_rid in sizes: mw += sizes[run_rid][4]
                lines[label(j, lab_rid) + ('' if run_rid in sizes else ' [idle]')] = n
            own_by = defaultdict(int)
            for (j, rid), c in sgc['own'].items(): own_by[sorted(M.prodby[rid])[0]] += size_r(j, rid, c, k)[3]
            for b, v in own_by.items(): floor_by[b] = max(floor_by[b], v)
            for r_, v in sgc['raw'].items(): rawcap[r_] = max(rawcap[r_], v)
            ext, emw = M.extraction(dict(rawcap), k)
            fuel_ok = k >= 4 or (k == 3 and any(TAGS.get(s, {}).get('name') == 'Petroleum Power' and sc['win'][s][1] <= sg['end']+1e-9 for s in sc['win']))
            pb = run2.power_block(k, mw+emw, sgc['hor'], st, 'A', fuel_ok=fuel_ok)
            if k >= 3 and fuel_ok: st['fuel'] = st.get('_fuel_now', 0)
            row = dict(phase=k, segment=sg['name'], start_h=sg['start']/60, end_h=sg['end']/60,
                       milestones=[TAGS[s]['name']+f" [{TAGS[s]['tag']}]" for s in sg['members']],
                       pay={}, machines=mach, reuse_floor=sum(floor_by.values()), MW=pb['D_total'], gens=dict(pb['gens']), lines=lines,
                       ore={r_: v for r_, v in rawcap.items() if v > 1e-6 and r_ != 'Heavy Oil Residue'},
                       pa_start=[p for p in M.PA[k] if max([sc['win'][m][1] for m in M3.gate(p) if m in sc['win']], default=0) <= sg['end']+1e-9
                                 and max([sc['win'][m][1] for m in M3.gate(p) if m in sc['win']], default=0) > sg['start']+1e-9*(sg['start']>0)-1e-9*(sg['start']==0) and sg['name'] != 'Project Assembly run'],
                       iters=res[k]['iters'])
            for s in sg['members']:
                for it, q in TAGS[s]['cost'].items(): row['pay'][it] = row['pay'].get(it, 0)+q
            row['new_lines'] = {j: n for j, n in lines.items() if n > (prev['lines'].get(j, 0) if prev else 0)}
            row['d_machines'] = mach-(prev['machines'] if prev else 0)
            row['d_MW'] = row['MW']-(prev['MW'] if prev else 0)
            rows.append(row); prev = row
    return rows, res
