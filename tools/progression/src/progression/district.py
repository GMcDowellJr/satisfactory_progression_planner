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

from production_adapter.contracts import ItemId, ProducerClass, RecipeId, ResourceCap
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

    def __post_init__(self) -> None:
        if self.count < 1:
            raise DistrictError(f"{self.item_id} {self.purity}: count must be at least 1")


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
        rate = _rate_for(rates, definition.extractor_class, node.purity)
        cap = (
            node.count * rate.nominal_rate_min * definition.extraction_clock
            * (1.0 - definition.reserve_fraction)
        )
        per_item[node.item_id] = per_item.get(node.item_id, 0.0) + cap
    declared = tuple(ResourceCap(item_id=i, rate_per_min=cap) for i, cap in per_item.items())
    closed = tuple(
        ResourceCap(item_id=i, rate_per_min=0.0)
        for i in resource_items if i not in per_item
    )
    return declared + closed


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
