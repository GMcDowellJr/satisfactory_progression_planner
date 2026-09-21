"""Rendering and the out-of-scope draw roll-up. No arithmetic that decides anything."""
from __future__ import annotations

from typing import Mapping

from production_adapter.contracts import ItemId
from production_adapter.gamedata import ReferenceData
from realization.contracts import Disposition

from .model import Declaration, SizingBasis, Solution


def out_of_scope_draw(
    decl: Declaration, data: ReferenceData, solution: Solution
) -> dict[ItemId, float]:
    """Draw on items no declared bus carries -- raw ore, and anything left out.

    Storage review section 7 quotes iron ingot and copper ingot draws for a
    declaration that has no ingot bus, so this is a reported quantity and not a
    solved one. It is computed on the same basis as the bus's own draw, which is
    the point: an out-of-scope figure on a different basis from the in-scope
    ones is the section 6.1 defect in a new place.
    """
    specs = {b.bus_id: b for b in decl.buses}
    draw: dict[ItemId, float] = {}
    for b in solution.buses:
        spec = specs[b.bus_id]
        recipe = data.recipes[spec.recipe_id]
        for item_id, per_min in recipe.inputs:
            if spec.source_of(item_id) is not None:
                continue
            peak = spec.presents_peak_draw
            if peak is None:
                peak = solution.sizing_basis is SizingBasis.PEAK
            if b.disposition is Disposition.WITHDRAWN or peak:
                flow = b.machines * per_min
            else:
                flow = b.demand_per_min * per_min / (b.rate_per_min or 1.0)
            draw[item_id] = draw.get(item_id, 0.0) + flow
    return draw


_HEAD = (
    f'  {"bus":22s}{"rate":>8s}{"ext":>8s}{"auto":>9s}{"withdr":>8s}'
    f'{"demand":>9s}{"cont":>8s}{"mach":>6s}{"clock":>7s}{"supply":>9s}{"R/min":>9s}  state'
)


def render(solution: Solution, *, title: str | None = None) -> str:
    lines = ["=" * 110, title or solution.declaration_name,
             f"  basis {solution.sizing_basis.value}, machine floor {solution.machine_floor}",
             _HEAD]
    for b in sorted(solution.buses, key=lambda x: -x.residual_per_min):
        lines.append(
            f"  {b.bus_id:22s}{b.rate_per_min:8.2f}{b.external_per_min:8.2f}"
            f"{b.automated_demand_per_min:9.2f}{b.withdrawal_per_min:8.2f}"
            f"{b.demand_per_min:9.2f}{b.continuous_machines:8.2f}{b.machines:6d}"
            f"{b.clock_percent:7.1f}{b.supply_per_min:9.2f}{b.residual_per_min:9.2f}"
            f"  {b.disposition.value}"
        )
    lines.append(
        f"  TOTAL MACHINES {solution.total_machines}"
        f"   continuous {solution.total_continuous_machines:.2f}"
        f"   integrality tax {solution.integrality_tax:.2f}"
    )
    return "\n".join(lines)


def render_out_of_scope(draw: Mapping[ItemId, float], data: ReferenceData) -> str:
    lines = ["  out-of-scope draw"]
    for item_id, rate in sorted(draw.items(), key=lambda kv: -kv[1]):
        name = data.items[item_id].display_name if item_id in data.items else item_id
        lines.append(f"    {name:26s}{rate:9.2f}/min")
    return "\n".join(lines)
