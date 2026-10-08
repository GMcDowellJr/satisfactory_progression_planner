"""Progression-layer modules. Sits above `production_adapter` and imports downward.

    unlocks   resolve a tech tier into a recipe set, and report what it withheld
    district  a district's declared nodes composed into resource caps (A26/A27)
    pool      which alternates are obtainable at a tier — not which you hold
    stock     the build-material bill, in quantities. NOT re-exported below and
              imported on demand: it is the one module here that needs
              `realization.contracts`, and an eager import would make this whole
              package unusable wherever that package is not on the path.
              `from progression import stock`

Nothing in `production_adapter` imports anything here. That direction is the whole
point of the boundary — see section 11.1 of docs/decisions/production_lp_formulation.md.
"""
from .district import (
    DistrictDefinition, DistrictError, NodeCount, Reach, bill_units, discover,
    extraction_nameplate_mw, recipe_ids_by_name, resource_caps, resources_in_reference_order,
)
from .pool import PoolAvailability, PoolDataError, available_at, resolve_slugs
from .unlocks import PROGRESSION_TYPES, TierUnlocks, UnlockDataError, at_tier

__all__ = [
    "DistrictDefinition", "DistrictError", "NodeCount", "PROGRESSION_TYPES", "Reach",
    "discover",
    "extraction_nameplate_mw",
    "PoolAvailability", "PoolDataError", "TierUnlocks", "UnlockDataError", "at_tier",
    "available_at", "bill_units", "recipe_ids_by_name", "resolve_slugs", "resource_caps",
    "resources_in_reference_order",
]
__version__ = "0.1.0"
