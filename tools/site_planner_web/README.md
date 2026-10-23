# Site planner web pages

Two static pages and a Web Worker that runs this repo's own Python in the
browser (Pyodide 0.27.7 from the CDN). Decisions: reframe record
(`docs/decisions/site_planner_reframe.md`), Amendment 10.

    picker.html    pick neighborhoods as sites, declare the run, then save the
                   portfolio-inputs/2 file or run it here
    index.html     render a portfolio-plan/1 record (from the picker's run, or
                   a file from `portfolio_run.py --export`)
    worker.js      Pyodide: neighborhoods recompute and portfolio runs
    precomputed/   precomputed neighborhood exports, the picker's starting
                   point (v0.20 policy: policy_v020.json -> neighborhoods_v020.json),
                   and the picker's base map (basemap_502094.png + .json)
    basemap.py     cuts the base map from the terrain raster in
                   planning_data/world/spatial/heightmap_build_502094
    bundle.py      traces the repo files the worker needs -> bundle_files.json

## Run locally

The worker fetches repo files, so serve the **repo root** over http
(`file://` can open both pages and files, but cannot run Python):

    python -m http.server 8000

then open `http://localhost:8000/tools/site_planner_web/picker.html`. From a
phone on the same network, use the machine's LAN address instead of
localhost. The first run starts Python (about 7 s in the container); later
runs take a fraction of a second.

## Keep the derived files in step

All three are checked by `tests/test_site_planner_web.py`:

    uv run python tools/neighborhoods.py --policy tools/site_planner_web/precomputed/policy_v020.json --export tools/site_planner_web/precomputed/neighborhoods_v020.json
    uv run python tools/site_planner_web/bundle.py --write
    uv run python tools/site_planner_web/basemap.py --write
