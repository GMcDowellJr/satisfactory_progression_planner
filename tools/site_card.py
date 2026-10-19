#!/usr/bin/env python3
"""The site card: what can be made at a site, and what limits it.

First slice of the site-planner reframe (docs/decisions/site_planner_reframe.md;
spec v1.0 proposed, F2 "local manufacturing opportunity"). Status under the
reframe's vocabulary: UNDER CONSIDERATION (handoff 2026-10-19 12:35, action 1),
not adopted. A joint above several packages, so it lives at tools/ root like
district_run.py. No new solver, no new arithmetic on recipes:

    sockets   world_resource_sockets.csv joined to a world configuration's
              resource_assignments.csv on socket_id; an unjoined row refuses
    site      socket ids as given, or every socket within a horizontal radius
              of a point (file order, no ranking)
    nodes     one NodeCount per socket, its extractor class DECLARED per
              (source_kind, item) or per source_kind; fracking cores and
              geothermal geysers are listed as not extracted, with the reason
    caps      progression.district.resource_caps: the site is closed, every
              raw it has no socket for is capped at 0. A declared supply
              (Water, which no socket carries) is added to its cap by name
    reach     progression.district.discover over the tier's recipes: which
              products the site can make at all, and for the rest the raws
              every enabled chain would need
    ceiling   one LpBackend.solve_district per makeable product, that product
              the only target: its MATERIAL CEILING alone, the caps it binds
              and their shadow prices, and the draw on every cap
    hints     for each product NOT makeable with the held recipes (tier base
              + declared), every single alternate not held that alone makes
              it makeable, tagged pool / later band / after MAM research from
              progression.pool. Reachability only; pairs are not tried
    pool      --compare-pool: the ceilings again with the tier's automatic
              pool added, beside the held ones. Every pool alternate at once,
              so an upper bound on what the drives at this tier could open

"Held" vs "pool" is Greg's framing (2026-10-19): what this site is with the
alternates I have, and what it could be with the ones I could get.

**Ceilings are alternatives, not a portfolio.** Each product's ceiling is the
whole site's supply given to that product alone. Two ceilings on one cap
cannot both be had; summing them double-counts the supply. The card says so
in its report and record. Competing products sharing the supply at once is a
portfolio solve (spec F3), which this slice does not make.

**Status `material_bound` (spec F7).** Power, belts, pipes, routing, node
reachability and buildable area are not assessed. Power stays outside the
solve (D5); that is the spec's "later conditional screen", not a default.

**It cannot choose, and that is the guardrail.** Extractor classes, the
extraction clock, the recipe tier and declared recipes, the scenario, the
tie-break goal and any declared supply are inputs. No min, max or sort here
(asserted by tests/test_site_card.py): sockets list in file order, caps in
declaration order, products in items.csv order.

    uv run python tools/site_card.py --at 1234 -567 --radius 500 --tier 5 \\
        --extractor resource_node=Build_MinerMk1_C \\
        --extractor resource_node:Desc_LiquidOil_C=Build_OilPump_C
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import math
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _src in ("production_adapter", "progression", "realization"):
    _path = str(REPO / "tools" / _src / "src")
    if _path not in sys.path:
        sys.path.insert(0, _path)

from production_adapter import (  # noqa: E402
    DistrictRequest, DistrictTarget, ResourceCap, Scenario, Weights, load,
)
from production_adapter.gamedata import ReferenceData, load_logistics  # noqa: E402
from production_adapter.lp_backend import Infeasible, LpBackend, PowerStatistic, Unbounded  # noqa: E402
from progression import (  # noqa: E402
    DistrictDefinition, NodeCount, at_tier, available_at, discover, recipe_ids_by_name,
    resource_caps, resources_in_reference_order,
)

WORLD = pathlib.Path("planning_data") / "world"
SOCKETS_CSV = WORLD / "canonical" / "world_resource_sockets.csv"
CARD_STATUS = "material_bound"
#: spec F7: named, never implied
NOT_ASSESSED = ("power", "belts", "pipes", "routing", "node reachability", "buildable area")
#: socket kinds that hold no extractor of their own, and why
NOT_EXTRACTED = {
    "fracking_core": "a resource well core activates its satellites; it extracts nothing itself",
    "geothermal_geyser": "a power source, not a material supply",
}
#: a cap is "drawn fully" within this fraction of itself (the pins' 1e-9
#: relative slack, with 1000x room; the solver's activity guard uses the same)
BINDING_RELATIVE = 1.0e-6
#: tie-break goals, the same four district_run.GOALS restates
GOALS = {
    "balanced": Weights(),
    "resources": Weights(resources=1.0, power=0.0, buildings=0.0),
    "power": Weights(resources=0.0, power=1.0, buildings=0.0),
    "buildings": Weights(resources=0.0, power=0.0, buildings=1.0),
}


class SiteCardError(ValueError):
    """A site, socket or declaration the card cannot use. Refused by name."""


# -- world sockets ------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Socket:
    """A world socket joined to its assignment in one world configuration."""

    socket_id: str
    source_kind: str          # resource_node | fracking_satellite | fracking_core | geothermal_geyser
    item_id: str | None       # None: the assignment names no resource (a geyser)
    purity: str
    east_m: float
    north_m: float
    elevation_m: float
    core_socket_id: str | None


def join_sockets(socket_rows, assignment_rows, world_config_id: str) -> tuple[Socket, ...]:
    """Join on socket_id, in socket-file order. A socket with no assignment row
    for `world_config_id`, an assignment for an unknown socket, or a socket
    assigned twice is refused: a site built on a half-joined world would
    report supply nobody can locate."""
    assigned: dict[str, dict] = {}
    for row in assignment_rows:
        if row["world_config_id"] != world_config_id:
            continue
        if row["socket_id"] in assigned:
            raise SiteCardError(f"{world_config_id}: {row['socket_id']} is assigned twice")
        assigned[row["socket_id"]] = row
    out: list[Socket] = []
    seen: set[str] = set()
    for row in socket_rows:
        sid = row["socket_id"]
        a = assigned.get(sid)
        if a is None:
            raise SiteCardError(f"{world_config_id}: socket {sid} has no assignment row")
        seen.add(sid)
        out.append(Socket(
            socket_id=sid, source_kind=row["source_kind"],
            item_id=a["resource_descriptor"] or None, purity=a["purity"],
            east_m=float(row["east_m"]), north_m=float(row["north_m"]),
            elevation_m=float(row["elevation_m"]),
            core_socket_id=row["core_socket_id"] or None,
        ))
    stray = [sid for sid in assigned if sid not in seen]
    if stray:
        raise SiteCardError(f"{world_config_id}: assignments for unknown sockets: {stray}")
    return tuple(out)


def load_sockets(repo: pathlib.Path, world_config_id: str) -> tuple[Socket, ...]:
    path = repo / WORLD / "configurations" / world_config_id / "resource_assignments.csv"
    if not path.exists():
        raise SiteCardError(f"no world configuration {world_config_id!r}: {path} does not exist")
    with open(repo / SOCKETS_CSV, encoding="utf-8", newline="") as f:
        sockets = list(csv.DictReader(f))
    with open(path, encoding="utf-8", newline="") as f:
        assignments = list(csv.DictReader(f))
    return join_sockets(sockets, assignments, world_config_id)


def sockets_within(
    sockets: tuple[Socket, ...], east_m: float, north_m: float, radius_m: float,
) -> tuple[str, ...]:
    """Socket ids whose HORIZONTAL distance from the point is at most the
    radius, in file order. Elevation is not a filter (spec F1: vertical
    separation is a friction factor, not an exclusion); the card lists it."""
    if not radius_m > 0.0:
        raise SiteCardError(f"radius must be positive, got {radius_m!r}")
    return tuple(
        s.socket_id for s in sockets
        if math.hypot(s.east_m - east_m, s.north_m - north_m) <= radius_m
    )


# -- the site -----------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class SiteSpec:
    """A site as DECLARED: its sockets and how they are worked.

    `extractors` maps (source_kind, item_id) or (source_kind, None) to an
    extractor class; the exact pair wins, then the kind. A socket whose pair
    and kind are both unmapped is refused: an Oil node is not a Miner's.
    `supply` is a declared rate per minute for a raw no socket carries
    (Water); it is added to that raw's cap and listed as declared."""

    label: str
    socket_ids: tuple[str, ...]
    extractors: tuple[tuple[tuple[str, str | None], str], ...]
    extraction_clock: float
    reserve_fraction: float = 0.0
    supply: tuple[tuple[str, float], ...] = ()


def _extractor_for(spec: SiteSpec, socket: Socket) -> str:
    table = dict(spec.extractors)
    cls = table.get((socket.source_kind, socket.item_id)) or table.get((socket.source_kind, None))
    if cls is None:
        raise SiteCardError(
            f"{socket.socket_id}: no extractor declared for ({socket.source_kind}, {socket.item_id})"
        )
    return cls


def site_nodes(
    sockets: tuple[Socket, ...], spec: SiteSpec,
) -> tuple[tuple[Socket, ...], tuple[NodeCount, ...], tuple[tuple[str, str], ...]]:
    """The site's sockets (spec order), one NodeCount per extracted socket, and
    the sockets not extracted with the reason. An unknown or repeated socket id
    refuses; a site with nothing to extract refuses."""
    if not spec.socket_ids:
        raise SiteCardError(f"{spec.label}: a site needs at least one socket")
    by_id = {s.socket_id: s for s in sockets}
    repeated = [sid for n, sid in enumerate(spec.socket_ids) if sid in spec.socket_ids[:n]]
    if repeated:
        raise SiteCardError(f"{spec.label}: sockets listed twice: {repeated}")
    unknown = [sid for sid in spec.socket_ids if sid not in by_id]
    if unknown:
        raise SiteCardError(f"{spec.label}: unknown sockets: {unknown}")
    chosen = tuple(by_id[sid] for sid in spec.socket_ids)
    nodes: list[NodeCount] = []
    skipped: list[tuple[str, str]] = []
    for s in chosen:
        if s.source_kind in NOT_EXTRACTED:
            skipped.append((s.socket_id, NOT_EXTRACTED[s.source_kind]))
            continue
        if s.item_id is None:
            raise SiteCardError(f"{s.socket_id}: a {s.source_kind} with no resource assigned")
        nodes.append(NodeCount(s.item_id, s.purity, 1, extractor_class=_extractor_for(spec, s)))
    if not nodes:
        raise SiteCardError(f"{spec.label}: none of its sockets is extracted: {skipped}")
    return chosen, tuple(nodes), tuple(skipped)


def with_supply(
    caps: tuple[ResourceCap, ...], supply: tuple[tuple[str, float], ...],
) -> tuple[ResourceCap, ...]:
    """Add each declared supply to its raw's cap. A supply on an item with no
    cap row (not a raw resource) or at a rate <= 0 is refused."""
    by_item = {c.item_id: c.rate_per_min for c in caps}
    for item, rate in supply:
        if item not in by_item:
            raise SiteCardError(f"declared supply {item}: not a raw resource the caps list")
        if not rate > 0.0:
            raise SiteCardError(f"declared supply {item}: rate {rate!r} must be positive")
        by_item[item] = by_item[item] + rate
    return tuple(ResourceCap(c.item_id, by_item[c.item_id]) for c in caps)


def site_caps(spec: SiteSpec, data: ReferenceData, rates, sockets: tuple[Socket, ...]):
    """(sockets, nodes, not extracted, definition, caps) for one declared site.
    Shared by the card and tools/portfolio_run.py. `rates` is
    `gamedata.load_logistics(repo)[1]`."""
    chosen, nodes, skipped = site_nodes(sockets, spec)
    # every node carries its own extractor class, so the definition's is never
    # read; it is the first node's only because the type requires one
    definition = DistrictDefinition(
        nodes=nodes, extractor_class=nodes[0].extractor_class,
        extraction_clock=spec.extraction_clock, reserve_fraction=spec.reserve_fraction,
        label=spec.label,
    )
    caps = with_supply(
        resource_caps(definition, rates, resources_in_reference_order(data)), spec.supply,
    )
    return chosen, nodes, skipped, definition, caps


# -- the card -----------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class CapUse:
    item_id: str
    cap_per_min: float
    draw_per_min: float
    residual_per_min: float
    binding: bool
    #: product ceiling per extra unit/min of this cap; None when not binding
    shadow_price: float | None


@dataclasses.dataclass(frozen=True)
class Opportunity:
    """One makeable product's ceiling ALONE. Not an operating promise (F2)."""

    item_id: str
    ceiling_per_min: float | None
    #: every positive cap, declaration order: draw, residual, binding
    caps: tuple[CapUse, ...]
    #: set instead of a ceiling when the solve refused, by its own message
    error: str | None = None


#: where an alternate the player does not hold would come from (progression.pool)
POOL_NOW, LATER_BAND, MAM_RESEARCH, UNCLASSIFIED = (
    "pool", "later band", "after MAM research", "unclassified",
)


@dataclasses.dataclass(frozen=True)
class Unreachable:
    item_id: str
    #: raws every enabled chain would need that the site does not have
    missing_raws: tuple[str, ...]
    #: single alternates NOT held, each of which alone makes the item makeable
    #: here, with where it comes from: (recipe_id, POOL_NOW | LATER_BAND |
    #: MAM_RESEARCH | UNCLASSIFIED). recipes.csv order. Pairs are not tried
    opened_by: tuple[tuple[str, str], ...] = ()


@dataclasses.dataclass(frozen=True)
class SiteCard:
    spec: SiteSpec
    world_config_id: str
    game_build_id: str
    scenario: Scenario
    tier: int
    declared_recipes: tuple[str, ...]
    goal: str
    sockets: tuple[Socket, ...]
    not_extracted: tuple[tuple[str, str], ...]
    nodes: tuple[NodeCount, ...]
    caps: tuple[ResourceCap, ...]
    opportunities: tuple[Opportunity, ...]
    unreachable: tuple[Unreachable, ...]
    #: --compare-pool: the same products under held + this tier's automatic
    #: pool, items.csv order; None when not asked for. MAM-research alternates
    #: are not in it (progression.pool: an advisory, not a filter)
    pool_opportunities: tuple[Opportunity, ...] | None = None
    #: the pool alternates the comparison added (not already held)
    pool_added: tuple[str, ...] = ()
    status: str = CARD_STATUS
    not_assessed: tuple[str, ...] = NOT_ASSESSED
    ceilings_are_alternatives: bool = True


def tier_products(data: ReferenceData, recipe_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Every non-raw item an enabled recipe outputs, in items.csv order."""
    made = {i for r in recipe_ids for i, _ in data.recipes[r].outputs}
    return tuple(i for i in data.items if i in made and i not in data.resource_items)


def _ceilings(
    backend: LpBackend, data: ReferenceData, items: tuple[str, ...],
    allowed, caps: tuple[ResourceCap, ...], weights: Weights,
) -> tuple[Opportunity, ...]:
    """One solve_district per item, that item the only target."""
    positive = tuple(c for c in caps if c.rate_per_min > 0.0)
    out: list[Opportunity] = []
    for item in items:
        request = DistrictRequest(
            targets=(DistrictTarget(item, weight=1.0),),
            allowed_recipes=allowed, resource_caps=caps, weights=weights,
        )
        try:
            response = backend.solve_district(request, data)
        except (Infeasible, Unbounded) as e:
            out.append(Opportunity(item, None, (), error=str(e)))
            continue
        draw = {r.item_id: r.rate_per_min for r in response.plan.raw_inputs}
        # Binding is read from the FINAL plan's draw. `response.binding` comes
        # from the first-stage vertex, where unconsumed=FREE lets an unused raw
        # be drawn to its cap and left over: Crude Oil "binding" at 0/1020 for
        # Iron Plate (measured 2026-10-19). The shadow price is still the
        # solver's, None where it listed none. "On the cap" is relative: each
        # lexicographic pin allows 1e-9 of the objective, and four stages left
        # Plastic's oil draw 1.02e-6 under 1020 (measured 2026-10-19)
        price = {b.item_id: b.shadow_price for b in response.binding}
        out.append(Opportunity(
            item_id=item,
            ceiling_per_min=response.targets[0].rate_per_min,
            caps=tuple(
                CapUse(
                    item_id=c.item_id, cap_per_min=c.rate_per_min,
                    draw_per_min=draw.get(c.item_id, 0.0),
                    residual_per_min=c.rate_per_min - draw.get(c.item_id, 0.0),
                    binding=draw.get(c.item_id, 0.0)
                    >= c.rate_per_min * (1.0 - BINDING_RELATIVE) - backend.tolerance,
                    shadow_price=price.get(c.item_id),
                )
                for c in positive
            ),
        ))
    return tuple(out)


def _source(recipe_id: str, pool) -> str:
    if recipe_id in pool.recipe_ids:
        return POOL_NOW
    if recipe_id in pool.not_yet:
        return LATER_BAND
    if recipe_id in pool.research_gated:
        return MAM_RESEARCH
    return UNCLASSIFIED


def unlock_hints(
    data: ReferenceData, held: tuple[str, ...], candidates: tuple[str, ...],
    caps: tuple[ResourceCap, ...], items: tuple[str, ...],
) -> dict[str, tuple[str, ...]]:
    """For each of `items`, the candidate recipes that ALONE make it makeable
    when added to `held`: one discover() closure per candidate, no LP and no
    choice among them. Candidates in the order given; pairs are not tried, so
    an item that needs two alternates at once lists none."""
    opened: dict[str, list[str]] = {i: [] for i in items}
    for rid in candidates:
        for x in discover(data, held + (rid,), caps, items):
            if x.makeable:
                opened[x.item_id].append(rid)
    return {i: tuple(r) for i, r in opened.items()}


def build_card(
    spec: SiteSpec, *, tier: int, scenario: Scenario, goal: str,
    power_statistic: PowerStatistic, declared_recipe_names: tuple[str, ...] = (),
    world_config_id: str = "default_502094", products: tuple[str, ...] | None = None,
    compare_pool: bool = False, repo: pathlib.Path = REPO,
) -> SiteCard:
    """Compose the card. `products` None: every product the tier can make
    anywhere with the held recipes, or with the pool too when `compare_pool`;
    otherwise those item ids, each refused if no recipe in that set outputs it.

    Held = the tier's base recipes + the declared ones: what the player has.
    Every unreachable product gets its unlock hints over ALL alternates not
    held, each tagged pool / later band / MAM research (progression.pool).
    `compare_pool` adds a second pass of ceilings under held + this tier's
    automatic pool: what the site could be with the alternates obtainable now.
    """
    if goal not in GOALS:
        raise SiteCardError(f"no goal {goal!r}; known: {list(GOALS)}")
    data = load(repo, scenario)
    _, rates = load_logistics(repo)
    sockets, nodes, skipped, _, caps = site_caps(
        spec, data, rates, load_sockets(repo, world_config_id),
    )
    declared = recipe_ids_by_name(data, declared_recipe_names)
    held = at_tier(repo, tier, declared=declared)
    wider = at_tier(repo, tier, declared=declared, include_pool=True) if compare_pool else None
    candidates = tier_products(data, (wider or held).recipe_ids)
    if products is not None:
        stray = [i for i in products if i not in candidates]
        if stray:
            raise SiteCardError(f"no recipe enabled at tier {tier} outputs {stray}")
        candidates = products
    reach = discover(data, held.recipe_ids, caps, candidates)

    backend = LpBackend(power_statistic=power_statistic)
    makeable = tuple(x.item_id for x in reach if x.makeable)
    opportunities = _ceilings(backend, data, makeable, held.allowed_recipes, caps, GOALS[goal])

    blocked = tuple(x for x in reach if not x.makeable)
    pool = available_at(repo, tier)
    not_held = tuple(r for r in data.recipes if r in held.withheld_alternates)
    hints = unlock_hints(data, held.recipe_ids, not_held, caps, tuple(x.item_id for x in blocked))
    unreachable = tuple(
        Unreachable(
            x.item_id, x.missing_raws,
            opened_by=tuple((r, _source(r, pool)) for r in hints[x.item_id]),
        )
        for x in blocked
    )

    pool_opps, added = None, ()
    if wider is not None:
        wider_reach = discover(data, wider.recipe_ids, caps, candidates)
        pool_opps = _ceilings(
            backend, data, tuple(x.item_id for x in wider_reach if x.makeable),
            wider.allowed_recipes, caps, GOALS[goal],
        )
        added = tuple(r for r in wider.recipe_ids if r not in held.recipe_ids)
    return SiteCard(
        spec=spec, world_config_id=world_config_id, game_build_id=data.game_build_id,
        scenario=data.scenario, tier=tier, declared_recipes=declared, goal=goal,
        sockets=sockets, not_extracted=skipped, nodes=nodes, caps=caps,
        opportunities=opportunities, unreachable=unreachable,
        pool_opportunities=pool_opps, pool_added=added,
    )


# -- report -------------------------------------------------------------------

def _name(data: ReferenceData, item_id: str | None) -> str:
    if item_id is None:
        return "-"
    item = data.items.get(item_id)
    return item.display_name if item else item_id


def report(card: SiteCard, data: ReferenceData) -> str:
    sc = card.scenario
    out = [
        f"site card: {card.spec.label}",
        f"  world {card.world_config_id}, game build {card.game_build_id}; tier {card.tier}"
        f" + {len(card.declared_recipes)} declared recipes; recipe x{sc.recipe_input_multiplier:g}",
        f"  extraction clock {card.spec.extraction_clock:.0%}, reserve "
        f"{card.spec.reserve_fraction:.0%}; goal {card.goal!r} breaks ties only",
        f"  status {card.status}: not assessed: " + ", ".join(card.not_assessed),
        "", f"sockets ({len(card.sockets)}, as listed)",
    ]
    for s in card.sockets:
        out.append(f"  {s.socket_id:52s} {s.source_kind:18s} {_name(data, s.item_id):14s} "
                   f"{s.purity:7s} elev {s.elevation_m:8.1f} m")
    for sid, why in card.not_extracted:
        out.append(f"  not extracted: {sid}: {why}")
    out += ["", "caps (declaration order; every other raw is capped at 0: the site is closed)"]
    declared = dict(card.spec.supply)
    for c in card.caps:
        if c.rate_per_min > 0.0:
            tag = f"  (includes declared supply {declared[c.item_id]:g})" if c.item_id in declared else ""
            out.append(f"  {_name(data, c.item_id):18s} {c.rate_per_min:9.2f}/min{tag}")
    out += ["", f"opportunities ({len(card.opportunities)}, items.csv order). Each ceiling is the "
            "whole site given to that product ALONE:",
            "  ceilings are alternatives, not additive; two on one cap cannot both be had"]
    for o in card.opportunities:
        if o.error is not None:
            out.append(f"  {_name(data, o.item_id):30s} refused: {o.error}")
            continue
        binds = "; ".join(
            f"{_name(data, u.item_id)} {u.cap_per_min:g}/min"
            + ("" if u.shadow_price is None else f" (shadow {u.shadow_price + 0.0:.4g})")
            for u in o.caps if u.binding
        ) or "no cap binds"
        out.append(f"  {_name(data, o.item_id):30s} {o.ceiling_per_min:10.3f}/min  limited by: {binds}")
    out += ["", f"not makeable here with the held recipes ({len(card.unreachable)}): the raws every "
            "held chain needs, then any single alternate not held that would open it alone"]
    for u in card.unreachable:
        out.append(f"  {_name(data, u.item_id):30s} needs "
                   + (", ".join(_name(data, i) for i in u.missing_raws)
                      or "an input that is not a socket resource (none named)"))
        if u.opened_by:
            out.append("  " + " " * 30 + " or one of: " + "; ".join(
                f"{data.recipes[r].display_name} [{src}]" for r, src in u.opened_by))
    out.append("  (pairs of alternates are not tried: an item that needs two at once lists none)")
    if card.pool_opportunities is not None:
        out += _pool_section(card, data)
    return "\n".join(out)


def _pool_section(card: SiteCard, data: ReferenceData) -> list[str]:
    """Held vs held + this tier's automatic pool, items.csv order of the wider pass."""
    held = {o.item_id: o for o in card.opportunities}
    out = ["", f"with this tier's automatic pool added ({len(card.pool_added)} alternates not held; "
           "MAM-research alternates excluded): ceiling held -> with pool",
           "  every pool alternate at once: an upper bound, each is a separate hard-drive pull"]
    for o in card.pool_opportunities:
        before = held.get(o.item_id)
        was = "not makeable" if before is None else (
            "refused" if before.ceiling_per_min is None else f"{before.ceiling_per_min:10.3f}")
        if o.error is not None:
            out.append(f"  {_name(data, o.item_id):30s} {was:>12s} -> refused: {o.error}")
            continue
        changed = before is None or before.ceiling_per_min is None or \
            abs(o.ceiling_per_min - before.ceiling_per_min) > 1e-6 * (1.0 + abs(o.ceiling_per_min))
        limits = ", ".join(_name(data, u.item_id) for u in o.caps if u.binding) or "no cap binds"
        out.append(f"  {_name(data, o.item_id):30s} {was:>12s} -> {o.ceiling_per_min:10.3f}/min"
                   f"  {'CHANGED' if changed else '       '}  limited by: {limits}")
    return out


def _extractor_arg(text: str) -> tuple[tuple[str, str | None], str]:
    key, sep, cls = text.partition("=")
    if not sep or not cls:
        raise argparse.ArgumentTypeError(f"expected KIND[:ITEM]=CLASS, got {text!r}")
    kind, _, item = key.partition(":")
    return (kind, item or None), cls


def _supply_arg(text: str) -> tuple[str, float]:
    item, sep, rate = text.partition("=")
    if not sep:
        raise argparse.ArgumentTypeError(f"expected ITEM=RATE, got {text!r}")
    return item, float(rate)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    where = ap.add_mutually_exclusive_group(required=True)
    where.add_argument("--sockets", help="comma-separated socket ids")
    where.add_argument("--at", nargs=2, type=float, metavar=("EAST_M", "NORTH_M"))
    ap.add_argument("--radius", type=float, help="metres, horizontal; with --at")
    ap.add_argument("--label", default=None)
    ap.add_argument("--world", default="default_502094")
    ap.add_argument("--tier", type=int, required=True)
    ap.add_argument("--recipe", action="append", default=[], help="declared recipe display name")
    ap.add_argument("--extractor", action="append", type=_extractor_arg, required=True,
                    help="KIND[:ITEM]=EXTRACTOR_CLASS, e.g. resource_node=Build_MinerMk1_C")
    ap.add_argument("--clock", type=float, required=True, help="extraction clock, 1.0 = 100%%")
    ap.add_argument("--supply", action="append", type=_supply_arg, default=[],
                    help="ITEM=RATE declared supply no socket carries, e.g. Desc_Water_C=240")
    ap.add_argument("--recipe-multiplier", type=float, required=True)
    ap.add_argument("--goal", default="balanced", choices=tuple(GOALS))
    ap.add_argument("--product", action="append", default=None, help="limit to these item ids")
    ap.add_argument("--compare-pool", action="store_true",
                    help="also solve with this tier's automatic alternate pool added")
    args = ap.parse_args(argv)
    if args.at is not None and args.radius is None:
        ap.error("--at needs --radius")
    if args.at is None and args.radius is not None:
        ap.error("--radius applies only with --at")
    if args.sockets:
        ids = tuple(s.strip() for s in args.sockets.split(",") if s.strip())
        label = args.label or f"{len(ids)} sockets"
    else:
        ids = sockets_within(load_sockets(REPO, args.world), args.at[0], args.at[1], args.radius)
        label = args.label or f"({args.at[0]:g}, {args.at[1]:g}) r {args.radius:g} m"
    spec = SiteSpec(label=label, socket_ids=ids, extractors=tuple(args.extractor),
                    extraction_clock=args.clock, supply=tuple(args.supply))
    scenario = Scenario(recipe_input_multiplier=args.recipe_multiplier)
    card = build_card(
        spec, tier=args.tier, scenario=scenario, goal=args.goal,
        power_statistic=PowerStatistic.MEAN, declared_recipe_names=tuple(args.recipe),
        world_config_id=args.world,
        products=None if args.product is None else tuple(args.product),
        compare_pool=args.compare_pool,
    )
    print(report(card, load(REPO, scenario)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
