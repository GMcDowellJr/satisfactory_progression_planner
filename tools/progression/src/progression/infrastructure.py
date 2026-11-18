"""Extractor and belt marks: the highest available, stepped down where it does not help.

Site-planner reframe A15.2, decided by Greg 2026-11-17. Reconciliation R6.

    B2   "if the goal is to maximize supply we'd want to use the highest mk
         miner/belt available at the time and work backwards using lower
         marks if the higher aren't helpful"
    Q1   "not helpful": the same delivered rate at lower power; for belts,
         "if product leading a set of machines is less than 60/min use a mk1
         belt instead of the mk2". Build cost is not a criterion.

So the policy has two halves, and it is a NAMED policy a caller declares
(`HIGHEST_THEN_STEP_DOWN`), never a silent default:

    supply      each socket's cap is read at the highest extractor mark the
                playthrough has (`highest_extractor`): that is the most the
                site can carry
    realize     once a plan says what each socket actually draws, each socket
                steps down to the lowest mark that carries that draw at no
                more power (`step_down_extractor`); each lane takes the lowest
                belt that carries its flow (`belt_for`)

What is "available" comes from `progression.availability` (milestones owned),
never from a phase index (the flaw the 2026-11-17 audit found in the external
prototype and in research/step_planner). Marks are ordered by CAPACITY, never by
parsing "Mk.3".

Power is compared as the solve charges it (reframe A4): base MW (scenario-
scaled, A7) / nominal rate x draw, linear in the draw at or below 100 % clock.
The game's clock curve (exponent 1.321929) sits below that line, so the
comparison is floor-safe; it is not re-derived here.

`belt_for` restates `realization.capabilities.minimum_sufficient`'s floor rule
(lowest capacity that carries the rate) over the milestone-filtered marks. It
cannot import it: progression may not import realization outside `stock`
(tests/test_progression_import_boundary.py).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from production_adapter.contracts import ItemId, ProducerClass
from production_adapter.gamedata import Capability, ExtractionRate, load_extraction_map_rows
from production_adapter.scenario import Scenario

from .availability import Availability

HIGHEST_THEN_STEP_DOWN = "highest_then_step_down"
POLICIES = (HIGHEST_THEN_STEP_DOWN,)

_EPS = 1e-9


class InfrastructureError(ValueError):
    """A mark cannot be chosen without guessing."""


@dataclass(frozen=True)
class ExtractorOption:
    extractor_class: ProducerClass
    nominal_rate_min: float   # at this socket's purity, 100 % clock
    mw: float                 # scenario-scaled base power at 100 %

    def mw_at(self, draw: float) -> float:
        return self.mw * draw / self.nominal_rate_min


def extractor_options(
    availability: Availability,
    item_id: ItemId,
    purity: str,
    rates: tuple[ExtractionRate, ...],
    base_mw: dict[ProducerClass, float],
    scenario: Scenario,
    *,
    repo_root=None,
    activated: bool | None = None,
) -> tuple[ExtractorOption, ...]:
    """The extractors the playthrough can build for this socket, lowest
    capacity first. Refuses when none is open, or when an open class has no
    (class, purity) rate row or no base power.

    `activated` restricts to one socket kind's family, from
    resource_extraction_map.csv's `requires_activator`: True for a resource
    well satellite (its extractor needs a pressurizer), False for a node.
    Without it, Crude Oil's Oil Extractor and Resource Well Extractor would be
    ranked against each other, and "highest" would name an extractor the
    socket cannot take. Needs `repo_root`. None: no restriction."""
    classes = availability.extractors.get(item_id, ())
    if activated is not None:
        if repo_root is None:
            raise InfrastructureError("activated= needs repo_root to read the extraction map")
        family = {r.extractor_class for r in load_extraction_map_rows(repo_root)
                  if r.item_id == item_id and bool(r.requires_activator) == activated}
        classes = tuple(c for c in classes if c in family)
    if not classes:
        raise InfrastructureError(f"{item_id}: no extractor is unlocked in this playthrough state"
                                  + ("" if activated is None else
                                     f" for a {'well' if activated else 'node'} socket"))
    out = []
    for cls in classes:
        hits = [r for r in rates if r.extractor_class == cls and r.purity == purity]
        if len(hits) != 1:
            raise InfrastructureError(
                f"{cls} on {purity}: {len(hits)} rows in extraction_rates.csv; one is required")
        if cls not in base_mw:
            raise InfrastructureError(f"{cls}: no base power in extraction_buildings.csv")
        out.append(ExtractorOption(cls, hits[0].nominal_rate_min, scenario.apply_power(base_mw[cls])))
    return tuple(sorted(out, key=lambda o: o.nominal_rate_min))


def highest_extractor(options: tuple[ExtractorOption, ...]) -> ExtractorOption:
    """The supply half: the most a socket can carry with what is unlocked."""
    if not options:
        raise InfrastructureError("no extractor options")
    return options[-1]


@dataclass(frozen=True)
class MarkChoice:
    """One socket's extractor, from the highest available to the one kept."""

    key: str                       # the socket id (or a node label)
    item_id: ItemId
    purity: str
    draw_per_min: float
    highest: ExtractorOption
    chosen: ExtractorOption | None   # None: the plan draws nothing here; build nothing
    reason: str

    @property
    def stepped_down(self) -> bool:
        return self.chosen is not None and self.chosen != self.highest

    @property
    def mw_saved(self) -> float:
        if self.chosen is None:
            return self.highest.mw_at(self.draw_per_min)
        return self.highest.mw_at(self.draw_per_min) - self.chosen.mw_at(self.draw_per_min)


def step_down_extractor(
    key: str, item_id: ItemId, purity: str, draw_per_min: float,
    options: tuple[ExtractorOption, ...],
) -> MarkChoice:
    """The realize half (Q1): the lowest mark that carries the draw at no more
    power than the highest would. A draw above the highest mark's rate is
    refused: the plan exceeded the socket's cap, which is a defect upstream."""
    top = highest_extractor(options)
    if draw_per_min < -_EPS:
        raise InfrastructureError(f"{key}: negative draw {draw_per_min}")
    if draw_per_min > top.nominal_rate_min + _EPS:
        raise InfrastructureError(
            f"{key}: draw {draw_per_min:g}/min exceeds {top.extractor_class}'s "
            f"{top.nominal_rate_min:g}/min on {purity}; the plan exceeded the socket's cap")
    if draw_per_min <= _EPS:
        return MarkChoice(key, item_id, purity, 0.0, top, None, "not drawn: no extractor needed")
    for option in options:   # lowest capacity first
        if (option.nominal_rate_min + _EPS >= draw_per_min
                and option.mw_at(draw_per_min) <= top.mw_at(draw_per_min) + _EPS):
            reason = ("the highest mark is needed" if option == top else
                      f"{option.extractor_class} carries {draw_per_min:g}/min at "
                      f"{option.mw_at(draw_per_min):.3g} MW against "
                      f"{top.mw_at(draw_per_min):.3g} MW on {top.extractor_class}")
            return MarkChoice(key, item_id, purity, draw_per_min, top, option, reason)
    return MarkChoice(key, item_id, purity, draw_per_min, top, top, "the highest mark is needed")


@dataclass(frozen=True)
class BeltChoice:
    flow_per_min: float
    lanes: int
    mark: Capability          # the mark each lane uses
    highest: Capability       # the highest the playthrough has

    @property
    def stepped_down(self) -> bool:
        return self.mark != self.highest


def belt_for(
    flow_per_min: float, availability: Availability, capability_type: str = "belt",
) -> BeltChoice:
    """Q1 for a lane: the lowest available mark that carries the flow ("less
    than 60/min: Mk.1, not Mk.2"). Past the highest mark the flow needs more
    than one lane: the lane count is what the HIGHEST mark needs (fewest
    lanes), and each lane then takes the lowest mark that carries its even
    share. `capability_type` "pipeline" applies the same rule to fluids."""
    marks = availability.capabilities(capability_type)
    if not marks:
        raise InfrastructureError(f"no {capability_type} is unlocked in this playthrough state")
    if not flow_per_min > 0:
        raise InfrastructureError(f"a {capability_type} flow must be positive, got {flow_per_min!r}")
    top = marks[-1]
    lanes = max(1, math.ceil(flow_per_min / top.capacity_per_min - _EPS))
    share = flow_per_min / lanes
    mark = next(m for m in marks if m.capacity_per_min + _EPS >= share)
    return BeltChoice(flow_per_min, lanes, mark, top)
