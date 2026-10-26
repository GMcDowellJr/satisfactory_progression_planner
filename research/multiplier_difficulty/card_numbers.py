"""Numbers for the mock-up's Factory and Power plant cards — scratch, 2026-10-26.
Factory = PA + ms + MAM + ext, normalised to the FACTORY 1/1/1 total (generator-
independent). Plant per generator: plant machine-min ratio vs 1/1/1 same
generator, and total work (factory + plant) vs 1/1/1 same generator (§5.6)."""
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
    print(f"== R{R:g} P{P:g} E{E:g}")
    for ph in TOP:
        parts, plants = phase_work(R, P, E, ph)
        bparts, bplants = base_w[ph]
        fb = sum(bparts.values())
        comp = [parts[k] / fb for k in ("PA", "ms", "MAM", "ext")]
        g = "; ".join(f"{n} plant {plants[n]/bplants[n]:.2f}x total {(sum(parts.values())+plants[n])/(fb+bplants[n]):.2f}x"
                      for n in plants)
        print(f"  ph{ph} factory {sum(comp):.2f} = " + "+".join(f"{c:.2f}" for c in comp) + " | " + g)
