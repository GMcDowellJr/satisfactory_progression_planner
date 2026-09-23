"""The stock pass: a build-material bill in QUANTITIES, never in rates.

Handoff next action 3, and the producer of `WithdrawalBasis.DERIVED_WHOLE_GAME_FLOOR`
— a value that has existed since 2026-09-22 with nothing emitting it.

    quantities in    settled machine counts, and a DECLARED bootstrap set
    quantities out   units of each item, split at the bootstrap
    never            a rate, a horizon, a machine count of its own

**It runs SEPARATELY from the flow traversal.** Folding it into the demand pass
is how amendment 5's loop — the machines that build the machines — gets smuggled
into a pass that refuses loops. Here there is no loop to smuggle: the bill is a
sum over a machine set that is handed in already settled, so the pass visits
nothing twice and terminates by construction.

**It cannot compute a machine count, and that is the guardrail.** `machines` is
a parameter. A module that derived its own counts would be deciding what to
build, which is a broader and more authoritative question than "what does this
bill come to" — and holding per-building costs, machine counts and tier unlocks
at once is exactly enough to drift into answering it. The restriction is in the
signature rather than in a policy, which is this repo's standing preference.

**Two of the five terms, and the other three are named rather than forgotten.**

    MACHINE_CONSTRUCTION   summed here. building_recipe_io.csv, exact
    BOOTSTRAP_SET          summed here. The same arithmetic over a DECLARED set
    UNLOCK_COST            summed WHEN A TIER IS GIVEN. The parked question —
                           whether anything resolves a capability to a numeric
                           tier — is answered: `schematics.csv` carries
                           `tech_tier` and `unlocks.py` has filtered on it
                           since it was written. Cumulative through the tier
    PROJECT_ASSEMBLY       summed WHEN PHASES ARE GIVEN. Scaled by
                           `Scenario.project_assembly_requirement_multiplier`,
                           never by the recipe multiplier — a term scaled by
                           the wrong one is silently wrong
    SPATIAL                NEVER summed here. Phase 5 owns the bounds

Whatever is left out keeps the bill a FLOOR, which is the property A5.5 needs,
so an absent term is a definition rather than a shortfall — and
`WithdrawalBill.terms` states which were consulted rather than leaving a reader
to infer it from a zero.

BOTH NEW TERMS LAND IN THE REMAINDER, NOT THE BOOTSTRAP. The bootstrap half is
"the initial machines needed to start the next tier" as declared, and that is
machines. A milestone purchase and a Space Elevator delivery are neither, so
folding them into the bootstrap would widen a definition the caller gave.

**No scenario.** Building construction costs do not scale with the recipe
multiplier (respec §8, measured in game at 1.25x and confirmed against the
snapshot). `gamedata.load_construction` takes no scenario and neither does
anything here.

Import direction, same as the rest of this package — downward, and asserted by
`tests/test_progression_import_boundary.py` rather than by this docstring:

    PERMITTED   production_adapter.contracts, .gamedata, .scenario
                realization.contracts   the bill TYPES only
    FORBIDDEN   production_adapter.backend, .lp_backend, .analysis
                realization.buses, .residual, .realize, .capabilities
                scipy, at any depth

`realization.contracts` is permitted for the same reason `busmodel` is allowed
`Disposition`: `WithdrawalBill`, `BillTerm` and `WithdrawalBasis` live in one
place or they drift into two.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

from production_adapter.contracts import ItemId, ProducerClass
from production_adapter.gamedata import ConstructionData, ReferenceData
from realization.contracts import BillTerm, WithdrawalBasis, WithdrawalBill

from .unlocks import SchematicId

#: The two terms EVERY call sums — the machine halves, which need nothing
#: declared beyond the sets themselves. UNLOCK_COST and PROJECT_ASSEMBLY are
#: added per call when the caller supplies them, because `terms` reports what
#: THIS call consulted and not what the module is capable of consulting.
BASE_TERMS: frozenset[BillTerm] = frozenset({
    BillTerm.MACHINE_CONSTRUCTION, BillTerm.BOOTSTRAP_SET,
})

#: Kept as the old name for the two-term case. `BASE_TERMS` is what it means.
SUMMED_TERMS = BASE_TERMS


class StockPassError(RuntimeError):
    """The pass declines rather than emitting a quantity it cannot stand behind."""


@dataclass(frozen=True)
class BootstrapSet:
    """The minimum equipment that brings the NEXT tier's chain online. DECLARED.

    Not derivable. "Minimum to start a tier" is a judgement about what counts as
    started, and no table holds it — coal power is at least 1 coal generator, 1
    water extractor, 1 miner and the infrastructure between them; steel is at
    least 2 miners, 1 foundry, 2 constructors, 2 storage and the same. Both are
    stated as MINIMUMS, which is one of the two reasons the bootstrap half is a
    floor. The other is that the infrastructure in each of them is the spatial
    term, absent until phase 5.

    `tier` is the tier being brought online, carried so a bill can say which one
    it bootstraps. Nothing here reads it — it is not a lookup key, because
    resolving a tier to anything is `unlocks.py`'s and is the parked question
    that blocks UNLOCK_COST.
    """

    tier: int
    buildings: tuple[tuple[ProducerClass, int], ...]

    def __post_init__(self) -> None:
        if not self.buildings:
            raise ValueError("a bootstrap set names at least one building")
        seen = [pc for pc, _ in self.buildings]
        if len(seen) != len(set(seen)):
            raise ValueError(
                f"tier {self.tier}: a producer class appears twice; state one count"
            )
        for producer_class, count in self.buildings:
            if count <= 0:
                raise ValueError(
                    f"{producer_class}: a bootstrap count must be positive. "
                    "A building that is not needed is left out, not declared as zero."
                )


@dataclass(frozen=True)
class StockPass:
    """What the pass produced: bills, and what it could not resolve.

    `unresolved` is REPORTED, never dropped. Respec §10.4: the Portable Miner is
    a build cost for Miner Mk.1/2/3 and the Drone, and it is equipment rather
    than a part, so it is absent from items.csv by construction — items.csv
    being the sole resource authority and carrying parts. Every miner's
    construction bill is therefore only partly resolvable, and §10.4's own
    verdict is that the §8.1 shape is to report the bill as incomplete and name
    the missing item rather than to recurse into workshop recipes.

    A caller that ignores `unresolved` gets a bill that is a floor by one more
    unmeasured margin than it thinks. The field exists so that is a choice
    rather than a surprise.
    """

    bills: dict[ItemId, WithdrawalBill]
    #: (source, cost input absent from items.csv), sorted. The source is a
    #: producer class for a building cost and a schematic id for an unlock
    #: cost — whichever names the row a reader would have to go and look at.
    unresolved: tuple[tuple[str, ItemId], ...]


@dataclass(frozen=True)
class ProjectAssemblyRequirement:
    """One Space Elevator delivery row, with its item RESOLVED to an id.

    `project_assembly_requirements.csv` carries `item_name` and no `item_id` —
    it is a wiki-sourced table, not a game-docs one. So the join is by DISPLAY
    NAME, which is the lookup the storage review warns about: a display-name
    lookup raises on `Turbo Rifle Ammo`, duplicated in the shipped data.

    That warning is about the RECIPE table. Measured against items.csv,
    2026-09-22: no display name is duplicated there at all, and all fifteen
    delivery rows resolve to exactly one item each. The join is therefore safe
    — by measurement, not by design — so `load_project_assembly` refuses a name
    that matches zero or more than one rather than relying on that holding.
    """

    phase: int
    phase_name: str
    item_id: ItemId
    quantity_1x: float


def load_project_assembly(
    repo_root: str | pathlib.Path,
    data: ReferenceData,
) -> tuple[ProjectAssemblyRequirement, ...]:
    """Read project_assembly_requirements.csv, resolving names to item ids.

    Quantities are the table's `quantity_default_1x` and are NOT scaled here —
    `project_assembly_cost` applies the multiplier, so the scaling happens once
    and at the point where the scenario is in hand.
    """
    import csv

    path = (
        pathlib.Path(repo_root)
        / "planning_data" / "game" / "reference"
        / "project_assembly_requirements.csv"
    )
    if not path.is_file():
        raise StockPassError(f"missing reference table: {path}")

    by_name: dict[str, list[ItemId]] = {}
    for item_id, item in data.items.items():
        by_name.setdefault(item.display_name, []).append(item_id)

    out: list[ProjectAssemblyRequirement] = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = row["item_name"]
            hits = by_name.get(name, [])
            if len(hits) != 1:
                raise StockPassError(
                    f"project assembly row names {name!r}, which matches "
                    f"{len(hits)} items in items.csv. The table carries no "
                    "item_id, so an ambiguous or absent display name cannot be "
                    "resolved and is refused rather than picked."
                )
            out.append(ProjectAssemblyRequirement(
                phase=int(row["phase"]),
                phase_name=row["phase_name"],
                item_id=hits[0],
                quantity_1x=float(row["quantity_default_1x"]),
            ))
    return tuple(out)


def cost_of(
    construction: ConstructionData,
    buildings: tuple[tuple[ProducerClass, int], ...],
) -> dict[ItemId, float]:
    """Per-item units for a machine set. Sum of per-building cost x count.

    Refuses an unknown producer by way of `ConstructionData.for_producer`, which
    raises rather than costing zero — an understated floor is the one failure
    the floor argument cannot absorb.
    """
    total: dict[ItemId, float] = {}
    for producer_class, count in buildings:
        if count < 0:
            raise StockPassError(f"{producer_class}: negative machine count {count}")
        for item_id, per_building in construction.for_producer(producer_class).items:
            total[item_id] = total.get(item_id, 0.0) + per_building * count
    return total


def unlock_cost(
    schematics: tuple[SchematicId, ...],
    costs: dict[SchematicId, tuple[tuple[ItemId, float], ...]],
) -> dict[ItemId, float]:
    """Per-item units to buy a set of schematics. Not scenario-scaled.

    A schematic absent from `costs` contributes nothing. That is a measured
    claim about the data, not a convenience — see `unlocks.schematic_costs`,
    whose docstring names the measurement and whose test pins it.

    Resolution and summing are split on purpose: `unlocks.schematics_at_tier`
    decides WHICH, this decides HOW MUCH, and neither can drift into the other's
    job. A filter that returned a bill would have stopped being a filter.
    """
    total: dict[ItemId, float] = {}
    for schematic_id in schematics:
        for item_id, amount in costs.get(schematic_id, ()):
            total[item_id] = total.get(item_id, 0.0) + amount
    return total


def project_assembly_cost(
    data: ReferenceData,
    requirements: tuple[ProjectAssemblyRequirement, ...],
    phases: tuple[int, ...],
) -> dict[ItemId, float]:
    """Space Elevator delivery quantities for the DECLARED phases.

    PHASES ARE DECLARED, NOT DERIVED FROM A TIER. The table's `delivery_unlocks`
    column is prose — "Tiers 3 and 4", "Project Assembly launch" — and parsing
    English into a tier mapping would be inventing one. The caller names the
    phases; a whole-game bill names all of them.

    Scaled by `Scenario.project_assembly_requirement_multiplier` through
    `apply_project_assembly_quantity`, which multiplies and ROUNDS — nearest,
    halves away from zero, the same rule as recipe inputs. It was read in game
    on 2026-09-22 rather than assumed to carry over from the recipe setting:
    0.25x turns phase 1's 50 Smart Plating into 13.

    **CORRECTED 2026-09-22.** This docstring previously named the probe as
    "1.25x, where phase 1's 50 Smart Plating lands on 62.5". THE GAME DOES NOT
    OFFER 1.25x HERE. Read from the settings menu, the selectable Project
    Assembly requirement multipliers are:

        0.25  0.5  0.75  1  2  5  10  25  50  100

    The recipe-input multiplier and this one are different settings with
    different value sets, and the old note had borrowed the former's 1.25.

    The tie was still REACHABLE, and only just — which is what made the read
    possible at all. Across all fifteen delivery rows and all ten multipliers,
    exactly four cells land on an exact half, all of them below 1x:

        phase 1  Smart Plating (50)              at 0.25x -> 12.5 -> 13 READ
                                                 at 0.75x -> 37.5
        phase 4  Thermal Propulsion Rocket (250) at 0.25x -> 62.5
                                                 at 0.75x -> 187.5

    Every multiplier at or above 1x is exact on every row, so the rounding
    could not have been observed there and cannot affect a bill computed
    there. The scenario of record uses 2.0x and no figure on it moves.

    No row falls below 1 at any multiplier, so `Scenario.input_amount_floor` —
    the unresolved sub-1x question for recipe INPUTS — does not arise for
    deliveries. Asserted in the tests rather than left as a reading.
    """
    wanted = set(phases)
    total: dict[ItemId, float] = {}
    for requirement in requirements:
        if requirement.phase not in wanted:
            continue
        scaled = data.scenario.apply_project_assembly_quantity(requirement.quantity_1x)
        total[requirement.item_id] = total.get(requirement.item_id, 0.0) + scaled
    return total


def bill_for(
    data: ReferenceData,
    construction: ConstructionData,
    *,
    bootstrap: BootstrapSet,
    machines: tuple[tuple[ProducerClass, int], ...],
    unlocks: tuple[SchematicId, ...] | None = None,
    unlock_costs: dict[SchematicId, tuple[tuple[ItemId, float], ...]] | None = None,
    project_assembly: tuple[ProjectAssemblyRequirement, ...] | None = None,
    phases: tuple[int, ...] | None = None,
) -> StockPass:
    """One `WithdrawalBill` per item the two machine sets consume.

        bootstrap_units   the declared bootstrap set, costed
        remainder_units   the settled machine counts, costed

    `machines` is the factory as it will stand — settled counts, handed in. This
    pass does not derive them and cannot; see the module docstring.

    EVERY EMITTED BILL CARRIES `SUMMED_TERMS`, including for an item that only
    one half contributes to. `terms` states which stores were CONSULTED, not
    which happened to be non-zero: a bill whose terms shrank when a number came
    out zero would make "the bootstrap contributes nothing" and "the bootstrap
    was not counted" the same report.

    An item absent from items.csv is left OUT of `bills` and named in
    `unresolved`. Emitting a bill for an item the reference layer does not carry
    would put a quantity of something with no form on a bus that has no carrier.
    """
    if (unlocks is None) != (unlock_costs is None):
        raise StockPassError(
            "unlocks and unlock_costs are given together or not at all. A "
            "schematic set with no cost table sums to zero and would be "
            "reported as UNLOCK_COST counted, which is the term set lying."
        )
    if (project_assembly is None) != (phases is None):
        raise StockPassError(
            "project_assembly and phases are given together or not at all. "
            "Phases are declared because delivery_unlocks is prose; a "
            "requirement table with no phases selects nothing and would be "
            "reported as PROJECT_ASSEMBLY counted."
        )

    terms = set(BASE_TERMS)
    boot = cost_of(construction, bootstrap.buildings)
    rest = cost_of(construction, machines)

    if unlocks is not None:
        terms.add(BillTerm.UNLOCK_COST)
        for item_id, amount in unlock_cost(unlocks, unlock_costs).items():
            rest[item_id] = rest.get(item_id, 0.0) + amount
    if project_assembly is not None:
        terms.add(BillTerm.PROJECT_ASSEMBLY)
        for item_id, amount in project_assembly_cost(
            data, project_assembly, phases
        ).items():
            rest[item_id] = rest.get(item_id, 0.0) + amount

    unresolved: list[tuple[str, ItemId]] = []
    for buildings in (bootstrap.buildings, machines):
        for producer_class, _count in buildings:
            for item_id, _amount in construction.for_producer(producer_class).items:
                if item_id not in data.items:
                    unresolved.append((producer_class, item_id))
    if unlocks is not None:
        for schematic_id in unlocks:
            for item_id, _amount in unlock_costs.get(schematic_id, ()):
                if item_id not in data.items:
                    unresolved.append((schematic_id, item_id))

    bills: dict[ItemId, WithdrawalBill] = {}
    for item_id in sorted(set(boot) | set(rest)):
        if item_id not in data.items:
            continue
        bills[item_id] = WithdrawalBill(
            bootstrap_units=boot.get(item_id, 0.0),
            remainder_units=rest.get(item_id, 0.0),
            terms=frozenset(terms),
            basis=WithdrawalBasis.DERIVED_WHOLE_GAME_FLOOR,
        )
    return StockPass(bills=bills, unresolved=tuple(sorted(set(unresolved))))
