"""The saved bus declarations. Restated from PRIMARY sources.

Every declaration here names where each of its parts came from. This is not
bookkeeping: the handoff names the specific trap for this work -- reconstructing
a declaration out of the output table it is supposed to reproduce -- and a
declaration whose source is not stated cannot be told apart from one that fell
into it.

TWO CASES, AND THEY CONTRADICT EACH OTHER ON ONE FIELD. Carried as two
declarations rather than reconciled in a note:

    STORAGE_REVIEW_*   the bundle config at
                       `scratchpad/satisfactory_storage_model_bundle/`, which
                       declares Screws as "Alternate: Cast Screws" (50/min) and
                       whose `_notes` say "Phase 1 uses default Rotor + Cast
                       Screws". One bus per item.
    WORKED_CASE_A4     the topology A3.1 describes and A3.5 computes, which runs
                       the BASE Screw recipe at 40/min. Split Wire buses.

The contradiction is real and is visible here rather than argued. A3.5's own
figures settle which recipe it ran under, independently of its screw row: its
Iron Rod bus draws 64.00/min, which is Rotor's 24.00 plus four screw machines at
10 rod/min each. Cast Screws draws iron INGOT and no rod at all, so no Cast
Screws configuration produces 64.00. The bundle config is the older artifact and
is not corrected here -- it is a different declaration, and forward-only.
"""
from __future__ import annotations

from typing import Mapping, Sequence

from production_adapter.gamedata import ReferenceData
from realization.contracts import Disposition

from .model import BusSpec, Declaration, SourceEdge


def _recorded(disposition: Disposition, *, withdrawal: bool = True) -> dict:
    """The `BusSpec` keywords that reproduce a PUBLISHED disposition. A12, Q5.

    The record was written in dispositions; the model is now declared in the
    storage toggle (D1). Where the toggle derives the record's disposition this
    returns the toggle alone. Where it cannot — BACK_UP with a withdrawal, a
    storing line observed after its container saturated, and SUNK — it adds
    the record path, `recorded_disposition`. This module is the only place
    under `tools/*/src` that uses it; `tests/test_refusals.py` asserts that by
    inspection.

    `withdrawal` is whether the spec being built declares one, which is what
    decides MATCHED against BACK_UP on the toggle's side.
    """
    stores = disposition in (Disposition.WITHDRAWN, Disposition.SUNK)
    derived = (
        Disposition.WITHDRAWN if stores
        else Disposition.MATCHED if withdrawal
        else Disposition.BACK_UP
    )
    if derived is disposition:
        return {"stores": stores}
    return {"stores": stores, "recorded_disposition": disposition}

# --------------------------------------------------------------------------
# ids, keyed canonically
# --------------------------------------------------------------------------
# `recipe_id` and `item_id`, never `display_name`. Storage review 6.3 records a
# display-name lookup raising on `Turbo Rifle Ammo`, which is duplicated in the
# shipped data (Recipe_CartridgeChaos_C / Recipe_CartridgeChaos_Packaged_C).

R_STITCHED_RIP = "Recipe_Alternate_ReinforcedIronPlate_2_C"
R_BASE_RIP = "Recipe_IronPlateReinforced_C"
R_CAST_SCREWS = "Recipe_Alternate_Screw_C"
R_BASE_SCREWS = "Recipe_Screw_C"
R_IRON_WIRE = "Recipe_Alternate_Wire_1_C"
R_WIRE = "Recipe_Wire_C"
R_CABLE = "Recipe_Cable_C"
R_CONCRETE = "Recipe_Concrete_C"
R_IRON_PLATE = "Recipe_IronPlate_C"
R_IRON_ROD = "Recipe_IronRod_C"
R_IRON_INGOT = "Recipe_IngotIron_C"
R_COPPER_INGOT = "Recipe_IngotCopper_C"
R_ROTOR = "Recipe_Rotor_C"
R_MODULAR_FRAME = "Recipe_ModularFrame_C"
R_SMART_PLATING = "Recipe_SpaceElevatorPart_1_C"
R_STEEL_BEAM = "Recipe_SteelBeam_C"
R_STEEL_PIPE = "Recipe_SteelPipe_C"
R_COPPER_SHEET = "Recipe_CopperSheet_C"
R_ENCASED_INDUSTRIAL_PIPE = "Recipe_Alternate_EncasedIndustrialBeam_C"

I_RIP = "Desc_IronPlateReinforced_C"
I_SCREW = "Desc_IronScrew_C"
I_WIRE = "Desc_Wire_C"
I_CABLE = "Desc_Cable_C"
I_CONCRETE = "Desc_Cement_C"
I_IRON_PLATE = "Desc_IronPlate_C"
I_IRON_ROD = "Desc_IronRod_C"
I_IRON_INGOT = "Desc_IronIngot_C"
I_COPPER_INGOT = "Desc_CopperIngot_C"
I_ROTOR = "Desc_Rotor_C"
I_MODULAR_FRAME = "Desc_ModularFrame_C"
I_SMART_PLATING = "Desc_SpaceElevatorPart_1_C"
I_STEEL_BEAM = "Desc_SteelPlate_C"
I_STEEL_PIPE = "Desc_SteelPipe_C"
I_COPPER_SHEET = "Desc_CopperSheet_C"
I_EIB = "Desc_SteelPlateReinforced_C"


# --------------------------------------------------------------------------
# case 1 -- the bundle config. ONE BUS PER ITEM
# --------------------------------------------------------------------------

def merged_declaration(
    name: str,
    lines: Sequence[tuple[str, str]],
    data: ReferenceData,
    *,
    provenance: str = "",
    external_per_min: Mapping[str, float] | None = None,
) -> Declaration:
    """One bus per item, every declared consumer drawing from it.

    THIS IS ITSELF A DECLARATION, not a derivation, and it is the storage
    review's. Bus record section 1 derived isolation from consumer count and
    amendment 3 contradicts it -- the partition is declared. But the merged
    partition is what the storage review and the section 4 recompute actually
    ran, so reproducing them requires stating it, once, here, rather than
    letting it be the default everywhere.

    `lines` is (item_id, recipe_id) in the config's own order. The bus id is the
    item id, which is exactly the assumption: a second bus of the same item
    would be unreachable.
    """
    declared = {item for item, _ in lines}
    specs = []
    for item_id, recipe_id in lines:
        sources = tuple(
            SourceEdge(input_item, input_item if input_item in declared else None)
            for input_item, _ in data.recipes[recipe_id].inputs
        )
        specs.append(
            BusSpec(
                bus_id=item_id,
                item_id=item_id,
                recipe_id=recipe_id,
                sources=sources,
                # WITHDRAWN, which the toggle states: storage ON, the default.
            )
        )
    return Declaration(
        name=name,
        buses=tuple(specs),
        external_per_min=dict(external_per_min or {}),
        provenance=provenance,
    )


#: `storage_progression_config.json`, phase `T1-2_preparing_T3-4`, item order and
#: recipe choices verbatim. External demand is ZERO -- the recovered rule; the
#: config's `automated_demand_per_min` column is DERIVED in-scope draw (A2.1)
#: and its declared values are void.
STORAGE_REVIEW_T1_2_LINES: tuple[tuple[str, str], ...] = (
    (I_RIP, R_STITCHED_RIP),
    (I_ROTOR, R_ROTOR),
    (I_MODULAR_FRAME, R_MODULAR_FRAME),
    (I_IRON_PLATE, R_IRON_PLATE),
    (I_IRON_ROD, R_IRON_ROD),
    (I_WIRE, R_WIRE),
    (I_CABLE, R_CABLE),
    (I_CONCRETE, R_CONCRETE),
    (I_SCREW, R_CAST_SCREWS),
)

#: Same file, phase `T3-4_preparing_T5-6`.
STORAGE_REVIEW_T3_4_LINES: tuple[tuple[str, str], ...] = (
    (I_RIP, R_STITCHED_RIP),
    (I_ROTOR, R_ROTOR),
    (I_MODULAR_FRAME, R_MODULAR_FRAME),
    (I_IRON_PLATE, R_IRON_PLATE),
    (I_IRON_ROD, R_IRON_ROD),
    (I_WIRE, R_WIRE),
    (I_CABLE, R_CABLE),
    (I_CONCRETE, R_CONCRETE),
    (I_STEEL_BEAM, R_STEEL_BEAM),
    (I_STEEL_PIPE, R_STEEL_PIPE),
    (I_COPPER_SHEET, R_COPPER_SHEET),
    (I_EIB, R_ENCASED_INDUSTRIAL_PIPE),
    (I_SCREW, R_CAST_SCREWS),
)

#: The config's `installed_capacity_per_min` column, per bus, for the section
#: 6.1 balance check ONLY. Where the config states `machines` instead, the
#: capacity is that count times the line's rate -- the config's own convention,
#: and the reason both fields appear in one file.
STORAGE_REVIEW_T1_2_MACHINES: Mapping[str, float] = {
    I_RIP: 1, I_ROTOR: 1, I_MODULAR_FRAME: 0.5, I_IRON_PLATE: 1,
    I_IRON_ROD: 2, I_WIRE: 1, I_SCREW: 1,
}
STORAGE_REVIEW_T1_2_CAPACITY: Mapping[str, float] = {I_CABLE: 3.0, I_CONCRETE: 6.0}
STORAGE_REVIEW_T1_2_DECLARED_DEMAND: Mapping[str, float] = {
    I_RIP: 2.7, I_ROTOR: 2.0, I_MODULAR_FRAME: 0.0, I_IRON_PLATE: 18.75,
    I_IRON_ROD: 23.0, I_WIRE: 25.0, I_CABLE: 0.0, I_CONCRETE: 0.0, I_SCREW: 50.0,
}

STORAGE_REVIEW_T3_4_MACHINES: Mapping[str, float] = {
    I_RIP: 1, I_ROTOR: 1, I_MODULAR_FRAME: 1, I_IRON_ROD: 2, I_STEEL_BEAM: 1,
    I_SCREW: 1,
}
STORAGE_REVIEW_T3_4_CAPACITY: Mapping[str, float] = {
    I_IRON_PLATE: 38.6, I_WIRE: 23.53, I_CABLE: 7.09, I_CONCRETE: 6.99,
    I_STEEL_PIPE: 10.8, I_COPPER_SHEET: 1.14, I_EIB: 0.2,
}
STORAGE_REVIEW_T3_4_DECLARED_DEMAND: Mapping[str, float] = {
    I_RIP: 3.525, I_ROTOR: 2.0, I_MODULAR_FRAME: 1.0, I_IRON_PLATE: 37.35,
    I_IRON_ROD: 26.0, I_WIRE: 14.4, I_CABLE: 4.0, I_CONCRETE: 1.2,
    I_STEEL_BEAM: 12.0, I_STEEL_PIPE: 9.6, I_COPPER_SHEET: 0.0, I_EIB: 0.0,
    I_SCREW: 50.0,
}

_BUNDLE = (
    "scratchpad/satisfactory_storage_model_bundle/satisfactory_storage_model/"
    "storage_progression_config.json, read 2026-09-21"
)


def storage_review_t1_2(data: ReferenceData) -> Declaration:
    return merged_declaration(
        "storage_review_T1-2", STORAGE_REVIEW_T1_2_LINES, data,
        provenance=f"{_BUNDLE}, phase T1-2_preparing_T3-4. External demand 0 "
                   "(crossover record section 1, recovered rule).",
    )


def storage_review_t3_4(data: ReferenceData) -> Declaration:
    return merged_declaration(
        "storage_review_T3-4", STORAGE_REVIEW_T3_4_LINES, data,
        provenance=f"{_BUNDLE}, phase T3-4_preparing_T5-6. External demand 0.",
    )


def storage_review_t1_2_base_rip(data: ReferenceData) -> Declaration:
    """Phase T1-2 with the BASE Reinforced Iron Plate recipe.

    Storage review section 7's second regime. An alternate is a RE-WIRING event:
    swapping the recipe moves the RIP line off the wire bus and onto the screw
    bus, so the source edges are restated rather than carried.
    """
    return storage_review_t1_2(data).replace_recipe(
        I_RIP, R_BASE_RIP,
        (SourceEdge(I_IRON_PLATE, I_IRON_PLATE), SourceEdge(I_SCREW, I_SCREW)),
    )


# --------------------------------------------------------------------------
# case 2 -- the worked case. SPLIT WIRE BUSES, base Screw
# --------------------------------------------------------------------------

#: A3.1, stated by Greg: "wire in that chain was Iron Wire for Stitched Iron
#: Plate -- wire for building comes from the copper branch in this case." Wire
#: has three consumers and is deliberately run as two unconnected buses.
BUS_WIRE_IRON = "wire_iron"
BUS_WIRE_COPPER = "wire_copper"
BUS_IRON_PLATE = "iron_plate"
BUS_IRON_PLATE_BUILD = "iron_plate_build"

#: A4.1, stated by Greg: "the Iron Plate is likely just a miss -- we'd want some
#: Iron Plate going to storage even if that means an entire Constructor's worth,
#: or some underclocked amount." Build plates are their own line, exactly like
#: Concrete and Cable.


def worked_case_a4(
    data: ReferenceData,
    *,
    smart_plating_per_min: float = 2.0,
    build_plate_disposition: Disposition = Disposition.MATCHED,
) -> Declaration:
    """The topology A3.1 describes, with A4.1's Iron Plate build line.

    Sources, field by field:

        root Smart Plating 2/min   the declaration root is the Space Elevator
                                   part rate. One Assembler is 2/min drawing
                                   2 RIP + 2 Rotor
        Stitched RIP               A3.1 and A3.5
        split Wire buses           A3.1, stated
        base Screw recipe          A3.5's Iron Rod bus draws 64.00/min, which is
                                   Rotor 24.00 plus four screw machines at 10
                                   rod/min. Cast Screws draws no rod at all
        withdrawal rates           the bundle config's
                                   `working_withdrawal_per_min` column, phase
                                   T1-2. These are section 8.2 geometric
                                   estimates and their author declares them a
                                   FLOOR (A3.3)
        Iron Plate build line      A4.1, and it is the 28th machine
        build lines are BACK_UP    A3.5 computed build-material draw "at its
                                   average rate"; the Iron Plate line is MATCHED
                                   because A4.1 is the comparison it exists for

    NOT taken from A3.5's output table. The one number below that A3.5 also
    states is the root, which A3.5 states in prose as its own input.

    This is NOT byte-identical to A3.5 and is not meant to be. A3.5's withdrawal
    column sits inside the demand sum on Concrete and Wire_copper and outside it
    on four other rows, under one verdict column; here every withdrawal is
    inside its own bus's demand. That is the uniformity A4.1 buys structurally,
    and it is why A3.5 is not a regression target until it is recomputed.
    """
    ore = SourceEdge  # local alias, for the out-of-scope edges below
    specs = (
        BusSpec(
            bus_id="smart_plating", item_id=I_SMART_PLATING, recipe_id=R_SMART_PLATING,
            sources=(SourceEdge(I_RIP, "rip"), SourceEdge(I_ROTOR, "rotor")),
        ),
        BusSpec(
            bus_id="rip", item_id=I_RIP, recipe_id=R_STITCHED_RIP,
            sources=(SourceEdge(I_IRON_PLATE, BUS_IRON_PLATE),
                     SourceEdge(I_WIRE, BUS_WIRE_IRON)),
            withdrawal_per_min=2.0,
        ),
        BusSpec(
            bus_id="rotor", item_id=I_ROTOR, recipe_id=R_ROTOR,
            sources=(SourceEdge(I_IRON_ROD, "iron_rod"),
                     SourceEdge(I_SCREW, "screws")),
            withdrawal_per_min=2.0,
        ),
        BusSpec(
            bus_id="screws", item_id=I_SCREW, recipe_id=R_BASE_SCREWS,
            sources=(SourceEdge(I_IRON_ROD, "iron_rod"),),
        ),
        BusSpec(
            bus_id=BUS_WIRE_IRON, item_id=I_WIRE, recipe_id=R_IRON_WIRE,
            sources=(SourceEdge(I_IRON_INGOT, "iron_ingot"),),
        ),
        BusSpec(
            bus_id=BUS_WIRE_COPPER, item_id=I_WIRE, recipe_id=R_WIRE,
            sources=(SourceEdge(I_COPPER_INGOT, "copper_ingot"),),
            withdrawal_per_min=5.0,
        ),
        BusSpec(
            bus_id="cable", item_id=I_CABLE, recipe_id=R_CABLE,
            sources=(SourceEdge(I_WIRE, BUS_WIRE_COPPER),),
            withdrawal_per_min=3.0, **_recorded(Disposition.BACK_UP),
        ),
        BusSpec(
            bus_id="concrete", item_id=I_CONCRETE, recipe_id=R_CONCRETE,
            sources=(ore("Desc_Stone_C", None),),
            withdrawal_per_min=6.0, **_recorded(Disposition.BACK_UP),
        ),
        BusSpec(
            bus_id=BUS_IRON_PLATE, item_id=I_IRON_PLATE, recipe_id=R_IRON_PLATE,
            sources=(SourceEdge(I_IRON_INGOT, "iron_ingot"),),
        ),
        BusSpec(
            bus_id=BUS_IRON_PLATE_BUILD, item_id=I_IRON_PLATE, recipe_id=R_IRON_PLATE,
            sources=(SourceEdge(I_IRON_INGOT, "iron_ingot"),),
            withdrawal_per_min=2.0, **_recorded(build_plate_disposition),
            # A4.2's "presents a 40/min peak draw ... that the upstream bus
            # must either carry or dip under" USED to be declared here, as
            # `presents_peak_draw=(build_plate_disposition is BACK_UP)`. That
            # it was derived from the disposition at the declaration site is
            # why A5.2 could remove the field outright rather than rename it:
            # it was never a declaration. `solve` now derives the same peak and
            # REPORTS it — the 40/min is `ConsumerShare.peak_per_min` on the
            # ingot bus, and it no longer sizes that bus.
        ),
        BusSpec(
            bus_id="iron_rod", item_id=I_IRON_ROD, recipe_id=R_IRON_ROD,
            sources=(SourceEdge(I_IRON_INGOT, "iron_ingot"),),
        ),
        BusSpec(
            bus_id="iron_ingot", item_id=I_IRON_INGOT, recipe_id=R_IRON_INGOT,
            sources=(ore("Desc_OreIron_C", None),),
        ),
        BusSpec(
            bus_id="copper_ingot", item_id=I_COPPER_INGOT, recipe_id=R_COPPER_INGOT,
            sources=(ore("Desc_OreCopper_C", None),),
        ),
    )
    suffix = "" if build_plate_disposition is Disposition.MATCHED else "_full_rate_plate"
    return Declaration(
        name=f"worked_case_A4{suffix}",
        buses=specs,
        external_per_min={"smart_plating": smart_plating_per_min},
        provenance="A3.1 (split Wire buses, stated), A3.5 (root, recipes, "
                   "topology), A4.1 (Iron Plate build line), bundle config "
                   "T1-2 (withdrawal rates, section 8.2 geometric FLOOR).",
    )


# --------------------------------------------------------------------------
# case 3 -- the alternate crossover regimes
# --------------------------------------------------------------------------

def crossover_regime(data: ReferenceData, *, stitched: bool, scale: float = 1.0) -> Declaration:
    """Bus record section 8's two regimes, targets held at RIP:Rotor = 5:4.

    Regime A is the base Reinforced Iron Plate recipe and has six buses; regime
    B is Stitched plus Iron Wire and has seven. The scale `s` multiplies both
    targets and nothing else.

    No Smart Plating root: section 8 declares the RIP and Rotor rates directly
    as the targets, which is why this is a third declaration and not a variant
    of the worked case.

    Solved on the AVERAGE basis with every bus BACK_UP, which is what section 8
    calls the need basis: a consumer that is satisfied backs up, so the steady
    draw is actual need rather than nameplate. That is the basis under which
    19.02 and 15.79 were computed.
    """
    back_up = Disposition.BACK_UP
    common = [
        BusSpec(bus_id="rotor", item_id=I_ROTOR, recipe_id=R_ROTOR, **_recorded(back_up, withdrawal=False),
                sources=(SourceEdge(I_IRON_ROD, "iron_rod"),
                         SourceEdge(I_SCREW, "screws"))),
        BusSpec(bus_id="screws", item_id=I_SCREW, recipe_id=R_BASE_SCREWS,
                **_recorded(back_up, withdrawal=False),
                sources=(SourceEdge(I_IRON_ROD, "iron_rod"),)),
        BusSpec(bus_id="iron_rod", item_id=I_IRON_ROD, recipe_id=R_IRON_ROD,
                **_recorded(back_up, withdrawal=False),
                sources=(SourceEdge(I_IRON_INGOT, "iron_ingot"),)),
        BusSpec(bus_id=BUS_IRON_PLATE, item_id=I_IRON_PLATE, recipe_id=R_IRON_PLATE,
                **_recorded(back_up, withdrawal=False),
                sources=(SourceEdge(I_IRON_INGOT, "iron_ingot"),)),
    ]
    if stitched:
        head = [
            BusSpec(bus_id="rip", item_id=I_RIP, recipe_id=R_STITCHED_RIP,
                    **_recorded(back_up, withdrawal=False),
                    sources=(SourceEdge(I_IRON_PLATE, BUS_IRON_PLATE),
                             SourceEdge(I_WIRE, BUS_WIRE_IRON))),
            BusSpec(bus_id=BUS_WIRE_IRON, item_id=I_WIRE, recipe_id=R_IRON_WIRE,
                    **_recorded(back_up, withdrawal=False),
                    sources=(SourceEdge(I_IRON_INGOT, "iron_ingot"),)),
        ]
    else:
        head = [
            BusSpec(bus_id="rip", item_id=I_RIP, recipe_id=R_BASE_RIP,
                    **_recorded(back_up, withdrawal=False),
                    sources=(SourceEdge(I_IRON_PLATE, BUS_IRON_PLATE),
                             SourceEdge(I_SCREW, "screws"))),
        ]
    tail = [
        BusSpec(bus_id="iron_ingot", item_id=I_IRON_INGOT, recipe_id=R_IRON_INGOT,
                **_recorded(back_up, withdrawal=False),
                sources=(SourceEdge("Desc_OreIron_C", None),)),
    ]
    return Declaration(
        name=f"crossover_{'B_stitched' if stitched else 'A_base'}",
        buses=tuple(head + common + tail),
        external_per_min={"rip": 5.0 * scale, "rotor": 4.0 * scale},
        provenance="bus_allocation_backpressure_and_residual.md section 8 "
                   "(targets 5 RIP/min + 4 Rotor/min, both regimes); "
                   "crossover record section 6 (need basis, 1.25x, scale s).",
    )
