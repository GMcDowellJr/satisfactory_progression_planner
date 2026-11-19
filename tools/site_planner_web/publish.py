#!/usr/bin/env python3
"""Copy the site planner pages, and exactly the files their worker fetches, into a static site.

Hosting decided by Greg, 2026-11-18 (reframe A20.7): Netlify, with deploy
previews per pull request, and GitHub Pages. The worker (worker.js) fetches
`bundle_files.json`'s paths relative to the repo root, so a host must keep the
repo layout. Netlify publishes `dist/`; this writes into it:

    dist/tools/site_planner_web/   the pages, worker.js, bundle_files.json,
                                   precomputed/ (every .html .js .json .png here)
    dist/<path>                    every path in bundle_files.json (bundle.py
                                   traces it from the code; nothing listed by hand)

The demand-expansion viewer stays at dist/index.html (netlify.toml builds it
first). A path in the list that is missing is refused by name, never skipped:
the worker would fail on it in the browser otherwise.

GitHub Pages serves the repo root from a branch instead (no build), so it needs
only `.nojekyll` at the root: without it Jekyll drops every file whose name
starts with "_", including the bundle's __init__.py files.

Standard library only: Netlify's build runs it with `uv run --no-project`.

    python tools/site_planner_web/publish.py --out dist
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
#: what the pages themselves need from tools/site_planner_web (no .py: the
#: worker's Python comes from bundle_files.json)
PAGE_SUFFIXES = (".html", ".js", ".json", ".png")


class PublishError(RuntimeError):
    """A file the published site needs is missing."""


def site_files() -> list[str]:
    """Repo-relative paths: the pages' own files, then the worker's bundle."""
    pages = {p.relative_to(REPO).as_posix() for p in HERE.rglob("*")
             if p.is_file() and p.suffix in PAGE_SUFFIXES and "__pycache__" not in p.parts}
    with open(HERE / "bundle_files.json", encoding="utf-8") as f:
        bundle = set(json.load(f))
    return sorted(pages | bundle)


def publish(out: pathlib.Path) -> list[str]:
    files = site_files()
    missing = [rel for rel in files if not (REPO / rel).is_file()]
    if missing:
        raise PublishError(f"files the site needs are missing: {missing}")
    for rel in files:
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, dst)
    return files


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True, type=pathlib.Path, help="the static site directory")
    args = ap.parse_args(argv)
    files = publish(args.out)
    print(f"published {len(files)} files to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
