"""A district's declared nodes, composed into resource caps. Crossover A26/A27.

    DistrictDefinition  nodes by purity, one extractor class, the extraction
                        clock, a reserve fraction          DECLARED
    resource_caps       -> tuple[ResourceCap, ...]         COMPOSED, nothing more

LP record 17.4: scarcity is a CONSTRAINT sourced from the world layer, and the
solver stays ignorant of geography. This module is that source's first,
declared form. A node count is a player's reading (D3) until the world layer
joins resource sockets to a site (A25.4); the shape of the output is the same
either way, so a later source replaces the reading, not the consumer.

**Both clocks are inputs (A27.1 K1).** The extraction clock here is the
extractors' under/overclock, a fraction of nameplate. The machine clock is a
realization setting and does not appear. Neither is a decision this module
holds a default for: `extraction_clock` is required.

**It cannot choose, and that is the guardrail.** No `min`, `max`, `sorted`
or rounding in this module (asserted from the source by
tests/test_progression_district.py). A cap is

    count * nominal_rate_min * extraction_clock * (1 - reserve_fraction)

summed per item in first-seen declaration order, and every raw resource the
definition does NOT declare is capped at 0.0: a district is closed. What it
has is what its nodes give; a supply from elsewhere is logistics (A24.1 S3)
and would be a declared import, which this definition does not yet carry.
Without the zero caps the solver would draw an undeclared ore without limit,
which is exactly the free supply v5.4.1 removed from the PWA. Nothing here
picks a node to leave idle, raises a clock, or ranks a resource.

**Not checked, and said so.** Belt capacity (a Miner Mk.1 on a pure node at
100 % already exceeds a Mk.1 belt), pipe capacity, and whether the nodes are
reachable from the site. A24.1 S3: logistics is a different set of tools, and
v5.5 rule 6 says the plan carries these as UNVERIFIED rather than implying
buildability. The upper clock bound is the game's 250 % (extraction_rates.csv
carries that column); anything above is refused.

Import direction: downward. `production_adapter.contracts` for the types and
`production_adapter.gamedata` for `ExtractionRate`/`ReferenceData`; never
the backend.
"""
from __future__ import annotations

from dataclasses import dataclass

from production_adapter.contracts import GeneratorFuel, ItemId, ProducerClass, RecipeId, ResourceCap
from production_adapter.gamedata import ExtractionRate, ReferenceData

#: The game's overclock ceiling, as extraction_rates.csv's max_250 column states it.
MAX_CLOCK = 2.5


class DistrictError(ValueError):
    """A definition the composer cannot use. Refused by name, never coerced."""


@dataclass(frozen=True)
class NodeCount:
    """So many nodes of one resource at one purity. A declared reading."""

    item_id: ItemId
    purity: str      # impure | normal | pure | none, as extraction_rates.csv spells them
    count: int
    #: None: the definition's extractor. Set for a node of another kind (a
    #: Water Extractor beside the miners); the (class, purity) row must exist
    extractor_class: ProducerClass | None = None
    #: None: the definition's extraction clock. Set when this node runs at its
    #: own (A34.2 F5: the water extractors feeding standing generators run at
    #: 100 % whatever the miners' case clock is)
    extraction_clock: float | None = None

    def __post_init__(self) -> None:
        if self.count < 1:
            raise DistrictError(f"{self.item_id} {self.purity}: count must be at least 1")
        if self.extraction_clock is not None and not 0.0 < self.extraction_clock <= MAX_CLOCK:
            raise DistrictError(
                f"{self.item_id} {self.purity}: extraction_clock {self.extraction_clock} is "
                f"outside (0, {MAX_CLOCK}]"
            )

    def clock(self, default: float) -> float:
        return default if self.extraction_clock is None else self.extraction_clock


@dataclass(frozen=True)
class DistrictDefinition:
    nodes: tuple[NodeCount, ...]
    extractor_class: ProducerClass
    extraction_clock: float          # fraction of nameplate; 1.0 = 100 %
    reserve_fraction: float = 0.0    # A25.4: a declared reservation, held uncommitted
    label: str = ""

    def __post_init__(self) -> None:
        if not self.nodes:
            raise DistrictError("a district needs at least one node")
        if not 0.0 < self.extraction_clock <= MAX_CLOCK:
            raise DistrictError(
                f"extraction_clock {self.extraction_clock} is outside (0, {MAX_CLOCK}]"
            )
        if not 0.0 <= self.reserve_fraction < 1.0:
            raise DistrictError(f"reserve_fraction {self.reserve_fraction} is outside [0, 1)")


def _rate_for(
    rates: tuple[ExtractionRate, ...], extractor_class: ProducerClass, purity: str,
) -> ExtractionRate:
    hits = [r for r in rates if r.extractor_class == extractor_class and r.purity == purity]
    if len(hits) != 1:
        raise DistrictError(
            f"extraction_rates.csv has {len(hits)} rows for ({extractor_class}, {purity}); "
            "one is required"
        )
    return hits[0]


def resources_in_reference_order(data: ReferenceData) -> tuple[ItemId, ...]:
    """The raw resources in items.csv row order: a deterministic order that is
    the reference layer's own, not one chosen here."""
    return tuple(i for i in data.items if i in data.resource_items)


def resource_caps(
    definition: DistrictDefinition,
    rates: tuple[ExtractionRate, ...],
    resource_items: tuple[ItemId, ...],
) -> tuple[ResourceCap, ...]:
    """Compose the declared nodes into caps: declared resources first, in
    declaration order, then every other raw resource at 0.0 (the district is
    closed), in the order `resource_items` gives them.

    `rates` is `gamedata.load_logistics(repo_root)[1]`. `resource_items` is an
    ORDERED tuple, `resources_in_reference_order(data)`: `ReferenceData.
    resource_items` is a frozenset, whose iteration order changes between
    processes under hash randomisation, and a plan whose cap list reorders
    itself between runs is not the same plan twice. An item that is not in
    `resource_items` is refused: a cap on a manufactured item is a different
    statement (a supply from elsewhere) and is not what a node declares.
    """
    per_item: dict[ItemId, float] = {}
    for node in definition.nodes:
        if node.item_id not in resource_items:
            raise DistrictError(f"{node.item_id} is not a raw resource; a node cannot declare it")
        rate = _rate_for(rates, node.extractor_class or definition.extractor_class, node.purity)
        cap = (
            node.count * rate.nominal_rate_min * node.clock(definition.extraction_clock)
            * (1.0 - definition.reserve_fraction)
        )
        per_item[node.item_id] = per_item.get(node.item_id, 0.0) + cap
    declared = tuple(ResourceCap(item_id=i, rate_per_min=cap) for i, cap in per_item.items())
    closed = tuple(
        ResourceCap(item_id=i, rate_per_min=0.0)
        for i in resource_items if i not in per_item
    )
    return declared + closed


def extraction_nameplate_mw(
    definition: DistrictDefinition, base_mw: dict[ProducerClass, float],
) -> float:
    """Every declared extractor at NAMEPLATE: count * base MW, summed (A25.3
    P2: underclocking only lowers draw, so the balance stays floor-safe).
    `base_mw` is `progression.power.load_power_tables(repo).extractors`, read
    there; a class absent from it is refused by name."""
    total = 0.0
    for node in definition.nodes:
        cls = node.extractor_class or definition.extractor_class
        if cls not in base_mw:
            raise DistrictError(f"{cls}: no base power in extraction_buildings.csv")
        total += node.count * base_mw[cls]
    return total


def bill_units(
    sources: tuple[tuple[str, tuple[tuple[ItemId, float], ...]], ...],
) -> dict[ItemId, float]:
    """Sum declared bill sources into units per item, first-seen order (A31).

    A source is (label, ((item, units), ...)): a Project Assembly phase's
    rows, a schematic's cost rows, a declared extra. The CALLER chooses the
    sources (which phases, which tiers, what the player still owes); this
    sums them and nothing else. Zero and negative units are refused: a bill
    that lists an item at nothing is a different statement from one that
    omits it, and this function cannot tell which was meant.
    """
    out: dict[ItemId, float] = {}
    for label, rows in sources:
        for item, units in rows:
            if units <= 0:
                raise DistrictError(f"bill source {label!r}: {item} at {units!r} units")
            out[item] = out.get(item, 0.0) + units
    return out


@dataclass(frozen=True)
class Reach:
    """Whether one item can be made here at all, and if not, why (A31 O34).

        makeable        some enabled recipe chain reaches it from a resource
                        with a positive cap
        missing_raws    raw resources every reaching chain would need that the
                        district caps at 0 (or does not cap but has no row
                        for): the ones a node would have to be declared for.
                        Empty when makeable, or when no enabled recipe makes
                        the item at all
        no_recipe       no enabled recipe outputs the item
    """

    item_id: ItemId
    makeable: bool
    missing_raws: tuple[ItemId, ...] = ()
    no_recipe: bool = False


def discover(
    data: ReferenceData,
    recipe_ids: tuple[RecipeId, ...],
    caps: tuple[ResourceCap, ...],
    items: tuple[ItemId, ...],
) -> tuple[Reach, ...]:
    """Which of `items` the district can make at all: a FORWARD CLOSURE over
    the enabled recipes from the raws with a positive cap, independent of
    rates (v5.5 Stage 2: discovery is not allocation). No LP, no choice: a
    recipe runs when every input is reachable, and its outputs become
    reachable; repeated until nothing changes. Byproducts count as outputs.

    An uncapped raw is treated as absent: `resource_caps` lists every raw a
    district has (A28.1 T1 closes the rest at 0), so a raw with no cap row is
    one the caller never declared.

    For an unreachable item the reason is the raws its enabled recipes need,
    transitively, that are not reachable: the nodes that would have to be
    declared. Reported in `items` order.
    """
    recipes = [data.recipes[r] for r in recipe_ids]
    available = {c.item_id for c in caps if c.rate_per_min is not None and c.rate_per_min > 0.0}
    reachable: set[ItemId] = set(available)
    changed = True
    while changed:
        changed = False
        for r in recipes:
            if all(i in reachable for i, _ in r.inputs):
                for i, _ in r.outputs:
                    if i not in reachable:
                        reachable.add(i)
                        changed = True

    producers: dict[ItemId, list] = {}
    for r in recipes:
        for i, _ in r.outputs:
            producers.setdefault(i, []).append(r)

    def missing(item: ItemId, trail: frozenset[ItemId]) -> tuple[ItemId, ...]:
        """Raws needed by every enabled chain to `item` that are not reachable,
        first-seen order; a cycle in the recipe graph is cut, not followed."""
        out: list[ItemId] = []
        for r in producers.get(item, ()):
            for i, _ in r.inputs:
                if i in reachable or i in trail:
                    continue
                if i in data.resource_items:
                    if i not in out:
                        out.append(i)
                else:
                    for raw in missing(i, trail | {item}):
                        if raw not in out:
                            out.append(raw)
        return tuple(out)

    return tuple(
        Reach(
            item_id=item,
            makeable=item in reachable,
            missing_raws=() if item in reachable or item not in producers else missing(item, frozenset()),
            no_recipe=item not in producers and item not in available,
        )
        for item in items
    )


def partition_recipes(
    buses: tuple[tuple[str, ItemId, RecipeId | None], ...],
) -> tuple[RecipeId, ...]:
    """The solve's recipe set, FROM the declared partition (A34, Greg: one
    recipe per bus). Each bus is (bus_id, item_id, recipe_id); every bus
    must name its recipe, and two buses of one item must name the same one.
    Returned in declaration order, each recipe once. The partition is then
    the single statement of which recipe makes which item, and the solve
    chooses rates only.
    """
    out: list[RecipeId] = []
    by_item: dict[ItemId, RecipeId] = {}
    for bus_id, item, recipe in buses:
        if recipe is None:
            raise DistrictError(f"{bus_id}: a district partition names each bus's recipe")
        if by_item.get(item, recipe) != recipe:
            raise DistrictError(
                f"{bus_id}: {item} is made by {recipe} here and by {by_item[item]} on "
                "another bus; one recipe per item (A34)"
            )
        by_item[item] = recipe
        if recipe not in out:
            out.append(recipe)
    return tuple(out)


@dataclass(frozen=True)
class StandingSupply:
    """Declared standing generators: their gross MW and the fuel and water they
    draw per minute from the district's own caps (A25.3 P3 "base + fed";
    A25.4 a declared reservation). Reported; the caps are reduced by it."""

    mw: float
    draws: tuple[tuple[ItemId, float], ...]
    generators: tuple[tuple[ProducerClass, ItemId, int], ...]


def standing_generation(
    rows: tuple[GeneratorFuel, ...],
    standing: tuple[tuple[ProducerClass, ItemId, int], ...],
) -> StandingSupply:
    """Count x gross MW and count x burn/supplemental rates, from the
    generator_fuels rows; an unknown (generator, fuel) pair or a count below
    one is refused by name."""
    mw = 0.0
    draws: dict[ItemId, float] = {}
    for generator_class, fuel, count in standing:
        if count < 1:
            raise DistrictError(f"{generator_class}/{fuel}: count must be at least 1")
        hits = [g for g in rows if g.generator_class == generator_class and g.fuel_item_id == fuel]
        if len(hits) != 1:
            raise DistrictError(
                f"generator_fuels.csv has {len(hits)} rows for ({generator_class}, {fuel})"
            )
        g = hits[0]
        mw += count * g.power_mw
        draws[fuel] = draws.get(fuel, 0.0) + count * g.burn_rate_per_min
        for item, rate in g.supplemental:
            draws[item] = draws.get(item, 0.0) + count * rate
    return StandingSupply(mw=mw, draws=tuple(draws.items()), generators=tuple(standing))


def caps_less_draws(
    caps: tuple[ResourceCap, ...], draws: tuple[tuple[ItemId, float], ...],
) -> tuple[ResourceCap, ...]:
    """The caps left for production after a declared fixed draw. A draw on an
    item with no cap, or above its cap, is refused: the standing generators
    cannot be fed from what the district does not have."""
    by_item = {c.item_id: c for c in caps}
    for item, rate in draws:
        cap = by_item.get(item)
        if cap is None or cap.rate_per_min is None:
            raise DistrictError(f"{item}: a standing draw of {rate:g}/min on a resource with no cap")
        if rate > cap.rate_per_min + 1e-9:
            raise DistrictError(
                f"{item}: standing generators draw {rate:g}/min against a cap of {cap.rate_per_min:g}"
            )
        by_item[item] = ResourceCap(item, cap.rate_per_min - rate)
    return tuple(by_item[c.item_id] for c in caps)


def _normalise(name: str) -> str:
    return " ".join(name.split()).casefold()


def recipe_ids_by_name(data: ReferenceData, names: tuple[str, ...]) -> tuple[RecipeId, ...]:
    """Display names -> recipe ids, in the order given. 0 or several hits refuse.

    "Alternate: Solid Steel Ingot" is a different string from "Solid Steel
    Ingot" and must be given as recipes.csv spells it; this resolver does not
    strip the prefix, because the prefix is how the two Compacted Coal rows
    (`Recipe_Alternate_EnrichedCoal_C` is the only one) stay distinguishable
    from a base recipe of the same name elsewhere in the table.
    """
    by_name: dict[str, list[RecipeId]] = {}
    for rid, recipe in data.recipes.items():
        by_name.setdefault(_normalise(recipe.display_name), []).append(rid)
    out: list[RecipeId] = []
    for name in names:
        hits = by_name.get(_normalise(name), [])
        if len(hits) != 1:
            raise DistrictError(f"recipe display name {name!r} matched {len(hits)} rows: {hits}")
        out.append(hits[0])
    return tuple(out)
