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
    UNLOCK_COST            NOT summed. schematic_costs.csv is canonical and
                           resolving a TIER to its schematic ids is a parked
                           open item — whether `unlocks.py` or
                           progression_clusters.csv already does it has not
                           been read
    PROJECT_ASSEMBLY       NOT summed. Scales by
                           `Scenario.project_assembly_requirement_multiplier`
                           and not by the recipe multiplier; a term scaled by
                           the wrong one is silently wrong
    SPATIAL                NOT summed. Phase 5 owns the bounds

Their absence is what keeps the bill a FLOOR, which is the property A5.5 needs,
so it is a definition rather than a shortfall — and `WithdrawalBill.terms`
states it rather than leaving a reader to infer it.

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

from dataclasses import dataclass

from production_adapter.contracts import ItemId, ProducerClass
from production_adapter.gamedata import ConstructionData, ReferenceData
from realization.contracts import BillTerm, WithdrawalBasis, WithdrawalBill

#: The terms this pass sums. Named once so the bills it emits and the tests
#: that check them cannot disagree about what was counted.
SUMMED_TERMS: frozenset[BillTerm] = frozenset({
    BillTerm.MACHINE_CONSTRUCTION, BillTerm.BOOTSTRAP_SET,
})


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
    #: (producer class, cost input absent from items.csv), sorted.
    unresolved: tuple[tuple[ProducerClass, ItemId], ...]


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


def bill_for(
    data: ReferenceData,
    construction: ConstructionData,
    *,
    bootstrap: BootstrapSet,
    machines: tuple[tuple[ProducerClass, int], ...],
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
    boot = cost_of(construction, bootstrap.buildings)
    rest = cost_of(construction, machines)

    unresolved: list[tuple[ProducerClass, ItemId]] = []
    for label, buildings in (("bootstrap", bootstrap.buildings), ("machines", machines)):
        for producer_class, _count in buildings:
            for item_id, _amount in construction.for_producer(producer_class).items:
                if item_id not in data.items:
                    unresolved.append((producer_class, item_id))

    bills: dict[ItemId, WithdrawalBill] = {}
    for item_id in sorted(set(boot) | set(rest)):
        if item_id not in data.items:
            continue
        bills[item_id] = WithdrawalBill(
            bootstrap_units=boot.get(item_id, 0.0),
            remainder_units=rest.get(item_id, 0.0),
            terms=SUMMED_TERMS,
            basis=WithdrawalBasis.DERIVED_WHOLE_GAME_FLOOR,
        )
    return StockPass(bills=bills, unresolved=tuple(sorted(set(unresolved))))
