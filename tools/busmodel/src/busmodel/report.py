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
            # Mirrors `solve`'s branch deliberately, and is not simplified:
            # under AVERAGE a WITHDRAWN bus draws its nameplate on its
            # out-of-scope inputs exactly as it does on its declared ones, and
            # under USAGE nothing does. `presents_peak_draw` is gone from both
            # sides as of 2026-09-22 (A5.2), so there is no per-bus override to
            # consult here either.
            if (
                solution.sizing_basis is SizingBasis.AVERAGE
                and b.disposition is Disposition.WITHDRAWN
            ):
                flow = b.machines * per_min
            elif solution.sizing_basis is SizingBasis.STORAGE and spec.stores:
                # A12: a storing line draws what it produces, on its
                # out-of-scope inputs as on its declared ones.
                flow = b.supply_per_min * per_min / (b.rate_per_min or 1.0)
            else:
                flow = b.demand_per_min * per_min / (b.rate_per_min or 1.0)
            draw[item_id] = draw.get(item_id, 0.0) + flow
    return draw


#: The last two columns are the REPORT the peak was demoted to (A6.4). They are
#: rendered on every basis, because the peak is computed on every basis and a
#: figure that only appears under one mode is a figure nobody reads.
_HEAD = (
    f'  {"bus":22s}{"rate":>8s}{"ext":>8s}{"auto":>9s}{"withdr":>8s}'
    f'{"demand":>9s}{"cont":>8s}{"mach":>6s}{"clock":>7s}{"supply":>9s}{"R/min":>9s}'
    f'{"peak":>9s}{"short":>8s}  state'
)


def render(solution: Solution, *, title: str | None = None) -> str:
    lines = ["=" * 127, title or solution.declaration_name,
             f"  basis {solution.sizing_basis.value}, machine floor {solution.machine_floor}",
             _HEAD]
    for b in sorted(solution.buses, key=lambda x: -x.residual_per_min):
        lines.append(
            f"  {b.bus_id:22s}{b.rate_per_min:8.2f}{b.external_per_min:8.2f}"
            f"{b.automated_demand_per_min:9.2f}{b.withdrawal_per_min:8.2f}"
            f"{b.demand_per_min:9.2f}{b.continuous_machines:8.2f}{b.machines:6d}"
            f"{b.clock_percent:7.1f}{b.supply_per_min:9.2f}{b.residual_per_min:9.2f}"
            f"{b.peak_demand_per_min:9.2f}{b.peak_shortfall_per_min:8.2f}"
            f"  {b.disposition.value}"
        )
    lines.append(
        f"  TOTAL MACHINES {solution.total_machines}"
        f"   continuous {solution.total_continuous_machines:.2f}"
        f"   integrality tax {solution.integrality_tax:.2f}"
    )
    # A12 (D1): REPORTED, never acted on. Remedy — overclock, somersloop, or
    # add a machine — is the player's, so none is named per line.
    empty = [b.bus_id for b in solution.buses if b.stores_nothing]
    if empty:
        lines.append(f"  storing, nothing to store: {', '.join(empty)}")
    return "\n".join(lines)


def render_out_of_scope(draw: Mapping[ItemId, float], data: ReferenceData) -> str:
    lines = ["  out-of-scope draw"]
    for item_id, rate in sorted(draw.items(), key=lambda kv: -kv[1]):
        name = data.items[item_id].display_name if item_id in data.items else item_id
        lines.append(f"    {name:26s}{rate:9.2f}/min")
    return "\n".join(lines)
