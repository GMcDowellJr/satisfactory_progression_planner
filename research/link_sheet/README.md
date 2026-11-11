# Link sheet: what moves between sites, and what carrying it takes (research)

Site planner reframe, Amendment 13. Research drivers, not tools: no test
covers them, and `p4_run.py` makes choices the tool layers refuse (see its
docstring). The solver change they rely on, `PortfolioRequest.target_scale`,
is tool code with tests (`tests/test_portfolio_solve.py`).

    p4_run.py       each Project Assembly phase-4 part at 1/min, solved over
                    per-raw sites (the most-capacity single-raw neighborhood
                    per raw, more while the draw is over capacity) with
                    target_scale 1.0 -> p4_run.json
    link_sheet.py   per directed site pair: items, stacks/min, straight and
                    corridor distance, belt and pipe share per open mark,
                    and per vehicle the round-trip budget and the average
                    speed that budget needs -> p4_links.json
    p4_run.json     checked in; regenerate with the first command below
    p4_links.json   checked in; needs the corridor graph, which is gitignored

Run from the repo root:

    uv run python -I research/link_sheet/p4_run.py --out research/link_sheet/p4_run.json
    uv run --with pandas --with scikit-image python scripts/generate_corridors.py
    uv run --with pandas --with scikit-image python -I research/link_sheet/link_sheet.py \
        research/link_sheet/p4_run.json --out research/link_sheet/p4_links.json

pandas and scikit-image are the corridor tool's own dependencies
(`tools/corridor_tool/pyproject.toml`), passed with `--with`, not added to the
dev group.

## Reading it

- **Nothing is chosen.** The sheet shows every open belt mark and every
  vehicle; the player picks. Vehicle speeds are not in the repo's sources, so
  the sheet gives the speed a single vehicle would NEED, not a verdict.
- **The plan is placement-blind.** Transfers are free in the solve (A1 P3) and
  the only locality term is volume (P5), so which site makes which
  intermediate is the solver's, not geography's. The sheet prices that plan;
  it does not say the plan is a sensible layout.
- **Corridor distance is terrain connectivity** (`corridors_v1`, 16 m step),
  not a belt, road or rail route. A site whose seed snaps into a different
  graph component gets no corridor distance (`unresolved`, with the reason).
- A transfer can print as 0.000 at three decimals: the solver keeps flows over
  its tolerance, and the record keeps exact values.
