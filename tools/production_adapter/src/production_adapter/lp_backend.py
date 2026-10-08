"""A Python-native LP backend: scipy.optimize.linprog, HiGHS underneath.

Implements section 7 of `docs/decisions/production_lp_formulation.md`. Section 10
of `docs/decisions/production_solver_selection.md` reopened build-vs-vendor and
named the Python-native path the expected outcome; this is that path. Nothing
here is derived from Candidate A's source — only from the formulation record,
which is ours.

Not registered on import. `production_adapter/__init__.py` deliberately does not
import this module, so the contract package stays dependency-free and
`registered()` stays empty until a caller says otherwise. Wire it explicitly:

    from production_adapter import load, OutputTarget, SolveRequest
    from production_adapter.lp_backend import LpBackend, PowerStatistic

    backend = LpBackend(power_statistic=PowerStatistic.MEAN)
    response = backend.solve(request, load(repo_root))

Three decisions are still open in the formulation record and are surfaced as
constructor arguments rather than baked in:

    D2   power statistic. DEFERRED by Greg (record section 12.1) until the
         variable-power tier has been played. `power_statistic` is therefore
         REQUIRED, with no default: the deferral is structural, so no caller can
         inherit a choice nobody made. Every producer in the current validation
         set is fixed-power, so min == mean == max there and the cases stay
         D2-independent by construction.
    D1   unconsumed output. `disposal` is blocked on P5 (no AWESOME Sink or
         generator exists in the reference layer), so the implementable default
         is `free` with every leftover named in `warnings` — the stopgap recorded
         at section 2.7. `forbid` is available; `disposal` raises.
    7.5  `canonical_mw` re-evaluates the selected recipe mix at canonical power
         rather than re-solving at the canonical scenario. That is what the
         contract's wording implies; the record flags the alternative as open and
         a warning says which one this is.

Power excludes extraction throughout (D5).
"""
from __future__ import annotations

import enum
import math
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

from .contracts import (
    BindingCap, DistrictRequest, DistrictResponse, ItemFlow, MachineCount, PowerReport,
    RawInput, RecipeMode, RecipeUse, ResourceCap, SolveRequest, SolveResponse, TargetRate,
)
from .gamedata import ReferenceData, Recipe

#: Upper bound on every recipe activity. Section 5 mitigation 2: an unbounded ray
#: becomes a bounded answer with a warning rather than a solver hang. Generous
#: enough never to bind on a real target.
ACTIVITY_UPPER_BOUND = 1.0e6

#: Upper bound on raw draw and on leftover slack. Same purpose, different scale:
#: these are per-minute rates, not machine counts.
FLOW_UPPER_BOUND = 1.0e9

#: Below this a variable is treated as zero. HiGHS' own primal feasibility
#: tolerance floors out around 1e-7 and it will return activities at ~1e-8 and
#: flows at ~1e-7 that are numerical noise rather than production; tightening the
#: solver option below that is rejected outright. 1e-6 sits above the noise and
#: two orders below the four decimal places section 8 validates to.
TOLERANCE = 1.0e-6

#: Leftovers are named in `warnings` only above this, which is the precision the
#: warning prints at. A figure that renders as "0.0000/min" is solver residue and
#: reporting it as unconsumed output is a false positive. `SolveResponse.items`
#: still carries every flow exactly, for a caller that wants the residue.
REPORT_EPSILON = 1.0e-4


class PowerStatistic(str, enum.Enum):
    """Which end of `PowerRange` the objective prices. D2, deferred."""

    MIN = "min"
    MEAN = "mean"
    MAX = "max"


class UnconsumedMode(str, enum.Enum):
    """D1. `DISPOSAL` is recorded as the recommendation and blocked on P5."""

    FREE = "free"
    FORBID = "forbid"
    DISPOSAL = "disposal"


class Infeasible(RuntimeError):
    """The LP has no solution. Under FORBID this is routine, not a defect."""


class SolverFailure(RuntimeError):
    """HiGHS returned neither an optimum nor an infeasibility."""


class Unbounded(RuntimeError):
    """A district solve with a weighted output that no cap bounds (A27.2).

    Routine, not a defect: a target whose whole chain runs on uncapped raw
    resources can be made at any rate, and "any rate" is not a plan. The
    message names the uncapped raws; cap them or drop the weight.
    """


def _statistic(recipe: Recipe, statistic: PowerStatistic) -> float:
    if statistic is PowerStatistic.MIN:
        return recipe.power.min_mw
    if statistic is PowerStatistic.MAX:
        return recipe.power.max_mw
    return recipe.power.mean_mw


def enabled_recipe_ids(
    request: SolveRequest | DistrictRequest, data: ReferenceData,
) -> tuple[str, ...]:
    """Sorted, per D3a mitigation 1. The sort is the determinism guard.

    Public because `analysis.py` needs it to decide whether two solve
    configurations share a feasible set. Duplicating it there would let the two
    notions of "which recipes are enabled" drift apart silently, and the whole
    point of that check is that it must not be wrong.
    """
    allowed = request.allowed_recipes
    if allowed.mode is RecipeMode.ALL:
        ids = set(data.recipes)
    elif allowed.mode is RecipeMode.BASE_ONLY:
        ids = set(data.base_recipes())
    else:
        ids = set(allowed.recipe_ids)
        unknown = ids - set(data.recipes)
        if unknown:
            raise ValueError(f"unknown recipe ids: {sorted(unknown)}")
    return tuple(sorted(ids))


@dataclass(frozen=True)
class _Problem:
    recipe_ids: tuple[str, ...]
    item_ids: tuple[str, ...]
    raw_ids: tuple[str, ...]
    n_x: int
    n_s: int
    n_l: int
    a_eq: np.ndarray
    b_eq: np.ndarray
    bounds: list[tuple[float, float | None]]
    primary: np.ndarray
    secondary: np.ndarray


class LpBackend:
    """The seam's first implementation. One LP, solved twice for determinism."""

    name = "scipy_highs"

    def __init__(
        self,
        power_statistic: PowerStatistic,
        unconsumed: UnconsumedMode = UnconsumedMode.FREE,
        activity_upper_bound: float = ACTIVITY_UPPER_BOUND,
        tolerance: float = TOLERANCE,
    ) -> None:
        self.power_statistic = PowerStatistic(power_statistic)
        self.unconsumed = UnconsumedMode(unconsumed)
        if self.unconsumed is UnconsumedMode.DISPOSAL:
            raise NotImplementedError(
                "D1 disposal is blocked on P5: planning_data/game/reference/ carries no "
                "AWESOME Sink and no generator, so a disposal activity cannot be given a "
                "throughput or a power draw. See production_lp_formulation.md section 2.7."
            )
        self.activity_upper_bound = float(activity_upper_bound)
        self.tolerance = float(tolerance)

    # -- model ------------------------------------------------------------

    def _build(self, request: SolveRequest, data: ReferenceData) -> _Problem:
        if request.existing_inventory:
            raise NotImplementedError(
                "existing_inventory is a Phase 4 hook and is not in the section 7 "
                "formulation; passing it would be silently ignored, so it raises instead."
            )

        recipe_ids = enabled_recipe_ids(request, data)
        targets = {o.item_id: o.rate_per_min for o in request.outputs}
        caps = {c.item_id: c.rate_per_min for c in request.resource_caps}
        return self._build_core(recipe_ids, targets, caps, request.weights, data)

    def _build_core(
        self, recipe_ids: tuple[str, ...], targets: dict[str, float],
        caps: dict[str, float | None], w, data: ReferenceData,
        floors: dict[str, float] | None = None,
    ) -> _Problem:
        """The section 7 matrices. `solve` and `solve_district` share them.

        `targets` are the b_eq demands (0.0 for a district target, whose output
        is then the item's leftover flow). `floors` are lower bounds on those
        leftovers and exist only for the district solve; the demand-driven
        solve never passes them, so its problem is unchanged by construction.
        """
        floors = floors or {}
        recipes = [data.recipes[rid] for rid in recipe_ids]

        items: set[str] = set()
        for r in recipes:
            items.update(i for i, _ in r.inputs)
            items.update(i for i, _ in r.outputs)
        items.update(targets)
        item_ids = tuple(sorted(items))
        item_index = {i: n for n, i in enumerate(item_ids)}

        raw_ids = tuple(i for i in item_ids if i in data.resource_items)
        raw_index = {i: n for n, i in enumerate(raw_ids)}

        unreachable = [
            i for i in targets
            if i not in raw_index and not any(i == it for r in recipes for it, _ in r.outputs)
        ]
        if unreachable:
            raise Infeasible(
                f"no enabled recipe produces {sorted(unreachable)}; widen allowed_recipes"
            )

        n_x, n_s = len(recipe_ids), len(raw_ids)
        n_l = len(item_ids) if self.unconsumed is UnconsumedMode.FREE else 0
        n = n_x + n_s + n_l

        a_eq = np.zeros((len(item_ids), n), dtype=float)
        b_eq = np.zeros(len(item_ids), dtype=float)
        for col, r in enumerate(recipes):
            for item, rate in r.outputs:
                a_eq[item_index[item], col] += rate
            for item, rate in r.inputs:
                a_eq[item_index[item], col] -= rate
        for item, col in raw_index.items():
            a_eq[item_index[item], n_x + col] = 1.0
        if n_l:
            for item, row in item_index.items():
                a_eq[row, n_x + n_s + row] = -1.0
        for item, rate in targets.items():
            b_eq[item_index[item]] = rate

        bounds: list[tuple[float, float | None]] = [
            (0.0, self.activity_upper_bound) for _ in recipe_ids
        ]
        for item in raw_ids:
            cap = caps.get(item)
            bounds.append((0.0, FLOW_UPPER_BOUND if cap is None else float(cap)))
        if n_l:
            bounds.extend((floors.get(item, 0.0), FLOW_UPPER_BOUND) for item in item_ids)

        primary = np.zeros(n, dtype=float)
        for col, r in enumerate(recipes):
            primary[col] = w.power * _statistic(r, self.power_statistic) + w.buildings
        primary[n_x:n_x + n_s] = w.resources
        # Leftover slack carries zero cost. Section 2.4 rejects an objective
        # penalty on leftovers: lambda has no physical referent. The secondary
        # objective below keeps leftovers minimal among optima instead, which
        # costs nothing and invents nothing.

        secondary = np.ones(n, dtype=float)

        return _Problem(
            recipe_ids=recipe_ids, item_ids=item_ids, raw_ids=raw_ids,
            n_x=n_x, n_s=n_s, n_l=n_l,
            a_eq=a_eq, b_eq=b_eq, bounds=bounds,
            primary=primary, secondary=secondary,
        )

    # -- solve ------------------------------------------------------------

    def _run(self, c, p: _Problem, extra_ub=None, extra_b=None, on_unbounded: str | None = None):
        result = linprog(
            c, A_ub=extra_ub, b_ub=extra_b, A_eq=p.a_eq, b_eq=p.b_eq,
            bounds=p.bounds, method="highs",
        )
        if result.status == 3 and on_unbounded:
            raise Unbounded(on_unbounded)
        if result.status == 2:
            raise Infeasible(
                "no feasible production plan"
                + (
                    " under unconsumed=forbid: a multi-output recipe's byproduct has no "
                    "enabled consumer (formulation record section 2.2)"
                    if self.unconsumed is UnconsumedMode.FORBID else ""
                )
            )
        if result.status != 0:
            raise SolverFailure(f"HiGHS status {result.status}: {result.message}")
        return result

    def solve(self, request: SolveRequest, data: ReferenceData) -> SolveResponse:
        p = self._build(request, data)

        first = self._run(p.primary, p)
        # D3a: among optima of the primary objective, pick the one minimising
        # total activity. A lexicographic refinement, not an epsilon perturbation
        # (section 4 rejects the latter: it makes the objective value meaningless
        # at the margin). "Fewer distinct recipes" is NOT implemented — it is a
        # cardinality objective and needs binaries, which section 7.4 rules out
        # while fork delta F2 stands. Recorded rather than silently approximated.
        z = float(first.fun)
        slack = max(abs(z), 1.0) * 1.0e-9
        second = self._run(
            p.secondary, p,
            extra_ub=p.primary.reshape(1, -1), extra_b=np.array([z + slack]),
        )
        v = np.asarray(second.x, dtype=float)
        # The tie that matters is in the recipe activities. Leftover slack carries
        # zero cost by construction (section 2.4), so it is degenerate in the
        # primary objective whenever any leftover exists at all; reporting that as
        # a broken tie would fire on nearly every solve and mean nothing. Section 4
        # is about recipe selections churning between runs, so compare those.
        tie_broken = bool(
            np.max(np.abs(v[:p.n_x] - np.asarray(first.x, dtype=float)[:p.n_x]))
            > self.tolerance
        )

        targets = {o.item_id: o.rate_per_min for o in request.outputs}
        return self._response(targets, request.resource_caps, data, p, v, z, tie_broken)

    # -- the district solve (A27.1 K2, A27.2) ------------------------------

    def solve_district(self, request: DistrictRequest, data: ReferenceData) -> DistrictResponse:
        """Supply-side: maximise the weighted selected outputs within the caps.

        Three LPs, lexicographic, each a refinement of the last within a 1e-9
        relative slack (the D3a pattern, extended by one stage):

            1  max  sum_i w_i * out_i         out_i = the target's leftover flow,
                                              bounded below by its floor
            2  min  goal cost                 request.weights, as `solve` prices it
            3  min  total activity            D3a tie-break

        A target with weight 0 and no floor is not in the problem at all and is
        reported as excluded at 0.0. A floor that cannot be met raises
        `Infeasible` naming the floor(s): alone-infeasible ones first, then the
        joint case. A weighted output that no cap bounds raises `Unbounded`.
        Needs `unconsumed=FREE`: the outputs ARE leftover flows.
        """
        if self.unconsumed is not UnconsumedMode.FREE:
            raise NotImplementedError(
                "a district target's output is its leftover flow (A27.2); under "
                "unconsumed=forbid every leftover is zero and there is nothing to maximise"
            )
        recipe_ids = enabled_recipe_ids(request, data)
        active = tuple(t for t in request.targets if t.is_active)
        targets = {t.item_id: 0.0 for t in active}
        floors = {t.item_id: t.minimum_rate for t in active if t.minimum_rate is not None}
        caps = {c.item_id: c.rate_per_min for c in request.resource_caps}
        p = self._build_core(recipe_ids, targets, caps, request.weights, data, floors)
        index = {i: n for n, i in enumerate(p.item_ids)}
        out_col = {t.item_id: p.n_x + p.n_s + index[t.item_id] for t in active}

        n = p.n_x + p.n_s + p.n_l
        c1 = np.zeros(n, dtype=float)
        for t in active:
            c1[out_col[t.item_id]] = -t.weight
        uncapped = [i for i in p.raw_ids if caps.get(i) is None]
        weighted = [t.item_id for t in active if t.weight > 0]
        try:
            first = self._run(
                c1, p,
                on_unbounded=(
                    f"weighted output of {weighted} is unbounded: raw inputs without a "
                    f"cap {uncapped} can feed it at any rate. Cap them or drop the weight"
                ),
            )
        except Infeasible:
            raise self._floor_diagnosis(recipe_ids, caps, request, data, floors) from None
        # HiGHS rarely reports status 3 here: the section 5 guards (activity and
        # flow upper bounds) turn a true ray into a huge finite answer. A plan
        # sitting on either guard is that ray, so it is refused by the same name.
        x1 = np.asarray(first.x, dtype=float)
        on_guard = (
            bool(np.any(x1[:p.n_x] >= self.activity_upper_bound - self.tolerance))
            or bool(np.any(x1[p.n_x:p.n_x + p.n_s] >= FLOW_UPPER_BOUND - 1.0))
        )
        if on_guard:
            raise Unbounded(
                f"weighted output of {weighted} is unbounded: raw inputs without a cap "
                f"{uncapped} can feed it at any rate (the answer sits on the section 5 "
                "guard). Cap them or drop the weight"
            )
        z1 = -float(first.fun)
        slack1 = max(abs(z1), 1.0) * 1.0e-9

        second = self._run(
            p.primary, p, extra_ub=c1.reshape(1, -1), extra_b=np.array([-z1 + slack1]),
        )
        z2 = float(second.fun)
        slack2 = max(abs(z2), 1.0) * 1.0e-9
        third = self._run(
            p.secondary, p,
            extra_ub=np.vstack([c1, p.primary]),
            extra_b=np.array([-z1 + slack1, z2 + slack2]),
        )
        v = np.asarray(third.x, dtype=float)
        tie_broken = bool(
            np.max(np.abs(v[:p.n_x] - np.asarray(second.x, dtype=float)[:p.n_x]))
            > self.tolerance
        )

        rates = {t.item_id: float(v[out_col[t.item_id]]) for t in active}
        plan = self._response(rates, request.resource_caps, data, p, v, z2, tie_broken)

        tol = self.tolerance
        target_rates = tuple(
            TargetRate(
                item_id=t.item_id,
                rate_per_min=rates.get(t.item_id, 0.0),
                weight=t.weight,
                minimum_rate=t.minimum_rate,
                at_floor=(
                    t.minimum_rate is not None
                    and rates.get(t.item_id, 0.0) <= t.minimum_rate + tol
                ),
                excluded=not t.is_active,
            )
            for t in request.targets
        )
        # Shadow prices come from stage 1, the only stage whose objective is
        # the weighted output. HiGHS reports a dual on every variable bound;
        # for an upper bound in a minimisation it is <= 0, and loosening the
        # bound by one unit changes the objective (-weighted output) by that
        # much, so the price of one more unit of cap is its negation.
        marginals = np.asarray(first.upper.marginals, dtype=float)
        s_first = np.asarray(first.x, dtype=float)[p.n_x:p.n_x + p.n_s]
        binding = tuple(
            BindingCap(
                item_id=i,
                cap_per_min=float(caps[i]),
                shadow_price=-float(marginals[p.n_x + col]),
            )
            for col, i in enumerate(p.raw_ids)
            if caps.get(i) is not None and s_first[col] >= float(caps[i]) - tol
        )
        return DistrictResponse(
            plan=plan, targets=target_rates, weighted_output=z1,
            goal=request.weights, binding=binding,
        )

    def _floor_diagnosis(
        self, recipe_ids, caps, request: DistrictRequest, data: ReferenceData,
        floors: dict[str, float],
    ) -> Infeasible:
        """Name the floors, one at a time, then jointly. Never drops one."""
        if not floors:
            return Infeasible("no feasible district plan, and no floor is declared")
        alone: list[str] = []
        for item, floor in floors.items():
            p1 = self._build_core(recipe_ids, {item: 0.0}, caps, request.weights, data, {item: floor})
            try:
                self._run(np.zeros(p1.n_x + p1.n_s + p1.n_l), p1)
            except Infeasible:
                alone.append(f"{item} {floor:g}/min")
        if alone:
            return Infeasible(
                "declared floors unreachable under the caps even alone: "
                + ", ".join(alone)
                + ". The remaining floors were not tested jointly"
            )
        scale, binding = self._floor_scale(recipe_ids, caps, request, data, floors)
        return Infeasible(
            "declared floors are each reachable alone but not together: "
            + ", ".join(f"{i} {f:g}/min" for i, f in floors.items())
            + f". Scaled together they fit up to {scale:.4f} of the declared values"
            + (f"; the caps that bind there: {binding}" if binding else "")
            + " (v5.5 rule 1: a conflict with the compromise named, nothing dropped)"
        )

    def _floor_scale(
        self, recipe_ids, caps, request: DistrictRequest, data: ReferenceData,
        floors: dict[str, float],
    ) -> tuple[float, list[str]]:
        """The largest lambda in (0, 1) for which every floor * lambda fits,
        by bisection to 1e-4, and the caps the draw sits on at that lambda.
        A diagnostic only: it is not a plan and nothing reads it as one."""
        targets = {i: 0.0 for i in floors}

        def feasible(lam: float):
            p = self._build_core(
                recipe_ids, targets, caps, request.weights, data,
                {i: f * lam for i, f in floors.items()},
            )
            try:
                return p, self._run(np.zeros(p.n_x + p.n_s + p.n_l), p)
            except Infeasible:
                return p, None

        lo, hi = 0.0, 1.0
        best = feasible(lo)
        for _ in range(16):
            mid = (lo + hi) / 2.0
            p, res = feasible(mid)
            if res is None:
                hi = mid
            else:
                lo, best = mid, (p, res)
        p, res = best
        if res is None:
            return 0.0, []
        s = np.asarray(res.x, dtype=float)[p.n_x:p.n_x + p.n_s]
        binding = [
            i for i, val in zip(p.raw_ids, s)
            if caps.get(i) is not None and caps[i] > 0.0 and val >= caps[i] - self.tolerance
        ]
        return lo, binding

    # -- response ---------------------------------------------------------

    def _response(
        self, targets: dict[str, float], caps: tuple[ResourceCap, ...],
        data: ReferenceData, p: _Problem, v: np.ndarray, z: float, tie_broken: bool,
    ) -> SolveResponse:
        tol = self.tolerance
        x = v[:p.n_x]
        s = v[p.n_x:p.n_x + p.n_s]

        used = [(rid, float(val)) for rid, val in zip(p.recipe_ids, x) if val > tol]

        recipes = tuple(
            RecipeUse(
                recipe_id=rid,
                producer_class=data.recipes[rid].producer_class,
                machine_equivalents=val,
                cycles_per_min=60.0 / data.recipes[rid].duration_sec * val,
            )
            for rid, val in used
        )

        produced: dict[str, float] = {i: 0.0 for i in p.item_ids}
        consumed: dict[str, float] = {i: 0.0 for i in p.item_ids}
        for rid, val in used:
            r = data.recipes[rid]
            for item, rate in r.outputs:
                produced[item] += rate * val
            for item, rate in r.inputs:
                consumed[item] += rate * val
        # Raw draw counts as production so that `net_per_min` carries the meaning
        # section 7.5 gives it: net is leftover, not "unaccounted raw".
        for item, val in zip(p.raw_ids, s):
            produced[item] += float(val)

        items = tuple(
            ItemFlow(item_id=i, produced_per_min=produced[i], consumed_per_min=consumed[i])
            for i in p.item_ids
            if produced[i] > tol or consumed[i] > tol
        )
        # Leftovers are derived from the reported flows, not read off the slack
        # variable, so the warning and the ItemFlow tuple cannot disagree. The
        # slack carries the solver's noise; the filtered flows do not.
        net = {i: produced[i] - consumed[i] - targets.get(i, 0.0) for i in p.item_ids}

        raw_inputs = tuple(
            RawInput(item_id=i, rate_per_min=float(val))
            for i, val in zip(p.raw_ids, s) if val > tol
        )

        by_class: dict[str, float] = {}
        for rid, val in used:
            pc = data.recipes[rid].producer_class
            by_class[pc] = by_class.get(pc, 0.0) + val
        machines = tuple(
            MachineCount(
                producer_class=pc,
                effective_count=count,
                physical_count_if_rounded=math.ceil(count - tol),
            )
            for pc, count in sorted(by_class.items())
        )

        scenario_mw = sum(_statistic(data.recipes[rid], self.power_statistic) * val
                          for rid, val in used)
        min_mw = sum(data.recipes[rid].power.min_mw * val for rid, val in used)
        max_mw = sum(data.recipes[rid].power.max_mw * val for rid, val in used)
        multiplier = data.scenario.machine_power_multiplier
        power = PowerReport(
            canonical_mw=scenario_mw / multiplier,
            scenario_mw=scenario_mw,
            min_mw=min_mw,
            max_mw=max_mw,
        )

        return SolveResponse(
            recipes=recipes, items=items, raw_inputs=raw_inputs,
            power=power, machines=machines, backend=self.name,
            warnings=self._warnings(caps, data, p, x, s, net, z, tie_broken),
        )

    def _warnings(
        self, caps: tuple[ResourceCap, ...], data: ReferenceData, p: _Problem,
        x: np.ndarray, s: np.ndarray, net: dict[str, float], z: float, tie_broken: bool,
    ) -> tuple[str, ...]:
        tol = self.tolerance
        out = [
            "power excludes extraction: raw resources enter at the model boundary "
            "(production_lp_formulation.md D5)",
            "canonical_mw re-evaluates the selected recipe mix at canonical power; it is "
            "not a second solve at Scenario() (section 7.5, open)",
        ]

        if p.n_l:
            spare = sorted((i, val) for i, val in net.items() if val > REPORT_EPSILON)
            if spare:
                out.append(
                    "unconsumed output is free and unmodelled (D1 stopgap, blocked on P5): "
                    + ", ".join(f"{i} {val:.4f}/min" for i, val in spare)
                )

        binding = sorted(
            rid for rid, val in zip(p.recipe_ids, x)
            if val >= self.activity_upper_bound - tol
        )
        if binding:
            out.append(
                f"activity upper bound {self.activity_upper_bound:g} binds on {binding}; "
                "the answer is bounded by the guard, not by the model (section 5 mitigation 2)"
            )

        capped = sorted(
            i for i, val in zip(p.raw_ids, s)
            if any(c.item_id == i and c.rate_per_min is not None
                   and val >= c.rate_per_min - tol for c in caps)
        )
        if capped:
            out.append(f"resource cap binds on {capped}")

        inverse = self._inverse_pairs(p, x, data)
        if inverse:
            out.append(
                "both directions of an inverse recipe pair are active, the signature of a "
                f"spurious cycle (section 5 mitigation 3): {inverse}"
            )

        if tie_broken:
            out.append(
                f"degenerate optimum at objective {z:.6f}: several recipe sets tie and the "
                "tie was broken by minimising total activity (D3a)"
            )

        return tuple(out)

    @staticmethod
    def _inverse_pairs(p: _Problem, x: np.ndarray, data: ReferenceData) -> list[tuple[str, str]]:
        active = {rid for rid, val in zip(p.recipe_ids, x) if val > TOLERANCE}
        signature: dict[tuple[frozenset[str], frozenset[str]], list[str]] = {}
        for rid in sorted(active):
            r = data.recipes[rid]
            key = (frozenset(i for i, _ in r.inputs), frozenset(i for i, _ in r.outputs))
            signature.setdefault(key, []).append(rid)
        pairs: list[tuple[str, str]] = []
        for (ins, outs), ids in signature.items():
            mirror = signature.get((outs, ins))
            if mirror and ins != outs:
                for a in ids:
                    for b in mirror:
                        if a < b:
                            pairs.append((a, b))
        return sorted(set(pairs))


def register_default(power_statistic: PowerStatistic, **kwargs) -> LpBackend:
    """Put an `LpBackend` in the process registry. Never called on import."""
    from .backend import register

    backend = LpBackend(power_statistic, **kwargs)
    register(backend)
    return backend
