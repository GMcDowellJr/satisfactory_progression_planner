"""Progression-layer modules. Sits above `production_adapter` and imports downward.

    unlocks   resolve a tech tier into a recipe set, and report what it withheld
    pool      which alternates are obtainable at a tier — not which you hold

Nothing in `production_adapter` imports anything here. That direction is the whole
point of the boundary — see section 11.1 of docs/decisions/production_lp_formulation.md.
"""
from .pool import PoolAvailability, PoolDataError, available_at, resolve_slugs
from .unlocks import PROGRESSION_TYPES, TierUnlocks, UnlockDataError, at_tier

__all__ = [
    "PROGRESSION_TYPES", "PoolAvailability", "PoolDataError", "TierUnlocks",
    "UnlockDataError", "at_tier", "available_at", "resolve_slugs",
]
__version__ = "0.1.0"
