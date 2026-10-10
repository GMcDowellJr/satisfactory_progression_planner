"""Alternate sensitivity: dataset C of the plan (section 7C).

For one alternate, build the graph twice, the base table and the base table
plus one `AlternatePin`, expand every in-scope target under both, and report
every source x target whose coefficient changed, with both values, the
difference, and a ratio or "new" / "removed". Targets that one graph refuses
and the other resolves are listed, not folded into a number.

Three modes (plan section 6): single substitution is `sensitivity`; the
sweep over every alternate is `sweep`; an explicit configuration is any
`RouteTable` with several pins, compared with `compare`.

Never a score, a sort or a "best" (demand-expansion record §5.5, LP §16.2:
alternate value is set-valued). Rows are in id order; the reader orders by
looking.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from production_adapter.contracts import ItemId, RecipeId
from production_adapter.gamedata import RecipeUnlock, ReferenceData
from production_adapter.scenario import Scenario

from .contracts import (
    AmbiguousRoute, CycleDetected, DeclarationError, DemandExpansionError, RouteTable,
    UnproducibleItem,
)
from .expand import UNDECLARED, expand

_ROUTE_REFUSALS = (AmbiguousRoute, UnproducibleItem, CycleDetected)
from .graph import RecipeGraph, build, primary_output
from .report import config_id, in_scope_targets

SENSITIVITY_COLUMNS = (
    "config_id", "alternate_recipe_id", "alternate_name",
    "source_item_id", "source_name", "target_item_id", "target_name",
    "default", "default_exact", "alternate", "alternate_exact",
    "difference", "difference_exact", "change_kind", "ratio",
)
SUMMARY_COLUMNS = (
    "config_id", "alternate_recipe_id", "alternate_name", "item_id", "item_name",
    "unlock", "applicable", "reason", "pairs_changed", "targets_changed",
    "targets_newly_resolved", "targets_newly_refused",
)


@dataclass(frozen=True)
class Sensitivity:
    """One alternate against the base table. `rows` are dataset C rows."""

    config_id: str
    alternate_recipe_id: RecipeId
    alternate_name: str
    item_id: ItemId
    item_name: str
    unlock: str
    applicable: bool
    reason: str
    rows: tuple[dict, ...]
    targets_changed: tuple[ItemId, ...]
    targets_newly_resolved: tuple[ItemId, ...]
    targets_newly_refused: tuple[ItemId, ...]

    def summary_row(self) -> dict:
        return {
            "config_id": self.config_id,
            "alternate_recipe_id": self.alternate_recipe_id,
            "alternate_name": self.alternate_name,
            "item_id": self.item_id, "item_name": self.item_name,
            "unlock": self.unlock, "applicable": self.applicable, "reason": self.reason,
            "pairs_changed": len(self.rows),
            "targets_changed": len(self.targets_changed),
            "targets_newly_resolved": len(self.targets_newly_resolved),
            "targets_newly_refused": len(self.targets_newly_refused),
        }


def _name(data: ReferenceData, item_id: ItemId) -> str:
    item = data.items.get(item_id)
    return item.display_name if item else item_id


def _coefficients(graph: RecipeGraph, targets, scenario, fluid_rounding):
    """(source, target) -> per unit, over the targets that resolve; and the
    targets that did not."""
    coeff: dict[tuple[ItemId, ItemId], Fraction] = {}
    refused: set[ItemId] = set()
    for t in targets:
        try:
            e = expand(graph, t, scenario, fluid_rounding)
        except _ROUTE_REFUSALS:
            refused.add(t)
            continue
        for s, q in e.embedded.items():
            coeff[(s, t)] = q
    return coeff, refused


def compare(
    base: RecipeGraph,
    other: RecipeGraph,
    scenario: Scenario = Scenario(),
    fluid_rounding=UNDECLARED,
    label: tuple[RecipeId, str] = ("", ""),
) -> tuple[tuple[dict, ...], tuple[ItemId, ...], tuple[ItemId, ...], tuple[ItemId, ...]]:
    """Every source x target whose coefficient differs between two graphs
    over the same canonical data, plus the targets that changed, those the
    base refuses and `other` resolves, and the reverse."""
    if base.data is not other.data:
        raise DemandExpansionError("compare needs two graphs over the same ReferenceData")
    targets = sorted(set(in_scope_targets(base)) | set(in_scope_targets(other)))
    fluid_unit = scenario.fluid_rounding_unit if fluid_rounding is UNDECLARED else fluid_rounding
    cid = config_id(base.routes, scenario, fluid_unit)
    a, refused_a = _coefficients(base, targets, scenario, fluid_rounding)
    b, refused_b = _coefficients(other, targets, scenario, fluid_rounding)
    data = base.data
    rows: list[dict] = []
    changed: set[ItemId] = set()
    for key in sorted(set(a) | set(b)):
        source, target = key
        if target in refused_a or target in refused_b:
            continue   # listed below, not folded into a difference
        x, y = a.get(key, Fraction(0)), b.get(key, Fraction(0))
        if x == y:
            continue
        changed.add(target)
        if x > 0 and y > 0:
            kind, ratio = "ratio", float(y / x)
        elif x == 0:
            kind, ratio = "new", ""
        else:
            kind, ratio = "removed", ""
        rows.append({
            "config_id": cid,
            "alternate_recipe_id": label[0], "alternate_name": label[1],
            "source_item_id": source, "source_name": _name(data, source),
            "target_item_id": target, "target_name": _name(data, target),
            "default": float(x), "default_exact": str(x),
            "alternate": float(y), "alternate_exact": str(y),
            "difference": float(y - x), "difference_exact": str(y - x),
            "change_kind": kind, "ratio": ratio,
        })
    return (
        tuple(rows),
        tuple(sorted(changed)),
        tuple(sorted(refused_a - refused_b)),
        tuple(sorted(refused_b - refused_a)),
    )


def _unlock_text(unlocks: dict[RecipeId, tuple[RecipeUnlock, ...]] | None, rid: RecipeId) -> str:
    if not unlocks or rid not in unlocks:
        return ""
    return "; ".join(f"T{u.tech_tier} {u.display_name}" for u in unlocks[rid])


def sensitivity(
    data: ReferenceData,
    routes: RouteTable,
    recipe_id: RecipeId,
    scenario: Scenario = Scenario(),
    fluid_rounding=UNDECLARED,
    unlocks: dict[RecipeId, tuple[RecipeUnlock, ...]] | None = None,
    base: RecipeGraph | None = None,
) -> Sensitivity:
    """One alternate substituted into `routes`. Inapplicable alternates (a
    resource or unlisted primary output, a conflict with a base pin, a
    recipe the data does not flag alternate) are returned with
    `applicable=False` and the reason, never skipped silently."""
    r = data.recipes.get(recipe_id)
    if r is None:
        raise DemandExpansionError(f"{recipe_id} is not in the reference layer")
    base = base or build(data, routes)
    fluid_unit = scenario.fluid_rounding_unit if fluid_rounding is UNDECLARED else fluid_rounding
    cid = config_id(routes, scenario, fluid_unit)
    item = primary_output(r)
    common = dict(
        config_id=cid, alternate_recipe_id=recipe_id, alternate_name=r.display_name,
        item_id=item, item_name=_name(data, item), unlock=_unlock_text(unlocks, recipe_id),
    )
    try:
        if item not in data.items:
            raise DeclarationError(f"primary output {item} is not listed in items.csv")
        other = build(data, routes.with_alternate(item, recipe_id, "single substitution"))
    except DeclarationError as err:
        return Sensitivity(**common, applicable=False, reason=str(err), rows=(),
                           targets_changed=(), targets_newly_resolved=(), targets_newly_refused=())
    rows, changed, resolved, refused = compare(
        base, other, scenario, fluid_rounding, label=(recipe_id, r.display_name)
    )
    return Sensitivity(**common, applicable=True, reason="", rows=rows,
                       targets_changed=changed, targets_newly_resolved=resolved,
                       targets_newly_refused=refused)


def sweep(
    data: ReferenceData,
    routes: RouteTable,
    scenario: Scenario = Scenario(),
    fluid_rounding=UNDECLARED,
    unlocks: dict[RecipeId, tuple[RecipeUnlock, ...]] | None = None,
) -> tuple[Sensitivity, ...]:
    """Single substitution of every alternate in the data, in recipe-id
    order. No ordering by effect."""
    base = build(data, routes)
    return tuple(
        sensitivity(data, routes, rid, scenario, fluid_rounding, unlocks, base=base)
        for rid in sorted(data.recipes)
        if data.recipes[rid].is_alternate
    )
