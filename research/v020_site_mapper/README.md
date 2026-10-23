# v0.20 site mapper: resource neighborhoods (provenance)

Kept for provenance, like `research/production_solver_evaluation`. Not wired
into any tool and not covered by a decision. Handoff 2026-10-19 18:28,
action 2 proposes bringing neighborhoods into the repo as a world-analysis
tool; until Greg picks that up, this is the source to start from.

## Source

From `site_logistics_opportunity_mapper_consolidated_v0_20_auto_multisite.zip`
(`site_mapper_v018/`), attached by Greg 2026-10-19. Only these three files are
carried; the rest of the archive (catalogs on Mk.2 / 1x / Phase 3 role
templates, viewers, the embedded SCIM map image) is exploration history and
stays out. The map image comes from satisfactory-calculator.com (third
party), so it is not committed to this public repo.

    resource_clusters.py         sha256 of the original 5ecb866ba20f70c4...;
                                 two lines changed, see below
    resource_first_clusters.json the saved output, verbatim
    resource_first_clusters.csv  the saved output; CRLF line ends -> LF

Changes from the original: the JSON `write_text` gained `newline='\n'` and
the `csv.DictWriter` gained `lineterminator='\n'`, so the script passes
`tests/test_writers_emit_lf.py`. No other change.

## Measured

2026-10-19 18:25 (container, master 6da07ee, the original) and again
2026-10-23 (container, this copy, on claude/portfolio-record dd93be3, whose
world data is master's):

- The script reads the repo's own world files:
  `planning_data/world/canonical/world_resource_sockets.csv` and
  `planning_data/world/configurations/default_502094/resource_assignments.csv`.
- Saved output: 276 neighborhoods, 522 distinct sockets; 0 missing from the
  repo's sockets or assignments.
- `python research/v020_site_mapper/resource_clusters.py --repo . --output X
  --csv Y` with its own defaults (radius 350 m, max 1000 candidates, overlap
  dedupe 0.78, min 2 nodes) writes JSON and CSV byte-identical to the saved
  files.

## What it is, in its own words

"A resource neighborhood is a candidate opportunity, not a verified build
site, resource allocation, water supply, or traversable connection."
Neighborhoods overlap; one socket can be in several. The radius, dedupe
threshold and minimum node count are policy: carried into a repo tool, they
would be declared inputs, not defaults (AGENTS.md "Layers report; they don't
choose").

Coordinates: repository `east_m` = game X; `north_m` = -game Y.
