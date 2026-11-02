# plan2.py -- per-phase recipe plan (Greg 2026-10-28 20:09). Scratch.
# At each phase's last required step (1P, all milestones, STRETCH P4/P5 x1.25):
#   1. A raw BINDS only if its share of default-world capacity (incl. power-plant draw) >= BIND_MIN (placeholder 10%).
#   2. If one binds: alternates that reduce it are applied to their items ("binding"), as alt_run.py (leave-one-out >= 0.5%,
#      substitutes added back). An alternate that would raise the binding share by > 0.5% of the standard share is EXCLUDED.
#   3. Every other item is a FREE CHOICE among its standard recipe and its admissible alternates in reach, decided per consumer
#      line (the item that consumes it; '*' = the item's own demand: milestones, PA, stock) by, in order:
#        a. fewest distinct raws feeding the line (the consumer's other inputs + this item's chain)
#        b. fewest raws new to the factory this phase (raws it would not otherwise mine/pump)
#        c. fewest machine-equivalents for the item's chain
#   One recipe per (consumer, item); items whose consumers all agree get one recipe.
import io, contextlib, json, math
from collections import defaultdict
import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))  # EDIT (a): sibling imports under python -I; outputs into this folder
with contextlib.redirect_stdout(io.StringIO()):
    import alt_run as AR
RL, PL, M = AR.RL, AR.PL, AR.M
BIND_MIN = 0.10
# Rarity (Greg 2026-10-28 20:25): a rare raw is usually processed at its own site and arrives as an intermediate, so once the
# factory mines it this phase it adds no complexity to a consumer line. Rare = <= 25 default-world sockets (the data splits at
# 19 SAM vs 51 crude; nothing in between). Location / declared inputs replace this later.
from collections import Counter as _C
_sock = _C()
for (it, kind, pur), n in RL.socks.items(): _sock[it] += n
RARE = {it for it, n in _sock.items() if n <= 25}
TOL = 0.005
RAW = RL.RAWS

def setup(k):
    r3 = AR.base_res[k]; sc = r3['sc']; cap = RL.capacity(k); T = sc['T']
    sg = [g for g in sc['segs'] if g['name'].startswith('Step')][-1]
    a_, e_ = int(math.floor(sg['start'])), max(int(math.floor(sg['start']))+1, min(T, int(math.ceil(sg['end']))))
    rawc = r3['rawc']
    top = lambda t: max(((rawc[r][t]/cap[r], r) for r in rawc if r in cap and cap[r] > 0 and rawc[r][t] > 0), default=(0, None))
    ts = max(range(a_, e_), key=lambda t: top(t)[0])
    d = {j: r3['prof'][j][ts]+r3['byp'][j][ts]-r3['cons'][j][ts] for j in M.R}
    d = {j: v for j, v in d.items() if abs(v) > 1e-9}
    clk = PL.Clock(k, sc); memo = {}
    reach = [rid for rid in RL.ALTS if PL.alt_time(rid, clk, memo)[0] <= sg['end']+1e-6]
    if k == 1: src = {}
    elif k == 2: src = dict(mode='coal')
    else:
        b0 = RL.lp(d, sorted(set(M.RID.values())), k, cap, 'base', P=1.0, plant=False)
        src = dict(mode='mixed', coal_load=min(RL.coal_cap(1.0), b0['mw']), fuel_crude_per_mw=RL.FUEL_CRUDE_PER_MW)
    STD = sorted(set(M.RID.values())) + (['Recipe_ResidualFuel_C'] if src.get('mode') == 'mixed' else [])
    factory_raws = {r for r, v in rawc.items() if r in RAW and v.max() > 1e-6}
    return dict(r3=r3, sc=sc, cap=cap, sg=sg, d=d, clk=clk, memo=memo, reach=reach, src=src, STD=STD, factory_raws=factory_raws)

def main_item(rid):
    return next((o for o in M.IO[rid]['rout'] if o in M.R), None)
def alt_name(rid): return M.rec[rid]['display_name'].replace('Alternate: ', '')

def build(k):
    C = setup(k); d, cap, STD, src = C['d'], C['cap'], C['STD'], C['src']
    lp = lambda recs, obj, bind=None: RL.lp(d, recs, k, cap, obj, bind, P=1.0, src=src)
    bp = lp(STD, 'base')
    bind, bsh = max(bp['share'].items(), key=lambda x: x[1])
    binding = bsh >= BIND_MIN
    constrained = {}; excluded = []; keep = []; keep_sh = bsh
    reach = [rid for rid in C['reach'] if main_item(rid) and AR.representable(rid, main_item(rid))]
    outside = sorted(alt_name(rid) for rid in C['reach'] if rid not in reach)
    sh = lambda q: q['share'].get(bind, 0)
    if binding:
        full = lp(STD+reach, 'res', bind); full_sh = sh(full)
        picked = [rid for rid in full['x'] if rid in reach]
        loo = {rid: (sh(lp(STD+[z for z in reach if z != rid], 'res', bind))-full_sh)/bsh for rid in picked}
        keep = [rid for rid in picked if loo[rid] >= TOL]
        while True:
            cur = lp(STD+keep, 'res', bind)
            if (sh(cur)-full_sh)/bsh <= TOL: break
            rest = [rid for rid in picked if rid not in keep]
            if not rest: break
            keep.append(min(rest, key=lambda rid: sh(lp(STD+keep+[rid], 'res', bind))))
        cur = lp(STD+keep, 'res', bind); keep_sh = sh(cur)
        for j in M.R:
            makers = {rid: x*M.IO[rid]['rout'].get(j, 0) for rid, x in cur['x'].items() if M.IO[rid]['rout'].get(j, 0) > 0}
            if makers:
                best = max(makers, key=makers.get)
                if best in keep: constrained[j] = best
    # candidates for free items: standard + admissible alternates
    cand = defaultdict(list)
    for rid in reach:
        j = main_item(rid)
        if j in constrained or rid in keep: continue
        if binding:
            recs = [r for r in STD+keep if M.IO[r]['rout'].get(j, 0) <= 0] + [rid]
            q = lp(recs, 'res', bind)
            if q is None or (sh(q)-keep_sh)/bsh > TOL:
                excluded.append([alt_name(rid), j, None if q is None else round((sh(q)-keep_sh)/bsh, 3)]); continue
        cand[j].append(rid)
    # ---- line complexity: whole-tree search ----
    # opts(j): the distinct ways to make j (its recipe and, recursively, its inputs' ways), one per distinct raw set, keeping the
    # fewest machines for each set and dropping ways dominated on (raw set superset, more machines). A parent scores its inputs'
    # ways TOGETHER (union of raws), so two choices cannot prop each other up the way a one-item-at-a-time search did.
    fr = C['factory_raws']
    def recipes_of(j):
        return [constrained[j]] if j in constrained else [M.RID[j]] + cand.get(j, [])
    memo_o = {}; per_rid = defaultdict(dict)   # per_rid[j][rid] = best way using recipe rid (unpruned across recipes), for labels
    def opts(j, depth=0):
        if j in memo_o: return memo_o[j]
        memo_o[j] = []       # cycle guard: a recipe path that loops back to j is not a way to make j here
        best = {}
        for rid in recipes_of(j):
            x = M.IO[rid]; n = 1.0/x['rout'][j]
            parts = []
            for i, v in x['rin'].items():
                if i in RAW: parts.append((i, [dict(raws=frozenset([i]), mach=0.0, rid=None, sub={})], 0.0))
                elif i in M.R: parts.append((i, opts(i, depth+1), v*n))
            combos = [(frozenset(), n, {})]
            for i, ol, w in parts:
                ol = sorted(ol, key=lambda o: (len(o['raws']), o['mach']))[:6]
                nxt = []
                for rs, m, sub in combos:
                    for idx, o in enumerate(ol):
                        nxt.append((rs | o['raws'], m + w*o['mach'], {**sub, i: o}))
                keep_ = {}
                for rs, m, sub in nxt:
                    if rs not in keep_ or m < keep_[rs][0]: keep_[rs] = (m, sub)
                combos = [(rs, m, sub) for rs, (m, sub) in keep_.items()]
            for rs, m, sub in combos:
                if rs not in best or m < best[rs]['mach']: best[rs] = dict(raws=rs, mach=m, rid=rid, sub=sub)
            if combos:
                per_rid[j][rid] = [dict(raws=rs, mach=m, rid=rid, sub=sub) for rs, m, sub in combos]
        ol = list(best.values())
        ol = [o for o in ol if not any(p is not o and p['raws'] <= o['raws'] and p['mach'] <= o['mach'] and (p['raws'] < o['raws'] or p['mach'] < o['mach']) for p in ol)]
        memo_o[j] = ol
        return ol
    cx = lambda rs: len([r for r in rs if not (r in RARE and r in fr)])      # line complexity
    key = lambda o: (cx(o['raws']), len(o['raws'] - fr), o['mach'])
    WHY = ('line complexity', 'no new raw', 'machines')
    def why_of(chosen_key, alt_key):
        for n_, (a1, b1) in enumerate(zip(chosen_key, alt_key)):
            if a1 < b1 - 1e-9: return WHY[n_]
            if a1 > b1 + 1e-9: return 'tie'
        return 'tie'
    def combine(rid, j, subs):
        x = M.IO[rid]; n = 1.0/x['rout'][j]; rs = set(); m = n
        for i, v in x['rin'].items():
            if i in RAW: rs.add(i)
            elif i in M.R and i in subs: rs |= subs[i]['raws']; m += v*n*subs[i]['mach']
        return dict(raws=frozenset(rs), mach=m)
    choice = {}; decided = {}
    import os
    if os.environ.get('DBG') and k == int(os.environ['DBG']):
        for jj in os.environ.get('DBGI', 'Screw').split(','):
            for o in sorted(opts(jj), key=key): print('   DBG', jj, M.rec[o['rid']]['display_name'], sorted(o['raws']), key(o))
    for p in M.ORDER:                       # each consumer line picks its inputs for its own best line
        ol = opts(p)
        if not ol or ol[0]['rid'] is None: continue
        op = min(ol, key=key)
        if p not in constrained and op['rid'] != M.RID[p]:
            std_ol = per_rid[p].get(M.RID[p], [])
            alt_k = key(min(std_ol, key=key)) if std_ol else (99, 99, 1e9)
            choice[('*', p)] = op['rid']; decided[('*', p)] = (op['rid'], why_of(key(op), alt_k), None, None)
        for i, oi in op['sub'].items():
            if oi['rid'] is None or i in constrained or oi['rid'] == M.RID[i]: continue
            choice[(p, i)] = oi['rid']
            std_i = per_rid[i].get(M.RID[i], [])
            if std_i:
                alt = combine(op['rid'], p, {**op['sub'], i: min(std_i, key=lambda o: key(o))})
                decided[(p, i)] = (oi['rid'], why_of(key(combine(op['rid'], p, op['sub'])), key(alt)), None, None)
            else:
                decided[(p, i)] = (oi['rid'], 'only option', None, None)
    active = {j for j in M.R if C['r3']['prof'][j].sum() > 1e-6}
    def consumers(j):
        return {'*'} | {c for (c, i) in choice if i == j and c in active}
    # ---- plan ----
    plan = defaultdict(dict)
    for j, rid in constrained.items():
        plan[j]['*'] = (rid, PL.alt_time(rid, C['clk'], C['memo'])[0], 'binding')
    for (ctx, j), (rid, why, s0, s1) in decided.items():
        if rid != M.RID[j] and j not in constrained and ctx in consumers(j):
            if ctx == '*' or ctx in active: plan[j][ctx] = (rid, PL.alt_time(rid, C['clk'], C['memo'])[0], why)
    report = dict(step=C['sg']['name'], bind=bind, share=round(bsh, 4), binding=bool(binding), kept_share=round(keep_sh, 4),
                  plan={j: {ctx: [alt_name(r), round(t/60, 2), why] for ctx, (r, t, why) in v.items()} for j, v in plan.items()},
                  excluded=excluded, outside_model=outside)
    return {j: {ctx: (r, t) for ctx, (r, t, why) in v.items()} for j, v in plan.items()}, report

if __name__ == '__main__':
    PLAN, REP = {}, {}
    for k in M.P:
        PLAN[k], REP[k] = build(k)
        r = REP[k]
        print(f"\nP{k} at {r['step']}: largest share {r['bind']} {r['share']:.1%} -> {'BINDS' if r['binding'] else 'nothing binds'}"
              + (f" (kept set {r['kept_share']:.1%})" if r['binding'] else ''))
        for j, v in sorted(r['plan'].items()):
            for ctx, (nm, t, why) in sorted(v.items()):
                print(f"   {j:24s} for {ctx:24s} <- {nm:28s} from {t:5.2f} h  [{why}]")
        if r['excluded']: print('   excluded (raise the binding share):', [e[0] for e in r['excluded']])
    json.dump(REP, open(HERE / 'plan2.json', 'w', newline="\n"), indent=1)  # EDIT (b)(d): LF; was cwd
    json.dump({k: {j: {c: list(x) for c, x in v.items()} for j, v in p.items()} for k, p in PLAN.items()}, open(HERE / 'plan2_raw.json', 'w', newline="\n"), indent=1)  # EDIT (b)(d)
