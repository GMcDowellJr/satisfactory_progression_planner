"""Typed results and named refusals for demand expansion.

Everything here is data. The refusals are the structural guard: a module that
raises `AmbiguousRoute` cannot quietly become a recipe chooser, which is what a
production solver is and what this package must not be (LP record §11.3,
demand-expansion record §6 and Amendment 1).
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from production_adapter.contracts import ItemId, RecipeId


class DemandExpansionError(RuntimeError):
    """Base of every named refusal in this package."""


class DeclarationError(DemandExpansionError):
    """A route-table entry no longer describes the data: an exclusion naming a
    recipe that is absent or already an alternate, or a pin that resolves
    nothing. A stale declaration is a choice nobody is making any more, so it is
    refused rather than ignored (the self-deleting data-gap pattern)."""


class AmbiguousRoute(DemandExpansionError):
    """An item on the path has more than one enabled recipe and no pin. The
    engine does not choose; the caller pins it in a route table, as a recorded
    decision (demand-expansion record §3.1.2, consequence 2)."""

    def __init__(self, item_id: ItemId, candidates: tuple[RecipeId, ...], path: tuple[ItemId, ...]):
        self.item_id = item_id
        self.candidates = candidates
        self.path = path
        super().__init__(
            f"{item_id} is produced by {len(candidates)} enabled recipes "
            f"({', '.join(candidates)}) on the path {' -> '.join(path)}. "
            "Demand expansion does not choose; pin one in the route table."
        )


class UnproducibleItem(DemandExpansionError):
    """A non-resource item on the path has no enabled recipe."""

    def __init__(self, item_id: ItemId, path: tuple[ItemId, ...]):
        self.item_id = item_id
        self.path = path
        super().__init__(
            f"{item_id} has no enabled recipe (path {' -> '.join(path)}). Either it "
            "is only made by an excluded or alternate recipe, or it is not made by "
            "a recipe at all."
        )


class CycleDetected(DemandExpansionError):
    """The chosen routes loop back on themselves. Under the default route table
    the base graph has no cycle (census, 2026-10-10); a caller's pins can create
    one, and a quantity recursion over a loop has no finite answer without a
    material-balance solve, which v1 does not carry."""

    def __init__(self, loop: tuple[ItemId, ...]):
        self.loop = loop
        super().__init__(f"recipe cycle: {' -> '.join(loop)}")


class FluidRoundingUndeclared(DemandExpansionError):
    """`fluid_rounding` is not one of the three variants. Until 2026-10-10 this
    also fired when a non-1x multiplier arrived with no declaration, because
    the adapter's default was an assumption and the variants differ by 6.7% on
    Crude Oil per Thermal Propulsion Rocket (Amendment 1). The rule has since
    been observed (Amendment 2), so the default is inherited again."""


class NotExpandable(DemandExpansionError):
    """The target is a raw resource. Resources are leaves, never expanded."""


@dataclass(frozen=True)
class Exclusion:
    """A base recipe removed from the enabled set, with the reason recorded."""

    recipe_id: RecipeId
    reason: str


@dataclass(frozen=True)
class RoutePin:
    """The one enabled recipe to use for an item that has several."""

    item_id: ItemId
    recipe_id: RecipeId
    reason: str


@dataclass(frozen=True)
class AlternatePin:
    """Enable ONE alternate recipe for ONE item and make it that item's only
    producer. The single relaxation of the alternates-off rule (demand-
    expansion record Amendment 3): an alternate enters the graph only here,
    named, with a reason, and replaces every base candidate for its item.
    A `RoutePin` selects among base recipes; this one admits an alternate.
    An item may carry one or the other, never both."""

    item_id: ItemId
    recipe_id: RecipeId
    reason: str


@dataclass(frozen=True)
class RouteTable:
    """A declared recipe configuration: curated exclusions plus pins.

    The structural rules that are NOT declarations, because they follow from
    what the data is rather than from a choice, live in `graph.build`: a recipe
    produces only its primary output, a resource is a leaf, an alternate is off
    unless named. Everything that IS a choice is here, with its reason.
    """

    name: str
    exclusions: tuple[Exclusion, ...] = ()
    pins: tuple[RoutePin, ...] = ()
    alternates: tuple[AlternatePin, ...] = ()

    def __post_init__(self) -> None:
        excluded = [e.recipe_id for e in self.exclusions]
        if len(set(excluded)) != len(excluded):
            raise DeclarationError(f"{self.name}: a recipe is excluded twice")
        pinned = [p.item_id for p in self.pins]
        if len(set(pinned)) != len(pinned):
            raise DeclarationError(f"{self.name}: an item is pinned twice")
        alt_items = [a.item_id for a in self.alternates]
        if len(set(alt_items)) != len(alt_items):
            raise DeclarationError(f"{self.name}: an item carries two alternate pins")
        both = sorted(set(pinned) & set(alt_items))
        if both:
            raise DeclarationError(
                f"{self.name}: {both} carry both a RoutePin and an AlternatePin; which "
                "wins would be a choice, so it is refused"
            )
        for e in self.exclusions:
            if not e.reason.strip():
                raise DeclarationError(f"{self.name}: exclusion of {e.recipe_id} has no reason")
        for p in self.pins:
            if not p.reason.strip():
                raise DeclarationError(f"{self.name}: pin of {p.item_id} has no reason")
        for a in self.alternates:
            if not a.reason.strip():
                raise DeclarationError(f"{self.name}: alternate pin of {a.item_id} has no reason")

    def with_alternate(self, item_id: ItemId, recipe_id: RecipeId, reason: str, name: str | None = None) -> "RouteTable":
        """This table plus one alternate pin. The name gains a suffix so the
        configuration is distinguishable by name as well as by hash."""
        return RouteTable(
            name=name or f"{self.name}+{recipe_id}",
            exclusions=self.exclusions,
            pins=self.pins,
            alternates=self.alternates + (AlternatePin(item_id, recipe_id, reason),),
        )


@dataclass(frozen=True)
class Expansion:
    """Quantities per ONE unit of `target`, under one route table and scenario.

    direct          inputs of the target's own recipe, per unit of target, after
                    the scenario's per-cycle rounding. Depth 1.
    embedded        every item on every path, per unit of target, summed over
                    paths: intermediates AND resources. This is the "embedded
                    coefficient"; `embedded[Motor]` for a Thermal Propulsion
                    Rocket is the Motor question answered.
    depth           shortest path to the item, in recipe steps from the target.
    recipe_cycles   cycles of each recipe per unit of target. A machine count
                    needs a horizon and a clock; neither is here.
    coproducts      non-primary outputs of the recipes used, per unit of target.
                    Reported, never netted against demand (Amendment 1, G): a
                    byproduct is not a producer.
    fluid_rounding_unit   the variant in force when the multiplier is not 1x
                    ("mL" unless overridden, Amendment 2); meaningless, and
                    recorded as given, at 1x.

    Exact rationals throughout; the stated per-cycle counts are integers (one
    2.5 m3 fluid aside) and the game's own rounding is applied before division.
    """

    target: ItemId
    route_table: str
    recipe_input_multiplier: float
    fluid_rounding_unit: str | None
    direct: dict[ItemId, Fraction]
    embedded: dict[ItemId, Fraction]
    depth: dict[ItemId, int]
    recipe_cycles: dict[RecipeId, Fraction]
    coproducts: dict[ItemId, Fraction]
