# nodes.py -- per-phase node defaults + world-supply ceiling (scratch, 2026-10-29).
# Draw = phase peak of factory raw draw (session model3 variant, all milestones) + power-plant draw.
# Plant draw: project step3-relief/site_data.json std, per-phase max (1R/1P, all-1 ppm) -- NOT re-run for the ppm cases.
# World nodes / extractor rates / tiers: copied from site_data.json (the canvas's own source).
import io, contextlib, math, json
import sys, pathlib; HERE = pathlib.Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))  # EDIT (a): sibling imports under python -I; outputs into this folder
with contextlib.redirect_stdout(io.StringIO()):
    import model3_ppm1029 as M3  # EDIT (c): was `import model3 as M3`, meaning the ppm-2026-10-29 session variant
import run2, model2 as M
PLANT = {1: {}, 2: {'Coal': 37.85}, 3: {'Coal': 120.0, 'Crude Oil': 25.04}, 4: {'Coal': 120.0, 'Crude Oil': 522.28},  # 2026-11-01: removed a second add of Fuel's crude; run2.power_block already puts it in pb['raw'] (plant crude was 2x).
         5: {'Coal': 120.0, 'Crude Oil': 983.28}}
WORLD = {"Nitrogen Gas": [2, 7, 36], "Crude Oil": [18, 18, 12], "SAM": [10, 6, 3], "Limestone": [15, 50, 29], "Iron Ore": [39, 42, 46],
         "Copper Ore": [13, 29, 13], "Caterium Ore": [0, 9, 8], "Coal": [15, 31, 16], "Raw Quartz": [3, 7, 7], "Sulfur": [6, 5, 5],
         "Bauxite": [5, 6, 6], "Uranium": [3, 2, 0]}
MINER = {1: [30, 60, 120], 2: [60, 120, 240], 3: [60, 120, 240], 4: [120, 240, 480], 5: [120, 240, 480]}
BELT = {1: 120, 2: 270, 3: 480, 4: 780, 5: 1200}
PIPE = {1: 300, 2: 300, 3: 600, 4: 600, 5: 600}
OIL = [60, 120, 240]; WELL = [30, 60, 120]
RAWS = list(WORLD)
def rates(r, k, oc=1.0):
    """per-node rate by purity [impure, normal, pure] at phase k tier and clock oc; 0 = not extractable yet."""
    if r == 'Crude Oil':
        return [0, 0, 0] if k < 3 else [min(v*oc, PIPE[k]) for v in OIL]
    if r == 'Nitrogen Gas':
        return [0, 0, 0] if k < 4 else [v*oc for v in WELL]
    return [min(v*oc, BELT[k]) for v in MINER[k]]
def world_cap(r, k, oc=1.0):
    return sum(n*v for n, v in zip(WORLD[r], rates(r, k, oc)))
def run(ppm):
    M3.FLOOR = 'base'; M3.FLOOR_RATE = None; M3.PPM = ppm
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out, *_ = M3.simulate_steps(run2.SCEN['all'])
    warns = [l for l in buf.getvalue().splitlines() if 'WARN' in l]
    res = {}
    for k in M.P:
        rc = out[k]['rawc']
        fac = {r: max(float(rc[r].max()), 0.0) for r in RAWS if r in rc}
        res[k] = dict(fac=fac, h=out[k]['sc']['T']/60)
    return res, warns
CASES = [('all1', '1/min, all phases', {}), ('p5x5', 'P5 at 5/min', {5: 5.0}), ('p5x40', 'P5 at 40/min (Overbuilder rates)', {5: 40.0})]
OUT = {'meta': dict(note='Node defaults per phase: normal purity at the phase extractor tier, 100% clock. Draw = factory peak '
                         '(session model) + power plant at the 1/min level. Ceiling = share of every node of that resource on '
                         'the map at the same tier, at 100% and at 250% clock.', plant_rerun=False), 'cases': []}
for key, label, ppm in CASES:
    res, warns = run(ppm)
    prev = {r: 0 for r in RAWS}; phases = {}
    for k in M.P:
        rows = []
        for r in RAWS:
            fac = res[k]['fac'].get(r, 0.0); pl = PLANT[k].get(r, 0.0); v = fac + pl
            if v < 0.05: continue
            nr = rates(r, k)[1]
            if nr == 0:
                rows.append(dict(r=r, draw=round(v, 1), plant=round(pl, 1), n=None, add=None, s100=None, s250=None, flag='not extractable this phase')); continue
            n = math.ceil(v/nr - 1e-9); add = max(0, n - prev[r]); prev[r] = max(prev[r], n)
            c100, c250 = world_cap(r, k), world_cap(r, k, 2.5)
            s100, s250 = v/c100, v/c250
            flag = 'over the map even at 250%' if s250 > 1 else 'over the map at 100%: needs overclock or alternates' if s100 > 1 else ''
            rows.append(dict(r=r, draw=round(v, 1), plant=round(pl, 1), n=n, add=add, s100=round(s100, 4), s250=round(s250, 4),
                             wnorm=round(c100/nr, 1), flag=flag))
        rows.sort(key=lambda x: -(x['s100'] or 0))
        phases[str(k)] = dict(h=round(res[k]['h'], 2), rows=rows)
    OUT['cases'].append(dict(key=key, label=label, warnings=len(warns), phases=phases))
json.dump(OUT, open(HERE / 'node_defaults.json', 'w', newline="\n"), separators=(',', ':'))  # EDIT (b)(d): LF; was cwd
for c in OUT['cases']:
    print('=====', c['label'], 'warnings', c['warnings'])
    for k, p in c['phases'].items():
        print(f" P{k} {p['h']:6.2f} h  " + ' | '.join(f"{x['r']} {x['draw']:.0f} n{x['n']}(+{x['add']}) {0 if x['s100'] is None else x['s100']*100:.0f}%/{0 if x['s250'] is None else x['s250']*100:.0f}%{' !' if x['flag'] else ''}" for x in p['rows']))
