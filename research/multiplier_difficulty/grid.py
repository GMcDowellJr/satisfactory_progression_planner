"""Precompute the R x P grid for the selector page — scratch, 2026-10-26.
Per (R, P, phase), components that the page combines linearly in E:
    w   [W_PA, W_ms, W_MAM]   recipe machine-min (PA at E=1)
    x   [ext_PA, ext_rest]    extractor machine-min
    e   [en_PA, en_rest]      energy MW-min (P-scaled)
    g   {gen: [net MW per generator, machine-min per generator-minute]}
Page: factory(E) = E*W_PA + W_ms + W_MAM + E*ext_PA + ext_rest
      energy(E)  = E*en_PA + en_rest; plant_g = energy / net * per_gen
Writes grid.json."""
import sys, pathlib, json, time
here = pathlib.Path(__file__).parent
sys.argv = [str(here / "work_axis.py"), sys.argv[1]]
src = open(here / "work_axis.py").read().split("base_w = {ph")[0]
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(src, "work_axis", "exec"))
Rs = [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]
Ps = [0.25, 0.5, 0.75, 1, 2, 5]
out = {}
t0 = time.time()
for R in Rs:
    for P in Ps:
        data = scenario_data(float(R), float(P))
        for ph in TOP:
            pab, msb, mmb = bills(ph)
            a = solve_full(data, pab, ph, P); b = solve_full(data, msb, ph, P); c = solve_full(data, mmb, ph, P)
            gens = {}
            for cls in unlocks.generators_open_at_tier(repo, TOP[ph], tuple(GENS)):
                net, per = plant(float(R), float(P), ph, GENS[cls])
                gens[cls.split("_")[1].replace("Generator", "")] = [round(net, 4), round(per, 4)]
            out[f"{R}|{P}|{ph}"] = {"w": [round(a[0], 2), round(b[0], 2), round(c[0], 2)],
                                    "x": [round(a[1], 2), round(b[1] + c[1], 2)],
                                    "e": [round(a[2], 2), round(b[2] + c[2], 2)], "g": gens}
        print(f"R{R} P{P} done {time.time()-t0:.0f}s", flush=True)
json.dump(out, open(here / "grid.json", "w", newline="\n"), separators=(",", ":"))
print("written", len(out))
