#!/usr/bin/env python3
"""Regenerate (or check) the repository's file manifests.

Two manifests exist, with different roots and different scopes:

    REPO_MANIFEST.csv          paths relative to the repo root
    planning_data/manifest.csv paths relative to planning_data/

Both are `path,bytes,sha256`, sorted ascending by path, CRLF line endings, and
neither lists itself. Those conventions were read off the committed files and are
reproduced here exactly, so a regeneration is a content change and never a format
change.

Scope is declared below rather than inferred, because what belongs in an integrity
baseline is a judgement, not a property of the filesystem. Two subtrees are outside
it: `data/` (route-tool working directory) and `planning_data/analysis/derived/`
(recomputable products of named scripts). Both stay on disk. Leaving either decision
implicit is how a regenerator quietly grows several hundred junk rows.

Default is --check: it reports drift and writes nothing. Pass --write to rewrite.

Exit codes
    0  in sync (check), or written (write)
    1  drift detected (check only)
    2  a declared root is missing

Usage
    python tools/regenerate_manifests.py
    python tools/regenerate_manifests.py --write
    python tools/regenerate_manifests.py --only repo --check
    python tools/regenerate_manifests.py --verbose
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
CHUNK = 1 << 20

# Directory names never walked, anywhere.
SKIP_DIRS = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".venv", "venv", ".git", ".vscode", ".idea",
}
# Directory name suffixes never walked (build metadata).
SKIP_DIR_SUFFIXES = (".egg-info",)
# File name suffixes never listed.
SKIP_SUFFIXES = (".pyc", ".pyo", ".log", ".tmp")
# Exact file names never listed.
SKIP_NAMES = {".DS_Store", "Thumbs.db"}


class Manifest:
    """One manifest: where it lives, what it covers, what it is relative to."""

    def __init__(self, name, out, root, roots=None, root_files=None, exclude=()):
        self.name = name
        self.out = REPO / out          # the manifest file itself
        self.root = REPO / root        # paths in the manifest are relative to this
        self.roots = roots             # subdirectories in scope; None means "all of root"
        self.root_files = root_files   # loose files directly under root, when roots is set
        self.exclude = tuple(exclude)  # subtrees carved back out, relative to root

    def targets(self):
        """Every in-scope file, as a path relative to self.root, sorted."""
        found = []
        if self.roots is None:
            found.extend(_walk(self.root))
        else:
            for sub in self.roots:
                d = self.root / sub
                if not d.is_dir():
                    raise FileNotFoundError(f"{self.name}: declared root {sub!r} does not exist")
                found.extend(_walk(d))
            for f in self.root_files or []:
                p = self.root / f
                if p.is_file():
                    found.append(p)
        rel = {p.relative_to(self.root).as_posix() for p in found}
        for ex in self.exclude:
            ex = ex.rstrip("/") + "/"
            rel = {p for p in rel if not p.startswith(ex)}
        rel.discard(self.out.relative_to(self.root).as_posix()
                    if self.out.is_relative_to(self.root) else "")
        return sorted(rel)


# Scope, declared. Edit here, visibly, rather than teaching the walker special cases.
# Order matters: planning_data/manifest.csv is itself inside REPO_MANIFEST's scope,
# so it must be written first or a single --write leaves the repo manifest stale.
#
# `analysis/derived/` is carved out deliberately (2026-09-18). It is 1,190 MB across
# 87 files — 47% of the repository — and every one of them is a recomputable product
# of a named script over canonical inputs. Hashing it made the manifests a slow,
# perpetually-drifting record of working state rather than an integrity baseline for
# repository content. The files stay on disk; they are simply not canon.
# `data/` was already outside scope for the same reason: route-tool working directory.
MANIFESTS = [
    Manifest(
        "planning_data",
        out="planning_data/manifest.csv",
        root="planning_data",
        exclude=["analysis/derived"],
    ),
    Manifest(
        "repo",
        out="REPO_MANIFEST.csv",
        root=".",
        roots=["docs", "planning_data", "scripts", "tests", "tools"],
        root_files=[".gitattributes", ".gitignore", "README.md", "VERSIONS.json"],
        exclude=["planning_data/analysis/derived"],
    ),
]


def _walk(base: pathlib.Path):
    stack = [base]
    while stack:
        d = stack.pop()
        for entry in d.iterdir():
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name in SKIP_DIRS or entry.name.endswith(SKIP_DIR_SUFFIXES):
                    continue
                stack.append(entry)
            elif entry.is_file():
                if entry.name in SKIP_NAMES or entry.name.endswith(SKIP_SUFFIXES):
                    continue
                yield entry


def digest(path: pathlib.Path) -> tuple[int, str]:
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
            n += len(chunk)
    return n, h.hexdigest()


def read_existing(path: pathlib.Path) -> dict[str, tuple[str, str]]:
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8", newline="") as f:
        return {r["path"]: (r["bytes"], r["sha256"]) for r in csv.DictReader(f)}


def render(rows: list[tuple[str, int, str]]) -> bytes:
    """CRLF, trailing newline, matching the committed files byte for byte."""
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["path", "bytes", "sha256"])
    for path, size, sha in rows:
        w.writerow([path, size, sha])
    return buf.getvalue().encode("utf-8")


def process(m: Manifest, write: bool, verbose: bool) -> bool:
    """Returns True if the manifest was already in sync."""
    old = read_existing(m.out)
    rows = []
    for rel in m.targets():
        size, sha = digest(m.root / rel)
        rows.append((rel, size, sha))
    new = {p: (str(s), h) for p, s, h in rows}

    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(p for p in set(old) & set(new) if old[p] != new[p])
    in_sync = not (added or removed or changed)

    print(f"\n{m.name}: {m.out.relative_to(REPO).as_posix()}")
    print(f"  {len(rows)} files in scope (was {len(old)})")
    if in_sync:
        print("  in sync")
    else:
        print(f"  +{len(added)} added   -{len(removed)} removed   ~{len(changed)} changed")
        for label, items in (("+", added), ("-", removed), ("~", changed)):
            show = items if verbose else items[:5]
            for p in show:
                print(f"    {label} {p}")
            if not verbose and len(items) > len(show):
                print(f"    {label} ... and {len(items) - len(show)} more")

    if write and not in_sync:
        m.out.write_bytes(render(rows))
        print(f"  written: {len(rows)} rows")
    return in_sync


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="rewrite the manifests (default: check only)")
    ap.add_argument("--check", action="store_true", help="explicit no-op default; report drift only")
    ap.add_argument("--only", choices=[m.name for m in MANIFESTS], help="limit to one manifest")
    ap.add_argument("--verbose", action="store_true", help="list every difference, not the first five")
    args = ap.parse_args()
    if args.write and args.check:
        sys.exit("--write and --check are mutually exclusive")

    selected = [m for m in MANIFESTS if not args.only or m.name == args.only]
    try:
        results = [process(m, args.write, args.verbose) for m in selected]
    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
        return 2

    if all(results):
        print("\nAll manifests in sync.")
        return 0
    if args.write:
        print("\nManifests rewritten.")
        return 0
    print("\nDrift detected. Re-run with --write to regenerate.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
