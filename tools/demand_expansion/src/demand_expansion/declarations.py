"""The default route table: DATA, with a reason beside every entry.

Decided by Greg, 2026-10-10 (demand-expansion record Amendment 1, item B):
record §3.1.1's curated set, carried as named exclusions, plus pins for the
structural residue that the Space Elevator deliveries actually reach.

What is NOT here, and why:

    Converter ore conversions   §3.1.1's second exclusion ("make raw resources
                                from other raws plus SAM"). Not a declaration:
                                `graph.build` never enables a recipe whose
                                primary output is a resource, because resources
                                are leaves. 17 base recipes fall to that rule
                                on this build (the record counted 9 on the
                                2026-09-19 data; the rule is what is locked).
    Silica                      Amendment 1 proposed a pin. Under the
                                primary-output rule Silica has one enabled
                                producer (Alumina Solution yields it as a
                                coproduct only), so a pin would resolve nothing
                                and `graph.build` refuses redundant pins.
    Ficsite Ingot               three Converter routes, no default (LP §14.5).
                                Left unpinned: Biochemical Sculptor and AI
                                Expansion Server refuse by name until a run
                                pins one.
    Compacted Coal, Power Shard, Fuel, Biomass, Alien Protein
                                §3.1.2: run-dependent, not a modelling choice.
                                No delivery reaches them under this table.
"""
from __future__ import annotations

from .contracts import Exclusion, RoutePin, RouteTable

_UNPACKAGE = (
    "Recipe_UnpackageAlumina_C",
    "Recipe_UnpackageBioFuel_C",
    "Recipe_UnpackageFuel_C",
    "Recipe_UnpackageIonizedFuel_C",
    "Recipe_UnpackageNitricAcid_C",
    "Recipe_UnpackageNitrogen_C",
    "Recipe_UnpackageOil_C",
    "Recipe_UnpackageOilResidue_C",
    "Recipe_UnpackageRocketFuel_C",
    "Recipe_UnpackageSulfuricAcid_C",
    "Recipe_UnpackageTurboFuel_C",
    "Recipe_UnpackageWater_C",
)
_UNPACKAGE_REASON = (
    "Record 3.1.1: a reversal, not a production route. Creates a cycle and a "
    "spurious producer for every packaged fluid."
)

#: Record 3.1.1's third exclusion. Flagged `is_alternate=false` in the shipped
#: data while research- or drive-gated (handoff §18.4). `Recipe_UnpackageTurboFuel_C`
#: is in both lists in the record; it is carried once here, under Unpackage.
_IS_ALTERNATE_DEFECT = (
    ("Recipe_Alternate_Turbofuel_C",
     "Record 3.1.1: is_alternate defect. The id says alternate; the flag says "
     "base. Turbofuel has no other base producer, so it is unproducible under "
     "this table, which is the state the record describes."),
    ("Recipe_PackagedTurboFuel_C",
     "Record 3.1.1: is_alternate defect, research-gated while flagged base."),
)

DEFAULT_ROUTES = RouteTable(
    name="default-2026-10-10",
    exclusions=tuple(Exclusion(r, _UNPACKAGE_REASON) for r in _UNPACKAGE)
    + tuple(Exclusion(r, why) for r, why in _IS_ALTERNATE_DEFECT),
    pins=(
        RoutePin(
            "Desc_Plastic_C", "Recipe_Plastic_C",
            "LP record §14.5, Amendment 1 (B). Residual Plastic is the Heavy Oil "
            "Residue sink; the direct Crude Oil recipe is the one the game's own "
            "naming calls Plastic. Reached by every delivery from Modular Engine up.",
        ),
        RoutePin(
            "Desc_Rubber_C", "Recipe_Rubber_C",
            "Same shape as Plastic. Reached by Modular Engine, Thermal Propulsion "
            "Rocket and Ballistic Warp Drive.",
        ),
    ),
)
