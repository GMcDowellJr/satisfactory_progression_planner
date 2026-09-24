"""1x recipe / 1x power / 1x elevator: 1 Smart Plating/min to the first 50 (Space Elevator phase 1)."""
import sys, pathlib, math
REPO = pathlib.Path('.').resolve()
for p in ("production_adapter", "progression", "realization"):
    sys.path.insert(0, str(REPO / "tools" / p / "src"))
from production_adapter import load, OutputTarget, SolveRequest, Scenario
from production_adapter.gamedata import load_construction, load_logistics
from production_adapter.lp_backend import LpBackend, PowerStatistic
from progression import at_tier, stock, unlocks
from realization import buses as B
from realization.realize import project_goals
from realization.contracts import BusDeclaration, RealizationRequest, SourceEdge, Disposition, ClockMode

SP, RIP, ROT, SCR, PLT, ROD, ING, ORE = ("Desc_SpaceElevatorPart_1_C","Desc_IronPlateReinforced_C","Desc_Rotor_C",
    "Desc_IronScrew_C","Desc_IronPlate_C","Desc_IronRod_C","Desc_IronIngot_C","Desc_OreIron_C")
TIER = 2
data = load(REPO)                       # Scenario(): 1x recipe, 1x power, 1x Project Assembly
print("scenario:", data.scenario if hasattr(data,'scenario') else Scenario())
caps, extraction = load_logistics(REPO)
allowed = at_tier(REPO, TIER).allowed_recipes
resp = LpBackend(power_statistic=PowerStatistic.MEAN).solve(
    SolveRequest(outputs=(OutputTarget(SP, 1.0),), allowed_recipes=allowed), data)
print("\n[1] LP solve, continuous")
for u in resp.recipes: print(f"   {u.recipe_id:34}{u.machine_equivalents:8.4f}")
print(f"   ore {resp.raw_inputs[0].rate_per_min:.2f}/min   power {resp.power.scenario_mw:.2f} MW (excl. extraction)")

def decl(sp_disp, **kw):
    return RealizationRequest(design_tier=TIER, buses=(
        BusDeclaration(bus_id="smart_plating", item_id=SP, sources=(SourceEdge(RIP,"rip"),SourceEdge(ROT,"rotor")), disposition=sp_disp, **kw),
        BusDeclaration(bus_id="rip", item_id=RIP, sources=(SourceEdge(PLT,"iron_plate"),SourceEdge(SCR,"screws")), disposition=Disposition.WITHDRAWN),
        BusDeclaration(bus_id="rotor", item_id=ROT, sources=(SourceEdge(ROD,"iron_rod"),SourceEdge(SCR,"screws")), disposition=Disposition.WITHDRAWN),
        BusDeclaration(bus_id="screws", item_id=SCR, sources=(SourceEdge(ROD,"iron_rod"),), disposition=Disposition.WITHDRAWN),
        BusDeclaration(bus_id="iron_plate", item_id=PLT, sources=(SourceEdge(ING,"iron_ingot"),), disposition=Disposition.WITHDRAWN),
        BusDeclaration(bus_id="iron_rod", item_id=ROD, sources=(SourceEdge(ING,"iron_ingot"),), disposition=Disposition.WITHDRAWN),
        BusDeclaration(bus_id="iron_ingot", item_id=ING, sources=(SourceEdge(ORE,None),), disposition=Disposition.WITHDRAWN),
    ))
for label, req in (("ALL BACK_UP, backpressure", RealizationRequest(design_tier=TIER, buses=tuple(__import__("dataclasses").replace(b, disposition=Disposition.BACK_UP) for b in decl(Disposition.WITHDRAWN).buses))), ("WITHDRAWN (runs flat out)", decl(Disposition.WITHDRAWN)),
                   ("BACK_UP, clocked to 1/min", decl(Disposition.BACK_UP, clock_mode=ClockMode.EXPLICIT))):
    buses = B.buses_from_response(resp, data, req, caps)
    print(f"\n[2] realization, Smart Plating {label}")
    print(f"   {'bus':14}{'mach':>5}{'clock%':>8}{'supply':>8}{'auto':>8}{'resid':>8}{'power MW':>9}")
    for b in buses:
        clk = ",".join(f"{l.clock_percent:.1f}" for l in b.lanes)
        print(f"   {b.bus_id:14}{b.machines:5}{clk:>8}{b.supply_per_min:8.2f}{b.automated_demand_per_min:8.2f}{b.residual.rate_per_min:8.2f}{sum(l.power_mw for l in b.lanes):9.2f}")
        for f in B.feasibility(b): print("     !", f)
    g, = project_goals(buses, (("phase 1", SP, 50.0),))
    print(f"   -> 50 Smart Plating at {g.rate_per_min:.2f}/min = {g.minutes_to_complete:.1f} min of running")
    machines = {}
    for b in buses:
        for l in b.lanes: machines[l.producer_class] = machines.get(l.producer_class, 0) + l.machines
    print("   machines:", machines, " total", sum(machines.values()))

construction = load_construction(REPO)
sp_pass = stock.bill_for(data, construction,
    bootstrap=stock.BootstrapSet(tier=TIER, buildings=(("Build_MinerMk1_C",1),("Build_GeneratorBiomass_Automated_C",1))),
    machines=tuple(sorted(machines.items())),
    unlocks=unlocks.schematics_at_tier(REPO, TIER), unlock_costs=unlocks.schematic_costs(REPO),
    project_assembly=stock.load_project_assembly(REPO, data), phases=(1,))
print("\n[3] stock pass: the bill to get there (bootstrap + machines + unlocks tiers 0-2 + phase 1 delivery)")
print(f"   {'item':34}{'bootstrap':>10}{'remainder':>10}{'total':>9}")
for item, bill in sorted(sp_pass.bills.items(), key=lambda kv: -(kv[1].bootstrap_units+kv[1].remainder_units)):
    print(f"   {data.items[item].display_name if hasattr(data.items[item],'display_name') else item:34}{bill.bootstrap_units:10.0f}{bill.remainder_units:10.0f}{bill.bootstrap_units+bill.remainder_units:9.0f}")
print("   unresolved:", sp_pass.unresolved)
print("   terms:", sorted(t.value for t in next(iter(sp_pass.bills.values())).terms))
print("\n[check] WITHDRAWN smart_plating: lane inputs vs what the source buses book")
buses = {b.bus_id: b for b in B.buses_from_response(resp, data, decl(Disposition.WITHDRAWN), caps)}
for l in buses["smart_plating"].lanes:
    for i in l.inputs: print(f"   lane takes {i.item_id:28}{i.rate_per_min:6.2f}/min from {i.source_bus_id}")
for k in ("rip","rotor"):
    print(f"   {k} books smart_plating at", [(c.draw_per_min, c.peak_per_min) for c in buses[k].consumers])
