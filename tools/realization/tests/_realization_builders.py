"""Constructors for the realization types, for tests that need a whole object.

Nothing in the repo built a `Bus`, a `BusDeclaration` or a `BusResidual` before
2026-09-21, which is why 23 type edits — including three renames chosen to break
loudly — broke nothing. These are the smallest well-formed instances that still
mean something, so a rename lands on a call site instead of on nobody.

Named `_realization_builders` rather than `_builders`: none of the test
directories carries an `__init__.py`, so a module is imported under its bare
basename and two files with one name collide across `testpaths`.
"""
from __future__ import annotations

from production_adapter.contracts import (
    ItemFlow, MachineCount, PowerReport, RawInput, RecipeUse, SolveResponse,
)
from production_adapter.gamedata import Producer

from realization.contracts import (
    Bus, BusDeclaration, BusResidual, Capability, ClockCause, ConsumerShare,
    Disposition, Lane, LaneInput, RealizationRequest, SourceEdge,
)

# Reference-layer values, restated so the pure arithmetic tests do not need the
# CSVs. `production_buildings.csv` carries the exponent on all eleven producers.
CONSTRUCTOR = Producer(
    producer_class="Build_ConstructorMk1_C",
    display_name="Constructor",
    power_model="fixed",
    base_power_mw=4.0,
    power_exponent=1.321929,
)
SMELTER = Producer(
    producer_class="Build_SmelterMk1_C",
    display_name="Smelter",
    power_model="fixed",
    base_power_mw=4.0,
    power_exponent=1.321929,
)
CONVERTER = Producer(
    producer_class="Build_Converter_C",
    display_name="Converter",
    power_model="variable",
    base_power_mw=0.0,
    power_exponent=1.321929,
)

BELT_MK2 = Capability(
    capability_id="belt_mk2",
    capability_type="belt",
    mark="Mk.2",
    capacity_per_min=120.0,
    unit="items/min",
    unlock_tier=2,
    unlock_text="Tier 2 - Logistics Mk.2",
)

I_SCREW = "Desc_IronScrew_C"
I_IRON_ROD = "Desc_IronRod_C"
I_IRON_PLATE = "Desc_IronPlate_C"
I_IRON_INGOT = "Desc_IronIngot_C"
R_SCREWS = "Recipe_Screw_C"
R_IRON_PLATE = "Recipe_IronPlate_C"


def lane(
    *,
    recipe_id: str = R_SCREWS,
    machines: int = 5,
    clock_percent: float = 100.0,
    clock_cause: ClockCause = ClockCause.FULL,
    output_item: str = I_SCREW,
    output_rate_per_min: float = 200.0,
    power_mw: float = 20.0,
) -> Lane:
    return Lane(
        recipe_id=recipe_id,
        producer_class="Build_ConstructorMk1_C",
        machines=machines,
        clock_percent=clock_percent,
        clock_cause=clock_cause,
        output_item=output_item,
        output_rate_per_min=output_rate_per_min,
        binding_side="output",
        binding_rate_per_min=output_rate_per_min,
        trunk=BELT_MK2,
        inputs=(
            LaneInput(
                item_id=I_IRON_ROD,
                rate_per_min=machines * 10.0,
                carrier=BELT_MK2,
                source_bus_id="iron_rod",
            ),
        ),
        power_mw=power_mw,
    )


def declaration(
    *,
    bus_id: str = "screws",
    item_id: str = I_SCREW,
    disposition: Disposition = Disposition.WITHDRAWN,
    withdrawal_per_min: float | None = None,
    extra_producers: int = 0,
    **kwargs,
) -> BusDeclaration:
    return BusDeclaration(
        bus_id=bus_id,
        item_id=item_id,
        sources=(SourceEdge(I_IRON_ROD, "iron_rod"),),
        disposition=disposition,
        withdrawal_per_min=withdrawal_per_min,
        extra_producers=extra_producers,
        **kwargs,
    )


def residual(
    *,
    bus_id: str = "screws",
    item_id: str = I_SCREW,
    rate_per_min: float = 1.0,
    disposition: Disposition = Disposition.WITHDRAWN,
    power_cost_mw: float = 0.0,
) -> BusResidual:
    return BusResidual(
        bus_id=bus_id,
        item_id=item_id,
        rate_per_min=rate_per_min,
        disposition=disposition,
        power_cost_mw=power_cost_mw,
    )


def bus(
    *,
    bus_id: str = "screws",
    item_id: str = I_SCREW,
    recipe_id: str = R_SCREWS,
    supply_per_min: float = 200.0,
    automated_demand_per_min: float = 199.0,
    withdrawal_per_min: float = 0.0,
    machines: int = 5,
    disposition: Disposition = Disposition.WITHDRAWN,
) -> Bus:
    """The screw bus of bus record sections 1 and 4, by default.

        199/min demand    RIP 75 (37.7%)   Rotor 124 (62.3%)
        5 machines, 200/min supply, R = 1.0/min
    """
    return Bus(
        bus_id=bus_id,
        item_id=item_id,
        recipe_id=recipe_id,
        supply_per_min=supply_per_min,
        automated_demand_per_min=automated_demand_per_min,
        withdrawal_per_min=withdrawal_per_min,
        lanes=(lane(recipe_id=recipe_id, machines=machines,
                    output_item=item_id, output_rate_per_min=supply_per_min),),
        consumers=(
            # One whole machine each at full rate, so usage and peak are the
            # same number here. `test_buses.py` builds the case where they
            # are not.
            ConsumerShare(recipe_id="Recipe_IronPlateReinforced_C",
                          draw_per_min=75.0, share=75.0 / 199.0,
                          peak_per_min=75.0),
            ConsumerShare(recipe_id="Recipe_Rotor_C",
                          draw_per_min=124.0, share=124.0 / 199.0,
                          peak_per_min=124.0),
        ),
        residual=residual(
            bus_id=bus_id, item_id=item_id,
            rate_per_min=supply_per_min - automated_demand_per_min,
            disposition=disposition,
        ),
    )


# --------------------------------------------------------------------------
# the worked case: screws -> RIP + Rotor -> Smart Plating
# --------------------------------------------------------------------------
#
# A3.1's topology minus the wire buses, which is the part of it that runs on
# BASE recipes and therefore needs no alternate declared. It exists so the
# bodies are exercised against the real reference layer rather than a stub:
# every rate below is read from the CSVs at the scenario of record, never
# restated here.
#
# At 1.25x, one base Assembler each of Reinforced Iron Plate and Rotor draws
# 75 and 124 screws/min, which is bus record section 1's measured row.

I_ROTOR = "Desc_Rotor_C"
I_SMART_PLATING = "Desc_SpaceElevatorPart_1_C"
R_RIP = "Recipe_IronPlateReinforced_C"
R_ROTOR = "Recipe_Rotor_C"
R_SMART_PLATING = "Recipe_SpaceElevatorPart_1_C"
ASSEMBLER = "Build_AssemblerMk1_C"
CONSTRUCTOR_CLASS = "Build_ConstructorMk1_C"

#: The record's screw bus: 199/min of automated demand against 40/min
#: producers, which is 4.975 machine-equivalents and ceils to 5.
SCREW_EQUIVALENTS = 199.0 / 40.0


def worked_buses(**screws) -> tuple[BusDeclaration, ...]:
    """The four declarations. `**screws` overrides the screw bus only."""
    screws.setdefault("disposition", Disposition.WITHDRAWN)
    return (
        BusDeclaration(bus_id="screws", item_id=I_SCREW,
                       sources=(SourceEdge(I_IRON_ROD, None),), **screws),
        BusDeclaration(bus_id="rip", item_id="Desc_IronPlateReinforced_C",
                       sources=(SourceEdge(I_SCREW, "screws"),
                                SourceEdge(I_IRON_PLATE, None)),
                       disposition=Disposition.WITHDRAWN),
        BusDeclaration(bus_id="rotor", item_id=I_ROTOR,
                       sources=(SourceEdge(I_SCREW, "screws"),
                                SourceEdge(I_IRON_ROD, None)),
                       disposition=Disposition.WITHDRAWN),
        BusDeclaration(bus_id="smart_plating", item_id=I_SMART_PLATING,
                       sources=(SourceEdge("Desc_IronPlateReinforced_C", "rip"),
                                SourceEdge(I_ROTOR, "rotor")),
                       disposition=Disposition.WITHDRAWN),
    )


def worked_request(design_tier: int = 4, **screws) -> RealizationRequest:
    """Tier 4 by default.

    NOT tier 2: at the scenario of record one Rotor Assembler draws 124
    screws/min and a Mk.2 belt carries 120, so the declaration is genuinely
    infeasible there. `test_buses.py` asserts that refusal on purpose.
    """
    return RealizationRequest(design_tier=design_tier, buses=worked_buses(**screws))


def worked_response(screw_equivalents: float = SCREW_EQUIVALENTS) -> SolveResponse:
    """What the solve would have returned for the worked case.

    `machine_equivalents` is the only figure the realization layer reads from
    it, and only where a bus has out-of-scope demand the declaration does not
    model. Cycle rates are carried because `RecipeUse` requires them and are
    read by nothing here.
    """
    return SolveResponse(
        recipes=(
            RecipeUse(R_SMART_PLATING, ASSEMBLER, 1.0, 2.0),
            RecipeUse(R_RIP, ASSEMBLER, 1.0, 5.0),
            RecipeUse(R_ROTOR, ASSEMBLER, 1.0, 4.0),
            RecipeUse(R_SCREWS, CONSTRUCTOR_CLASS, screw_equivalents, 10.0),
        ),
        items=tuple(
            ItemFlow(i, 1.0, 1.0)
            for i in (I_SCREW, "Desc_IronPlateReinforced_C", I_ROTOR,
                      I_SMART_PLATING, I_IRON_ROD, I_IRON_PLATE)
        ),
        raw_inputs=(RawInput(I_IRON_ROD, 0.0),),
        power=PowerReport(0.0, 0.0, 0.0, 0.0),
        machines=(MachineCount(CONSTRUCTOR_CLASS, screw_equivalents, 5),),
        backend="test",
    )
