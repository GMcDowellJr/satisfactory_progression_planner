"""The seam. Everything above this line is ours; everything below is upstream.

No backend is wired up yet. Which one lands is still open — see
docs/decisions/production_solver_selection.md:

  * Candidate A (lunafoxfire/yet-another-factory-planner) is MIT and benchmarked
    clean against our data, but its LP engine glpk.js is GPL-3.0, and fork delta
    F1 (swap for HiGHS) is unresolved.
  * Candidate A-prime (lunafoxfire/satisfactory-planner) is technically better on
    every axis and uses an MIT engine, but carries no licence at all. A request is
    outstanding.

The adapter contract is deliberately identical either way, so this file is the
only thing the outcome changes.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from .contracts import SolveRequest, SolveResponse
from .gamedata import ReferenceData


@runtime_checkable
class Backend(Protocol):
    """A production solver, behind our contract."""

    name: str

    def solve(self, request: SolveRequest, data: ReferenceData) -> SolveResponse:
        ...


class BackendNotSelected(NotImplementedError):
    """Raised until the Phase 0 licence questions are settled."""


class UnselectedBackend:
    """Placeholder so the adapter is importable and testable before a solver lands."""

    name = "unselected"

    def solve(self, request: SolveRequest, data: ReferenceData) -> SolveResponse:
        raise BackendNotSelected(
            "no production solver is wired up yet: fork delta F1 (glpk.js GPL-3.0) "
            "and the licence request on lunafoxfire/satisfactory-planner are both open. "
            "See docs/decisions/production_solver_selection.md."
        )


_REGISTRY: dict[str, Backend] = {}


def register(backend: Backend) -> None:
    if backend.name in _REGISTRY:
        raise ValueError(f"backend already registered: {backend.name}")
    _REGISTRY[backend.name] = backend


def get(name: str | None = None) -> Backend:
    if not _REGISTRY:
        return UnselectedBackend()
    if name is None:
        if len(_REGISTRY) > 1:
            raise ValueError(f"several backends registered, name one: {sorted(_REGISTRY)}")
        return next(iter(_REGISTRY.values()))
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(f"unknown backend {name!r}; registered: {sorted(_REGISTRY)}") from None


def registered() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))
