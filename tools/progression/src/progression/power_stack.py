"""The staged generation ledger: generators by class, in the order obtained.

Site-planner reframe A18, decided by Greg 2026-11-17. It answers A16.3's
P1–P3:

    P1   "generator order in order obtained per tier/phase": one stack, and
         each class joins it when its milestone is owned. The order comes
         from the data: the tech tier of the schematic that unlocks the
         generator's build recipe (Biomass Burner with HUB Upgrade 6, tier 0;
         Coal Power, 3; Petroleum Power, 5; Nuclear Power, 8)
    P2   "backup means if power demand spikes above what coal or other
         provides the bioburners turn [on and] produce power to compensate up
         to its max before the power grid turns off"
    P3   "leaves/wood gathered by hand - converted to biomass then biofuel
         through constructors"

Claude's reading, which Greg may reverse (A18.2): the class obtained LAST
carries the load (primary), sized to the need in whole units. Every earlier
class is backup: it is built (its standing units are declared, the ones left
from earlier phases), idle at steady state, and its capacity is the spike
headroom above the primary before the grid trips.

What it reports, choosing nothing:

    primary   units = the need over one unit's MW, rounded up; the feed rate of
              each fuel that class burns, at the need, with its Water. Every
              fuel is listed and none is chosen
    backup    declared standing units, their headroom in MW, each fuel's feed
              at full output
    biomass   for Solid Biofuel, the hand-gathered chain per source: Leaves or
              Wood per minute, Biomass and Biofuel constructors, and their
              P-scaled draw. The chain's own power is NOT added back to the
              need; the report names it (A11.5)

A report. It does not reduce the plan's own power need (A18: "let's not have
it reduce the plans own power need"), and it checks no fuel supply against
the factory's caps.
"""
from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass

from production_adapter.contracts import ItemId, ProducerClass, RecipeId
from production_adapter.gamedata import (
    ReferenceData, load_building_recipe_rows, load_generators, load_schematic_rows,
    load_schematic_unlock_rows,
)

from .playthrough import PlaythroughState
from .unlocks import buildings_unlocked

PRIMARY = "primary"
BACKUP = "backup"

BIOMASS_BURNER = "Build_GeneratorBiomass_Automated_C"
SOLID_BIOFUEL = "Desc_Biofuel_C"
BIOMASS = "Desc_GenericBiomass_C"
#: A18 P3: what is gathered by hand, and the constructor recipe that makes
#: Biomass from it; then Recipe_Biofuel_C makes Solid Biofuel from Biomass.
HAND_GATHERED: dict[ItemId, RecipeId] = {
    "Desc_Leaves_C": "Recipe_Biomass_Leaves_C",
    "Desc_Wood_C": "Recipe_Biomass_Wood_C",
}
BIOFUEL_RECIPE = "Recipe_Biofuel_C"

_EPS = 1e-9


class PowerStackError(ValueError):
    """The stack cannot be stated without guessing."""


@dataclass(frozen=True)
class FuelFeed:
    fuel_item_id: ItemId
    per_min: float
    supplemental: tuple[tuple[ItemId, float], ...]


@dataclass(frozen=True)
class BiofuelChain:
    source_item_id: ItemId          # gathered by hand
    by_hand_per_min: float
    biomass_constructors: float
    biofuel_constructors: float
    constructor_mw: float           # P-scaled; not added to the need
    owned: bool                     # both recipes owned in this state


@dataclass(frozen=True)
class StackLine:
    generator_class: ProducerClass
    obtained_with: str              # the schematic's display name
    obtained_tier: int
    role: str                       # PRIMARY | BACKUP
    units: float                    # primary: whole units built; backup: declared standing
    unit_mw: float
    output_mw: float                # primary: the need it carries; backup: its full headroom
    feeds: tuple[FuelFeed, ...]
    biofuel: tuple[BiofuelChain, ...] = ()


@dataclass(frozen=True)
class PowerStack:
    need_mw: float
    lines: tuple[StackLine, ...]    # in the order obtained

    @property
    def headroom_mw(self) -> float:
        """Above the need, before the grid trips: the primary's spare from
        whole units plus every backup's full output."""
        primary = next(l for l in self.lines if l.role == PRIMARY)
        spare = primary.units * primary.unit_mw - self.need_mw
        return spare + sum(l.output_mw for l in self.lines if l.role == BACKUP)


def generators_in_order_obtained(
    repo_root: str | pathlib.Path, state: PlaythroughState,
) -> tuple[tuple[ProducerClass, str, int], ...]:
    """(class, unlocking schematic's name, its tier) for every generator the
    state owns, in the order obtained (tier, then schematic id)."""
    owned = state.owned_schematics
    open_buildings, _ = buildings_unlocked(repo_root, lambda s: s.schematic_id in owned)
    schematics = {s.schematic_id: s for s in load_schematic_rows(repo_root)}
    unlocks: dict[RecipeId, list[str]] = {}
    for u in load_schematic_unlock_rows(repo_root):
        unlocks.setdefault(u.recipe_id, []).append(u.schematic_id)
    built_by = {b.building_class: b.recipe_id for b in load_building_recipe_rows(repo_root)}
    out = []
    for cls in dict.fromkeys(g.generator_class for g in load_generators(repo_root)):
        desc = "Desc_" + cls[len("Build_"):]
        if desc not in open_buildings:
            continue
        granting = [schematics[s] for s in unlocks.get(built_by[desc], ()) if s in owned]
        first = min(granting, key=lambda s: (s.tech_tier, s.schematic_id))
        out.append((cls, first.display_name, first.tech_tier))
    return tuple(sorted(out, key=lambda t: (t[2], t[1])))


def power_stack(
    repo_root: str | pathlib.Path,
    data: ReferenceData,
    state: PlaythroughState,
    need_mw: float,
    owned_recipes: tuple[RecipeId, ...],
    standing: dict[ProducerClass, int] | None = None,
) -> PowerStack:
    """`need_mw` is the plan's need (P-scaled). `standing` declares the backup
    units already built, by class; a class not named has none standing."""
    if not need_mw >= 0:
        raise PowerStackError(f"need_mw must be non-negative, got {need_mw!r}")
    standing = dict(standing or {})
    bad = sorted(c for c, n in standing.items()
                 if not isinstance(n, int) or isinstance(n, bool) or n < 0)
    if bad:
        raise PowerStackError(f"standing units must be non-negative integers: {bad}")
    order = generators_in_order_obtained(repo_root, state)
    if not order:
        raise PowerStackError("no generator is unlocked in this playthrough state")
    known = {cls for cls, _, _ in order}
    stray = sorted(set(standing) - known)
    if stray:
        raise PowerStackError(f"standing generators not unlocked in this state: {stray}")
    rows = load_generators(repo_root)
    owned = frozenset(owned_recipes)
    primary_cls = order[-1][0]
    lines = []
    for cls, name, tier in order:
        fuels = [g for g in rows if g.generator_class == cls]
        unit_mw = fuels[0].power_mw
        if cls == primary_cls:
            role, units, output = PRIMARY, float(math.ceil(need_mw / unit_mw - _EPS)), need_mw
        else:
            n = standing.get(cls, 0)
            role, units, output = BACKUP, float(n), n * unit_mw
        load = output / unit_mw                          # generator-equivalents at 100 %
        feeds = tuple(FuelFeed(g.fuel_item_id, load * g.burn_rate_per_min,
                               tuple((i, load * r) for i, r in g.supplemental))
                      for g in fuels)
        chains = ()
        if cls == BIOMASS_BURNER:
            biofuel = next((f.per_min for f in feeds if f.fuel_item_id == SOLID_BIOFUEL), None)
            if biofuel is not None:
                chains = _biofuel_chains(data, biofuel, owned)
        lines.append(StackLine(cls, name, tier, role, units, unit_mw, output, feeds, chains))
    return PowerStack(need_mw, tuple(lines))


def _biofuel_chains(data: ReferenceData, biofuel_per_min: float,
                    owned: frozenset) -> tuple[BiofuelChain, ...]:
    bf = data.recipes[BIOFUEL_RECIPE]
    biofuel_constructors = biofuel_per_min / dict(bf.outputs)[SOLID_BIOFUEL]
    biomass_per_min = biofuel_constructors * dict(bf.inputs)[BIOMASS]
    out = []
    for source, rid in HAND_GATHERED.items():
        r = data.recipes[rid]
        biomass_constructors = biomass_per_min / dict(r.outputs)[BIOMASS]
        out.append(BiofuelChain(
            source_item_id=source,
            by_hand_per_min=biomass_constructors * dict(r.inputs)[source],
            biomass_constructors=biomass_constructors,
            biofuel_constructors=biofuel_constructors,
            constructor_mw=biomass_constructors * r.power.mean_mw
            + biofuel_constructors * bf.power.mean_mw,
            owned=rid in owned and BIOFUEL_RECIPE in owned,
        ))
    return tuple(out)


def report_lines(stack: PowerStack) -> list[str]:
    lines = [f"  power stack (order obtained), need {stack.need_mw:.4g} MW, headroom "
             f"{stack.headroom_mw:.4g} MW before the grid trips:"]
    for l in stack.lines:
        what = (f"{l.units:g} x {l.generator_class} carry {l.output_mw:.4g} MW"
                if l.role == PRIMARY else
                f"{l.units:g} x {l.generator_class} standing, up to {l.output_mw:.4g} MW on a spike")
        lines.append(f"    {l.role} ({l.obtained_with}, tier {l.obtained_tier}): {what}")
        for f in l.feeds:
            sup = "".join(f", {r:.4g} {i}/min" for i, r in f.supplemental)
            lines.append(f"      {f.fuel_item_id}: {f.per_min:.4g}/min{sup}")
        for c in l.biofuel:
            flag = "" if c.owned else " (recipes not owned yet)"
            lines.append(f"      by hand: {c.by_hand_per_min:.4g} {c.source_item_id}/min -> "
                         f"{c.biomass_constructors:.3g} + {c.biofuel_constructors:.3g} constructors, "
                         f"{c.constructor_mw:.3g} MW (not added to the need){flag}")
    return lines
