# Architecture

```text
Local game extraction
  terrain + water + provenance + POIs
                 \
                  -> canonical planner package
                 /
SCIM screenshot -> visual road preprocessor -> aligned road prior

canonical planner package + road prior
                |
                v
          mode-aware A*
                |
     +----------+-----------+
     |                      |
 route + validation     POI detour scorer
```

## Authority

- Local height/water/provenance: physical routing authority.
- SCIM visual roads: semantic preference only.
- Movement profile: policy/configuration.
- Solver result: derived hypothesis with machine-readable validation.

## Why raster first

The road overlay does not need survey geometry. A 5 m aligned road-prior raster is simpler and more
robust than attempting to infer perfect graph topology from thick screenshot lines. The A* solver
can use a corridor band around those lines while physical constraints come from the local game data.

A true vector road graph can be added later if it improves performance or route explainability.
