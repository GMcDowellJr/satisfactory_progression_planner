Satisfactory Site & Logistics Planner — Repository Capability Inventory

Date: 2026-10-12
Basis: site-planning specification v1.0; GitHub GMcDowellJr/satisfactory_progression_planner master tree, AGENTS.md, architecture and component READMEs; supplied v0.20 archive docs; mobile prototype. This is a source/document inventory, not an end-to-end runtime audit.

Product assessment

The necessary substrates mostly exist, but are separated into a canonical GitHub world/progression/production repository, a standalone v0.20 site-opportunity workflow, and a Pyodide/assignable-stage prototype. Build the product layer, not a new solver.

Capability matrix

|Specification capability         |Evidence                                                                 |Status                                     |Minimal action                               |
|---------------------------------|-------------------------------------------------------------------------|-------------------------------------------|---------------------------------------------|
|Canonical game/recipe/scenario   |planning_data/game/reference; production_adapter/gamedata.py, scenario.py|Available                                  |Use sole canonical authority                 |
|World sockets/configuration      |planning_data/world; resource_authority decision                         |Available                                  |Validate socket ID/purity crosswalk          |
|Worldwide neighborhoods          |v0.20 resource_clusters.py, 276 neighborhoods                            |Available separately                       |Reconcile to repository world                |
|Local product ceilings           |v0.18 site_capability_catalog.py                                         |Partial/default recipes/material only      |Canonical coefficients and evidence labels   |
|Multi-product/site demand        |v0.18 shared_balance.py; v0.19 multi_site_portfolio.py                   |Partial                                    |User-selected mixes, shared budgets          |
|Exclusive socket ownership       |v0.19/v0.20                                                              |Available in evaluated candidate portfolios|Retain as scenario ledger                    |
|Flexible stage locations         |assignable prototype                                                     |Prototype                                  |Integrate via repo LP, preserve constraints  |
|Automated multi-site search      |v0.20 auto_multi_site_discovery.py                                       |Initial; three Phase 3 partitions          |Search complements not predefined roles      |
|Buildable site footprints        |tools/build_surface_tool v9                                              |Available as analysis                      |Link footprints to sites                     |
|Transport-neutral corridors      |tools/corridor_tool                                                      |Available                                  |Pair with candidate site relationships       |
|Mode-aware route work            |tools/satisfactory_route_tool                                            |Available as tool                          |Apply selectively, report evidence level     |
|Unlocks and phase horizon        |reference + progression tools                                            |Available substrate                        |Site eligibility and deltas                  |
|Mobile map and client            |offline SCIM HTML; Pyodide prototype                                     |Prototype/fragmented                       |One versioned site-planning response + map UI|
|Power/water/operating feasibility|production power reports, standalone energy/water studies                |Partial                                    |Conditional screen only                      |

Retain and reuse

1. production_adapter.gamedata as only reference CSV loader; Scenario for all multiplier transforms.
2. production_adapter.lp_backend/HiGHS as the sole production LP numerical implementation; if site-indexed constraints are required, extend shared formulation, do not build a second generic solver.
3. Materialized world socket geometry and assignment crosswalk.
4. Build-surface footprint geometry, corridor topology and existing route tools as independent analysis providers.
5. v0.20 worldwide neighborhood selection, site-capability ideas, socket exclusivity, transfer ledger and offline SCIM viewer concepts.
6. Pyodide as client execution option, with schema/provenance handshake and no JS recipe mathematics.

Fragmented seams

• World sockets vs v0.20 snapshots/cluster identifiers.
• v0.20 recursive recipe expansion vs canonical scenario-transformed recipe coefficients.
• Neighborhoods vs buildable footprints vs corridor access as candidate-site evidence.
• Role-partitioned discovery vs free stage assignment and shared resource ledger.
• v0.18–v0.20 bespoke HTML/JSON formats vs mobile client protocol.
• Aggregate production solver and experimental spatial LP formulation.

Keep outside initial product workflow

• Machine counts, clock/shard selection, belt/pipe placement and factory floorplans.
• Exact build orders, time-phased optimization and playthrough schedule.
• Exhaustive all-pairs route solving; detailed hydraulics and disposal mechanics.
• Desktop VTK interface as mandatory mobile dependency (retain as QA).
• Rewriting production math and complex numerical reoptimization without a geographic decision payoff.
These modules can remain in the repository; ‘outside initial workflow’ does not imply deletion.

Minimum viable worldwide integration (vertical slice)

1. Site Index: normalized site_id, candidate geometry, socket IDs, resource type/purity/rate, height difference, build-surface reference, evidence metadata. Regenerate from repo materialized world and adapt 276 v0.20 neighborhoods; log unresolved joins.
2. Opportunity Catalog: phase/product/family, canonical transformed input coefficients, local material upper bound, binding resource, missing inputs, alternate-recipe dependency, utilization/residuals; do not claim operating feasibility.
3. Relationship Explorer: for a selected site/product, find candidate suppliers for a missing resource/intermediate; return alternative stage placements with shared socket ownership and explicit directional transfer; allow heuristic bounded selection and mark search coverage.
4. Connection Overlay: selected transfer site pairs map to straight-line/unresolved/candidate/recovered corridor evidence via existing tools, not assumed roads.
5. Mobile SCIM Map: tap site, see opportunities/resources/limitations; choose product, reveal complementary sites; inspect 2–3 alternative networks; compare evidence and route burden. Render stable site/opportunity/flow/connection records from Python JSON; use Pyodide for targeted recalculations and precomputed catalogs for world browsing.

Product acceptance gates

• RC219: Oil/Plastic opportunity visible despite Copper-limited local Computers, with complementary Electronics site proposed.
• Mixed Iron/Coal/Limestone/Caterium site: several eligible products, shared budget, no double counting.
• Alternate Computer placement: moving Plastic changes stage location and explicit flow, without a fixed role template.
• Two selected overlapping neighborhoods cannot both claim one socket.
• Unverified route is not drawn as verified; vertical separation affects evidence without automatic exclusion.
• 1x / 1.25x / 2x scenarios use repo rounded recipe inputs with diagnostic provenance.
• Desktop Python and Pyodide accept same versioned request and return compatible result schemas.

Delivery stages

Stage A: Site Index + canonical opportunity catalog + mobile map of worldwide opportunities. This is the first useful release and needs no generalized multi-site optimizer.
Stage B: Simple complementary-site and directional transfer exploration on selected sites; integrate existing spatial LP only when necessary for shared allocation.
Stage C: competing uses, progression comparisons and route evidence overlays.
Stage D: conditional operating screening (power/water/disposal) where it changes site choices.

Constraints and unknowns

Current master repository inspected via connected GitHub, but end-to-end integration, generated data currency, browser performance, and site crosswalk consistency have not been executed in this assessment. Do not equate presence of modules with verified current artifacts. v0.20 has 276 overlapping neighborhoods and 12 saved candidate portfolios by its own documentation; these are not 276 verified build sites nor 12 physically feasible factory networks. Repo and v0.20 appear to use different snapshots; join coverage must be measured.