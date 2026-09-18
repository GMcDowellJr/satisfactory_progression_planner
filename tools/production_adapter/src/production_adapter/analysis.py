"""Compare solve configurations against each other. It does not choose between them.

Plan section 1.5: *do not collapse all tradeoffs into one opaque score; prefer
Pareto comparisons before introducing a weighted composite objective.* D3b, in
`docs/decisions/production_lp_formulation.md` section 12.2: the tool should
*surface both versions and their downstream impacts rather than return one ranked
answer.* This module is that instruction made executable.

Its first use is D2, the deferred power statistic: solve the same request under
`min`, `mean` and `max` and read what the choice costs, rather than picking one on
theory. D2 is not resolved by doing so — each solve still uses exactly one
statistic. What changes is that the decision can wait for evidence instead of
blocking on one.

**It cannot recommend, by construction.** There is no `best`, no `rank`, no score,
and no sort. `Comparison.variants` is returned in the caller's order and is never
reordered by any metric. Nothing here returns a single variant. That is the same
structural guard `_demand_oracle.AmbiguousDemand` uses: a thing that cannot pick
cannot quietly become the progression layer.

The second guard is about honesty rather than scope. Two configurations can only be
priced against each other when they share a feasible set — when only the *metric*
differs. If the scenario, the enabled recipes, the targets, the caps or the
unconsumed mode differ, one variant's plan is not a valid plan for the other and
re-pricing it would produce a number that looks like a comparison and is not. Those
cells come back as `None` with the reason named in `Comparison.incomparable`,
never as a value.

Dependency direction, per section 11.1: this imports `lp_backend`; nothing in the
adapter imports this. `__init__.py` does not import it either, so the contract
package stays dependency-free.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import SolveRequest, SolveResponse, Weights
from .gamedata import Recipe, ReferenceData
from .lp_backend import LpBackend, PowerStatistic, enabled_recipe_ids


def _power(recipe: Recipe, statistic: PowerStatistic) -> float:
    """Deliberately a second implementation of `lp_backend._statistic`.

    Three lines, and keeping them separate makes this module an independent
    evaluator of the backend rather than a restatement of it — the same reason
    `tests/_fixed_recipe_expectations.py` reads the CSVs directly instead of going
    through `gamedata`. If the two ever disagree, a test should say so.
    """
    if statistic is PowerStatistic.MIN:
        return recipe.power.min_mw
    if statistic is PowerStatistic.MAX:
        return recipe.power.max_mw
    return recipe.power.mean_mw


class InconsistentComparison(RuntimeError):
    """A regret came back meaningfully negative.

    Regret is non-negative by construction: comparable variants share a feasible
    set, so one's plan is always a valid plan for the other and can never cost less
    than that other's own optimum. A real negative means either the feasibility
    signature admitted a pair it should not have, or a solve did not reach its
    optimum. Both are defects, and neither should be rounded away.
    """


#: D3a's second-stage LP accepts the primary optimum within a relative slack of
#: 1e-9, so a cross-priced plan can undercut a reported optimum by about that much.
#: Below this, a negative regret is that slack and is snapped to zero; above it,
#: `InconsistentComparison` is raised.
REGRET_NOISE = 1.0e-6


@dataclass(frozen=True)
class Variant:
    """One solve configuration. The axis of difference is whatever the caller varies.

    Power statistic, weights, allowed recipes, scenario, unconsumed mode — all of
    them are just fields of `request`, `data` or `backend`, so nothing here is
    specific to D2.
    """

    label: str
    request: SolveRequest
    data: ReferenceData
    backend: LpBackend

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("a variant needs a label")


@dataclass(frozen=True)
class Feasibility:
    """What determines the constraint set, as opposed to the objective.

    Two variants whose `Feasibility` is equal admit exactly the same plans, so
    either one's plan can be priced under the other's metric and the resulting
    difference is a real regret. Unequal, and no cross-pricing is defensible.
    """

    scenario: tuple[float, float, float]
    recipe_ids: tuple[str, ...]
    targets: tuple[tuple[str, float], ...]
    caps: tuple[tuple[str, float | None], ...]
    unconsumed: str
    activity_upper_bound: float

    def why_not(self, other: "Feasibility") -> str | None:
        """The first difference, named. `None` when the two are comparable."""
        if self.scenario != other.scenario:
            return f"different scenario {self.scenario} vs {other.scenario}"
        if self.recipe_ids != other.recipe_ids:
            n = len(set(self.recipe_ids) ^ set(other.recipe_ids))
            return f"different enabled recipe sets ({n} recipes differ)"
        if self.targets != other.targets:
            return "different output targets"
        if self.caps != other.caps:
            return "different resource caps"
        if self.unconsumed != other.unconsumed:
            return f"different unconsumed mode ({self.unconsumed} vs {other.unconsumed})"
        if self.activity_upper_bound != other.activity_upper_bound:
            return "different activity upper bound"
        return None


def _feasibility(variant: Variant) -> Feasibility:
    s = variant.data.scenario
    return Feasibility(
        scenario=(
            s.recipe_input_multiplier,
            s.machine_power_multiplier,
            s.project_assembly_requirement_multiplier,
        ),
        recipe_ids=enabled_recipe_ids(variant.request, variant.data),
        targets=tuple(sorted((o.item_id, o.rate_per_min) for o in variant.request.outputs)),
        caps=tuple(sorted(
            (c.item_id, c.rate_per_min) for c in variant.request.resource_caps
        )),
        unconsumed=variant.backend.unconsumed.value,
        activity_upper_bound=variant.backend.activity_upper_bound,
    )


@dataclass(frozen=True)
class Solved:
    """One variant's answer, plus the figures a comparison is made of."""

    label: str
    response: SolveResponse
    objective: float          # under this variant's own metric
    power_min_mw: float
    power_stat_mw: float      # under this variant's own statistic
    power_max_mw: float
    raw_total_per_min: float
    machine_total: float
    recipe_ids: frozenset[str]


def _objective(
    response: SolveResponse, data: ReferenceData, weights: Weights,
    statistic: PowerStatistic,
) -> float:
    """Section 7.4's objective, evaluated from a response.

    The disposal term is absent because D1 disposal is blocked on P5, and the
    leftover slack carries zero cost by construction (section 2.4), so neither
    contributes. Recomputed here rather than read off the LP, which does not
    expose it.
    """
    raw = sum(r.rate_per_min for r in response.raw_inputs)
    power = sum(
        _power(data.recipes[u.recipe_id], statistic) * u.machine_equivalents
        for u in response.recipes
    )
    machines = sum(u.machine_equivalents for u in response.recipes)
    return weights.resources * raw + weights.power * power + weights.buildings * machines


@dataclass(frozen=True)
class Comparison:
    """Figures, differences, and what could not be compared. No verdict.

    `variants` preserves the caller's order and is never sorted. There is
    deliberately no accessor that returns one variant.
    """

    variants: tuple[Solved, ...]
    regret: dict[tuple[str, str], float | None]
    incomparable: dict[tuple[str, str], str]
    recipe_differences: dict[tuple[str, str], tuple[tuple[str, ...], tuple[str, ...]]]

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(v.label for v in self.variants)

    def format_table(self, precision: int = 2) -> str:
        """A plain-text rendering. Descriptive only — the row order is the caller's."""
        width = max([len(v.label) for v in self.variants] + [8])
        lines = [
            f"{'variant':<{width}}  {'objective':>12}  {'min MW':>10}  {'stat MW':>10}"
            f"  {'max MW':>10}  {'raw/min':>10}  {'machines':>9}  recipes"
        ]
        for v in self.variants:
            lines.append(
                f"{v.label:<{width}}  {v.objective:>12.{precision}f}"
                f"  {v.power_min_mw:>10.{precision}f}  {v.power_stat_mw:>10.{precision}f}"
                f"  {v.power_max_mw:>10.{precision}f}  {v.raw_total_per_min:>10.{precision}f}"
                f"  {v.machine_total:>9.{precision}f}  {len(v.recipe_ids):>3d}"
            )
        lines.append("")
        lines.append("regret: cost of running the ROW's plan under the COLUMN's metric,")
        lines.append("        minus that column's own optimum. Zero on the diagonal.")
        corner = "plan vs metric"
        header = f"{corner:<{width}}" + "".join(
            f"  {label:>12}" for label in self.labels
        )
        lines.append(header)
        for plan in self.labels:
            cells = []
            for metric in self.labels:
                value = self.regret.get((plan, metric))
                cells.append(f"  {'n/a':>12}" if value is None else f"  {value:>12.{precision}f}")
            lines.append(f"{plan:<{width}}" + "".join(cells))
        if self.incomparable:
            lines.append("")
            lines.append("not comparable:")
            for (plan, metric), reason in sorted(self.incomparable.items()):
                lines.append(f"  {plan} under {metric}: {reason}")
        return "\n".join(lines)


def compare(variants: tuple[Variant, ...] | list[Variant]) -> Comparison:
    """Solve every variant and cross-price each plan under every comparable metric."""
    variants = tuple(variants)
    if len(variants) < 2:
        raise ValueError("a comparison needs at least two variants")
    labels = [v.label for v in variants]
    duplicates = {label for label in labels if labels.count(label) > 1}
    if duplicates:
        raise ValueError(f"variant labels must be unique: {sorted(duplicates)}")

    solved: list[Solved] = []
    for variant in variants:
        response = variant.backend.solve(variant.request, variant.data)
        statistic = variant.backend.power_statistic
        solved.append(Solved(
            label=variant.label,
            response=response,
            objective=_objective(response, variant.data, variant.request.weights, statistic),
            power_min_mw=response.power.min_mw,
            power_stat_mw=response.power.scenario_mw,
            power_max_mw=response.power.max_mw,
            raw_total_per_min=sum(r.rate_per_min for r in response.raw_inputs),
            machine_total=sum(u.machine_equivalents for u in response.recipes),
            recipe_ids=frozenset(u.recipe_id for u in response.recipes),
        ))

    feasibility = {v.label: _feasibility(v) for v in variants}
    by_label = {v.label: v for v in variants}
    optimum = {s.label: s.objective for s in solved}

    regret: dict[tuple[str, str], float | None] = {}
    incomparable: dict[tuple[str, str], str] = {}
    for plan in solved:
        for metric in variants:
            key = (plan.label, metric.label)
            reason = feasibility[plan.label].why_not(feasibility[metric.label])
            if reason is not None:
                regret[key] = None
                incomparable[key] = reason
                continue
            cost = _objective(
                plan.response, metric.data, metric.request.weights,
                metric.backend.power_statistic,
            )
            value = cost - optimum[metric.label]
            if value < 0.0:
                tolerance = max(1.0, abs(optimum[metric.label])) * REGRET_NOISE
                if value < -tolerance:
                    raise InconsistentComparison(
                        f"{plan.label}'s plan costs {-value:.6g} LESS under {metric.label}'s "
                        f"metric than {metric.label}'s own optimum. Either the feasibility "
                        "check admitted a pair it should not have, or a solve did not reach "
                        "its optimum."
                    )
                value = 0.0
            regret[key] = value

    differences: dict[tuple[str, str], tuple[tuple[str, ...], tuple[str, ...]]] = {}
    for a in solved:
        for b in solved:
            if a.label < b.label:
                differences[(a.label, b.label)] = (
                    tuple(sorted(a.recipe_ids - b.recipe_ids)),
                    tuple(sorted(b.recipe_ids - a.recipe_ids)),
                )

    return Comparison(
        variants=tuple(solved), regret=regret,
        incomparable=incomparable, recipe_differences=differences,
    )


def power_statistic_variants(
    request: SolveRequest, data: ReferenceData, **backend_kwargs
) -> tuple[Variant, ...]:
    """The D2 instance of the general tool: the same request under all three statistics.

    Returned in `min, mean, max` order, which is the statistic's own order and not a
    preference. `backend_kwargs` goes to `LpBackend` for everything except
    `power_statistic`, which is what this varies.
    """
    if "power_statistic" in backend_kwargs:
        raise ValueError("power_statistic is what this varies; do not pin it")
    return tuple(
        Variant(
            label=statistic.value,
            request=request,
            data=data,
            backend=LpBackend(power_statistic=statistic, **backend_kwargs),
        )
        for statistic in (PowerStatistic.MIN, PowerStatistic.MEAN, PowerStatistic.MAX)
    )
