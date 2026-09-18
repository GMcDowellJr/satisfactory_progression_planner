#!/usr/bin/env python3
"""Verify the pinned game Docs snapshot, and detect a game patch.

Two things are checked:

  1. The repo-local snapshot at `repo_copy_path` still hashes to the pin. This is
     what makes the reference layer reproducible without the game installed, so a
     mismatch here is corruption, not a patch.
  2. The live file in the game install, when reachable. A mismatch there means the
     game has been patched and every derived table is stale.

Exit codes
    0  OK       snapshot verified; live install matches, or is simply not present here
    1  DRIFT    live install differs from the pin — the game has been patched
    2  MISSING  nothing verifiable: no snapshot and no reachable live file
                (also returned with --require-live when the live file is absent)
    3  STAMP    the stamp is malformed, or the repo snapshot does not match it

Usage
    python tools/check_game_docs_provenance.py
    python tools/check_game_docs_provenance.py --path "D:/SteamLibrary/.../en-US.json"
    SATISFACTORY_DOCS=/path/to/en-US.json python tools/check_game_docs_provenance.py
    python tools/check_game_docs_provenance.py --require-live    # CI on a game machine

    --restamp   after reviewing a DRIFT, record the live file as the new pin. Does
                NOT re-derive anything and does NOT replace the snapshot; it only
                updates the stamp, and says what is still owed.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
STAMP = REPO / "planning_data" / "provenance" / "game_docs_source.csv"
BUILDS = REPO / "planning_data" / "game" / "reference" / "game_builds.csv"
CHUNK = 1 << 20

OK, DRIFT, MISSING, STAMP_ERR = 0, 1, 2, 3

DERIVED = [
    "planning_data/game/reference/recipes.csv",
    "planning_data/game/reference/recipe_io.csv",
    "planning_data/game/reference/recipe_producers.csv",
    "planning_data/game/reference/items.csv",
    "planning_data/game/reference/production_buildings.csv",
    "planning_data/game/reference/recipe_variable_power.csv",
    "planning_data/game/reference/extraction_buildings.csv",
    "planning_data/game/reference/extraction_rates.csv",
    "planning_data/game/reference/resource_extraction_map.csv",
]


def sha256_of(path: pathlib.Path) -> tuple[str, int]:
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def read_stamp() -> dict:
    with open(STAMP, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        sys.exit(f"STAMP: expected exactly one pinned source in {STAMP}, found {len(rows)}")
    row = rows[0]
    expected = "docs_" + row["sha256"][:12]
    if row["game_build_id"] != expected:
        sys.exit(f"STAMP: game_build_id {row['game_build_id']} does not derive from sha256 "
                 f"(expected {expected})")
    with open(BUILDS, encoding="utf-8") as f:
        known = {r["game_build_id"] for r in csv.DictReader(f)}
    if row["game_build_id"] not in known:
        sys.exit(f"STAMP: {row['game_build_id']} is not registered in game_builds.csv")
    return row


def check_snapshot(stamp: dict) -> bool | None:
    """True verified, False corrupt, None not configured/absent."""
    rel = (stamp.get("repo_copy_path") or "").strip()
    if not rel:
        print("snapshot      : none recorded")
        return None
    path = REPO / rel
    if not path.is_file():
        print(f"snapshot      : MISSING at {rel}")
        return None
    sha, size = sha256_of(path)
    if sha == stamp["sha256"]:
        print(f"snapshot      : OK   {rel} ({size} bytes)")
        return True
    print(f"snapshot      : CORRUPT {rel}")
    print(f"                expected {stamp['sha256']}")
    print(f"                found    {sha}")
    return False


def restamp(stamp: dict, path: pathlib.Path, sha: str, size: int) -> None:
    new = dict(stamp)
    new["game_build_id"] = "docs_" + sha[:12]
    new["sha256"] = sha
    new["bytes"] = str(size)
    new["source_path"] = str(path)
    new["mtime_utc"] = datetime.datetime.utcfromtimestamp(
        path.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%SZ")
    new["captured_on"] = datetime.date.today().isoformat()
    new["repo_copy_path"] = ""
    with open(STAMP, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(new))
        w.writeheader()
        w.writerow(new)
    print(f"\nrestamped -> {new['game_build_id']}")
    print("Still owed, none of which this did for you:")
    print(f"  1. copy the new file to planning_data/game/source_snapshots/{new['game_build_id']}/")
    print("     and set repo_copy_path to it (it was cleared, not repointed)")
    print("  2. add a row for the new build to game_builds.csv")
    print("  3. re-derive and re-reconcile every table listed above")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", help="override the stamped live-install path")
    ap.add_argument("--require-live", action="store_true",
                    help="treat an unreachable live install as a failure")
    ap.add_argument("--restamp", action="store_true",
                    help="record the live file as the new pin")
    args = ap.parse_args()

    stamp = read_stamp()
    print(f"stamped build : {stamp['game_build_id']}  ({stamp['bytes']} bytes, "
          f"captured {stamp['captured_on']})")
    snapshot = check_snapshot(stamp)
    if snapshot is False:
        print("\nThe repo snapshot no longer matches the pin. Restore it from the game "
              "install or from version control before trusting any derived table.")
        return STAMP_ERR

    live = pathlib.Path(args.path or os.environ.get("SATISFACTORY_DOCS") or stamp["source_path"])
    print(f"live install  : {live}")

    if not live.is_file():
        print("                not reachable here")
        if args.require_live:
            print("MISSING: --require-live was set.")
            return MISSING
        if snapshot:
            print("\nOK: snapshot verified. A game patch cannot be detected from this machine — "
                  "run this where the game is installed to check for one.")
            return OK
        print("MISSING: no snapshot and no live file; nothing could be verified.")
        print("         Pass --path or set SATISFACTORY_DOCS if the game lives elsewhere.")
        return MISSING

    sha, size = sha256_of(live)
    if sha == stamp["sha256"]:
        print(f"                OK   {sha}")
        print("\nOK: derived tables are current for this game build.")
        return OK

    print(f"                DRIFT {sha}")
    print(f"       stamped        {stamp['sha256']}")
    print(f"       live build would be docs_{sha[:12]} ({size} bytes vs {stamp['bytes']})")
    print("\nThe game has been patched. The snapshot still pins the build these tables were "
          "derived from, so nothing is lost — but every table below now describes an older "
          "game and must be re-derived and re-reconciled:")
    for p in DERIVED:
        print(f"  {p}")
    if args.restamp:
        restamp(stamp, live, sha, size)
    else:
        print("\nRe-run with --restamp once you have re-derived, to record the new pin.")
    return DRIFT


if __name__ == "__main__":
    sys.exit(main())
