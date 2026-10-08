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
    power        A25.3 P1 in the solve (A29): coal generators may be built,
                 900 MW existing/imported grid and 30 MW spare as Greg's
                 PWA scenario states them; extraction at nameplate (P2)
    clocks       extraction: "shipped" 100 % (TEST_V5_4_3_DISTRICT_SCENARIO.js)
                 and "readme" 25 % (README_V5_4_4); machine clock 25 % (both)
    reserve      0
    scenario     1.25x recipe cost, 5x machine power (A25 / the challenge run)
    recipes      at_tier(4) standard recipes + DECLARED: the two MAM caterium
                 base recipes (the tier filter withholds research) and the
                 five alternates of the built factory
    bill         A31 (Greg, 2026-10-08: value is what is needed later). The
                 three terminal products the v5.5 plan names are BILL
                 products: their proportions come from Project Assembly
                 phase 2 plus the milestone costs of tiers 3, 4 and 5 (the
                 current tiers and the next, A25.2 O11). Measured 2026-10-08:
                 VF 1000, EIB 600, Motor 200 (Motor appears in no tier 3-4
                 milestone; tier 5 is why it is in the bill at all). Weight
                 1.0 each: spare capacity is worth what the bill says. No
                 floors: a bill product gets its proportion or the solve
                 says which cap stops it. EXTRAS is empty; it is where a
                 declared trickle outside the bill would go
    baseline     the v5.4.4 shipped-fixture portfolio, for the Stage 0 row
                 (measured 2026-10-08, node v22.22.0)

`tools/district_run.py` composes it; tests/test_district_phase2.py pins it.
"""
from __future__ import annotations

from production_adapter import DistrictTarget, Scenario
from progression import NodeCount

LABEL = "phase 2 reference district (tiers 3-4)"
PHASE = 2
TIERS = (3, 4)
RECIPE_TIER = 4
#: realization's preferred clock (v5.5 rule 2 keeps it distinct from a trickle)
MACHINE_CLOCK = 0.25

I = dict(
    ORE="Desc_OreIron_C", COAL="Desc_Coal_C", STONE="Desc_Stone_C", GOLD="Desc_OreGold_C",
    VF="Desc_SpaceElevatorPart_2_C", MOTOR="Desc_Motor_C", EIB="Desc_SteelPlateReinforced_C",
    PIPE="Desc_SteelPipe_C", BEAM="Desc_SteelPlate_C", ROT="Desc_Rotor_C",
    CON="Desc_Cement_C", QW="Desc_HighSpeedWire_C", WATER="Desc_Water_C",
)

NODES = (
    NodeCount(I["ORE"], "pure", 3),
    NodeCount(I["COAL"], "pure", 2),
    NodeCount(I["STONE"], "pure", 1),
    NodeCount(I["GOLD"], "normal", 1),
    NodeCount(I["WATER"], "none", 2, extractor_class="Build_WaterPump_C"),
)
EXTRACTOR = "Build_MinerMk1_C"
#: power in the solve (A29): generator classes the district may build, the
#: declared outside supply, and the required margin. Values from Greg's
#: v5.4.1 reproduction settings (900 MW grid, 30 MW spare)
GENERATORS = ("Build_GeneratorCoal_C",)
GRID_MW = 900.0
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
#: bill products: (item, weight). Units come from the bill at run time
BILL_TARGETS = ((I["VF"], 1.0), (I["MOTOR"], 1.0), (I["EIB"], 1.0))
#: extras outside the bill (A27.2 shape): none declared
EXTRAS: tuple[DistrictTarget, ...] = ()

#: v5.4.4 on its shipped fixture (100 % extraction), items per minute. Stator
#: and Motor received 0 there. The Stage 0 baseline row re-solves THESE rates as
#: demands under the composed caps, so the shared-intermediate ledger can be
#: compared with the PWA's five separate Solid Steel Ingot banks.
V544_SHIPPED_RATES = (
    (I["PIPE"], 30.0), (I["BEAM"], 12.3), (I["EIB"], 3.8), (I["VF"], 1.1),
    (I["ROT"], 4.0), (I["CON"], 7.2), (I["QW"], 60.0),
)
