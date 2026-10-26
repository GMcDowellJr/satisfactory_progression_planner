"""Biomass burner routes from a declared gathering mix — scratch, 2026-10-26.
Patches grid.json: replaces g["Biomass"] with two routes (D30/D31):
    Biomass   gathered mix -> Biomass (Constructor) -> burner
    Biofuel   gathered mix -> Biomass -> Solid Biofuel (Constructor) -> burner
Gathering mix DECLARED by Greg 2026-10-26: 5 stacks of Leaves to 1 of Wood
(2,500 Leaves : 200 Wood by count, stack sizes from items.csv). Mycelia and
Alien Protein not in the mix (Greg: Mycelia occasional; protein goes to DNA
capsules). Recipe inputs R-scaled via the scenario; constructor power P-scaled.
Entry: [net MW per burner, machine-min per burner-minute incl. itself,
        leaves per burner-minute, wood per burner-minute].
Usage: python -I biomass_routes.py <repo> <grid.json>"""
import sys, pathlib, json
repo = pathlib.Path(sys.argv[1]); gp = pathlib.Path(sys.argv[2])
sys.path.insert(0, str(repo / "tools/production_adapter/src"))
from production_adapter import gamedata
from production_adapter.scenario import Scenario
base = gamedata.load(repo)
LEAVES, WOOD = 2500.0, 200.0
GROSS, MJ_BIOMASS, MJ_BIOFUEL = 30.0, 180.0, 450.0


def cyc(rec):
    return 60.0 / rec.duration_sec


def amt(rec, item):
    for i, a, _ in rec.input_amounts:
        if i == item:
            return a
    raise KeyError(item)


def out(rec, item):
    for i, a, _ in rec.output_amounts:
        if i == item:
            return a
    raise KeyError(item)


def routes(R, P):
    d = base if (R, P) == (1, 1) else base.with_scenario(Scenario(recipe_input_multiplier=R, machine_power_multiplier=P, input_amount_floor=1))
    rl, rw, rb = d.recipes["Recipe_Biomass_Leaves_C"], d.recipes["Recipe_Biomass_Wood_C"], d.recipes["Recipe_Biofuel_C"]
    con_mw = d.producers["Build_ConstructorMk1_C"].base_power_mw
    lc, wc = LEAVES / amt(rl, "Desc_Leaves_C"), WOOD / amt(rw, "Desc_Wood_C")       # cycles per bundle
    biomass_per_bundle = lc * out(rl, "Desc_GenericBiomass_C") + wc * out(rw, "Desc_GenericBiomass_C")
    res = {}
    for name in ("Biomass", "Biofuel"):
        burn_mj = GROSS * 60.0
        if name == "Biomass":
            biomass = burn_mj / MJ_BIOMASS
            extra_con = 0.0
        else:
            bcycles = burn_mj / MJ_BIOFUEL / out(rb, "Desc_Biofuel_C")
            biomass = bcycles * amt(rb, "Desc_GenericBiomass_C")
            extra_con = bcycles / cyc(rb)
        bundles = biomass / biomass_per_bundle
        cons = bundles * lc / cyc(rl) + bundles * wc / cyc(rw) + extra_con
        res[name] = [round(GROSS - cons * con_mw, 4), round(1 + cons, 5), round(bundles * LEAVES, 4), round(bundles * WOOD, 4)]
    return res


grid = json.load(open(gp))
cache = {}
for k, v in grid.items():
    R, P, ph = k.split("|")
    key = (float(R), float(P))
    if key not in cache:
        cache[key] = routes(*key)
    if "Biomass" in v["g"]:
        rest = {n: x for n, x in v["g"].items() if n != "Biomass"}
        v["g"] = {**cache[key], **rest}
json.dump(grid, open(gp, "w", newline="\n"), separators=(",", ":"))
for key in ((1.0, 1.0), (1.0, 5.0), (1.25, 5.0), (2.0, 5.0)):
    print(key, cache[key])
