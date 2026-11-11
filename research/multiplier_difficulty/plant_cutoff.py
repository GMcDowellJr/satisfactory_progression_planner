"""Plant cutoff — scratch, 2026-10-26. NOT repo code. Loads node_ceiling.py.

For each sole-source generator (D27), R and purity world, bisects the P in
[1, 8] above which the plant can't net positive power on default sockets
(k -> 0: the phase can't be finished on that source at any pace). ">8" means
no cutoff below P = 8. HiGHS failures past stage 1 at a near-zero scale are
counted as k = 0 and listed at the end.

Usage: python -I plant_cutoff.py <repo> [impure|normal|pure ...]   (none: world)
"""
import sys, pathlib
repo = sys.argv[1]
here = pathlib.Path(repo) / "research/multiplier_difficulty"
PURS = [None if a == "world" else a for a in sys.argv[2:]]
sys.argv = [str(here / "node_ceiling.py"), repo]
__file__ = str(here / "node_ceiling.py")
src = open(__file__).read().split('print("world sockets used"')[0]
exec(compile(src, __file__, "exec"))


FAILS = []


def k_of(R, P, ph, gn):
    g = next(x for x in gens_open(ph) if gname(x) == gn)
    try:
        return ceiling(R, P, 1.0, ph, g)[0]
    except Exception as ex:          # HiGHS gives up past stage 1 when the scale is ~0
        FAILS.append((R, round(P, 3), ph, gn, type(ex).__name__))
        return 0.0


def p_star(R, ph, gn, lo=1.0, hi=8.0):
    if k_of(R, hi, ph, gn) > 1e-9:
        return f">{hi:g}"
    if k_of(R, lo, ph, gn) <= 1e-9:
        return f"<={lo:g}"
    for _ in range(14):
        mid = (lo + hi) / 2
        if k_of(R, mid, ph, gn) > 1e-9:
            lo = mid
        else:
            hi = mid
    return f"{(lo + hi) / 2:.2f}"


for pur in (PURS or [None, "normal", "impure"]):
    globals()["PURITY"] = pur
    label = pur or "world"
    for gn, phs in (("Nuclear", (4, 5)), ("Fuel", (3, 4, 5)), ("Coal", (2, 3, 4, 5))):
        cells = []
        for R in (1.0, 1.25, 1.5, 1.75, 2.0):
            cells.append(f"R{R:g}: " + "/".join(p_star(R, ph, gn) for ph in phs))
        print(f"{label:7s} {gn:8s} P* (ph {'/'.join(map(str, phs))})  " + "   ".join(cells), flush=True)

print('solver failures treated as k=0:', len(FAILS), FAILS[:6])
