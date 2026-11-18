"""The staged generation ledger: generators by class, in the order obtained.

Site-planner reframe A18 and A19, decided by Greg 2026-11-17.

    P1   "generator order in order obtained per tier/phase": each class joins
         when its milestone is owned. The order comes from the data: the tech
         tier of the schematic that unlocks the generator's build recipe
         (Biomass Burner with HUB Upgrade 6, tier 0; Coal Power, 3; Petroleum
         Power, 5; Nuclear Power, 8)
    P2   "backup means if power demand spikes above what coal or other
         provides the bioburners turn [on and] produce power to compensate up
         to its max before the power grid turns off"
    P3   "leaves/wood gathered by hand - converted to biomass then biofuel
         through constructors"
    A19  "power generation continues into future phases - bioburners act as
         backup because they only burn fuel/generate power when needed";
         "reported how many of each type would be required by way of
         demonstrating needs and a separate ratio system for how to supply
         the power"

So the report has two parts, and chooses nothing:

    alone    every owned class covering the whole need by itself: units and
             each fuel's feed. It demonstrates the need
    supply   how the need is met:
               standing   generators built in earlier phases keep running and
                          carry load first, in the order obtained
               backup     Biomass Burners, once any other class is owned: built,
                          idle at steady state, their full output is spike
                          headroom. While they are the only class they carry
                          the load
               new        what is left is carried by the declared generation
                          mix (class -> share, shares summing to 1), or, with
                          no mix declared, by the class obtained last. New
                          units are whole: ceil(the load not covered by that
                          class's standing units / unit MW)

The Biomass Burner's Solid Biofuel gets the hand-gathered chain per source
(Leaves, Wood): by hand per minute, Biomass and Biofuel constructors, and
their P-scaled draw. That draw is NOT added to the need (A18: disposal and
power never reduce or inflate the plan's own need; the chain is named, A11.5).

`supply_check` (A19, Greg: "power stack should check supply if intent of
factory is fuel") states, for every line carrying load, whether each of its
fuels (and their supplemental fluids) is there at the feed. What is "there"
is the caller's: the factory track passes the site's leftovers when the
factory is DECLARED a power site. The intent is declared, never inferred from
the resources: coal with water is "typically" power and coal with iron
"typically" steel, and oil "almost always" includes power "unless specifically
excluded or not needed": typical, not a rule.
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

PRIMARY = "primary"      # the class obtained last, carrying what standing units leave
STANDING = "standing"    # built in an earlier phase, still running
MIX = "mix"              # carrying its declared share of what standing units leave
BACKUP = "backup"        # Biomass Burners once another class is owned
IDLE = "idle"            # owned, nothing standing, no share: built nothing

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

# supply_check statuses
COVERED = "covered"      # the site has at least the feed left over
SHORT = "short"          # it has less (possibly none)
PUMPED = "pumped"        # Water: from Water Extractors beside the generators
NO_PUMP = "no_water_extractor"   # Water, and no Water Extractor is owned
BY_HAND = "by_hand"      # a Biomass Burner fuel the site does not make: gathered
CARRIES_LOAD = (PRIMARY, STANDING, MIX)


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
class AloneLine:
    """One class covering the whole need by itself (A19: demonstrates the need)."""

    generator_class: ProducerClass
    units: float
    unit_mw: float
    feeds: tuple[FuelFeed, ...]


@dataclass(frozen=True)
class StackLine:
    generator_class: ProducerClass
    obtained_with: str              # the schematic's display name
    obtained_tier: int
    role: str                       # PRIMARY | STANDING | MIX | BACKUP | IDLE
    standing_units: float           # declared, built in earlier phases
    new_units: float                # whole units this plan adds
    unit_mw: float
    load_mw: float                  # what it carries at steady state (backup: 0)
    feeds: tuple[FuelFeed, ...]     # at load (backup: at its full output, on a spike)
    biofuel: tuple[BiofuelChain, ...] = ()

    @property
    def capacity_mw(self) -> float:
        return (self.standing_units + self.new_units) * self.unit_mw


@dataclass(frozen=True)
class PowerStack:
    need_mw: float
    lines: tuple[StackLine, ...]    # in the order obtained
    alone: tuple[AloneLine, ...]    # in the order obtained
    mix: tuple[tuple[ProducerClass, float], ...] = ()

    @property
    def headroom_mw(self) -> float:
        """Above the need, before the grid trips: every running class's spare
        capacity plus every backup's full output."""
        return sum(l.capacity_mw for l in self.lines) - self.need_mw


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
    mix: dict[ProducerClass, float] | None = None,
) -> PowerStack:
    """`need_mw` is the plan's need (P-scaled). `standing` declares the units
    already built, by class (a class not named has none). `mix` optionally
    declares how what standing units leave is shared (class -> share, summing
    to 1); without it the class obtained last carries it."""
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
    known = [cls for cls, _, _ in order]
    stray = sorted(set(standing) - set(known))
    if stray:
        raise PowerStackError(f"standing generators not unlocked in this state: {stray}")
    mix = dict(mix or {})
    if mix:
        unknown = sorted(set(mix) - set(known))
        if unknown:
            raise PowerStackError(f"generation mix names classes not unlocked: {unknown}")
        if any(not v > 0 for v in mix.values()):
            raise PowerStackError("generation mix shares must be positive")
        if abs(sum(mix.values()) - 1.0) > 1e-9:
            raise PowerStackError(f"generation mix shares sum to {sum(mix.values()):g}, not 1")

    rows = load_generators(repo_root)
    owned = frozenset(owned_recipes)
    unit_mw = {cls: next(g.power_mw for g in rows if g.generator_class == cls) for cls in known}
    only_biomass = known == [BIOMASS_BURNER]

    def is_backup(cls):
        return cls == BIOMASS_BURNER and not only_biomass and cls not in mix

    # standing units run first, in the order obtained (A19); backups idle
    load: dict[ProducerClass, float] = {cls: 0.0 for cls in known}
    left = need_mw
    for cls in known:
        if is_backup(cls):
            continue
        take = min(standing.get(cls, 0) * unit_mw[cls], left)
        load[cls] += take
        left -= take
    # what standing units leave: the declared mix, else the class obtained last
    shares = mix or {known[-1]: 1.0}
    for cls, share in shares.items():
        load[cls] += left * share

    lines = []
    for cls, name, tier in order:
        n_standing = standing.get(cls, 0)
        uncovered = max(0.0, load[cls] - n_standing * unit_mw[cls])
        new = float(math.ceil(uncovered / unit_mw[cls] - _EPS)) if uncovered > _EPS else 0.0
        if is_backup(cls):
            role, at = BACKUP, n_standing * unit_mw[cls]
        elif mix and cls in mix:
            role, at = MIX, load[cls]
        elif not mix and cls == known[-1]:
            role, at = PRIMARY, load[cls]
        elif load[cls] > _EPS:
            role, at = STANDING, load[cls]
        else:
            role, at = IDLE, 0.0
        feeds = _feeds(rows, cls, at)
        chains = _chains(data, cls, feeds, owned)
        lines.append(StackLine(cls, name, tier, role, float(n_standing), new, unit_mw[cls],
                               0.0 if role == BACKUP else load[cls], feeds, chains))
    alone = tuple(AloneLine(cls, float(math.ceil(need_mw / unit_mw[cls] - _EPS)), unit_mw[cls],
                            _feeds(rows, cls, need_mw)) for cls in known)
    return PowerStack(need_mw, tuple(lines), alone, tuple(mix.items()))


def _feeds(rows, cls: ProducerClass, mw: float) -> tuple[FuelFeed, ...]:
    fuels = [g for g in rows if g.generator_class == cls]
    units = mw / fuels[0].power_mw                       # generator-equivalents at 100 %
    return tuple(FuelFeed(g.fuel_item_id, units * g.burn_rate_per_min,
                          tuple((i, units * r) for i, r in g.supplemental)) for g in fuels)


def _chains(data, cls, feeds, owned) -> tuple[BiofuelChain, ...]:
    if cls != BIOMASS_BURNER:
        return ()
    biofuel = next((f.per_min for f in feeds if f.fuel_item_id == SOLID_BIOFUEL), None)
    if biofuel is None or biofuel <= _EPS:
        return ()
    return _biofuel_chains(data, biofuel, owned)


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


@dataclass(frozen=True)
class FuelCheck:
    generator_class: ProducerClass
    fuel_item_id: ItemId            # the fuel option this check belongs to
    item_id: ItemId                 # the fuel itself, or a supplemental (Water)
    need_per_min: float
    available_per_min: float | None # None: not capped (a declared unlimited supply)
    status: str


@dataclass(frozen=True)
class SupplyCheck:
    checks: tuple[FuelCheck, ...]
    #: per line carrying load: the fuel options whose every check is covered,
    #: pumped or by hand. Empty: no option is fed. More than one: the choice is
    #: the player's (A19 does not pick a fuel).
    fed_by: tuple[tuple[ProducerClass, tuple[ItemId, ...]], ...]
    note: str


def supply_check(
    stack: PowerStack, available: dict[ItemId, float | None], *,
    water_extractor_owned: bool, water_item_id: ItemId = "Desc_Water_C",
) -> SupplyCheck:
    """Every fuel option of every line carrying load, against `available`
    (the site's leftover per minute; an item not named has none). Backup
    lines are not checked: they burn only on a spike (A18 P2). Lines are
    checked one at a time: two lines that would burn the same item are not
    summed (only Water is shared, and it is pumped)."""
    checks = []
    fed_by = []
    for line in stack.lines:
        if line.role not in CARRIES_LOAD or line.load_mw <= _EPS:
            continue
        fed = []
        for f in line.feeds:
            mine = []
            for item, need in ((f.fuel_item_id, f.per_min), *f.supplemental):
                have = available.get(item, 0.0)
                if item == water_item_id and not (have is None or have >= need - _EPS):
                    status = PUMPED if water_extractor_owned else NO_PUMP
                elif have is None or have >= need - _EPS:
                    status = COVERED
                elif line.generator_class == BIOMASS_BURNER:
                    status = BY_HAND
                else:
                    status = SHORT
                mine.append(FuelCheck(line.generator_class, f.fuel_item_id, item, need, have,
                                      status))
            checks += mine
            if all(c.status in (COVERED, PUMPED, BY_HAND) for c in mine):
                fed.append(f.fuel_item_id)
        fed_by.append((line.generator_class, tuple(fed)))
    return SupplyCheck(tuple(checks), tuple(fed_by),
                       "leftover = the site's cap less the solve's draw, plus fuel by-products "
                       "routed to generators; delivered goal-mix items leave the site and are "
                       "not counted")


def supply_lines(check: SupplyCheck) -> list[str]:
    lines = [f"  power from the site (declared): {check.note}"]
    for cls, fed in check.fed_by:
        lines.append(f"    {cls}: " + (f"fed by {', '.join(fed)}" if fed else "NO fuel option is fed"))
    for c in check.checks:
        if c.status == COVERED and c.item_id == c.fuel_item_id:
            continue
        have = "uncapped" if c.available_per_min is None else f"{c.available_per_min:.4g}/min left"
        lines.append(f"      {c.fuel_item_id}: {c.item_id} {c.need_per_min:.4g}/min needed, "
                     f"{have}: {c.status}")
    return lines


def report_lines(stack: PowerStack) -> list[str]:
    lines = [f"  power need {stack.need_mw:.4g} MW; each type alone (demonstrates the need):"]
    for a in stack.alone:
        lines.append(f"    {a.units:g} x {a.generator_class}, one of: "
                     + ", ".join(f"{f.fuel_item_id} {f.per_min:.4g}/min" for f in a.feeds))
    how = "declared mix" if stack.mix else "the class obtained last carries what standing leaves"
    lines.append(f"  supply ({how}); headroom {stack.headroom_mw:.4g} MW before the grid trips:")
    for l in stack.lines:
        units = f"{l.standing_units:g} standing + {l.new_units:g} new"
        if l.role == BACKUP:
            what = f"{units}, idle, up to {l.capacity_mw:.4g} MW on a spike"
        else:
            what = f"{units}, carrying {l.load_mw:.4g} MW"
        lines.append(f"    {l.role} {l.generator_class} ({l.obtained_with}, tier "
                     f"{l.obtained_tier}): {what}")
        if l.role != IDLE and (l.load_mw > _EPS or l.capacity_mw > _EPS):
            for f in l.feeds:
                sup = "".join(f", {r:.4g} {i}/min" for i, r in f.supplemental)
                lines.append(f"      {f.fuel_item_id}: {f.per_min:.4g}/min{sup}")
        for c in l.biofuel:
            flag = "" if c.owned else " (recipes not owned yet)"
            lines.append(f"      by hand: {c.by_hand_per_min:.4g} {c.source_item_id}/min -> "
                         f"{c.biomass_constructors:.3g} + {c.biofuel_constructors:.3g} constructors, "
                         f"{c.constructor_mw:.3g} MW (not added to the need){flag}")
    return lines
