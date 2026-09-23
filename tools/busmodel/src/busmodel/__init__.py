"""Bus-level recompute against the reference layer.

The oracle for every bus figure the decision records publish. It reads reference
data only through `production_adapter.gamedata`, which holds the locked claim to
be the only place in the repo that knows CSV column names -- and which is why
the scratch model this replaces could never be committed.

    model          the solve: declared partition, per-bus steady state, the two
                   recovered rules (external demand 0, machine floor 1)
    declarations   the saved declarations, each naming its primary source
    report         rendering and the out-of-scope draw roll-up
    cli            the driver

`tests/test_published_tables.py` is the point of the package: it turns five
published tables plus amendment 4's central comparison into regression tests.
"""
from .model import (
    BalanceDelta,
    BusModelError,
    BusNotDeclared,
    BusSolution,
    BusSpec,
    ConsumerShare,
    CreditedFlowCycle,
    Declaration,
    DispositionUnavailable,
    SOLVE_BASES,
    SizingBasis,
    Solution,
    SourceEdge,
    balance_check,
    solve,
)

__all__ = [
    "BalanceDelta",
    "BusModelError",
    "BusNotDeclared",
    "BusSolution",
    "BusSpec",
    "ConsumerShare",
    "CreditedFlowCycle",
    "Declaration",
    "DispositionUnavailable",
    "SOLVE_BASES",
    "SizingBasis",
    "Solution",
    "SourceEdge",
    "balance_check",
    "solve",
]
