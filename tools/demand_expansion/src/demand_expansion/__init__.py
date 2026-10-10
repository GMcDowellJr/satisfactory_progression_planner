"""Demand expansion: declared requirements to item quantities.

Sits above `production_adapter` and imports downward only (LP record §11.1).
`progression` may import this package; this package imports nothing above the
adapter. See README.md and docs/demand_expansion/SPECIFICATION.md.
"""
from .aggregate import Delivery, Growth, PhaseCell, PhaseDemand, aggregate
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
from .report import (
    COEFFICIENT_COLUMNS, PHASE_COLUMNS, UNRESOLVED_COLUMNS, Dataset, build_dataset,
    config_id, in_scope_targets, markdown_report, route_table_sha256,
)

__all__ = [
    "AmbiguousRoute", "COEFFICIENT_COLUMNS", "Census", "CycleDetected", "DEFAULT_ROUTES",
    "Dataset", "DeclarationError", "Delivery", "DemandExpansionError", "Exclusion",
    "Expansion", "FluidRoundingUndeclared", "Growth", "NotExpandable", "PHASE_COLUMNS",
    "PhaseCell", "PhaseDemand", "RecipeGraph", "RoutePin", "RouteTable",
    "UNDECLARED", "UNRESOLVED_COLUMNS", "UnproducibleItem", "aggregate", "build",
    "build_dataset", "census", "config_id", "expand", "find_cycles",
    "in_scope_targets", "markdown_report", "primary_output", "route_for",
    "route_table_sha256",
]
