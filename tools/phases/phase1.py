"""Phase 1 (tier 2): the DECLARATION. Data as code; nothing here runs.

D6 build step 1 (project doc d6-phase-defaults-and-lane-standing-design,
Amendment 2 P1, Greg 2026-09-24). Moved from tests/test_goal_run.py's case of
record (goal_run_driver.md amendment 4) so phase 2 has a phase 1 to default
its standing from (D6 G1). `tools/phase_run.py` composes it.

    partition   the first-50 partition plus the build-material lines, each
                build-material line carrying its recipe_id (P30). Bus ids
                match phase 2's for every shared item: standing is matched
                by bus_id (D6 G3), asserted in tests/test_phase_standing.py
    goals       Project Assembly phase 1, anchored on Smart Plating
    recipes     at_tier(RECIPE_TIER), standard recipes only
    unlocks     every schematic with tech_tier in TIERS. TIERS = (2,) is what
                the case of record bills; tier 1 is not billed here
    bootstrap   DECLARED outright: the Mk1 coal step as the TARGET for
                bringing tier 3 online, as the record declares it. Not A19 +
                POWER_STEP: that shape would add 2 assemblers (Rotor, Smart
                Plating) the record does not bill (D6 Amendment 2 P1).
                `phase_run` refuses a declaration carrying BOOTSTRAP and
                POWER_STEP or PREVIOUS_TIER together
"""
from __future__ import annotations

from realization import BusDeclaration, SourceEdge

LABEL = "phase 1 (tier 2)"
PHASE = 1
TIERS = (2,)
RECIPE_TIER = 2
DESIGN_TIER = 2
ANCHOR_ITEM = "Desc_SpaceElevatorPart_1_C"
#: The case of record's bootstrap target (amendment 4): the Mk1 coal step
BOOTSTRAP = (("Build_MinerMk1_C", 2), ("Build_GeneratorCoal_C", 4), ("Build_WaterPump_C", 2))

B, S = BusDeclaration, SourceEdge
#: item ids
I = dict(SP="Desc_SpaceElevatorPart_1_C", RIP="Desc_IronPlateReinforced_C", ROT="Desc_Rotor_C",
 SCR="Desc_IronScrew_C", PLT="Desc_IronPlate_C", ROD="Desc_IronRod_C", ING="Desc_IronIngot_C",
 ORE="Desc_OreIron_C", CUO="Desc_OreCopper_C", CU="Desc_CopperIngot_C", WIRE="Desc_Wire_C",
 CABLE="Desc_Cable_C", SHEET="Desc_CopperSheet_C", STONE="Desc_Stone_C", CON="Desc_Cement_C")
#: the case of record's partition (see module docstring)
BUSES = (
 B(bus_id="smart_plating", item_id=I["SP"], sources=(S(I["RIP"],"rip"), S(I["ROT"],"rotor"))),
 B(bus_id="rip", item_id=I["RIP"], sources=(S(I["PLT"],"iron_plate"), S(I["SCR"],"screws"))),
 B(bus_id="rotor", item_id=I["ROT"], sources=(S(I["ROD"],"iron_rod"), S(I["SCR"],"screws"))),
 B(bus_id="screws", item_id=I["SCR"], sources=(S(I["ROD"],"iron_rod"),)),
 B(bus_id="iron_plate", item_id=I["PLT"], sources=(S(I["ING"],"iron_ingot"),)),
 B(bus_id="iron_rod", item_id=I["ROD"], sources=(S(I["ING"],"iron_ingot"),)),
 B(bus_id="iron_ingot", item_id=I["ING"], sources=(S(I["ORE"],None),)),
 B(bus_id="copper_ingot", item_id=I["CU"], recipe_id="Recipe_IngotCopper_C", sources=(S(I["CUO"],None),)),
 B(bus_id="wire", item_id=I["WIRE"], recipe_id="Recipe_Wire_C", sources=(S(I["CU"],"copper_ingot"),)),
 B(bus_id="cable", item_id=I["CABLE"], recipe_id="Recipe_Cable_C", sources=(S(I["WIRE"],"wire"),)),
 B(bus_id="copper_sheet", item_id=I["SHEET"], recipe_id="Recipe_CopperSheet_C", sources=(S(I["CU"],"copper_ingot"),)),
 B(bus_id="concrete", item_id=I["CON"], recipe_id="Recipe_Concrete_C", sources=(S(I["STONE"],None),)),
)
