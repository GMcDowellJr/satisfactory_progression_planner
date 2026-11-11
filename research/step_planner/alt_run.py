# alt_run.py -- option (ii): per phase, the resource-lean pick at the phase's last required step (1P), at most one alternate
# per item (the recipe making the largest share of that item in the pick), only alternates that relieve the binding raw, applied from the alternate's unlock minute.
# Alternates whose inputs or outputs fall outside model3's item set (e.g. Heavy Oil Residue, Packaged Water) are named and left out.
import io, contextlib, json, math, csv
import numpy as np
import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))  # EDIT (a): sibling imports under python -I; outputs into this folder
with contextlib.redirect_stdout(io.StringIO()):
    import relief as RL, place as PL, model2 as M, run2, model3 as M3, model3a as A
    base_res, _ = M3.simulate_steps(run2.SCEN['all'])
OK_ITEMS = set(M.R) | RL.RAWS
def representable(rid, j):
    io_ = M.IO[rid]
    return all(i in OK_ITEMS for i in io_['in']) and j in M.R and all(o in M.R or o in RL.RAWS for o in io_['out'] if o != j)

def pick(k):
    r3 = base_res[k]; sc = r3['sc']; cap = RL.capacity(k); T = sc['T']
    sg = [g for g in sc['segs'] if g['name'].startswith('Step')][-1]
    a_, e_ = int(math.floor(sg['start'])), max(int(math.floor(sg['start']))+1, min(T, int(math.ceil(sg['end']))))
    rawc = r3['rawc']
    top = lambda t: max(((rawc[r][t]/cap[r], r) for r in rawc if r in cap and cap[r] > 0 and rawc[r][t] > 0), default=(0, None))
    ts = max(range(a_, e_), key=lambda t: top(t)[0])
    d = {j: r3['prof'][j][ts]+r3['byp'][j][ts]-r3['cons'][j][ts] for j in M.R}
    d = {j: v for j, v in d.items() if abs(v) > 1e-9}
    clk = PL.Clock(k, sc); memo = {}
    reach = [rid for rid in RL.ALTS if PL.alt_time(rid, clk, memo)[0] <= sg['end']+1e-6]
    fuel_ok = k >= 4 or k == 3
    if k == 1: src = {}
    elif k == 2: src = dict(mode='coal')
    else:
        b0 = RL.lp(d, RL.STD if False else sorted(set(M.RID.values())), k, cap, 'base', P=1.0, plant=False)
        src = dict(mode='mixed', coal_load=min(RL.coal_cap(1.0), b0['mw']), fuel_crude_per_mw=RL.FUEL_CRUDE_PER_MW)
    STD = sorted(set(M.RID.values())) + (['Recipe_ResidualFuel_C'] if src.get('mode') == 'mixed' else [])
    bp = RL.lp(d, STD, k, cap, 'base', P=1.0, src=src)
    bind = max(bp['share'].items(), key=lambda x: x[1])[0]
    full = RL.lp(d, STD+reach, k, cap, 'res', bind, P=1.0, src=src)
    sh = lambda q: q['share'].get(bind, 0); base_sh = sh(bp); full_sh = sh(full)
    picked = [rid for rid in full['x'] if rid in reach]
    # relieving = leave-one-out effect on the binding share >= 0.5% of the standard-recipe share (Greg 2026-10-28 19:31)
    loo = {rid: (sh(RL.lp(d, STD+[z for z in reach if z != rid], k, cap, 'res', bind, P=1.0, src=src))-full_sh)/base_sh for rid in picked}
    keep = [rid for rid in picked if loo[rid] >= 0.005]
    # substitutes can each read ~0 alone: add back, greedily, whatever recovers most until within 0.5% of the full pick
    while True:
        cur = RL.lp(d, STD+keep, k, cap, 'res', bind, P=1.0, src=src)
        if (sh(cur)-full_sh)/base_sh <= 0.005: break
        rest = [rid for rid in picked if rid not in keep]
        if not rest: break
        keep.append(min(rest, key=lambda rid: sh(RL.lp(d, STD+keep+[rid], k, cap, 'res', bind, P=1.0, src=src))))
    indifferent = sorted(M.rec[rid]['display_name'].replace('Alternate: ', '') for rid in picked if rid not in keep)
    r_ = RL.lp(d, STD+keep, k, cap, 'res', bind, P=1.0, src=src)
    reach = keep
    plan = {}; skipped = []
    for j in M.R:
        makers = {rid: x*M.IO[rid]['rout'].get(j, 0) for rid, x in r_['x'].items() if M.IO[rid]['rout'].get(j, 0) > 0}
        if not makers: continue
        best = max(makers, key=makers.get)
        if best in reach:
            nm = M.rec[best]['display_name'].replace('Alternate: ', '')
            if not representable(best, j): skipped.append(nm); continue
            share = makers[best]/sum(makers.values())
            plan[j] = (best, PL.alt_time(best, clk, memo)[0], nm, round(share, 2))
    used_outside = sorted({M.rec[rid]['display_name'].replace('Alternate: ', '') for rid in r_['x'] if rid in reach
                           and not any(M.IO[rid]['rout'].get(j, 0) > 0 for j in plan if plan[j][0] == rid)} - set(skipped))
    return sg['name'], bind, plan, skipped, used_outside, indifferent, (base_sh, full_sh, sh(r_))

if __name__ == '__main__':
    PLAN = {}; info = {}
    for k in M.P:
        seg, bind, plan, skipped, other, indiff, shs = pick(k)
        PLAN[k] = {j: (v[0], v[1]) for j, v in plan.items()}
        info[k] = dict(step=seg, bind=bind, plan={j: [v[2], round(v[1]/60, 2), v[3]] for j, v in plan.items()}, skipped=skipped, not_applied=other,
                       indifferent=indiff, share_std_full_kept=[round(x, 4) for x in shs])
        print(f"P{k} picked at {seg} (binds {bind}): {len(plan)} items on alternates; share std {shs[0]:.4f} full pick {shs[1]:.4f} kept {shs[2]:.4f}")
        print('    indifferent (not applied):', indiff)
        for j, v in plan.items(): print(f"    {j:24s} <- {v[2]:28s} from {v[1]/60:5.2f} h  (pick share {v[3]:.0%})")
        if skipped: print('    outside model3 items, left out:', skipped)
        if other: print('    picked but not the main recipe of any item (one-per-item rule):', other)
    with contextlib.redirect_stdout(io.StringIO()):
        rows, res = A.evaluate(run2.SCEN['all'], PLAN)
    ref = json.load(open(HERE / 'steps_all_step2.json'))  # EDIT (a): was '/home/claude/pa/steps_all.json'; renamed copy of Project step2-milestones-power/steps_all.json
    print('\nphase/segment             std mach  alt mach |  std MW   alt MW | std floor alt floor | GS iters')
    for a, b in zip(rows, ref):
        print(f"P{a['phase']} {a['segment'][:22]:22s} {b['machines']:8d} {a['machines']:8d} | {b['MW']:7.0f} {a['MW']:8.0f} | {b['reuse_floor']:9d} {a['reuse_floor']:9d} | {a['iters']}")
    json.dump(rows, open(HERE / 'steps_all_alts.json', 'w', newline="\n"), indent=1, default=float)  # EDIT (b)(d)
    json.dump(info, open(HERE / 'alt_plan.json', 'w', newline="\n"), indent=1)  # EDIT (b)(d)
