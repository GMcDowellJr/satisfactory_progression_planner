"""Common-baseline card numbers — scratch, 2026-10-26. Every figure is
machine-minutes / FACTORY machine-minutes at 1/1/1 (same phase), so rows for
different power sources share one denominator. Factory = PA+ms+MAM+ext."""
import sys, pathlib
here = pathlib.Path(__file__).parent
WS = [tuple(float(x) for x in a.split(":")) for a in sys.argv[2:]]
sys.argv = [str(here / "work_axis.py"), sys.argv[1]]
src = open(here / "work_axis.py").read().split("base_w = {ph")[0]
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(src, "work_axis", "exec"))
base_w = {ph: phase_work(1.0, 1.0, 1.0, ph) for ph in TOP}
for R, P, E in WS:
    print(f"== R{R:g} P{P:g} E{E:g}   (each / factory 1/1/1)")
    for ph in TOP:
        parts, plants = phase_work(R, P, E, ph)
        bparts, bplants = base_w[ph]
        fb = sum(bparts.values())
        comp = [parts[k] / fb for k in ("PA", "ms", "MAM", "ext")]
        fac = sum(comp)
        g = "; ".join(f"{n} plant {plants[n]/fb:.2f} total {fac + plants[n]/fb:.2f} (1/1/1 total {1 + bplants[n]/fb:.2f})" for n in plants)
        print(f"  ph{ph} factory {fac:.2f} = " + "+".join(f"{c:.2f}" for c in comp) + " | " + g)
