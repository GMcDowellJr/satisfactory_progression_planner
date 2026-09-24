"""Phase 2 (tiers 3-4): the DECLARATION. Data as code; nothing here runs.

Moved out of tests/test_phase_two_run.py (Greg, 2026-09-24: "Python module +
CLI") so a run at another anchor rate is a CLI argument, not a test edit.
`tools/phase_run.py` composes it; the test imports it and pins its figures.

    partition   one bus per item, all storing, plus the build-material lines
                and an Encased Industrial Beam line (A19 M2, confirmed as-is)
    goals       Project Assembly phase 2, anchored on Smart Plating (A15.1)
    recipes     at_tier(RECIPE_TIER), standard recipes only
    unlocks     every schematic with tech_tier in TIERS (A19 M1)
    bootstrap   derived by the A19 minimum against PREVIOUS_TIER, plus
                POWER_STEP added per class (A20). POWER_STEP is DECLARED:
                power is outside the A19 rule
"""
from __future__ import annotations

from realization import BusDeclaration, SourceEdge

LABEL = "phase 2 (tiers 3-4)"
PHASE = 2
TIERS = (3, 4)
PREVIOUS_TIER = 2
RECIPE_TIER = 4
DESIGN_TIER = 4
ANCHOR_ITEM = "Desc_SpaceElevatorPart_1_C"
#: A20: the Mk1 coal step "for now" (2 Miner Mk.1, 4 coal generators, 2 water extractors)
POWER_STEP = (("Build_MinerMk1_C", 2), ("Build_GeneratorCoal_C", 4), ("Build_WaterPump_C", 2))

B, S = BusDeclaration, SourceEdge
#: item ids
I = dict(SP="Desc_SpaceElevatorPart_1_C", VF="Desc_SpaceElevatorPart_2_C", AW="Desc_SpaceElevatorPart_3_C",
 MF="Desc_ModularFrame_C", STA="Desc_Stator_C", BEAM="Desc_SteelPlate_C", PIPE="Desc_SteelPipe_C",
 STI="Desc_SteelIngot_C", RIP="Desc_IronPlateReinforced_C", ROT="Desc_Rotor_C", SCR="Desc_IronScrew_C",
 PLT="Desc_IronPlate_C", ROD="Desc_IronRod_C", ING="Desc_IronIngot_C", ORE="Desc_OreIron_C", COAL="Desc_Coal_C",
 CU="Desc_CopperIngot_C", CUO="Desc_OreCopper_C", WIRE="Desc_Wire_C", CABLE="Desc_Cable_C", SHEET="Desc_CopperSheet_C",
 STONE="Desc_Stone_C", CON="Desc_Cement_C", EIB="Desc_SteelPlateReinforced_C")
#: the phase-2 partition (see module docstring)
BUSES = (
 B(bus_id="smart_plating", item_id=I["SP"], sources=(S(I["RIP"],"rip"), S(I["ROT"],"rotor"))),
 B(bus_id="versatile_framework", item_id=I["VF"], sources=(S(I["MF"],"modular_frame"), S(I["BEAM"],"steel_beam"))),
 B(bus_id="automated_wiring", item_id=I["AW"], sources=(S(I["STA"],"stator"), S(I["CABLE"],"cable"))),
 B(bus_id="modular_frame", item_id=I["MF"], sources=(S(I["RIP"],"rip"), S(I["ROD"],"iron_rod"))),
 B(bus_id="stator", item_id=I["STA"], sources=(S(I["PIPE"],"steel_pipe"), S(I["WIRE"],"wire"))),
 B(bus_id="steel_beam", item_id=I["BEAM"], sources=(S(I["STI"],"steel_ingot"),)),
 B(bus_id="steel_pipe", item_id=I["PIPE"], sources=(S(I["STI"],"steel_ingot"),)),
 B(bus_id="steel_ingot", item_id=I["STI"], sources=(S(I["ORE"],None), S(I["COAL"],None))),
 B(bus_id="rip", item_id=I["RIP"], sources=(S(I["PLT"],"iron_plate"), S(I["SCR"],"screws"))),
 B(bus_id="rotor", item_id=I["ROT"], sources=(S(I["ROD"],"iron_rod"), S(I["SCR"],"screws"))),
 B(bus_id="screws", item_id=I["SCR"], sources=(S(I["ROD"],"iron_rod"),)),
 B(bus_id="iron_plate", item_id=I["PLT"], sources=(S(I["ING"],"iron_ingot"),)),
 B(bus_id="iron_rod", item_id=I["ROD"], sources=(S(I["ING"],"iron_ingot"),)),
 B(bus_id="iron_ingot", item_id=I["ING"], sources=(S(I["ORE"],None),)),
 B(bus_id="copper_ingot", item_id=I["CU"], sources=(S(I["CUO"],None),)),
 B(bus_id="wire", item_id=I["WIRE"], sources=(S(I["CU"],"copper_ingot"),)),
 B(bus_id="cable", item_id=I["CABLE"], sources=(S(I["WIRE"],"wire"),)),
 B(bus_id="copper_sheet", item_id=I["SHEET"], recipe_id="Recipe_CopperSheet_C", sources=(S(I["CU"],"copper_ingot"),)),
 B(bus_id="concrete", item_id=I["CON"], recipe_id="Recipe_Concrete_C", sources=(S(I["STONE"],None),)),
 B(bus_id="encased_industrial_beam", item_id=I["EIB"], recipe_id="Recipe_EncasedIndustrialBeam_C",
   sources=(S(I["BEAM"],"steel_beam"), S(I["CON"],"concrete"))),
)
