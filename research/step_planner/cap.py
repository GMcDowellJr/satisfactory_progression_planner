import io, contextlib, math
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # EDIT (a): sibling imports under python -I
with contextlib.redirect_stdout(io.StringIO()):
    import model3_ppm1029 as M3  # EDIT (c): was `import model3 as M3`, meaning the ppm-2026-10-29 session variant
import run2, model2 as M
RATE = {1: 60, 2: 120, 3: 120, 4: 240, 5: 240}
STOCK = sorted(j for j in M.R if set(M.prodby[M.RID[j]]) & M.HIGH)
print('stack sizes (stockpiled items):', {j: int(M.stack.get(j, 0)) for j in STOCK if M.stack.get(j, 0)})
def run(ppm, slots):
    M3.PPM = ppm; M3.STOCK_SLOTS = slots
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): out, *_ = M3.simulate_steps(run2.SCEN['all'])
    nw = sum('WARN' in l for l in buf.getvalue().splitlines())
    rows = []
    for k in M.P:
        o = out[k]; g = lambda r: max(o['rawc'][r].max(), 0) if r in o['rawc'] else 0
        mach = sum(M.size(j, o['prof'][j].max(), k)[3] for j in M.R if o['prof'][j].max() > 1e-6)
        rows.append((k, g('Copper Ore'), g('Iron Ore'), mach, o['prof']['Nuclear Pasta'].sum(), o['S']['Nuclear Pasta']))
    return rows, nw
for name, ppm in [('all 1', {}), ('all 5', {k: 5.0 for k in M.P}), ('P5=5 only', {5: 5.0})]:
    base = None
    for slots in (0, 48, 24):
        rows, nw = run(ppm, slots)
        if base is None: base = rows
        print(f"== {name:10s} cap {'none' if not slots else str(slots)+' slots':9s} warn {nw}")
        for (k, cu, fe, m, pm, ps), (_, cu0, fe0, m0, *_r) in zip(rows, base):
            print(f"   P{k} Cu {cu:6.0f} n{math.ceil(cu/RATE[k]-1e-9):3d} | Fe {fe:6.0f} n{math.ceil(fe/RATE[k]-1e-9):3d} | mach {m:5d} | pasta made {pm:5.0f} carried {ps:5.0f}")
