"""The Phase 2 reference district: the DECLARATION. Data as code; nothing runs.

Crossover A26.1 C2 (the fixture is declared here) and A27.1 K1 (both clocks
are inputs, so the extraction clock has two named cases and neither is "the"
reference). Greg's district as reported to the v5.4.x planner and in its
README_V5_4_4 regression scenario; the recipe set is the alternate family the
v5.5 plan requires the fixture to preserve, resolved by display name through
`gamedata` so an edit to recipes.csv refuses rather than drifts.

    nodes        3 pure Iron, 2 pure Coal, 1 pure Limestone, 1 normal Caterium,
                 plus 2 Water Extractors (phase 1's carry, A25.1 O7 / A20)
    extractor    Miner Mk.1 for the ores; the water nodes name their own
    power        A34 (Greg, 2026-10-08): 4 standing coal generators, 300 MW,
                 fed from the district's own coal and water (their draw
                 comes off the caps first); the plan STATES the factory's
                 draw against that supply. Power is not in the solve here;
                 district_run --power puts it in (A29) with the standing
                 300 MW as the supply and no new generators
    clocks       extraction: "shipped" 100 % (TEST_V5_4_3_DISTRICT_SCENARIO.js)
                 and "readme" 25 % (README_V5_4_4); machine clock 25 % (both)
    reserve      0
    scenario     1.25x recipe cost, 5x machine power (A25 / the challenge run)
    recipes      ONE PER ITEM, read from the partition (A34, Greg: "single
                 recipe per bus"); the tier filter plus the DECLARED names
                 (MAM caterium, the five alternates) must grant every one,
                 else the run refuses
    bill         A31 (Greg, 2026-10-08: value is what is needed later). The
                 three terminal products the v5.5 plan names are BILL
                 products: their proportions come from Project Assembly
                 phase 2 plus the milestone costs of tiers 3, 4 and 5 (the
                 current tiers and the next, A25.2 O11). Measured 2026-10-08:
                 VF 1000, EIB 600, Motor 200 (Motor appears in no tier 3-4
                 milestone; tier 5 is why it is in the bill at all). A34
                 (Greg): EVERY makeable bill item is a target unless
                 BILL_EXCLUDED names it; weight 1.0 each. No floors: a bill
                 product gets its proportion or the solve says which cap
                 stops it. EXTRAS is empty; it is where a declared trickle
                 outside the bill would go
    baseline     the v5.4.4 shipped-fixture portfolio, for the Stage 0 row
                 (measured 2026-10-08, node v22.22.0)

    partition    one bus per item, its recipe DECLARED (a tripwire: a plan
                 that picks another recipe is refused by name, A30), every
                 line clocked explicitly and NOT storing (stores=False), so
                 the realized rates are the plan's rates (v5.5 "factory
                 parity"); the residual realization reports is idle
                 headroom of whole machines, not overflow. extra_producers 0: the
                 minimum machine set. The PWA's 25 % maximum machine clock
                 (MACHINE_CLOCK) is NOT applied: realization has no
                 machines-versus-clock policy (LP 22.4, A29.3 O29)

`tools/district_run.py` composes it; tests/test_district_phase2.py pins it.
"""
from __future__ import annotations

from production_adapter import DistrictTarget, Scenario
from progression import NodeCount
from realization import BusDeclaration, ClockMode, SourceEdge

LABEL = "phase 2 reference district (tiers 3-4)"
PHASE = 2
TIERS = (3, 4)
RECIPE_TIER = 4
#: the PWA scenario's maximum machine clock. Carried, NOT applied (see partition)
MACHINE_CLOCK = 0.25
DESIGN_TIER = 4

I = dict(
    ORE="Desc_OreIron_C", COAL="Desc_Coal_C", STONE="Desc_Stone_C", GOLD="Desc_OreGold_C",
    VF="Desc_SpaceElevatorPart_2_C", MOTOR="Desc_Motor_C", EIB="Desc_SteelPlateReinforced_C",
    PIPE="Desc_SteelPipe_C", BEAM="Desc_SteelPlate_C", ROT="Desc_Rotor_C",
    CON="Desc_Cement_C", QW="Desc_HighSpeedWire_C", WATER="Desc_Water_C",
    SP="Desc_SpaceElevatorPart_1_C", AW="Desc_SpaceElevatorPart_3_C", CABLE="Desc_Cable_C",
    RIP="Desc_IronPlateReinforced_C", STA="Desc_Stator_C", MF="Desc_ModularFrame_C",
    STI="Desc_SteelIngot_C", SCR="Desc_IronScrew_C", PLT="Desc_IronPlate_C",
    ROD="Desc_IronRod_C", ING="Desc_IronIngot_C", WIRE="Desc_Wire_C", CAT="Desc_GoldIngot_C",
)

NODES = (
    NodeCount(I["ORE"], "pure", 3),
    NodeCount(I["COAL"], "pure", 2),
    NodeCount(I["STONE"], "pure", 1),
    NodeCount(I["GOLD"], "normal", 1),
    #: at 100 % in every case (A34.2 F5): they feed the standing generators
    NodeCount(I["WATER"], "none", 2, extractor_class="Build_WaterPump_C", extraction_clock=1.0),
)
EXTRACTOR = "Build_MinerMk1_C"
#: A34: standing generators (class, fuel, count), fed from the district's caps.
#: Greg, 2026-10-08: "4 coal generators make 300 MW"
STANDING_GENERATORS = (("Build_GeneratorCoal_C", I["COAL"], 4),)
#: the required margin when power is put IN the solve (--power); the v5.4.1 setting
SPARE_MW = 30.0
#: A27.1 K1: two cases, both inputs. Keys are the CLI's --case values.
EXTRACTION_CLOCK_CASES = {"shipped": 1.0, "readme": 0.25}
RESERVE = 0.0

SCENARIO = Scenario(recipe_input_multiplier=1.25, machine_power_multiplier=5.0)

#: recipes.csv display names, exactly as spelled. Refused on 0 or several hits.
DECLARED_RECIPE_NAMES = (
    "Caterium Ingot",
    "Quickwire",
    "Alternate: Iron Wire",
    "Alternate: Stitched Iron Plate",
    "Alternate: Solid Steel Ingot",
    "Alternate: Quickwire Stator",
    "Alternate: Steel Rotor",
)

#: A31: the bill's sources, declared. Project Assembly phases and the
#: schematic tiers whose milestone costs are still owed
BILL_PHASES = (2,)
BILL_TIERS = (3, 4, 5)
#: A34: bill items NOT to make here, by id. Everything else makeable is a target
BILL_EXCLUDED: tuple[str, ...] = ()
#: weight of every bill product (A31 V5: 1.0 = worth what the bill says)
BILL_WEIGHT = 1.0
#: extras outside the bill (A27.2 shape): none declared
EXTRAS: tuple[DistrictTarget, ...] = ()

B, S = BusDeclaration, SourceEdge
R = dict(
    SP="Recipe_SpaceElevatorPart_1_C", AW="Recipe_SpaceElevatorPart_3_C", CABLE="Recipe_Cable_C",
    VF="Recipe_SpaceElevatorPart_2_C", MOTOR="Recipe_Motor_C", EIB="Recipe_EncasedIndustrialBeam_C",
    MF="Recipe_ModularFrame_C", RIP="Recipe_Alternate_ReinforcedIronPlate_2_C",   # Stitched Iron Plate
    ROT="Recipe_Rotor_C", STA="Recipe_Alternate_Stator_C",                          # Quickwire Stator
    BEAM="Recipe_SteelBeam_C", PIPE="Recipe_SteelPipe_C",
    STI="Recipe_Alternate_IngotSteel_1_C",                                           # Solid Steel Ingot
    PLT="Recipe_IronPlate_C", ROD="Recipe_IronRod_C", SCR="Recipe_Screw_C",
    WIRE="Recipe_Alternate_Wire_1_C",                                                # Iron Wire
    ING="Recipe_IngotIron_C", CON="Recipe_Concrete_C", CAT="Recipe_IngotCaterium_C",
    QW="Recipe_Quickwire_C",
)
#: every line: declared recipe, explicit clock, not storing (see module docstring)
X = dict(stores=False, clock_mode=ClockMode.EXPLICIT)
#: the partition (see module docstring): one bus per item the site makes of the
#: bill, its recipe declared; the solve's recipe set is read from here (A34)
BUSES = (
    B(bus_id="smart_plating", item_id=I["SP"], recipe_id=R["SP"],
      sources=(S(I["RIP"], "rip"), S(I["ROT"], "rotor"),), **X),
    B(bus_id="automated_wiring", item_id=I["AW"], recipe_id=R["AW"],
      sources=(S(I["STA"], "stator"), S(I["CABLE"], "cable"),), **X),
    B(bus_id="cable", item_id=I["CABLE"], recipe_id=R["CABLE"],
      sources=(S(I["WIRE"], "wire"),), **X),
    B(bus_id="versatile_framework", item_id=I["VF"], recipe_id=R["VF"],
      sources=(S(I["MF"], "modular_frame"), S(I["BEAM"], "steel_beam"),), **X),
    B(bus_id="motor", item_id=I["MOTOR"], recipe_id=R["MOTOR"],
      sources=(S(I["ROT"], "rotor"), S(I["STA"], "stator"),), **X),
    B(bus_id="encased_industrial_beam", item_id=I["EIB"], recipe_id=R["EIB"],
      sources=(S(I["BEAM"], "steel_beam"), S(I["CON"], "concrete"),), **X),
    B(bus_id="modular_frame", item_id=I["MF"], recipe_id=R["MF"],
      sources=(S(I["RIP"], "rip"), S(I["ROD"], "iron_rod"),), **X),
    B(bus_id="rip", item_id=I["RIP"], recipe_id=R["RIP"],
      sources=(S(I["PLT"], "iron_plate"), S(I["WIRE"], "wire"),), **X),
    B(bus_id="rotor", item_id=I["ROT"], recipe_id=R["ROT"],
      sources=(S(I["ROD"], "iron_rod"), S(I["SCR"], "screws"),), **X),
    B(bus_id="stator", item_id=I["STA"], recipe_id=R["STA"],
      sources=(S(I["PIPE"], "steel_pipe"), S(I["QW"], "quickwire"),), **X),
    B(bus_id="steel_beam", item_id=I["BEAM"], recipe_id=R["BEAM"],
      sources=(S(I["STI"], "steel_ingot"),), **X),
    B(bus_id="steel_pipe", item_id=I["PIPE"], recipe_id=R["PIPE"],
      sources=(S(I["STI"], "steel_ingot"),), **X),
    B(bus_id="steel_ingot", item_id=I["STI"], recipe_id=R["STI"],
      sources=(S(I["ING"], "iron_ingot"), S(I["COAL"], None),), **X),
    B(bus_id="iron_plate", item_id=I["PLT"], recipe_id=R["PLT"],
      sources=(S(I["ING"], "iron_ingot"),), **X),
    B(bus_id="iron_rod", item_id=I["ROD"], recipe_id=R["ROD"],
      sources=(S(I["ING"], "iron_ingot"),), **X),
    B(bus_id="screws", item_id=I["SCR"], recipe_id=R["SCR"],
      sources=(S(I["ROD"], "iron_rod"),), **X),
    B(bus_id="wire", item_id=I["WIRE"], recipe_id=R["WIRE"],
      sources=(S(I["ING"], "iron_ingot"),), **X),
    B(bus_id="iron_ingot", item_id=I["ING"], recipe_id=R["ING"],
      sources=(S(I["ORE"], None),), **X),
    B(bus_id="concrete", item_id=I["CON"], recipe_id=R["CON"],
      sources=(S(I["STONE"], None),), **X),
    B(bus_id="caterium_ingot", item_id=I["CAT"], recipe_id=R["CAT"],
      sources=(S(I["GOLD"], None),), **X),
    B(bus_id="quickwire", item_id=I["QW"], recipe_id=R["QW"],
      sources=(S(I["CAT"], "caterium_ingot"),), **X),
)

#: v5.4.4 on its shipped fixture (100 % extraction), items per minute. Stator
#: and Motor received 0 there. The Stage 0 baseline row re-solves THESE rates as
#: demands under the composed caps, so the shared-intermediate ledger can be
#: compared with the PWA's five separate Solid Steel Ingot banks.
V544_SHIPPED_RATES = (
    (I["PIPE"], 30.0), (I["BEAM"], 12.3), (I["EIB"], 3.8), (I["VF"], 1.1),
    (I["ROT"], 4.0), (I["CON"], 7.2), (I["QW"], 60.0),
)
