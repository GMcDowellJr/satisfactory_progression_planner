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
    """The equipment this stage wants STANDING to bring the next tier online. DECLARED.

    Not derivable. What counts as started is a judgement, and no table holds it.
    CORRECTED 2026-09-24 (goal_run_driver.md amendment 4): this docstring said
    coal power is "at least 1 coal generator, 1 water extractor, 1 miner" — a
    minimum, and with 1 miner where Greg revised to 2 on 2026-09-23. The set is
    now a TARGET: the case of record declares the Mk1 coal step, 2 miners, 4
    coal generators and 2 water extractors (what one Mk1 belt carries). The
    2:1:1 minimum is still a valid declaration; steel is at least 2 miners, 1
    foundry, 2 constructors, 2 storage. The half stays a floor because the
    infrastructure between the machines is the spatial term, absent until
    phase 5, and because a declared target can only leave things out.

    What already stands is a separate reading (`StandingBuildings`), netted in
    `bill_for`. The set keeps its non-empty invariant: it is the target, not
    what is left to build (D4 P2).

    `tier` is the tier being brought online, carried so a bill can say which one
    it bootstraps. Nothing here reads it — it is not a lookup key, because
    resolving a tier to anything is `unlocks.py`'s and is the parked question
    that blocks UNLOCK_COST.

    AMENDED 2026-09-24 (crossover A19). Greg: the bootstrap is "always the
    minimum to begin producing new items". That rule makes the PRODUCTION
    bootstrap derivable: `derive_bootstrap` below. "Not derivable" above
    stands for anything outside the rule (a power step, storage, a target
    larger than the minimum), which is still declared.
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
    #: D4. The building netting the bills were summed after; None when no
    #: standing reading was declared, in which case the bills are gross
    standing_net: "NetBuildings | None" = None


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
    standing: "StandingBuildings | None" = None,
) -> StockPass:
    """One `WithdrawalBill` per item the two machine sets consume.

    D4 (2026-09-24). `standing` is the reading of machines already placed at
    stage open. When given, both sets are netted against it first
    (`net_buildings`, lines before bootstrap) and each half is costed over
    its OWED machines; the netting rides on `StockPass.standing_net`. When
    absent, every figure is as before.

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

    if standing is None:
        net = None
        boot_set, machine_set = bootstrap.buildings, machines
    else:
        net = net_buildings(bootstrap, machines, standing)
        boot_set = tuple((pc, n) for pc, n in net.owed_bootstrap.items() if n)
        machine_set = tuple((pc, n) for pc, n in net.owed_machines.items() if n)

    terms = set(BASE_TERMS)
    boot = cost_of(construction, boot_set)
    rest = cost_of(construction, machine_set)

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
    for buildings in (boot_set, machine_set):
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
    return StockPass(
        bills=bills, unresolved=tuple(sorted(set(unresolved))), standing_net=net,
    )


# --------------------------------------------------------------------------
# D3: stock on hand at stage open, netted against the bill. 2026-09-23.
# --------------------------------------------------------------------------
#
# Greg's decisions on the D3 note (project doc
# d3-carry-forward-design-2026-09-23.md): carry is DECLARED; a derived
# estimate may be shown beside it but NEVER nets, including when nothing is
# declared (P1); netting lives here because it is quantity arithmetic (P2);
# it is against the item's whole bill, not a half (P3).
#
# WHY ONLY A DECLARED INVENTORY NETS. The bill is a floor: bill <= true bill.
# Netting gives bill - carry, and that stays a floor only if carry >= true
# carry, i.e. only if carry is a CEILING. A read of the player's inventory is
# a measurement. A modelled carry understates whenever lines ran faster than
# paced, which is how the pre-Smart-Plating window is played, and so breaks
# the floor. The restriction is in the signature: `net_of` takes a
# `DeclaredOnHand` and refuses anything else, so an estimate cannot be passed
# in by accident.


@dataclass(frozen=True)
class DeclaredOnHand:
    """Units of each item the player HOLDS at stage open. Read, not modelled.

    Pairs, like `BootstrapSet.buildings`, so the declaration is hashable and
    keeps the caller's order. An item named twice is refused rather than
    summed: two readings of one item is a declaration error, not a total.
    """

    units: tuple[tuple[ItemId, float], ...]

    def __post_init__(self) -> None:
        seen = [item_id for item_id, _ in self.units]
        if len(seen) != len(set(seen)):
            raise ValueError("an item appears twice in the on-hand declaration; state one count")
        for item_id, amount in self.units:
            if amount < 0:
                raise ValueError(f"{item_id}: on-hand units cannot be negative, got {amount}")


@dataclass(frozen=True)
class NetStock:
    """A bill netted against a declared inventory. Nothing clamped silently.

        owed      one entry per BILLED item, in bill order: whole bill less
                  what is held, or 0.0 when the holding covers it
        surplus   what is held beyond the bill: billed items in bill order,
                  then unbilled held items in declaration order. Includes
                  held items no bill names — they carry on,
                  and dropping them would lose the reading

    Conservation, per item: owed + on_hand == bill + surplus. Asserted in the
    tests. The `WithdrawalBill` objects are untouched; this is a separate
    object and its basis is the declaration it was netted against.
    """

    owed: dict[ItemId, float]
    surplus: dict[ItemId, float]
    on_hand: DeclaredOnHand


def net_of(bills: dict[ItemId, WithdrawalBill], on_hand: DeclaredOnHand) -> NetStock:
    """Each item's whole bill, bootstrap plus remainder, less what is held.

    A sign test splits the difference into `owed` or `surplus`. That is a
    branch on one number, not a comparison between alternatives: there is no
    min, max or sort here, and asserted so.
    """
    if not isinstance(on_hand, DeclaredOnHand):
        raise StockPassError(
            f"net_of takes a DeclaredOnHand, got {type(on_hand).__name__}. Only "
            "a read inventory nets: a modelled carry can understate, and an "
            "understated carry breaks the floor (D3 P1)."
        )
    held = dict(on_hand.units)
    owed: dict[ItemId, float] = {}
    surplus: dict[ItemId, float] = {}
    for item_id, bill in bills.items():
        difference = bill.bootstrap_units + bill.remainder_units - held.get(item_id, 0.0)
        if difference > 0:
            owed[item_id] = difference
        else:
            owed[item_id] = 0.0
            if difference < 0:
                surplus[item_id] = -difference
    for item_id, amount in on_hand.units:
        if item_id not in bills and amount > 0:
            surplus[item_id] = amount
    return NetStock(owed=owed, surplus=surplus, on_hand=on_hand)


# --------------------------------------------------------------------------
# D4: machines standing at stage open, netted per producer class. 2026-09-24.
# --------------------------------------------------------------------------
#
# goal_run_driver.md amendment 4. Standing is a DECLARED reading, the D3 rule:
# a machine counts when the player lets this stage's plan use it (commitment,
# not run state), and one the player won't repurpose is left out — no
# "committed" field (D4 (a)). It nets the class's whole demand, bootstrap and
# lines (D4 (b)); the LINES are covered first and what is left covers the
# bootstrap — Greg's call on 2026-09-24, resolving the P3/P4 conflict (P3 said
# no order; P4 costs the owed machines into two halves, which needs one).
#
# Floor check: over-declaring standing shrinks the bill, so it stays <= true
# and stays a floor, only a looser one. Netting is not assignment: nothing
# here says WHICH standing machine goes on which lane.


@dataclass(frozen=True)
class StandingBuildings:
    """Machines PLACED at stage open that this stage's plan may use. Read, not modelled.

    Pairs, like `BootstrapSet.buildings` and `DeclaredOnHand.units`: hashable,
    caller order kept. A class named twice is refused rather than summed. Zero
    is a valid reading; a negative is not.
    """

    buildings: tuple[tuple[ProducerClass, int], ...]

    def __post_init__(self) -> None:
        seen = [pc for pc, _ in self.buildings]
        if len(seen) != len(set(seen)):
            raise ValueError("a producer class appears twice in the standing declaration; state one count")
        for producer_class, count in self.buildings:
            if count < 0:
                raise ValueError(f"{producer_class}: a standing count cannot be negative, got {count}")


@dataclass(frozen=True)
class NetBuildings:
    """Both machine sets netted against a standing reading. Nothing clamped silently.

        owed_machines    one entry per class in `machines`, in its order
        owed_bootstrap   one entry per class in the bootstrap, in its order
        surplus          standing beyond both: bootstrap classes in bootstrap
                         order, then line-only classes in machines order, then
                         standing-only classes in declaration order. Kept,
                         because dropping it would lose the reading

    Conservation, per class:
        owed_machines + owed_bootstrap + standing == machines + bootstrap + surplus
    Asserted in the tests.
    """

    owed_machines: dict[ProducerClass, int]
    owed_bootstrap: dict[ProducerClass, int]
    surplus: dict[ProducerClass, int]
    standing: StandingBuildings


def net_buildings(
    bootstrap: BootstrapSet,
    machines: tuple[tuple[ProducerClass, int], ...],
    standing: StandingBuildings,
) -> NetBuildings:
    """Per class: standing covers the lines first, then the bootstrap.

    Two sign tests per class, the `net_of` pattern: a branch on one number,
    not a comparison between alternatives. No min, max, sort or round, and
    asserted so.
    """
    if not isinstance(standing, StandingBuildings):
        raise StockPassError(
            f"net_buildings takes a StandingBuildings, got {type(standing).__name__}. "
            "Only a declared reading nets (D3 P1, D4 P1)."
        )
    held = dict(standing.buildings)
    lines: dict[ProducerClass, int] = {}
    for producer_class, count in machines:
        lines[producer_class] = lines.get(producer_class, 0) + count
    boot = dict(bootstrap.buildings)

    left: dict[ProducerClass, int] = {}
    owed_machines: dict[ProducerClass, int] = {}
    for producer_class, count in lines.items():
        difference = count - held.get(producer_class, 0)
        if difference > 0:
            owed_machines[producer_class] = difference
            left[producer_class] = 0
        else:
            owed_machines[producer_class] = 0
            left[producer_class] = -difference

    owed_bootstrap: dict[ProducerClass, int] = {}
    surplus: dict[ProducerClass, int] = {}
    for producer_class, count in boot.items():
        difference = count - left.get(producer_class, held.get(producer_class, 0))
        if difference > 0:
            owed_bootstrap[producer_class] = difference
        else:
            owed_bootstrap[producer_class] = 0
            if difference < 0:
                surplus[producer_class] = -difference
    for producer_class, spare in left.items():
        if producer_class not in boot and spare > 0:
            surplus[producer_class] = spare
    for producer_class, count in standing.buildings:
        if producer_class not in lines and producer_class not in boot and count > 0:
            surplus[producer_class] = count
    return NetBuildings(
        owed_machines=owed_machines,
        owed_bootstrap=owed_bootstrap,
        surplus=surplus,
        standing=standing,
    )


# --------------------------------------------------------------------------
# A19: the minimum bootstrap, derived. 2026-09-24.
# --------------------------------------------------------------------------
#
# Greg, 2026-09-24: "bootstrap is always the minimum to begin producing new
# items -- for steel that's ... 1 miner for coal, 1 for iron, 1 foundry, 1
# constructor for beam, 1 for pipe and versatile frameworks which needs 1
# assembler, beams and modular frame (which then assumes either another set of
# lanes or transport from another factory)". As a rule:
#
#   NEW RECIPE   a recipe the phase's solve uses that was not open before the
#                phase (`open_before`, the previous tier's recipe set)
#   PRODUCERS    one machine of each new recipe's producer class
#   EXTRACTORS   one per distinct raw resource a new recipe consumes, of the
#                one extractor class open before the phase. Inputs that are
#                not new (modular frame) are assumed to arrive: existing lanes
#                or transport, per Greg
#
# Power is not an item, so a power step is outside the rule and stays declared.


#: How a derived set came to be. Carried beside it, not inside `BootstrapSet`.
DERIVED_MINIMUM = (
    "DERIVED: one producer per recipe new this phase, one extractor per raw "
    "resource those recipes consume (crossover A19). A minimum; excludes power"
)


@dataclass(frozen=True)
class DerivedBootstrap:
    bootstrap: BootstrapSet
    #: (recipe_id, producer_class), in the solve's order
    new_recipes: tuple[tuple[str, ProducerClass], ...]
    #: (resource item, extractor class), first-seen order
    extractors: tuple[tuple[ItemId, ProducerClass], ...]
    basis: str = DERIVED_MINIMUM


def derive_bootstrap(
    data: ReferenceData,
    recipes_used: tuple[str, ...],
    *,
    open_before: tuple[str, ...],
    extractors_open: dict[ItemId, tuple[ProducerClass, ...]],
    tier: int,
) -> DerivedBootstrap:
    """The A19 minimum. Every input is handed in; nothing is chosen here.

    `recipes_used` is the recipe ids of the phase's solve (a SolveResponse's
    `recipes`, in its order). `open_before` is
    `unlocks.at_tier(repo, previous tier).recipe_ids`. `extractors_open` is
    `unlocks.extractors_open_at_tier(repo, previous tier)`.

    REFUSED: no new recipe (a bootstrap names at least one building); a raw
    resource with no extractor open before the phase, or with more than one
    (which one is the caller's declaration). Addition only; no min, max, sort
    or round.
    """
    before = set(open_before)
    new = [(r, data.recipes[r].producer_class) for r in recipes_used if r not in before]
    if not new:
        raise StockPassError(
            "the solve uses no recipe that was closed before the phase, so the A19 "
            "minimum is empty. Declare a bootstrap, or check open_before."
        )
    resources: list[ItemId] = []
    for recipe_id, _ in new:
        for item_id, _rate in data.recipes[recipe_id].inputs:
            if item_id in data.resource_items and item_id not in resources:
                resources.append(item_id)
    extractors: list[tuple[ItemId, ProducerClass]] = []
    for item_id in resources:
        classes = extractors_open.get(item_id, ())
        if len(classes) != 1:
            raise StockPassError(
                f"{item_id}: {len(classes)} extractor classes open before the phase "
                f"{classes}. The A19 minimum takes exactly one; declare the bootstrap."
            )
        extractors.append((item_id, classes[0]))

    counts: dict[ProducerClass, int] = {}
    for _item, extractor in extractors:
        counts[extractor] = counts.get(extractor, 0) + 1
    for _recipe, producer_class in new:
        counts[producer_class] = counts.get(producer_class, 0) + 1
    return DerivedBootstrap(
        bootstrap=BootstrapSet(tier=tier, buildings=tuple(counts.items())),
        new_recipes=tuple(new),
        extractors=tuple(extractors),
    )
