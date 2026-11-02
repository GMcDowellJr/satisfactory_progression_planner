# plant_resize.py -- research driver (2026-11-01): the power-plant draw re-sized per ppm case.
#
# nodes.py holds one PLANT table, the 1/min plant, for every case. This driver re-runs the plant for each
# case of nodes.py's CASES: factory draw as nodes.py has it (model3_ppm1029, FLOOR base, PPM per case), plant
# draw the site_data.py way after its 2026-11-01 fix -- record run2.power_block per step segment while the
# model's evaluate() runs, plant raw = pb['raw'] (power_block already holds the crude for Fuel), per phase
# = max over segments. Generator mix and settings are run2's (PMULT 1.0, NUCLEAR False); nothing is chosen here.
#
# Check before the cases: at 1/min the per-phase plant must equal site_data.json's std plant (per-phase max);
# the run stops on a mismatch rather than writing figures.
#
#   uv run python -I research/step_planner/plant_resize.py      -> plant_resize.json beside this file
import io, contextlib, json, pathlib, sys
from collections import defaultdict
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
with contextlib.redirect_stdout(io.StringIO()):
    import model3_ppm1029_plant as M3
import run2, model2 as M

WORLD_RAWS = ["Nitrogen Gas", "Crude Oil", "SAM", "Limestone", "Iron Ore", "Copper Ore", "Caterium Ore", "Coal", "Raw Quartz",
              "Sulfur", "Bauxite", "Uranium", "Water"]
PLANT_RAWS = ["Coal", "Crude Oil", "Nitrogen Gas", "Water"]
CASES = [("all1", {}), ("p5x5", {5: 5.0}), ("p5x40", {5: 40.0})]   # nodes.py CASES

orig = run2.power_block; REC = []
def rec_pb(k, d_fac, hor, st, variant, fuel_ok=True):
    pb = orig(k, d_fac, hor, st, variant, fuel_ok=fuel_ok); REC.append((k, pb)); return pb
run2.power_block = rec_pb

def run(ppm):
    M3.FLOOR = "base"; M3.FLOOR_RATE = None; M3.PPM = ppm
    REC.clear(); buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out, *_ = M3.simulate_steps(run2.SCEN["all"])
        assert not REC
        M3.evaluate(run2.SCEN["all"])
    warns = [l for l in buf.getvalue().splitlines() if "WARN" in l]
    segs = defaultdict(list); i = 0
    for k in M.P:
        for sg in out[k]["sc"]["segs"]:
            kk, pb = REC[i]; i += 1
            assert kk == k
            segs[k].append(dict(seg=sg["name"], plant={r: float(v) for r, v in pb["raw"].items() if v > 0},
                                gens=dict(pb["gens"]), MW=float(pb["D_total"])))
    assert i == len(REC)
    phases = {}
    for k in M.P:
        L = segs[k]
        phases[str(k)] = dict(
            h=out[k]["sc"]["T"] / 60,
            factory={r: max(float(out[k]["rawc"][r].max()), 0.0) for r in WORLD_RAWS if r in out[k]["rawc"]},
            plant={r: max(s["plant"].get(r, 0.0) for s in L) for r in PLANT_RAWS},
            gens={g: max(s["gens"].get(g, 0) for s in L) for g in ("Biomass Burner", "Coal Generator", "Fuel Generator")},
            peak_MW=max(s["MW"] for s in L))
    return dict(ppm={str(k): v for k, v in ppm.items()}, warns=warns, phases=phases)

res = {key: run(ppm) for key, ppm in CASES}

# check: the 1/min plant equals site_data.json's std plant, per-phase max over segments
sd = json.load(open(HERE / "site_data.json"))
for k in M.P:
    want = {r: max([s["plant"].get(r, 0.0) for s in sd["std"][str(k)]] or [0.0]) for r in ("Coal", "Crude Oil")}
    got = res["all1"]["phases"][str(k)]["plant"]
    for r, w in want.items():
        if abs(got.get(r, 0.0) - w) > 0.01:
            sys.exit(f"STOP: P{k} {r} plant {got.get(r, 0.0):.2f} != site_data.json std {w:.2f}")
print("check: 1/min plant matches site_data.json std (Coal, Crude Oil), every phase")

for key, r in res.items():
    print(f"\n{key} PPM={r['ppm']} WARN lines: {len(r['warns'])}")
    for k, p in r["phases"].items():
        g = p["gens"]
        print(f"  P{k} {p['h']:6.2f} h  coal gens {g['Coal Generator']:3d} fuel gens {g['Fuel Generator']:4d}  peak {p['peak_MW']:9.1f} MW  | "
              + "  ".join(f"{x} fac {p['factory'].get(x, 0):8.1f} plant {p['plant'].get(x, 0):8.1f}" for x in ("Coal", "Crude Oil", "Water")))
with open(HERE / "plant_resize.json", "w", newline="\n") as f:
    json.dump(res, f, indent=1)
