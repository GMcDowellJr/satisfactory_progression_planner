# site_data.py -- per-step raw draws (factory peak within the step + power plant) for the canvas site view, 1R/1P. Scratch.
import io, contextlib, json, math
from collections import defaultdict
import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))  # EDIT (a): sibling imports under python -I; outputs into this folder
with contextlib.redirect_stdout(io.StringIO()):
    import relief as RL, run2, model2 as M, model3 as M3, model3b as B, plan2 as P2
orig = run2.power_block; REC = []
def rec_pb(k, d_fac, hor, st, variant, fuel_ok=True):
    pb = orig(k, d_fac, hor, st, variant, fuel_ok=fuel_ok); REC.append(pb); return pb
run2.power_block = rec_pb
WORLD = set(RL.RAWS) - set(RL.HAND)
def draws(kind):
    REC.clear()
    with contextlib.redirect_stdout(io.StringIO()):
        if kind == 'std':
            res, _ = M3.simulate_steps(run2.SCEN['all']); rows = M3.evaluate(run2.SCEN['all'])
        else:
            PLAN = {k: P2.build(k)[0] for k in M.P}
            res, _ = B.simulate_steps(run2.SCEN['all'], PLAN); rows, _ = B.evaluate(run2.SCEN['all'], PLAN)
    out = {}; i = 0
    for k in M.P:
        sc = res[k]['sc']; T = sc['T']; rawc = res[k]['rawc']; segs = []
        for sg in sc['segs']:
            pb = REC[i]; i += 1
            a_, e_ = int(math.floor(sg['start'])), max(int(math.floor(sg['start']))+1, min(T, int(math.ceil(sg['end']))))
            fac = {r: float(max(v[a_:e_].max(), 0)) for r, v in rawc.items() if r in WORLD and v[a_:e_].size}
            plant = {r: float(v) for r, v in pb['raw'].items() if r in WORLD and v > 0}
            # 2026-11-01: removed a second add of Fuel's crude; run2.power_block already puts it in pb['raw'] (plant crude was 2x).
            name = 'PA Finish' if sg['name'] == 'Project Assembly run' else ('Extras' if sg['name'].startswith('Extras') else sg['name'])
            segs.append(dict(seg=name, fac={r: round(v, 2) for r, v in fac.items() if v > 1e-3},
                             plant={r: round(v, 2) for r, v in plant.items() if v > 1e-3}))
        out[k] = segs
    return out
data = dict(std=draws('std'), plan=draws('plan'))
# world sockets per raw and purity (wells = satellites), rates by extractor / purity, tiers by phase
socks = defaultdict(lambda: {'impure': 0, 'normal': 0, 'pure': 0})
for (it, kind, pur), n in RL.socks.items(): socks[it][pur] += n
data['world'] = {r: dict(v) for r, v in socks.items()}
data['rates'] = {f'{c}|{p}': v for (c, p), v in RL.RATE.items()}
data['tiers'] = {k: dict(miner=M.MINER[k][0], miner_rate_normal=M.MINER[k][1], belt=M.BELT[k][1], pipe=M.PIPE[k][1]) for k in M.P}
json.dump(data, open(HERE / 'site_data.json', 'w', newline="\n"), separators=(',', ':'))  # EDIT (b)(d): LF; was cwd
print(len(json.dumps(data)))
for kind in ('std', 'plan'):
    s = data[kind][4][3]; print(kind, 'P4', s['seg'], s['fac'], s['plant'])
print(data['world']); print(data['tiers'])
