# World Data

`world/` is the build-versioned physical-world substrate used by analysis tools.

## Current extraction: build 502094

`manifests/world_502094.json` is the authoritative layer registry. It currently binds:

- 625 resource sockets from first-party installed game assets;
- 625 default resource/purity assignments;
- 4,446 static collectible rows;
- 1,764 normalized primary exploration POIs;
- 1 m terrain/water rasters.

## Resource identity

`canonical/world_resource_sockets.csv` uses the extracted actor `id` as `socket_id`. The corresponding save actor instance is `Persistent_Level:PersistentLevel.<socket_id>`, allowing a future save reader to join altered resource assignments back to fixed placement. Fracking satellites retain `core_socket_id`.

`configurations/default_502094/resource_assignments.csv` stores the build-502094 default resource and purity separately. It is replaceable by another world/save configuration with the same schema.

## Coordinate convention

Canonical coordinates are metres: east = +X, north = -Y, elevation = +Z. Raw resource extraction is retained in centimetres under `source_snapshots/build_502094/`.

## Extraction vs analysis

Extraction records physical facts. `buildable_areas` and `corridor_topology` are intentionally listed in the manifest as incomplete derived analysis layers. Site suitability, district interpretation, and progression allocation do not belong here.
