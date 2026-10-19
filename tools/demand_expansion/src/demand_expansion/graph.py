"""The recipe graph under a route table, and the census that pins its shape.

Four structural rules live here because they follow from what the data is,
not from a choice (demand-expansion record Amendment 1, items B and G, and
Amendment 4):

    primary output   a recipe produces, for expansion purposes, only the output
                     the game lists first. Everything else it yields is a
                     coproduct: reported, never a producer. With byproducts as
                     producers Plastic "contains" Motor through a ten-step chain
                     of alternates and byproducts (plan review, 2026-10-10).
    resource leaf    a resource is never expanded and no recipe whose primary
                     output is a resource is enabled. This is record 3.1.1's
                     Converter exclusion as a rule rather than a list.
    alternates off   `is_alternate=true` recipes are never enabled by this
                     module except through an `AlternatePin`, which names
                     one alternate for one item and makes it the item's only
                     producer (Amendment 3). A run that holds one pins it.
    coproduct leaf   an item no enabled recipe makes FIRST but some enabled
                     recipe makes as a coproduct (Heavy Oil Residue from
                     Plastic and Rubber, Compacted Coal from Rocket Fuel,
                     Polymer Resin from Fuel) is a leaf: its requirement is
                     reported and not expanded. Which coproduct line covers
                     it, and what becomes of the surplus, is a planning
                     choice the engine does not make. Greg, 2026-10-10: the
                     byproduct "can be used by any recipe that needs it; the
                     HOR alt just makes more" (Amendment 4). A declared
                     alternate that makes the item first turns the leaf back
                     into an expanded item, which is exactly "makes more".

Everything that IS a choice arrives in the `RouteTable`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from production_adapter.contracts import ItemId, RecipeId
from production_adapter.gamedata import Recipe, ReferenceData

from .contracts import (
    AmbiguousRoute, DeclarationError, DemandExpansionError, RouteTable, UnproducibleItem,
)


def primary_output(recipe: Recipe) -> ItemId:
    """The first listed output. Refuses a recipe with none."""
    if not recipe.output_amounts:
        raise DeclarationError(f"{recipe.recipe_id} has no outputs in the reference layer")
    return recipe.output_amounts[0][0]


@dataclass(frozen=True)
class RecipeGraph:
    data: ReferenceData
    routes: RouteTable
    #: base recipes minus exclusions minus resource-primary recipes
    enabled: frozenset[RecipeId]
    #: item -> enabled recipes whose PRIMARY output it is, pins applied, sorted
    producers: Mapping[ItemId, tuple[RecipeId, ...]]
    #: enabled recipe -> its primary output
    primary: Mapping[RecipeId, ItemId]
    #: items with no producer that some enabled recipe makes as a coproduct
    coproduct_leaves: frozenset[ItemId] = frozenset()

    def is_resource(self, item_id: ItemId) -> bool:
        return item_id in self.data.resource_items

    def is_leaf(self, item_id: ItemId) -> bool:
        """A resource or a coproduct leaf: reported, never expanded."""
        return item_id in self.data.resource_items or item_id in self.coproduct_leaves


def build(data: ReferenceData, routes: RouteTable) -> RecipeGraph:
    """Apply a route table to CANONICAL data. Refuses a stale declaration, and
    refuses data that already carries a scenario: `expand` applies the
    scenario itself, so pre-scaled inputs would be scaled twice (a 1.25x
    Modular Engine's 3 Motors becoming 4) or reported as 1x. Found by review
    on PR #3, 2026-10-10."""
    if not data.scenario.is_canonical:
        raise DemandExpansionError(
            "demand expansion takes canonical reference data and applies the scenario "
            f"itself; this data already carries {data.scenario!r}. Load with "
            "gamedata.load(repo_root) and pass the Scenario to expand()/aggregate()."
        )
    recipes = data.recipes
    for e in routes.exclusions:
        r = recipes.get(e.recipe_id)
        if r is None:
            raise DeclarationError(
                f"{routes.name} excludes {e.recipe_id}, which is not in the reference "
                "layer. Remove the exclusion."
            )
        if r.is_alternate:
            raise DeclarationError(
                f"{routes.name} excludes {e.recipe_id}, which the data now flags as an "
                "alternate. The exclusion no longer does anything; remove it."
            )
    excluded = {e.recipe_id for e in routes.exclusions}
    enabled: set[RecipeId] = set()
    primary: dict[RecipeId, ItemId] = {}
    producers: dict[ItemId, list[RecipeId]] = {}
    for rid, r in recipes.items():
        if r.is_alternate or rid in excluded:
            continue
        p = primary_output(r)
        if p in data.resource_items:
            continue
        enabled.add(rid)
        primary[rid] = p
        producers.setdefault(p, []).append(rid)
    resolved: dict[ItemId, tuple[RecipeId, ...]] = {
        item: tuple(sorted(rs)) for item, rs in producers.items()
    }
    for alt in routes.alternates:
        r = recipes.get(alt.recipe_id)
        if r is None:
            raise DeclarationError(
                f"{routes.name} enables {alt.recipe_id}, which is not in the reference layer."
            )
        if not r.is_alternate:
            raise DeclarationError(
                f"{routes.name} enables {alt.recipe_id} as an alternate, but the data flags "
                "it base. Use a RoutePin to select among base recipes."
            )
        p = primary_output(r)
        if p != alt.item_id:
            raise DeclarationError(
                f"{routes.name} enables {alt.recipe_id} for {alt.item_id}, but its primary "
                f"output is {p}. An alternate pin names the item the recipe makes first."
            )
        if p in data.resource_items:
            raise DeclarationError(
                f"{routes.name} enables {alt.recipe_id}, whose primary output {p} is a "
                "resource. Resources are leaves; a recipe making one is never enabled."
            )
        enabled.add(alt.recipe_id)
        primary[alt.recipe_id] = p
        resolved[p] = (alt.recipe_id,)
    for pin in routes.pins:
        candidates = resolved.get(pin.item_id, ())
        if len(candidates) < 2:
            raise DeclarationError(
                f"{routes.name} pins {pin.item_id} to {pin.recipe_id}, but that item has "
                f"{len(candidates)} enabled producer(s). A pin that resolves nothing is a "
                "stale choice; remove it."
            )
        if pin.recipe_id not in candidates:
            raise DeclarationError(
                f"{routes.name} pins {pin.item_id} to {pin.recipe_id}, which is not among "
                f"its enabled producers {candidates}. A pin may only select; it cannot "
                "enable an excluded or alternate recipe."
            )
        resolved[pin.item_id] = (pin.recipe_id,)
    coproducts: set[ItemId] = set()
    for rid in enabled:
        for item, _, _ in recipes[rid].output_amounts[1:]:
            coproducts.add(item)
    leaves = frozenset(
        i for i in coproducts if i not in resolved and i not in data.resource_items
    )
    return RecipeGraph(
        data=data,
        routes=routes,
        enabled=frozenset(enabled),
        producers=resolved,
        primary=primary,
        coproduct_leaves=leaves,
    )


def route_for(graph: RecipeGraph, item_id: ItemId, path: tuple[ItemId, ...] = ()) -> RecipeId:
    """The one enabled recipe for an item, or a named refusal."""
    candidates = graph.producers.get(item_id, ())
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise UnproducibleItem(item_id, path + (item_id,))
    raise AmbiguousRoute(item_id, candidates, path + (item_id,))


def find_cycles(graph: RecipeGraph) -> tuple[tuple[ItemId, ...], ...]:
    """Strongly connected components of size > 1 (or self-loops) in the item
    graph, with an edge from each item to every input of every candidate
    recipe. A superset of what any resolution could use, so an empty result
    means no pin set can create a cycle from these producers."""
    edges: dict[ItemId, set[ItemId]] = {}
    for item, rids in graph.producers.items():
        if graph.is_leaf(item):
            continue
        for rid in rids:
            for i, _, _ in graph.data.recipes[rid].input_amounts:
                edges.setdefault(item, set()).add(i)
    index: dict[ItemId, int] = {}
    low: dict[ItemId, int] = {}
    on_stack: set[ItemId] = set()
    stack: list[ItemId] = []
    out: list[tuple[ItemId, ...]] = []
    counter = 0

    def strong(v: ItemId) -> None:
        nonlocal counter
        index[v] = low[v] = counter
        counter += 1
        stack.append(v)
        on_stack.add(v)
        for w in sorted(edges.get(v, ())):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on_stack:
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp: list[ItemId] = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.append(w)
                if w == v:
                    break
            if len(comp) > 1 or v in edges.get(v, ()):
                out.append(tuple(sorted(comp)))

    for v in sorted(edges):
        if v not in index:
            strong(v)
    return tuple(out)


@dataclass(frozen=True)
class Census:
    """The shape of the reference layer under a route table, as counts and
    names. `tests/test_demand_expansion_census.py` pins the 2026-10-10 values;
    when the data moves, the test moves with a reason."""

    recipes: int
    base_recipes: int
    alternate_recipes: int
    items: int
    resources: int
    #: items with >1 BASE recipe listing them as ANY output (the naive view)
    base_multi_producer_items: int
    #: base recipes whose primary output is a resource (the Converter rule)
    resource_primary_base_recipes: int
    enabled_recipes: int
    #: items with >1 enabled producer after pins, sorted
    ambiguous_items: tuple[ItemId, ...]
    #: byproduct-only items, reported and never expanded (Amendment 4)
    coproduct_leaves: tuple[ItemId, ...]
    cycles: tuple[tuple[ItemId, ...], ...]
    #: item ids used by any recipe that items.csv does not list, sorted
    io_items_absent_from_items: tuple[ItemId, ...]
    #: listed non-resource items no base recipe makes (as any output), sorted
    items_without_base_recipe: tuple[ItemId, ...]
    #: True when, for every recipe one of whose outputs carries the recipe's
    #: own display name, that output is listed first. The primary-output rule
    #: and the name rule agree on this build if so.
    name_match_is_first_output: bool


def census(graph: RecipeGraph) -> Census:
    data = graph.data
    base = {rid: r for rid, r in data.recipes.items() if not r.is_alternate}
    any_output: dict[ItemId, set[RecipeId]] = {}
    for rid, r in base.items():
        for i, _, _ in r.output_amounts:
            any_output.setdefault(i, set()).add(rid)
    io_items: set[ItemId] = set()
    for r in data.recipes.values():
        io_items.update(i for i, _, _ in r.input_amounts)
        io_items.update(i for i, _, _ in r.output_amounts)
    name_match_first = True
    for r in data.recipes.values():
        names = [data.items[i].display_name if i in data.items else None for i, _, _ in r.output_amounts]
        if r.display_name in names and names[0] != r.display_name:
            name_match_first = False
    return Census(
        recipes=len(data.recipes),
        base_recipes=len(base),
        alternate_recipes=len(data.recipes) - len(base),
        items=len(data.items),
        resources=len(data.resource_items),
        base_multi_producer_items=sum(1 for rs in any_output.values() if len(rs) > 1),
        resource_primary_base_recipes=sum(
            1 for r in base.values() if primary_output(r) in data.resource_items
        ),
        enabled_recipes=len(graph.enabled),
        ambiguous_items=tuple(sorted(i for i, rs in graph.producers.items() if len(rs) > 1)),
        coproduct_leaves=tuple(sorted(graph.coproduct_leaves)),
        cycles=find_cycles(graph),
        io_items_absent_from_items=tuple(sorted(io_items - set(data.items))),
        items_without_base_recipe=tuple(sorted(
            i for i in data.items
            if i not in data.resource_items and i not in any_output
        )),
        name_match_is_first_output=name_match_first,
    )
