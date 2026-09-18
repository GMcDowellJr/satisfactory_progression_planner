"""Export per-save POI collected state for Satisfactory Navigator (state contract v1).

This is a PLAYTHROUGH-STATE export. It reads one .sav, joins what the save records
against the canonical POI table, and writes a sparse list of collected POI ids.
It does not order POIs, judge reachability, or restate positions (those live in the
catalog).

Rules, as observed on build 502094 saves (2026-09-17); expect revision:
  * Every POI type: collected if the save lists it as destroyed. The join key is
    (level cell, actor leaf name), matching exploration_pois.csv source_cell and
    the leaf of source_object_id.
  * crash_site additionally: collected if the saved pod actor carries
    mHasBeenLooted = true (a looted pod can remain standing).
  * A POI with neither record is treated as available. A pod in a cell no save has
    streamed has no record, and cannot have been looted without being streamed.

Save selection: saves whose header session name equals --session (case-insensitive),
newest by header save time. This is the latest save on disk, which may not be the save
the player loads.

The save parser is `pioneersav` from a local SatisfactoryMCP checkout (read-only use).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCHEMA_VERSION = 1
STATE_KIND = "satisfactory_navigator_poi_state"
DEFAULT_MCP_SRC = Path.home() / "Documents" / "SatisfactoryMCP" / "src"
LOOTED_PROPERTY = "mHasBeenLooted"
OPENED_PROPERTY = "mHasBeenOpened"
DROP_POD_TYPE_SUFFIX = "/BP_DropPod.BP_DropPod_C"
RULES = {
    "all_types": "collected if listed in the save's destroyed actors, joined on (cell, leaf)",
    "crash_site": f"also collected if the saved pod actor has {LOOTED_PROPERTY}=true",
    "default": "no record -> available",
}
_BRANCH_LEN_ERROR = re.compile(r"archive header read (\d+) bytes, expected \d+ \(branch string")
_NET_EPOCH = dt.datetime(1, 1, 1, tzinfo=dt.timezone.utc)


# ---------------------------------------------------------------- save access

def load_pioneersav(mcp_src: Path):
    if not (mcp_src / "pioneersav" / "__init__.py").is_file():
        raise SystemExit(f"pioneersav not found under {mcp_src}; pass --mcp-src or set SATISFACTORY_MCP_SRC")
    if str(mcp_src) not in sys.path:
        sys.path.insert(0, str(mcp_src))
    import pioneersav  # noqa: PLC0415
    return pioneersav


def read_save(ps, path: Path):
    """read_full_save, tolerating a changed archive-header branch length.

    pioneersav (as of the 2026-09-10 checkout) asserts a 59-byte archive header. The
    1.2 'anniversary' branch string is longer, so the first mismatch is adopted once,
    for this process, and reported. Any other parse error propagates.
    """
    try:
        return ps.read_full_save(path), None
    except ps.ParseError as exc:
        m = _BRANCH_LEN_ERROR.search(str(exc))
        if not m:
            raise
        from pioneersav import objects  # noqa: PLC0415
        objects.ARCHIVE_HEADER_LEN = int(m.group(1))
        note = f"pioneersav archive header length adjusted to {m.group(1)} bytes for this run"
        return ps.read_full_save(path), note


def default_saves_root() -> Path:
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "FactoryGame" / "Saved" / "SaveGames"


def select_save(ps, saves_root: Path, session: str) -> tuple[Path, object]:
    wanted = session.casefold()
    best = None
    for path in sorted(saves_root.rglob("*.sav")):
        try:
            info = ps.read_info(path)
        except Exception:  # noqa: BLE001 - unreadable/foreign .sav files are skipped
            continue
        if (info.session_name or "").casefold() != wanted:
            continue
        if best is None or info.save_datetime_ticks > best[1].save_datetime_ticks:
            best = (path, info)
    if best is None:
        raise SystemExit(f"no save with session name {session!r} under {saves_root}")
    return best


def ticks_to_iso(ticks: int) -> str:
    return (_NET_EPOCH + dt.timedelta(microseconds=ticks // 10)).isoformat(timespec="seconds")


def session_file_token(session: str) -> str:
    """File-name token for a session. The mod must apply the same rule."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", session)


# ---------------------------------------------------------------- state derivation

def leaf(path: str) -> str:
    return str(path).rsplit(".", 1)[-1]


def _props(obj) -> dict:
    out = {}
    for entry in getattr(obj, "properties", None) or []:
        if len(entry) >= 2:
            out[entry[0]] = entry[1]
    return out


def pod_flags(save) -> dict[tuple[str, str], dict]:
    """(cell, leaf) -> {'opened': bool, 'looted': bool} for every saved drop-pod actor."""
    flags: dict[tuple[str, str], dict] = {}
    for level in save.levels:
        for header, obj in zip(level.headers, level.objects):
            if not str(getattr(header, "type_path", "")).endswith(DROP_POD_TYPE_SUFFIX):
                continue
            p = _props(obj)
            flags[(level.name, leaf(header.instance_name))] = {
                "opened": bool(p.get(OPENED_PROPERTY)),
                "looted": bool(p.get(LOOTED_PROPERTY)),
            }
    return flags


def load_poi_index(path: Path) -> dict[tuple[str, str], dict]:
    index: dict[tuple[str, str], dict] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["source_cell"], leaf(r["source_object_id"]))
            if key in index:
                raise SystemExit(f"duplicate (cell, leaf) key in POI table: {key}")
            index[key] = r
    return index


def derive_state(poi_index: dict, destroyed: list[tuple[str, str]], pods: dict) -> dict:
    destroyed_keys = {(cell, leaf(path)) for cell, path in destroyed}
    collected: dict[str, str] = {}
    opened_not_looted: list[str] = []
    for key, row in poi_index.items():
        pid = row["poi_id"]
        if key in destroyed_keys:
            collected[pid] = "destroyed"
        elif row["poi_type"] == "crash_site" and key in pods:
            if pods[key]["looted"]:
                collected[pid] = "looted_flag"
            elif pods[key]["opened"]:
                opened_not_looted.append(pid)

    totals = Counter(r["poi_type"] for r in poi_index.values())
    got = Counter(poi_index_row["poi_type"] for poi_index_row in poi_index.values()
                  if poi_index_row["poi_id"] in collected)
    counts = {
        t: {"total": totals[t], "collected": got[t], "available": totals[t] - got[t]}
        for t in sorted(totals)
    }
    matched = len({k for k in destroyed_keys if k in poi_index})
    return {
        "collected": sorted(collected),
        "collected_reason": {pid: collected[pid] for pid in sorted(collected)},
        "opened_not_looted": sorted(opened_not_looted),
        "counts": counts,
        "diagnostics": {
            "destroyed_records": len(destroyed_keys),
            "destroyed_matched_to_pois": matched,
            "saved_drop_pod_actors": len(pods),
        },
    }


def build_state(poi_index: dict, pois_sha: str, save_path: Path, info, save, notes: list[str]) -> dict:
    derived = derive_state(poi_index, save.destroyed_actors, pod_flags(save))
    return {
        "schema_version": SCHEMA_VERSION,
        "state_kind": STATE_KIND,
        "world_build_cl": int(info.build_version),
        "pois_source_sha256": pois_sha,
        "save": {
            "file_name": save_path.name,
            "session_name": info.session_name,
            "session_file_token": session_file_token(info.session_name),
            "save_identifier": info.save_identifier,
            "save_time_utc": ticks_to_iso(info.save_datetime_ticks),
            "play_duration_s": int(info.play_duration_s),
            "selection": "newest save by header time with this session name; may differ from the save actually loaded",
        },
        "rules": RULES,
        "notes": notes,
        **derived,
    }


# ---------------------------------------------------------------- cli

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (ROOT / p).resolve()


def default_out_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "FactoryGame" / "Saved" / "SatisfactoryNavigator"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--session", help="header session name, e.g. test (newest matching save is used)")
    g.add_argument("--save", type=Path, help="explicit .sav path")
    p.add_argument("--saves-root", type=Path, default=None)
    p.add_argument("--pois", default="planning_data/world/canonical/exploration_pois.csv")
    p.add_argument("--mcp-src", type=Path, default=Path(os.environ.get("SATISFACTORY_MCP_SRC", DEFAULT_MCP_SRC)))
    p.add_argument("--out-dir", type=Path, default=None, help="default: %%LOCALAPPDATA%%/FactoryGame/Saved/SatisfactoryNavigator")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ps = load_pioneersav(args.mcp_src)

    if args.save:
        save_path = args.save
        info = ps.read_info(save_path)
    else:
        save_path, info = select_save(ps, args.saves_root or default_saves_root(), args.session)

    save, note = read_save(ps, save_path)
    notes = [note] if note else []
    notes.extend(f"parser warning at {off}: {what}" for off, what in (save.warnings or [])[:20])

    pois_path = resolve(args.pois)
    state = build_state(load_poi_index(pois_path), sha256_file(pois_path), save_path, info, save, notes)

    out_dir = args.out_dir or default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"poi_state.{state['save']['session_file_token']}.json"
    with out.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")

    summary = ", ".join(f"{t} {c['collected']}/{c['total']}" for t, c in state["counts"].items())
    print(f"{save_path.name} ({state['save']['save_time_utc']}): collected {summary}")
    for n in notes:
        print(f"note: {n}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
