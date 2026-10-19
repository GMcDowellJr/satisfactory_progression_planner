"""Phase aggregation: deliveries x per-unit expansions -> quantities per phase.

Plan section 7B and demand-expansion record A1.5. The caller names the scope
by passing the delivery rows (record §6: the module never selects them); the
Project Assembly multiplier is applied here, once, and reported as its own
column, separate from the recipe multiplier (record §3.3).

Two rules that are definitions rather than data, stated so they can be
disagreed with:

    self-count     a delivered item counts as itself, at coefficient 1, in the
                   phase that delivers it. Phase 3's 500 Modular Engines are
                   500 Modular Engines required by phase 3, and phase 4's 250
                   rockets add 625 more through their recipe.
    incomplete     a delivery the engine refuses (an unpinned ambiguity on its
                   path, under the default table: Biochemical Sculptor and AI
                   Expansion Server on Ficsite Ingot) is listed in
                   `unresolved` and its phase is marked incomplete. Its OWN
                   quantity is still counted, because the delivery row states
                   it; only its dependencies are unknown. Every quantity that
                   sums an incomplete phase is a lower bound, and the cell
                   says so. Nothing is guessed for it. (The self-count was
                   skipped with the rest until PR #3 review, 2026-10-10.)

Incremental and cumulative views are kept apart (plan section 7B): a part is
not growing because its earlier phases are being counted again.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from production_adapter.contracts import ItemId
from production_adapter.gamedata import ProjectAssemblyRequirement
from production_adapter.scenario import Scenario

from .contracts import AmbiguousRoute, CycleDetected, DemandExpansionError, UnproducibleItem
from .expand import UNDECLARED, expand

#: What a single delivery may fail on. Anything else (an unknown fluid
#: variant, pre-scaled data) is a configuration error and propagates.
_ROUTE_REFUSALS = (AmbiguousRoute, UnproducibleItem, CycleDetected)
from .graph import RecipeGraph


@dataclass(frozen=True)
class Delivery:
    """One delivery row as aggregated: the 1x quantity, the scaled quantity,
    and whether its expansion resolved."""

    phase: int
    phase_name: str
    item_id: ItemId
    quantity_1x: float
    quantity: Fraction
    #: None when expanded; the refusal's class name and message otherwise
    refusal: str | None = None


@dataclass(frozen=True)
class Growth:
    """Phase-over-phase growth. `ratio` is current / previous when the previous
    phase required the item; "new" when it did not and this one does; "none"
    when neither does. Never infinity (plan section 7B)."""

    kind: str                      # "ratio" | "new" | "none"
    ratio: Fraction | None = None


@dataclass(frozen=True)
class PhaseCell:
    """One item in one phase. All quantities are units, exact.

    quantity     required by this phase's deliveries (incremental)
    previous     the same for the previous phase in the table (0 for the first)
    growth       quantity against previous
    cumulative   this phase and every earlier one
    remaining    every later phase, excluding this one
    complete     this phase expanded every delivery
    cumulative_complete, remaining_complete
                 every phase in that sum is complete; False means lower bound
    """

    item_id: ItemId
    phase: int
    quantity: Fraction
    previous: Fraction
    growth: Growth
    cumulative: Fraction
    remaining: Fraction
    complete: bool
    cumulative_complete: bool
    remaining_complete: bool


@dataclass(frozen=True)
class PhaseDemand:
    route_table: str
    recipe_input_multiplier: float
    fluid_rounding_unit: str | None
    project_assembly_multiplier: float
    phases: tuple[int, ...]
    deliveries: tuple[Delivery, ...]
    unresolved: tuple[Delivery, ...]
    complete: dict[int, bool]
    #: item -> phase -> cell, every item that any resolved delivery embeds,
    #: with a cell for every phase (zero cells included so growth is defined)
    cells: dict[ItemId, dict[int, PhaseCell]]

    def item(self, item_id: ItemId) -> tuple[PhaseCell, ...]:
        """One item across the phases, in phase order. Empty if never required."""
        by_phase = self.cells.get(item_id, {})
        return tuple(by_phase[p] for p in self.phases if p in by_phase)

    def first_phase(self, item_id: ItemId) -> int | None:
        for cell in self.item(item_id):
            if cell.quantity > 0:
                return cell.phase
        return None

    def last_phase(self, item_id: ItemId) -> int | None:
        """The dependency horizon: the last phase that requires the item. A
        lower bound on the horizon when a later phase is incomplete."""
        last = None
        for cell in self.item(item_id):
            if cell.quantity > 0:
                last = cell.phase
        return last


def _growth(current: Fraction, previous: Fraction) -> Growth:
    if previous > 0:
        return Growth("ratio", current / previous)
    if current > 0:
        return Growth("new")
    return Growth("none")


def aggregate(
    graph: RecipeGraph,
    deliveries: tuple[ProjectAssemblyRequirement, ...],
    scenario: Scenario = Scenario(),
    fluid_rounding=UNDECLARED,
) -> PhaseDemand:
    """Quantities per item per phase for the given delivery rows.

    Phases are the distinct phase numbers in `deliveries`, ascending. "Previous"
    means the previous phase in that sequence, not phase - 1.
    """
    if not deliveries:
        raise DemandExpansionError("no deliveries: the caller names the scope (record §6)")
    phases = tuple(sorted({d.phase for d in deliveries}))
    per_phase: dict[int, dict[ItemId, Fraction]] = {p: {} for p in phases}
    complete: dict[int, bool] = {p: True for p in phases}
    rows: list[Delivery] = []
    unresolved: list[Delivery] = []
    expansions = {}
    for d in deliveries:
        quantity = Fraction(repr(scenario.apply_project_assembly_quantity(d.quantity_1x)))
        bucket = per_phase[d.phase]
        bucket[d.item_id] = bucket.get(d.item_id, Fraction(0)) + quantity      # self-count
        try:
            if d.item_id not in expansions:
                expansions[d.item_id] = expand(graph, d.item_id, scenario, fluid_rounding)
            e = expansions[d.item_id]
        except _ROUTE_REFUSALS as err:
            row = Delivery(d.phase, d.phase_name, d.item_id, d.quantity_1x, quantity,
                           refusal=f"{type(err).__name__}: {err}")
            rows.append(row)
            unresolved.append(row)
            complete[d.phase] = False
            continue
        rows.append(Delivery(d.phase, d.phase_name, d.item_id, d.quantity_1x, quantity))
        for item, per_unit in e.embedded.items():
            bucket[item] = bucket.get(item, Fraction(0)) + per_unit * quantity

    items = sorted({i for bucket in per_phase.values() for i in bucket})
    cells: dict[ItemId, dict[int, PhaseCell]] = {}
    for item in items:
        series = [per_phase[p].get(item, Fraction(0)) for p in phases]
        total = sum(series, Fraction(0))
        running = Fraction(0)
        running_complete = True
        by_phase: dict[int, PhaseCell] = {}
        for idx, p in enumerate(phases):
            q = series[idx]
            prev = series[idx - 1] if idx else Fraction(0)
            running += q
            running_complete = running_complete and complete[p]
            later = phases[idx + 1:]
            by_phase[p] = PhaseCell(
                item_id=item,
                phase=p,
                quantity=q,
                previous=prev,
                growth=_growth(q, prev),
                cumulative=running,
                remaining=total - running,
                complete=complete[p],
                cumulative_complete=running_complete,
                remaining_complete=all(complete[l] for l in later),
            )
        cells[item] = by_phase

    first = next(iter(expansions.values()), None)
    if first is None:
        raise DemandExpansionError(
            "no delivery expanded; the configuration cannot be stamped from a refusal"
        )
    return PhaseDemand(
        route_table=graph.routes.name,
        recipe_input_multiplier=scenario.recipe_input_multiplier,
        fluid_rounding_unit=first.fluid_rounding_unit,
        project_assembly_multiplier=scenario.project_assembly_requirement_multiplier,
        phases=phases,
        deliveries=tuple(rows),
        unresolved=tuple(unresolved),
        complete=complete,
        cells=cells,
    )
