#!/usr/bin/env python3
"""Inline build.py's JSON and the picker's base map into page_template.html.

Research, not tools (site planner reframe A14). The output is the Site links
page as published; it is a build product, not checked in (out/ is ignored).

    uv run --with pandas --with scikit-image python scripts/generate_corridors.py
    uv run --with pandas --with scikit-image python -I research/site_links/build.py --out research/site_links/out/site_links.json
    uv run python -I research/site_links/page.py research/site_links/out/site_links.json --out research/site_links/out/site-links.html
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASEMAP = REPO / "tools/site_planner_web/precomputed/basemap_502094.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("data", type=pathlib.Path)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    a = ap.parse_args(argv)
    d = json.loads(a.data.read_text(encoding="utf-8"))
    bm = json.loads(BASEMAP.read_text(encoding="utf-8"))
    d["basemap"] = {k: bm[k] for k in ("x_m", "y_m", "width_m", "height_m")}
    png = (BASEMAP.parent / bm["image"]).read_bytes()
    d["img"] = "data:image/png;base64," + base64.b64encode(png).decode()
    page = (HERE / "page_template.html").read_text(encoding="utf-8").replace(
        "__DATA__", json.dumps(d, separators=(",", ":")))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(page, encoding="utf-8", newline="\n")
    print(f"{a.out} {len(page) / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
