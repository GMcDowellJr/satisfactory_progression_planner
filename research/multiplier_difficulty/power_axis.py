"""Power axis on the D19/D22 footing — scratch driver, 2026-10-26. NOT repo code.

Reuses mam_bill.py's placement and bills (exec'd from the file beside this).
Everything is ENERGY for the whole phase bill (PA x E + milestones + MAM),
in MW-minutes. It is invariant to time-vs-machines (D19), like machine-minutes.

    demand     manufacturing (LP scenario_mw, P-scaled), plus ore/oil extraction
               at the highest extractor mark open at the phase's top tier
               (D12), plus water extraction, all at normal purity, x P (O1, A7).
               Pickups draw nothing. Nitrogen (resource wells only) is unmapped
               and named.
    supply     per generator type open at the top tier (D6). The generators
               report as a set; none is chosen. Per generator-minute:
               gross MW (not P-scaled, O2) minus parasitic = energy to make
               its fuel at burn rate plus its supplemental water, priced the
               same way (P- and R-scaled). Declared fuel per generator:
               Biomass Leaves (a pickup: zero parasitic), Coal Coal,
               Fuel Fuel, Nuclear Uranium Fuel Rod. Nuclear waste NOT handled.
    output     energy multiplier vs 1/1/1 with components; per generator,
               net MW per unit and the generator-minutes multiplier vs 1/1/1
               on the same generator type.

Usage: python -I power_axis.py <repo> R:P [R:P ...]
"""
import sys, pathlib
here = pathlib.Path(__file__).parent
scen = [tuple(float(x) for x in a.split(":")) for a in sys.argv[2:]] or [(1.0, 5.0)]
sys.argv = [str(here / "mam_bill.py"), sys.argv[1]]
src = open(here / "mam_bill.py").read().split("W = {}")[0]
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(src, "mam_bill", "exec"))

ext_rows = rows("extraction_rates.csv")
RATE = {(r["extractor_class"], r["purity"]): float(r["nominal_rate_min"]) for r in ext_rows}
BASE_MW = {r["extractor_class"]: float(r["base_power_mw"]) for r in rows("extraction_buildings.csv")}
EMAP = {}
for r in rows("resource_extraction_map.csv"):
    EMAP.setdefault(r["item_id"], []).append(r["extractor_class"])
MARK = ["Build_MinerMk3_C", "Build_MinerMk2_C", "Build_MinerMk1_C", "Build_OilPump_C", "Build_WaterPump_C"]
FUEL = {"Build_GeneratorBiomass_Automated_C": "Desc_Leaves_C", "Build_GeneratorCoal_C": "Desc_Coal_C",
        "Build_GeneratorFuel_C": "Desc_LiquidFuel_C", "Build_GeneratorNuclear_C": "Desc_NuclearFuelRod_C"}
GENS = {g.generator_class: g for g in gamedata.load_generators(repo) if FUEL.get(g.generator_class) == g.fuel_item_id}
unmapped = set()


def mw_per_unit(item, ph):
    """Extractor MW per (unit/min) at 1P, highest open mark, normal purity."""
    open_cls = set(unlocks.extractors_open_at_tier(repo, TOP[ph]).get(item, ()))
    for c in MARK:
        if c in open_cls and c in EMAP.get(item, ()):
            rate = RATE.get((c, "normal")) or RATE.get((c, "none"))
            return BASE_MW[c] / rate
    unmapped.add(item)
    return 0.0


def energy(data, bill, ph, P):
    """(manufacturing, ore+oil extraction, water extraction) in MW-minutes."""
    bill = {i: q for i, q in bill.items() if q > 0 and i in names}
    if not bill:
        return 0.0, 0.0, 0.0
    r = be.solve(SolveRequest(outputs=tuple(OutputTarget(i, q * K) for i, q in bill.items()),
                              allowed_recipes=priced_recipes(ph)), data)
    ore = water = 0.0
    for x in r.raw_inputs:
        if x.item_id in PICKUPS:
            continue
        e = x.rate_per_min / K * mw_per_unit(x.item_id, ph) * P
        if x.item_id == "Desc_Water_C":
            water += e
        else:
            ore += e
    return r.power.scenario_mw / K, ore, water


def scenario_data(R, P):
    if (R, P) == (1.0, 1.0):
        return pricing
    return dataclasses.replace(
        base.with_scenario(Scenario(recipe_input_multiplier=R, machine_power_multiplier=P, input_amount_floor=1)),
        resource_items=pricing.resource_items)


def demand(R, P, ph, E=1.0):
    data = scenario_data(R, P)
    pab, msb, mmb = bills(ph)
    bill = collections.Counter()
    for i, q in pab.items(): bill[i] += E * q
    for b in (msb, mmb):
        for i, q in b.items(): bill[i] += q
    return energy(data, bill, ph, P)


def net_per_gen(R, P, ph, g):
    """Net MW from one generator running one minute, after its parasitic load."""
    data = scenario_data(R, P)
    fuel_bill = {g.fuel_item_id: g.burn_rate_per_min}
    m, o, w = energy(data, fuel_bill, ph, P) if g.fuel_item_id not in PICKUPS else (0.0, 0.0, 0.0)
    sup = sum(q * mw_per_unit(i, ph) * P for i, q in g.supplemental)
    return g.power_mw - (m + o + w + sup), m + o + w + sup


base_d = {ph: demand(1.0, 1.0, ph) for ph in TOP}
gens_at = {ph: unlocks.generators_open_at_tier(repo, TOP[ph], tuple(GENS)) for ph in TOP}
print("generators open:", {ph: [GENS[c].generator_class.split('_')[1] for c in v] for ph, v in gens_at.items()})
print("1/1/1 energy, MW-min (mfg, ore, water):", {ph: tuple(round(x) for x in v) for ph, v in base_d.items()})
for R, P in scen:
    print(f"== R{R:g} P{P:g}   energy multiplier = mfg + ore + water | per open generator: net MW/unit (parasitic) -> generator-minutes x")
    for ph in TOP:
        d = demand(R, P, ph); b = sum(base_d[ph])
        cells = []
        for c in gens_at[ph]:
            g = GENS[c]
            n, par = net_per_gen(R, P, ph, g); n1, _ = net_per_gen(1.0, 1.0, ph, g)
            mult = (sum(d) / n) / (b / n1) if n > 0 else float("inf")
            cells.append(f"{c.split('_')[1]} {n:.1f} ({par:.1f}) -> {mult:.2f}x")
        print(f"  ph{ph} {sum(d)/b:6.2f} = {d[0]/b:.2f}+{d[1]/b:.2f}+{d[2]/b:.2f} | " + "; ".join(cells))
if unmapped:
    print("unmapped (no extractor MW):", sorted(names.get(i, i) for i in unmapped))
