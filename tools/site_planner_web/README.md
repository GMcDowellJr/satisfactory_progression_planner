# Site planner web pages

Three static pages and a Web Worker that runs this repo's own Python in the
browser (Pyodide 0.27.7 from the CDN). Decisions: reframe record
(`docs/decisions/site_planner_reframe.md`), Amendments 10 and 20.

    picker.html    pick neighborhoods as sites, declare the run, then save the
                   portfolio-inputs/2 file or run it here
    index.html     render a portfolio-plan/1 record (from the picker's run, or
                   a file from `portfolio_run.py --export`)
    planner.html   the run and factory tracks (A20), in tabs: Playthrough
                   (milestones, research, alternates, scenario, generators
                   built and mix), Run (run-inputs/1 -> run-plan/1), Hand-off
                   (a neighborhood as the site, every factory declaration),
                   Factory (factory-inputs/1 -> factory-plan/1)
    worker.js      Pyodide: neighborhoods recompute, portfolio runs, and the
                   planner's ops (catalog, tier, generators, run_plan, handoff,
                   factory)
    precomputed/   precomputed neighborhood exports, the picker's starting
                   point (v0.20 policy: policy_v020.json -> neighborhoods_v020.json),
                   and the picker's base map (basemap_502094.png + .json)
    basemap.py     cuts the base map from the terrain raster in
                   planning_data/world/spatial/heightmap_build_502094
    bundle.py      traces the repo files the worker needs -> bundle_files.json
    publish.py     copies the pages + bundle into a static site (Netlify's dist/)

## Run locally

The worker fetches repo files, so serve the **repo root** over http
(`file://` can open both pages and files, but cannot run Python):

    python -m http.server 8000

then open `http://localhost:8000/tools/site_planner_web/picker.html` (portfolio)
or `.../planner.html` (run and factory). From a
phone on the same network, use the machine's LAN address instead of
localhost. The first run starts Python (about 7 s in the container); later
runs take a fraction of a second.

## Hosted (reframe A20.7)

- **Netlify:** `netlify.toml` builds the demand-expansion viewer, then runs
  `publish.py --out dist`, which copies these pages and exactly the files in
  `bundle_files.json` at their repo paths. Each pull request gets a deploy
  preview; open `<preview>/tools/site_planner_web/planner.html`.
- **GitHub Pages:** Settings → Pages → Deploy from a branch → root. The root
  `.nojekyll` keeps the `__init__.py` files. Open
  `https://gmcdowelljr.github.io/satisfactory_progression_planner/tools/site_planner_web/planner.html`.

## Keep the derived files in step

All three are checked by `tests/test_site_planner_web.py`:

    uv run python tools/neighborhoods.py --policy tools/site_planner_web/precomputed/policy_v020.json --export tools/site_planner_web/precomputed/neighborhoods_v020.json
    uv run python tools/site_planner_web/bundle.py --write
    uv run python tools/site_planner_web/basemap.py --write
