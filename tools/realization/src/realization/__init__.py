"""Post-solve realization: a solved plan expressed as equipment at a declared tier.

    from production_adapter import load, OutputTarget, SolveRequest
    from production_adapter.gamedata import load_logistics
    from production_adapter.lp_backend import LpBackend, PowerStatistic
    from realization import RealizationRequest, realize

    data = load(repo_root, MARGINAL_PEAK_DEBOTTLENECK)
    caps, extraction = load_logistics(repo_root)
    response = LpBackend(power_statistic=PowerStatistic.MEAN).solve(request, data)

    report = realize(response, data, caps, extraction,
                     RealizationRequest(design_tier=4))

This package adds NO capability to the solver. It imports
`production_adapter.contracts` and `production_adapter.gamedata` — types and
read-only reference data — and never `backend`, `lp_backend` or `analysis`.
A layer that reads `effective_count` and cannot call `linprog` cannot become a
second solver; the import restriction is asserted by inspection in the tests.
"""
from .contracts import (
    Bus, BusDeclaration, BusId, BusNotDeclared, BusResidual, Capability,
    ClockCause, ClockDistribution, ClockMode, ConsumerShare, Coverage,
    CreditedFlowCycle, DesignTier, Disposition, DispositionUnavailable,
    ExtractionRate, Lane, LaneInfeasible, LaneInput, NodeDeclaration,
    PartitionIncomplete, ProjectedGoal, RealizationError, RealizationReport,
    RealizationRequest, SourceEdge, TierUnavailable, WithdrawalBasis,
)
from .realize import credited_flow_order, project_goals, realize

__all__ = [
    "Bus", "BusDeclaration", "BusId", "BusNotDeclared", "BusResidual",
    "Capability", "ClockCause", "ClockDistribution", "ClockMode",
    "ConsumerShare", "Coverage", "CreditedFlowCycle", "DesignTier",
    "Disposition", "DispositionUnavailable", "ExtractionRate", "Lane",
    "LaneInfeasible", "LaneInput", "NodeDeclaration", "PartitionIncomplete",
    "ProjectedGoal", "RealizationError", "RealizationReport",
    "RealizationRequest", "SourceEdge", "TierUnavailable", "WithdrawalBasis",
    "credited_flow_order", "project_goals", "realize",
]
__version__ = "0.1.0"
