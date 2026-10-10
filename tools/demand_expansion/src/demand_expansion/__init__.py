"""Demand expansion: declared requirements to item quantities.

Sits above `production_adapter` and imports downward only (LP record §11.1).
`progression` may import this package; this package imports nothing above the
adapter. See README.md and docs/demand_expansion/SPECIFICATION.md.
"""
from .contracts import (
    AmbiguousRoute,
    CycleDetected,
    DeclarationError,
    DemandExpansionError,
    Exclusion,
    Expansion,
    FluidRoundingUndeclared,
    NotExpandable,
    RoutePin,
    RouteTable,
    UnproducibleItem,
)
from .declarations import DEFAULT_ROUTES
from .expand import UNDECLARED, expand
from .graph import Census, RecipeGraph, build, census, find_cycles, primary_output, route_for

__all__ = [
    "AmbiguousRoute", "Census", "CycleDetected", "DEFAULT_ROUTES", "DeclarationError",
    "DemandExpansionError", "Exclusion", "Expansion", "FluidRoundingUndeclared",
    "NotExpandable", "RecipeGraph", "RoutePin", "RouteTable", "UNDECLARED",
    "UnproducibleItem", "build", "census", "expand", "find_cycles", "primary_output",
    "route_for",
]
