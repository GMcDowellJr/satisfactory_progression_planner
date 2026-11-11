import io, contextlib, math
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # EDIT (a): sibling imports under python -I
with contextlib.redirect_stdout(io.StringIO()):
    import model3_ppm1029 as M3  # EDIT (c): was `import model3 as M3`, meaning the ppm-2026-10-29 session variant
import run2, model2 as M
RATE = {1: 60, 2: 120, 3: 120, 4: 240, 5: 240}     # normal node, miner tier per phase (model2 MINER)
def run(ppm):
    M3.FLOOR = 'base'; M3.FLOOR_RATE = None; M3.PPM = ppm
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out, *_ = M3.simulate_steps(run2.SCEN['all'])
    warns = [l for l in buf.getvalue().splitlines() if 'WARN' in l]
    res = {}
    for k in M.P:
        o = out[k]; T = o['sc']['T']
        cu = max(o['rawc']['Copper Ore'].max(), 0) if 'Copper Ore' in o['rawc'] else 0
        fe = o['rawc']['Iron Ore'].max(); ls = o['rawc']['Limestone'].max() if 'Limestone' in o['rawc'] else 0
        mach = sum(M.size(j, o['prof'][j].max(), k)[3] for j in M.R if o['prof'][j].max() > 1e-6)
        res[k] = dict(h=T/60, cu=cu, fe=fe, ls=ls, mach=mach, ncu=math.ceil(cu/RATE[k]-1e-9), nfe=math.ceil(fe/RATE[k]-1e-9),
                      pasta=o['prof']['Nuclear Pasta'].max())
    return res, warns
cases = [('all 1', {}), ('all 2', {k: 2.0 for k in M.P}), ('all 5', {k: 5.0 for k in M.P}), ('P5=5 only', {5: 5.0})]
R = {}
for name, ppm in cases:
    R[name], w = run(ppm)
    print(f"===== {name}   warnings: {len(w)}" + (f"  e.g. {w[:2]}" if w else ''))
    for k in M.P:
        r = R[name][k]; b = R['all 1'][k]
        rat = lambda key: (r[key]/b[key] if b[key] > 1e-9 else float('nan'))
        print(f"  P{k} {r['h']:6.1f} h | Cu {r['cu']:7.0f} (x{rat('cu'):4.2f}) n{r['ncu']:3d} | Fe {r['fe']:7.0f} (x{rat('fe'):4.2f}) n{r['nfe']:3d} | "
              f"mach {r['mach']:5d} (x{rat('mach'):4.2f}) | pasta {r['pasta']:.2f}/min")
