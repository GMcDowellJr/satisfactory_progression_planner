# Rocky Desert District Phases v1.1

This revision separates production flow from spatial preference, uses centralized terminal storage as the default topology, and treats same-line extension as the normal expansion pattern.

## Storage default

```text
Production → downstream consumers → central storage → overflow → shared sink
```

- Storage is assumed useful for essentially every produced item.
- Non-project items default to retained/construction storage and may feed a Dimensional Depot.
- Elevator/project parts default to project buffers rather than general construction storage.
- Storage is distance-tolerant relative to production so storage can be clustered for access and overflow routing.
- Central storage becomes a reserve/backpressure buffer after it fills even though it is not inline.

## Expansion default

The normal growth pattern is **extend the existing line first**. Two smelters on a 60/min feed becoming four smelters on a 120/min feed is the model. Parallel/duplicate lines are secondary responses to throughput or physical constraints.

## Western Coast Starter Works / Home Base

### A0 — Bootstrap [DEFINED]

Temporary/basic starter production while unlocking stable logistics.

- Current: belt `belt_mk1`, miner `miner_mk1`
- Design basis: belt `belt_mk2`, miner `miner_mk1`
- Expansion: Reserve straight 120/min corridors; temporary machines may be replaced.
- Transition: Reach Mk.2 belts / stable starter resource feed.

### A1 — Starter Works Baseline [DEFINED]

Permanent early construction-material and Project Assembly starter production.

- Current: belt `belt_mk2`, miner `miner_mk1`
- Design basis: belt `belt_mk2`, miner `miner_mk2`
- Expansion: Keep module edges open for reserve Iron activation and storage expansion.
- Transition: Mk.2 miners and/or need for higher starter surplus.

### A2 — Expanded Starter / Storage [PARAMETERIZED]

Increase starter surplus, activate reserves as needed, integrate dimensional storage/overflow.

- Current: belt `belt_mk2`, miner `miner_mk2`
- Design basis: belt `belt_mk3`, miner `miner_mk2`
- Expansion: Expand outward; avoid inserting new machines into core chains.
- Transition: Construction demand or downstream consumption justifies reserve activation.

### A3 — Home / Logistics Interchange [PARAMETERIZED]

Transition from primary production center toward mall/storage/interchange.

- Current: belt `belt_mk3`, miner `miner_mk2`
- Design basis: belt `belt_mk3`, miner `miner_mk2`
- Expansion: Prioritize storage/logistics frontage over dense new local production.
- Transition: Regional transport network becomes primary.

## Northern / Coastal Coal Power

### B0 — Coal Power Commission [DEFINED]

First autonomous coal-power grid using local coal and water.

- Current: belt `belt_mk2`, miner `miner_mk1`
- Design basis: belt `belt_mk2`, miner `miner_mk1`
- Expansion: Reserve generator and water-extractor expansion line.
- Transition: Power demand exceeds initial block.

### B1 — Coal Power Expansion [PARAMETERIZED]

Expand autonomous generation using additional local coal capacity.

- Current: belt `belt_mk2`, miner `miner_mk1`
- Design basis: belt `belt_mk3`, miner `miner_mk2`
- Expansion: Add generator blocks rather than rework existing manifold.
- Transition: Mk.2 mining and/or sustained regional power demand.

### B2 — Shared Coal Release [PLACEHOLDER]

Potentially release conditional coal capacity after stronger power sources are established.

- Current: belt `n/a`, miner `n/a`
- Design basis: belt `n/a`, miner `n/a`
- Expansion: No default physical recommendation beyond preserving optional export access.
- Transition: Power district no longer requires all reserved coal.

## Southeast / Interior Steel Works

### C0 — Steel Commissioning [DEFINED]

Bring basic Steel Beam and Steel Pipe production online for progression and construction.

- Current: belt `belt_mk2`, miner `miner_mk1`
- Design basis: belt `belt_mk3`, miner `miner_mk2`
- Expansion: Build permanent manifolds with unused extension length reserved for later machines rather than duplicating lines.
- Transition: Need Encased Industrial Beam production before Encased Industrial Pipe is available.

### C1 — Initial Encased Beam Production [DEFINED]

Produce Encased Industrial Beams with the default Steel Beam + Concrete recipe while continuing Steel Pipe production for construction and later use.

- Current: belt `belt_mk2`, miner `miner_mk1`
- Design basis: belt `belt_mk3`, miner `miner_mk2`
- Expansion: Extend the existing Beam and Pipe lines in place; reserve a Pipe-side EIB branch for the later recipe transition.
- Transition: Encased Industrial Pipe alternate recipe acquired.

### C2 — Encased Industrial Pipe Transition [DEFINED]

Move Encased Industrial Beam production from Steel Beam + Concrete to Steel Pipe + Concrete; Pipe becomes the dominant shared steel intermediate.

- Current: belt `belt_mk3`, miner `miner_mk2`
- Design basis: belt `belt_mk3`, miner `miner_mk2`
- Expansion: Retain Beam production for construction/project demand while extending the Pipe manifold to EIB and other consumers.
- Transition: Steel Rotor and broader motor-component production justified.

### C3 — Permanent 270/min Steel / Motor Components [DEFINED]

Operate mature pipe-heavy steel production with dedicated EIB, Rotor, Stator, and downstream Motor capacity.

- Current: belt `belt_mk3`, miner `miner_mk2`
- Design basis: belt `belt_mk4`, miner `miner_mk2`
- Expansion: Extend existing manifolds first; duplicate a line only after belt capacity, footprint length, or logistics makes further extension undesirable.
- Transition: Regional rail backbone and/or higher export demand.

### C4 — Rail-Integrated Steel Expansion [PARAMETERIZED]

Connect mature steel outputs to regional logistics and expand throughput as needed.

- Current: belt `belt_mk4`, miner `miner_mk2`
- Design basis: belt `belt_mk4`, miner `miner_mk2`
- Expansion: Continue same-line extension where practical; add parallel/duplicate lines only when a physical or throughput limit is reached.
- Transition: Late-game regional demand or logistics constraints.

## Western Beaches Petrochemical / Fuel

### D0 — Temporary Oil [DEFINED]

Early plastic/rubber with residue safety valve; do not overbuild.

- Current: belt `n/a`, miner `n/a`
- Design basis: belt `n/a`, miner `n/a`
- Expansion: Keep crude capacity and physical space uncommitted for permanent fuel/recycling architecture.
- Transition: Preferred oil alternates available.

### D1 — Permanent Petrochemical [PARAMETERIZED]

Heavy Oil Residue + recycled plastic/rubber architecture.

- Current: belt `n/a`, miner `n/a`
- Design basis: belt `n/a`, miner `n/a`
- Expansion: Separate plastic/rubber modules with independent storage and room for fuel expansion.
- Transition: Fuel/power or downstream petrochemical demand.

### D2 — Fuel / Power Expansion [PARAMETERIZED]

Mature fuel production and regional power expansion.

- Current: belt `n/a`, miner `n/a`
- Design basis: belt `n/a`, miner `n/a`
- Expansion: Extend fuel and generator modules along reserved fluid/logistics corridors.
- Transition: Diluted Fuel and sustained power demand.

## Northwest Structural / HMF Reserve

### E0 — Structural Reserve [PLACEHOLDER]

Reserve footprint/resources for later HMF production.

- Current: belt `n/a`, miner `n/a`
- Design basis: belt `n/a`, miner `n/a`
- Expansion: Preserve resource access and factory pad; defer detailed topology.
- Transition: Industrial Manufacturing and preferred HMF recipe.

### E1 — Heavy Modular Frame Works [PARAMETERIZED]

Permanent Modular Frame → Heavy Modular Frame chain.

- Current: belt `belt_mk3`, miner `miner_mk2`
- Design basis: belt `belt_mk4`, miner `miner_mk2`
- Expansion: Leave logistics/import side open for steel/concrete feeds and later Fused Frames.
- Transition: Heavy Encased Frame secured.

### E2 — Fused Frame Expansion [PLACEHOLDER]

Add Fused Modular Frame production when late inputs/logistics justify it.

- Current: belt `n/a`, miner `n/a`
- Design basis: belt `n/a`, miner `n/a`
- Expansion: Expand outward from HMF output/logistics edge.
- Transition: Late-game fused-frame demand.

## Bauxite-to-Water Aluminum Works

### F0 — Bauxite Claim / Logistics [DEFINED]

Secure Bauxite extraction and move ore toward reliable water.

- Current: belt `belt_mk3`, miner `miner_mk2`
- Design basis: belt `belt_mk4`, miner `miner_mk2`
- Expansion: Preserve downhill/rail logistics corridor; avoid heavy highland processing.
- Transition: Preferred aluminum recipes available.

### F1 — Permanent Aluminum [PARAMETERIZED]

Water-side alumina/scrap/ingot production using simplified aluminum chain.

- Current: belt `belt_mk4`, miner `miner_mk2`
- Design basis: belt `belt_mk4`, miner `miner_mk2`
- Expansion: Separate wet process, scrap, ingot, and export edges; preserve room for more bauxite feed.
- Transition: Sloppy Alumina + Pure Aluminum Ingot.

### F2 — Aluminum Expansion / Export [PLACEHOLDER]

Increase aluminum throughput and rail export.

- Current: belt `belt_mk4`, miner `miner_mk2`
- Design basis: belt `belt_mk5`, miner `miner_mk3`
- Expansion: Add repeated process blocks near water/logistics edge.
- Transition: Late-game aluminum demand.

## Advanced Manufacturing / Logistics Junction

### G0 — Site Selection / Junction [DEFINED]

Select buildable, rail-accessible logistics/advanced-manufacturing location.

- Current: belt `n/a`, miner `n/a`
- Design basis: belt `n/a`, miner `n/a`
- Expansion: Reserve broad station/campus footprint and multiple approach directions.
- Transition: Regional rail backbone planning.

### G1 — Advanced Manufacturing [PLACEHOLDER]

Consolidate low-volume T7-T9 advanced assembly.

- Current: belt `belt_mk4`, miner `n/a`
- Design basis: belt `belt_mk5`, miner `n/a`
- Expansion: Organize around logistics frontage; add independent advanced modules.
- Transition: Imported advanced part flows established.

### G2 — Late Logistics Hub [PLACEHOLDER]

Regional rail/drone interchange and late-game export/import consolidation.

- Current: belt `belt_mk5`, miner `n/a`
- Design basis: belt `belt_mk6`, miner `n/a`
- Expansion: Reserve station/drone expansion zones and avoid blocking trunk corridors.
- Transition: Late-game logistics demand.

## District C recipe transition

### Before Encased Industrial Pipe
```text
Steel Ingot
├→ Beam → Encased Industrial Beam
└→ Pipe → construction/storage
```

### After Encased Industrial Pipe
```text
Steel Ingot
├→ Pipe ─┬→ Encased Industrial Beam
│        ├→ Rotor ─┐
│        └→ Stator ─┴→ Motor
└→ Beam → construction / Versatile Framework
```

The EIB recipe change is modeled as a topology transition: the dominant EIB feed moves from Beam to Pipe.