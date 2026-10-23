#!/usr/bin/env python3
"""Resource neighborhoods: socket-centred candidate groupings of a world's
resource sockets. A world-analysis tool; it finds, it does not choose.

Handoff 2026-10-19 18:28 action 2, carried from
research/v020_site_mapper/resource_clusters.py (v0.20 site mapper, Greg's
upload of 2026-10-19). A neighborhood is a CANDIDATE, not a verified build
site, an allocation of sockets, a water supply or a traversable connection
(v0.20's own words, kept). Neighborhoods overlap; one socket can be in many.
The picker (handoff action 3) turns a chosen neighborhood into a SiteSpec by
its socket ids, and portfolio_run refuses two sites that share a socket.

    candidates   one per included socket: every included socket within
                 `radius_m` HORIZONTAL metres of it (site_card.sockets_within,
                 the definition site cards use), kept if it has at least
                 `min_nodes`
    dedupe       OPTIONAL. Walk the candidates in the declared order; drop
                 one whose socket set overlaps a kept one at Jaccard >=
                 `jaccard` AND whose seed is within `seed_distance_m` of that
                 one's seed. Without dedupe, every candidate is reported, in
                 socket file order.

Policy is declared, never defaulted (decided by Greg, 2026-10-23, on the
measured sensitivity of v0.20's 276 neighborhoods to each choice):

    include      the (source_kind, item_id) pairs that count; (kind, None)
                 means every item of that kind. A pair that matches no
                 socket in the world is refused by name
    radius_m, min_nodes
    dedupe       Dedupe(jaccard, seed_distance_m, order), all three or none.
                 Dedupe is order-dependent (the order decides which of two
                 near-duplicates survives), so the order is policy too; it
                 is named from ORDERS, and v0.20's is "most_types_first"

v0.20's settings, for regenerating its 276 (tests/test_neighborhoods.py):
radius 350, min 2, Dedupe(0.78, 175.0, "most_types_first"), include every
resource_node item but uranium, and fracking satellites and cores of Crude
Oil and Nitrogen Gas (no Water wells, no geysers). Its candidate cap (1000)
is not carried: a cap truncates by the order, and 276 never reached it.

Purity weights for "most_types_first" are the purity multipliers of
extraction_rates.csv (through gamedata.load_logistics); a purity with two
multipliers across extractors is refused rather than one picked.

    uv run python tools/neighborhoods.py --radius 350 --min-nodes 2 \\
        --include resource_node:Desc_OreIron_C ... \\
        --dedupe-jaccard 0.78 --dedupe-seed-m 175 --dedupe-order most_types_first \\
        --export neighborhoods.json
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import math
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
for _src in ("production_adapter", "progression", "realization"):
    _path = str(REPO / "tools" / _src / "src")
    if _path not in sys.path:
        sys.path.insert(0, _path)
if str(REPO / "tools") not in sys.path:
    sys.path.insert(0, str(REPO / "tools"))

from production_adapter import load  # noqa: E402
from production_adapter.gamedata import load_logistics  # noqa: E402

import site_card  # noqa: E402

#: the export's schema tag; a client checks it before reading
EXPORT_SCHEMA = "neighborhoods/1"
#: what a neighborhood is NOT (v0.20's limitations, kept)
NOT_ASSESSED = ("terrain traversability or elevation connection", "buildable platform at the seed",
                "exclusive ownership of sockets (neighborhoods overlap)", "water or shoreline access",
                "corridor, rail, tractor or truck feasibility")


class NeighborhoodError(ValueError):
    """A policy or world the tool cannot use. Refused by name."""


@dataclasses.dataclass(frozen=True)
class Dedupe:
    jaccard: float
    seed_distance_m: float
    order: str


@dataclasses.dataclass(frozen=True)
class Policy:
    include: tuple[tuple[str, str | None], ...]
    radius_m: float
    min_nodes: int
    dedupe: Dedupe | None


@dataclasses.dataclass(frozen=True)
class Neighborhood:
    seed_socket_id: str
    east_m: float
    north_m: float
    #: included sockets within the radius, in socket file order
    socket_ids: tuple[str, ...]
    #: per item, how many sockets of each purity, first-seen order
    purity_counts: tuple[tuple[str, tuple[tuple[str, int], ...]], ...]


def _most_types_first(c: Neighborhood, weight: dict[str, float]) -> tuple:
    """v0.20's order: most distinct items, then most sockets, then most
    purity-weighted sockets, then seed id (a total order, so the walk is
    reproducible). 'Distinctive mixed neighborhoods first', in its words."""
    return (-len(c.purity_counts), -len(c.socket_ids),
            -sum(weight[p] * n for _, counts in c.purity_counts for p, n in counts),
            c.seed_socket_id)


def _seed_id(c: Neighborhood, weight: dict[str, float]) -> tuple:
    return (c.seed_socket_id,)


#: the dedupe orders a caller may name; none is a default
ORDERS = {"most_types_first": _most_types_first, "seed_id": _seed_id}


def weights_from_rates(rates) -> dict[str, float]:
    """purity -> multiplier from extraction-rate rows. The same purity must
    carry one multiplier for every extractor, or it is refused."""
    out: dict[str, float] = {}
    for r in rates:
        if r.purity in out and out[r.purity] != r.purity_multiplier:
            raise NeighborhoodError(
                f"purity {r.purity!r} has multipliers {out[r.purity]} and {r.purity_multiplier} "
                "across extractors; no single weight to order by"
            )
        out[r.purity] = r.purity_multiplier
    return out


def purity_weights(repo: pathlib.Path = REPO) -> dict[str, float]:
    """weights_from_rates over extraction_rates.csv (gamedata.load_logistics)."""
    return weights_from_rates(load_logistics(repo)[1])


def _check(policy: Policy, sockets) -> None:
    if not policy.radius_m > 0.0:
        raise NeighborhoodError(f"radius must be positive, got {policy.radius_m!r}")
    if not (isinstance(policy.min_nodes, int) and policy.min_nodes >= 1):
        raise NeighborhoodError(f"min_nodes must be a positive integer, got {policy.min_nodes!r}")
    if not policy.include:
        raise NeighborhoodError("declare which sockets count (include): nothing is included by default")
    twice = [p for n, p in enumerate(policy.include) if p in policy.include[:n]]
    if twice:
        raise NeighborhoodError(f"included twice: {twice}")
    unmatched = [p for p in policy.include
                 if not any(s.source_kind == p[0] and (p[1] is None or s.item_id == p[1]) for s in sockets)]
    if unmatched:
        raise NeighborhoodError(f"include pairs that match no socket in this world: {unmatched}")
    d = policy.dedupe
    if d is not None:
        if not 0.0 < d.jaccard <= 1.0:
            raise NeighborhoodError(f"dedupe jaccard must be in (0, 1], got {d.jaccard!r}")
        if not d.seed_distance_m >= 0.0:
            raise NeighborhoodError(f"dedupe seed distance must be >= 0, got {d.seed_distance_m!r}")
        if d.order not in ORDERS:
            raise NeighborhoodError(f"no dedupe order {d.order!r}; known: {list(ORDERS)}")


def discover(sockets: tuple[site_card.Socket, ...], policy: Policy,
             weights: dict[str, float] | None = None) -> tuple[Neighborhood, ...]:
    """The neighborhoods of `sockets` under `policy` (module docstring).
    `weights` (purity_weights()) is needed only by an order that reads it."""
    _check(policy, sockets)
    pool = tuple(s for s in sockets
                 if (s.source_kind, s.item_id) in policy.include or (s.source_kind, None) in policy.include)
    by_id = {s.socket_id: s for s in pool}
    candidates = []
    for seed in pool:
        ids = site_card.sockets_within(pool, seed.east_m, seed.north_m, policy.radius_m)
        if len(ids) < policy.min_nodes:
            continue
        counts: dict[str, dict[str, int]] = {}
        for sid in ids:
            s = by_id[sid]
            per = counts.setdefault(s.item_id, {})
            per[s.purity] = per.get(s.purity, 0) + 1
        candidates.append(Neighborhood(
            seed.socket_id, seed.east_m, seed.north_m, ids,
            tuple((item, tuple(per.items())) for item, per in counts.items()),
        ))
    d = policy.dedupe
    if d is None:
        return tuple(candidates)
    if d.order == "most_types_first":
        if weights is None:
            raise NeighborhoodError("order 'most_types_first' weighs purity: pass purity_weights()")
        stray = sorted({p for c in candidates for _, per in c.purity_counts for p, _ in per} - set(weights))
        if stray:
            raise NeighborhoodError(f"purities with no multiplier in extraction_rates: {stray}")
    key = ORDERS[d.order]
    kept: list[Neighborhood] = []
    kept_sets: list[frozenset[str]] = []
    for c in sorted(candidates, key=lambda c: key(c, weights)):
        mine = frozenset(c.socket_ids)
        if any(len(mine & other) / len(mine | other) >= d.jaccard
               and math.hypot(c.east_m - k.east_m, c.north_m - k.north_m) <= d.seed_distance_m
               for k, other in zip(kept, kept_sets)):
            continue
        kept.append(c)
        kept_sets.append(mine)
    return tuple(kept)


def export_doc(neighborhoods: tuple[Neighborhood, ...], policy: Policy, sockets,
               world_config_id: str, data) -> dict:
    """One JSON document: the declared policy, the included sockets (so a
    picker or map needs no copy of the world files), and the neighborhoods."""
    used = {sid for n in neighborhoods for sid in n.socket_ids}
    items = dict.fromkeys(s.item_id for s in sockets if s.socket_id in used)
    return {
        "schema": EXPORT_SCHEMA,
        "game_build_id": data.game_build_id,
        "world_config_id": world_config_id,
        "coordinates": "repository east_m = game X; north_m = -game Y (metres)",
        "policy": {
            "include": [{"source_kind": k, "item_id": i} for k, i in policy.include],
            "radius_m": policy.radius_m, "min_nodes": policy.min_nodes,
            "dedupe": None if policy.dedupe is None else dataclasses.asdict(policy.dedupe),
        },
        "not_assessed": list(NOT_ASSESSED),
        "sockets": [dataclasses.asdict(s) for s in sockets if s.socket_id in used],
        "neighborhoods": [
            {"seed_socket_id": n.seed_socket_id, "east_m": n.east_m, "north_m": n.north_m,
             "socket_ids": list(n.socket_ids),
             "purity_counts": {item: dict(per) for item, per in n.purity_counts}}
            for n in neighborhoods
        ],
        "names": {"items": {i: data.items[i].display_name for i in items if i in data.items}},
    }


POLICY_KEYS = ("include", "radius_m", "min_nodes", "dedupe")


def policy_from_doc(doc: dict) -> Policy:
    """A Policy from the shape an export's `policy` block has, so an export
    carries a policy that can be re-run as given (the picker's recompute,
    the precomputed exports' regeneration). Every key required; unknown
    keys refused."""
    def keys(where, obj, want):
        if not isinstance(obj, dict):
            raise NeighborhoodError(f"{where}: expected an object")
        missing, extra = [k for k in want if k not in obj], [k for k in obj if k not in want]
        if missing or extra:
            raise NeighborhoodError(f"{where}: missing {missing}, not known {extra}")
    keys("policy", doc, POLICY_KEYS)
    for n, p in enumerate(doc["include"]):
        keys(f"policy.include[{n}]", p, ("source_kind", "item_id"))
    d = doc["dedupe"]
    if d is not None:
        keys("policy.dedupe", d, ("jaccard", "seed_distance_m", "order"))
    return Policy(
        include=tuple((p["source_kind"], p["item_id"]) for p in doc["include"]),
        radius_m=doc["radius_m"], min_nodes=doc["min_nodes"],
        dedupe=None if d is None else Dedupe(d["jaccard"], d["seed_distance_m"], d["order"]),
    )


def export_for(policy_doc: dict, world_config_id: str, repo: pathlib.Path = REPO) -> dict:
    """The neighborhoods/1 document for a policy document: what the CLI's
    --export writes and what the picker's in-browser recompute returns."""
    policy = policy_from_doc(policy_doc)
    sockets = site_card.load_sockets(repo, world_config_id)
    weights = purity_weights(repo) if policy.dedupe is not None else None
    return export_doc(discover(sockets, policy, weights), policy, sockets, world_config_id, load(repo))


def write_export(doc: dict, path: pathlib.Path) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")


def _include_arg(text: str) -> tuple[str, str | None]:
    kind, sep, item = text.partition(":")
    if not kind:
        raise argparse.ArgumentTypeError(f"expected KIND or KIND:ITEM_ID, got {text!r}")
    return kind, (item if sep else None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--world", default="default_502094")
    ap.add_argument("--policy", type=pathlib.Path,
                    help="a policy JSON (an export's `policy` block) instead of the flags below; "
                         "mixing it with them is refused")
    ap.add_argument("--radius", type=float, help="metres, horizontal")
    ap.add_argument("--min-nodes", type=int)
    ap.add_argument("--include", action="append", type=_include_arg,
                    help="KIND or KIND:ITEM_ID (repeat); e.g. resource_node:Desc_OreIron_C")
    ap.add_argument("--dedupe-jaccard", type=float)
    ap.add_argument("--dedupe-seed-m", type=float)
    ap.add_argument("--dedupe-order", choices=tuple(ORDERS))
    ap.add_argument("--export", type=pathlib.Path)
    args = ap.parse_args(argv)
    flags = (args.radius, args.min_nodes, args.include, args.dedupe_jaccard, args.dedupe_seed_m,
             args.dedupe_order)
    if args.policy is not None:
        if any(f is not None for f in flags):
            ap.error("--policy declares the whole policy; drop --radius/--min-nodes/--include/--dedupe-*")
        try:
            with open(args.policy, encoding="utf-8") as f:
                policy_doc = json.load(f)
        except FileNotFoundError:
            ap.error(f"--policy: no file at {args.policy}")
        except json.JSONDecodeError as exc:
            ap.error(f"--policy: {args.policy} is not JSON ({exc})")
    else:
        missing = [n for n, v in (("--radius", args.radius), ("--min-nodes", args.min_nodes),
                                  ("--include", args.include)) if v is None]
        if missing:
            ap.error(f"required without --policy: {missing}")
        parts = (args.dedupe_jaccard, args.dedupe_seed_m, args.dedupe_order)
        if any(p is not None for p in parts) and not all(p is not None for p in parts):
            ap.error("dedupe is all three of --dedupe-jaccard, --dedupe-seed-m, --dedupe-order, or none")
        policy_doc = {
            "include": [{"source_kind": k, "item_id": i} for k, i in args.include],
            "radius_m": args.radius, "min_nodes": args.min_nodes,
            "dedupe": None if parts[0] is None else
            {"jaccard": parts[0], "seed_distance_m": parts[1], "order": parts[2]},
        }
    doc = export_for(policy_doc, args.world)
    found = doc["neighborhoods"]
    print(f"{len(found)} neighborhoods, {len({s for n in found for s in n['socket_ids']})} distinct sockets"
          + ("" if policy_doc["dedupe"] is None else f"; dedupe {policy_doc['dedupe']}"))
    if args.export:
        write_export(doc, args.export)
        print(f"exported: {args.export}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
