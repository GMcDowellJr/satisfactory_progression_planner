# demand_expansion

The LP record §11 shared module, placed and named by demand-expansion record
Amendment 1 (decided by Greg, 2026-10-10). It expands a declared target into
item quantities per unit of that target, under a declared route table and a
declared scenario, and keeps the coefficient at every intermediate part, so
"Motors per Thermal Propulsion Rocket" is a lookup, not a derivation.

    contracts      typed results and the named refusals
    declarations   the route table: curated exclusions and pins, each with a reason
    graph          enabled recipes, primary outputs, producers, the census
    expand         the engine: per-unit coefficients, depth, recipe cycles, coproducts
    aggregate      deliveries x expansions -> per item per phase: incremental,
                   cumulative, remaining, growth; refused deliveries listed,
                   their phase marked incomplete
    report         datasets A and B as rows, provenance, a Markdown report;
                   writes nothing. tools/demand_expansion_cli.py writes.
    sensitivity    dataset C: one alternate against the base table, every
                   source x target that changes; the sweep over all 110.
                   Never a score or an order (record §5.5).
    viewer         the self-contained page's data: reference facts, the
                   route table, the alternates list, and this engine's results
                   as the oracle the page's JavaScript port checks itself
                   against at every load. The page is viewer/template.html;
                   the CLI's `viewer` writes it.

What it does not do, by construction: choose a recipe (an item with several
enabled producers is refused by name), decide rates (quantities only; no
horizon), optimise alternates, or read a file (all data via `gamedata.load`).

    docs/demand_expansion/SPECIFICATION.md     the contract
    docs/demand_expansion/VALIDATION.md        the independently derived fixtures
