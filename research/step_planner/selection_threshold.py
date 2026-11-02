# selection_threshold.py -- research driver (2026-11-01): where one site stops being enough.
#
# Per case, phase and raw: ratio = draw / capacity of the single best neighborhood of that raw alone.
# Over 1, no one place supplies that raw at that phase, so a second site (or more) is forced on it.
# Capacity only: the neighborhood ranks by what its sockets can extract at the phase's extractor tier,
# never by where it is -- location quality depends on logistics, and logistics comes after this.
#
# Inputs (all declared; none defaulted):
#   draws        plant_resize.json beside this file: factory peak per phase (standard recipes, as nodes.py)
#                + the power plant re-sized per case, crude counted once (site_data.py fix of 2026-11-01)
#   radius       --radius metres, one or more (tools/neighborhoods.py, socket-centred, horizontal)
#   neighborhood one raw at a time; no dedupe; min_nodes 1 -- each candidate is one disc of that raw only
#   power set    the fuel route that feeds the fuel generators (POWER_SETS below). Only the crude-sourced
#                fuel energy is re-routed; coal generators, their coal and water, and the Residual Fuel credit
#                stay as run2 has them. S1-S3 are applied from P4 on (Diluted Fuel's HUB prerequisite is tier_7_8 in
#                alternate_recipe_unlocks.csv; nitrogen wells open at P4 in nodes.py); P1-P3 report S0 only.
#                Which set a player actually holds by then is not checked: MAM Sulfur research and hard drives.
#
# Rule breaks, declared (research, not tools/): the extractor/belt/pipe tier tables are nodes.py's copies,
# not read through gamedata (AGENTS.md "one loader"); recipe ratios for the power sets are typed in from
# recipe_io.csv / generator_fuels.csv (build 502094), cited per line. The fuel chains' own machine power and
# the Compacted Coal by-product of Nitro Rocket Fuel are not counted, so S1-S3 read slightly better than real.
# Water is not thresholded: Greg, 2026-11-01, treat it as unlimited (ocean extractors), power and logistics aside.
#
#   uv run python -I research/step_planner/selection_threshold.py . --radius 350 1000
#       -> stdout, and selection_threshold_output.txt beside this file
from __future__ import annotations
import argparse, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("repo", type=pathlib.Path)
ap.add_argument("--radius", type=float, nargs="+", required=True)
a = ap.parse_args()
sys.path.insert(0, str(a.repo.resolve() / "tools"))
import site_card, neighborhoods as NB  # noqa: E402

RUN = json.load(open(HERE / "plant_resize.json"))

# --- power sets: raw per minute per MW of fuel-generator output ---------------------------------------
# generator_fuels.csv: Fuel 750 MJ, Turbofuel 2000 MJ, Rocket Fuel 3600 MJ per m3; MW = MJ/min / 60
FUEL, TURBO, ROCKET = 60 / 750, 60 / 2000, 60 / 3600
STD_FUEL = {"Crude Oil": 1.5}                      # Recipe_LiquidFuel_C: 6 crude -> 4 fuel (+3 resin)
DIL_FUEL = {"Crude Oil": 0.375, "Water": 1.0}      # Recipe_Alternate_HeavyOilResidue_C 3 crude -> 4 HOR;
                                                   # Recipe_Alternate_DilutedFuel_C 5 HOR + 10 water -> 10 fuel
def scale(d, k): return {r: v * k for r, v in d.items()}
def plus(*ds):
    o: dict[str, float] = {}
    for d in ds:
        for r, v in d.items(): o[r] = o.get(r, 0.0) + v
    return o
POWER_SETS = {
    "S0 standard Fuel": scale(STD_FUEL, FUEL),
    "S1 HOR + Diluted Fuel": scale(DIL_FUEL, FUEL),
    # Recipe_Alternate_Turbofuel_C 6 fuel + 4 compacted coal -> 5; Recipe_Alternate_EnrichedCoal_C 5 coal + 5 sulfur -> 5
    "S2 S1 + Turbofuel": plus(scale(DIL_FUEL, TURBO * 6 / 5), {"Coal": TURBO * 4 / 5, "Sulfur": TURBO * 4 / 5}),
    # Recipe_Alternate_RocketFuel_Nitro_C 4 fuel + 3 N2 + 4 sulfur + 2 coal -> 6 (+1 compacted coal, not credited)
    "S3 S1 + Nitro Rocket Fuel": plus(scale(DIL_FUEL, ROCKET * 4 / 6),
                                      {"Nitrogen Gas": ROCKET * 3 / 6, "Sulfur": ROCKET * 4 / 6, "Coal": ROCKET * 2 / 6}),
}

# --- extraction capacity (nodes.py tables) ------------------------------------------------------------
MINER = {1: [30, 60, 120], 2: [60, 120, 240], 3: [60, 120, 240], 4: [120, 240, 480], 5: [120, 240, 480]}
BELT = {1: 120, 2: 270, 3: 480, 4: 780, 5: 1200}
PIPE = {1: 300, 2: 300, 3: 600, 4: 600, 5: 600}
OIL = [60, 120, 240]; WELL = [30, 60, 120]; PUR = {"impure": 0, "normal": 1, "pure": 2}
ITEM = {"Iron Ore": ("resource_node", "Desc_OreIron_C"), "Copper Ore": ("resource_node", "Desc_OreCopper_C"),
        "Limestone": ("resource_node", "Desc_Stone_C"), "Coal": ("resource_node", "Desc_Coal_C"),
        "Caterium Ore": ("resource_node", "Desc_OreGold_C"), "Raw Quartz": ("resource_node", "Desc_RawQuartz_C"),
        "Sulfur": ("resource_node", "Desc_Sulfur_C"), "Bauxite": ("resource_node", "Desc_OreBauxite_C"),
        "SAM": ("resource_node", "Desc_SAM_C"), "Crude Oil": ("resource_node", "Desc_LiquidOil_C"),
        "Nitrogen Gas": ("fracking_satellite", "Desc_NitrogenGas_C")}
def rate(r, k, purity):
    i = PUR[purity]
    if r == "Crude Oil": return 0 if k < 3 else min(OIL[i], PIPE[k])
    if r == "Nitrogen Gas": return 0 if k < 4 else WELL[i]
    return min(MINER[k][i], BELT[k])

sockets = site_card.load_sockets(a.repo, "default_502094")
W = NB.purity_weights(a.repo)
best, world = {}, {}
for raw, inc in ITEM.items():
    for rad in a.radius:
        hoods = NB.discover(sockets, NB.Policy(include=(inc,), radius_m=rad, min_nodes=1, dedupe=None), W)
        for k in range(1, 6):
            best[(rad, raw, k)] = max(sum(n * rate(raw, k, p) for _, pc in h.purity_counts for p, n in pc) for h in hoods)
    for k in range(1, 6):
        world[(raw, k)] = sum(rate(raw, k, s.purity) for s in sockets if (s.source_kind, s.item_id) == inc)

lines = [f"selection_threshold.py -- radius {' / '.join(f'{r:g} m' for r in a.radius)}; ratio = draw / best single "
         "same-raw neighborhood; map = draw / every socket of that raw at the phase tier; * = over 1 at the first radius"]
for case, cd in RUN.items():
    for ph in sorted(cd["phases"], key=int):
        k = int(ph); d = cd["phases"][ph]
        mw_crude = d["plant"].get("Crude Oil", 0.0) / 1.5 * 750 / 60   # fuel-generator MW now fed from crude
        for sname, coef in POWER_SETS.items():
            if k < 4 and sname != "S0 standard Fuel": continue
            draws = dict(d["factory"])
            draws["Coal"] = draws.get("Coal", 0.0) + d["plant"].get("Coal", 0.0)
            for r, v in coef.items():
                draws[r] = draws.get(r, 0.0) + v * mw_crude
            rows = []
            for r in ITEM:
                v = draws.get(r, 0.0)
                if v < 0.05: continue
                caps = [best[(rad, r, k)] for rad in a.radius]
                rat = [v / c if c else float("inf") for c in caps]
                mp = v / world[(r, k)] * 100 if world[(r, k)] else float("inf")
                rows.append((rat[0], f"   {'*' if rat[0] > 1 else ' '} {r:13s} {v:9.0f}  " +
                             " / ".join(f"{x:6.2f}" for x in rat) + f"   map {mp:6.1f}%"))
            water = d["factory"].get("Water", 0.0) + d["plant"].get("Water", 0.0) + coef.get("Water", 0.0) * mw_crude
            lines.append(f"\n{case} P{k} | {sname} | fuel MW from crude {mw_crude:,.0f} | water {water:,.0f}/min (not thresholded)")
            lines += [t for _, t in sorted(rows, key=lambda x: -x[0])]
text = "\n".join(lines) + "\n"
print(text, end="")
(HERE / "selection_threshold_output.txt").write_text(text, newline="\n")
