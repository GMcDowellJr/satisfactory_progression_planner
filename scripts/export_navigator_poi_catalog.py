"""Export the Satisfactory Navigator POI catalog (client contract v2).

This is a CLIENT-EXPORT tool.  It projects canonical world facts into the
runtime frame the in-game mod uses.  It does not order POIs, choose routes,
decide reachability, or assert collected state.

Contract summary (see planning_data/schema/navigator_poi_catalog_v2.schema.json):
  * location_cm is Unreal world space: x = east_m*100, y = -north_m*100,
    z = elevation_m*100.
  * match_key is source_object_id after the first ':'; the mod compares it to
    the same suffix of AActor::GetPathName().
  * state is always "unknown" in this version; no save reader is wired in.
  * foot_topology_facts (optional, --foot-facts) are raw snap facts, not a
    reachability or safety judgement.

Output is deterministic for identical inputs (no timestamps).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCHEMA_VERSION = 2
CATALOG_KIND = "satisfactory_navigator_poi_catalog"
COORD_FRAME = {
    "name": "ue_world_cm",
    "x": "east_m * 100",
    "y": "-north_m * 100",
    "z": "elevation_m * 100",
}
MATCH_KEY_RULE = "substring after the first ':' of source_object_id; compare to the same substring of AActor::GetPathName()"

TYPE_LABELS = {
    "crash_site": "Crash Site",
    "somersloop": "Somersloop",
    "mercer_sphere": "Mercer Sphere",
    "power_slug_blue": "Blue Power Slug",
    "power_slug_yellow": "Yellow Power Slug",
    "power_slug_purple": "Purple Power Slug",
}

# Runtime evidence for match_key + coord_frame, by poi_type.  Only types listed
# here are marked match_verified=true.  Extend only with new runtime evidence.
RUNTIME_VERIFICATION = {
    "crash_site": {
        "status": "verified",
        "game_build": "++FactoryGame+rel-main-anniversary-2026-CL-502094",
        "evidence": "FactoryGame.log 2026-09-16: 29/29 loaded BP_DropPod_C actors matched by match_key; max coordinate error 0.05 cm",
    },
}

POI_FIELDS_REQUIRED = [
    "poi_id", "poi_type", "source_object_id", "source_class",
    "east_m", "north_m", "elevation_m", "source_game_build", "source_sha256",
]


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (ROOT / p).resolve()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def match_key(source_object_id: str) -> str:
    if ":" not in source_object_id:
        raise ValueError(f"source_object_id has no ':' separator: {source_object_id!r}")
    key = source_object_id.split(":", 1)[1]
    if not key:
        raise ValueError(f"empty match_key for {source_object_id!r}")
    return key


def to_ue_cm(east_m: float, north_m: float, elevation_m: float) -> dict[str, float]:
    return {
        "x": round(east_m * 100.0, 3),
        "y": round(-north_m * 100.0, 3) + 0.0,  # normalize -0.0
        "z": round(elevation_m * 100.0, 3),
    }


def make_label(poi_type: str, poi_id: str) -> str:
    tail = poi_id.rsplit("_", 1)[-1]
    return f"{TYPE_LABELS.get(poi_type, poi_type)} {tail}"


def _float(row: dict, field: str) -> float:
    value = float(row[field])
    if not math.isfinite(value):
        raise ValueError(f"{row['poi_id']}: non-finite {field}")
    return value


def load_pois(path: Path, types: set[str] | None) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [c for c in POI_FIELDS_REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"{path}: missing columns {missing}")
        rows = list(reader)
    if types is not None:
        unknown = types - {r["poi_type"] for r in rows}
        if unknown:
            raise SystemExit(f"--types not present in source: {sorted(unknown)}")
        rows = [r for r in rows if r["poi_type"] in types]
    return rows


def load_foot_facts(path: Path) -> dict[str, dict]:
    facts: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["snap_status"] != "SNAPPED":
                facts[r["poi_id"]] = {"snap_status": r["snap_status"]}
                continue
            rank = int(r["global_component_rank"])
            facts[r["poi_id"]] = {
                "snap_status": r["snap_status"],
                "global_component_rank": rank,
                "primary_network_member": rank == 1,
                "snap_spatial_distance_m": round(float(r["snap_spatial_distance_m"]), 3),
                "snap_dz_m": round(float(r["snap_dz_m"]), 3),
            }
    return facts


def build_catalog(rows: list[dict], sources: list[dict], foot_facts: dict[str, dict] | None) -> dict:
    builds = {r["source_game_build"] for r in rows}
    if len(builds) != 1:
        raise SystemExit(f"expected one source_game_build, found {sorted(builds)}")
    world_build = builds.pop()

    pois = []
    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    for r in sorted(rows, key=lambda r: r["poi_id"]):
        pid = r["poi_id"]
        key = match_key(r["source_object_id"])
        if pid in seen_ids:
            raise SystemExit(f"duplicate poi_id {pid}")
        if key in seen_keys:
            raise SystemExit(f"duplicate match_key {key}")
        seen_ids.add(pid)
        seen_keys.add(key)

        poi = {
            "id": pid,
            "type": r["poi_type"],
            "label": make_label(r["poi_type"], pid),
            "match_key": key,
            "source_object_id": r["source_object_id"],
            "source_class": r["source_class"],
            "location_cm": to_ue_cm(_float(r, "east_m"), _float(r, "north_m"), _float(r, "elevation_m")),
            "match_verified": r["poi_type"] in RUNTIME_VERIFICATION,
            "state": "unknown",
        }
        if foot_facts is not None:
            if pid not in foot_facts:
                raise SystemExit(f"{pid}: missing from foot snap facts")
            poi["foot_topology_facts"] = foot_facts[pid]
        pois.append(poi)

    counts = Counter(p["type"] for p in pois)
    return {
        "schema_version": SCHEMA_VERSION,
        "catalog_kind": CATALOG_KIND,
        "world_build": world_build,
        "coord_frame": COORD_FRAME,
        "match_key_rule": MATCH_KEY_RULE,
        "state_source": None,
        "runtime_verification": {t: RUNTIME_VERIFICATION[t] for t in sorted(RUNTIME_VERIFICATION)},
        "foot_topology_facts_note": (
            None if foot_facts is None else
            "Raw nearest-3D snap facts from foot topology (2 m clearance, bridges forbidden). "
            "Not a reachability or safety judgement; do not filter on these."
        ),
        "sources": sources,
        "counts": {t: counts[t] for t in sorted(counts)},
        "pois": pois,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pois", default="planning_data/world/canonical/exploration_pois.csv")
    p.add_argument("--types", nargs="+", default=None, help="poi_type filter (default: all)")
    p.add_argument("--foot-facts", action="store_true", help="attach raw foot-topology snap facts")
    p.add_argument("--foot-snap", default="planning_data/analysis/derived/foot_exploration_data/poi_topology_snap.csv")
    p.add_argument("--out", default="planning_data/exports/satisfactory_navigator/poi_catalog.v2.json")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    pois_path = resolve(args.pois)
    rows = load_pois(pois_path, set(args.types) if args.types else None)
    if not rows:
        raise SystemExit("no POIs selected")

    sources = [{"role": "pois", "path": args.pois.replace("\\", "/"), "sha256": sha256_file(pois_path)}]
    foot_facts = None
    if args.foot_facts:
        snap_path = resolve(args.foot_snap)
        foot_facts = load_foot_facts(snap_path)
        sources.append({"role": "foot_snap", "path": args.foot_snap.replace("\\", "/"), "sha256": sha256_file(snap_path)})

    catalog = build_catalog(rows, sources, foot_facts)

    out = resolve(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        f.write("\n")

    summary = ", ".join(f"{t}={n}" for t, n in catalog["counts"].items())
    print(f"wrote {len(catalog['pois'])} POIs ({summary}) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
