# Rocky Desert Functional Topology v1

This pass extends functional topology coverage from A/C to all Rocky Desert districts. It is intentionally shallow: responsibilities, major flows, recipe transitions, storage behavior, expansion intent, and logistics interfaces are modeled; exact machine placement and route geometry are not.

## Western Coast Starter Works / Home Base

### Functional modules
- **Iron Plate** — starter_basic [DEFINED]
- **Iron Rod** — starter_basic [DEFINED]
- **Screws** — starter_intermediate [DEFINED]
- **Reinforced Iron Plate** — starter_intermediate [DEFINED]
- **Rotor** — starter_intermediate [DEFINED]
- **Modular Frame** — starter_finished [DEFINED]
- **Smart Plating** — project_part [DEFINED]
- **Wire** — starter_basic [PARAMETERIZED]
- **Cable** — starter_basic [DEFINED]
- **Copper Sheet** — starter_basic [DEFINED]
- **Concrete** — starter_basic [DEFINED]

## Northern / Coastal Coal Power

### Functional modules
- **Coal** — resource_feed [DEFINED]
- **Water** — resource_feed [DEFINED]
- **Power** — power_generation [DEFINED]
- **Compacted Coal** — fuel_intermediate [PARAMETERIZED]

### District interfaces
- `export` **Power** via `grid` →/from `rocky_desert_a;rocky_desert_c;regional` [DEFINED] — B supplies early autonomous regional power.
- `conditional_export` **Coal** via `belt/vehicle/rail_later` →/from `regional` [PLACEHOLDER] — Only after power reserve is no longer needed.

## Southeast / Interior Steel Works

### Functional modules
- **Steel Ingot** — steel_primary [DEFINED]
- **Steel Pipe** — steel_primary [DEFINED]
- **Steel Beam** — steel_primary [DEFINED]
- **Encased Industrial Beam** — steel_intermediate [DEFINED]
- **Rotor** — steel_intermediate [DEFINED]
- **Stator** — steel_intermediate [DEFINED]
- **Motor** — steel_finished [DEFINED]
- **Versatile Framework** — project_part [PARAMETERIZED]
- **Automated Wiring** — project_part [PARAMETERIZED]

## Western Beaches Petrochemical / Fuel

### Functional modules
- **Crude Oil** — resource_feed [DEFINED]
- **Plastic** — petrochemical_output [DEFINED]
- **Rubber** — petrochemical_output [DEFINED]
- **Heavy Oil Residue** — petrochemical_intermediate [DEFINED]
- **Petroleum Coke** — safety_valve [DEFINED]
- **Fuel** — fuel_output [PARAMETERIZED]
- **Plastic** — recycle_loop [DEFINED]
- **Rubber** — recycle_loop [DEFINED]
- **Power** — power_generation [PARAMETERIZED]

### District interfaces
- `export` **Plastic** via `truck_then_rail` →/from `rocky_desert_a;rocky_desert_g` [DEFINED] — Construction and electronics supply.
- `export` **Rubber** via `truck_then_rail` →/from `rocky_desert_a;rocky_desert_g` [DEFINED] — Construction and advanced production.
- `local_use_or_export` **Fuel** via `pipeline/local_generation` →/from `rocky_desert_d;regional` [PARAMETERIZED] — Primarily power/fuel use.

## Northwest Structural / HMF Reserve

### Functional modules
- **Iron Ore** — resource_feed [PARAMETERIZED]
- **Concrete** — structural_basic [DEFINED]
- **Modular Frame** — structural_intermediate [DEFINED]
- **Heavy Modular Frame** — structural_finished [DEFINED]
- **Fused Modular Frame** — advanced_structural [PLACEHOLDER]

### District interfaces
- `import` **Steel Pipe / steel products** via `truck_then_rail` →/from `rocky_desert_c` [PARAMETERIZED] — HMF chain depends on steel-side inputs.
- `export` **Heavy Modular Frame** via `truck_then_rail` →/from `rocky_desert_a;rocky_desert_g` [DEFINED] — Construction and advanced manufacturing.

## Bauxite-to-Water Aluminum Works

### Functional modules
- **Bauxite** — resource_feed [DEFINED]
- **Water** — resource_feed [DEFINED]
- **Alumina Solution** — aluminum_wet_process [DEFINED]
- **Aluminum Scrap** — aluminum_intermediate [DEFINED]
- **Aluminum Ingot** — aluminum_primary [DEFINED]
- **Alclad Aluminum Sheet** — aluminum_output [DEFINED]
- **Aluminum Casing** — aluminum_output [DEFINED]

### District interfaces
- `internal_transfer` **Bauxite** via `belt/truck_then_rail_candidate` →/from `highland_to_water` [DEFINED] — Critical pathing problem: highland extraction to water-side process.
- `export` **Aluminum products** via `rail` →/from `rocky_desert_g;regional` [DEFINED] — Primary late regional export.

## Advanced Manufacturing / Logistics Junction

### Functional modules
- **Logistics Hub** — logistics_interface [DEFINED]
- **Computer** — advanced_electronics [PARAMETERIZED]
- **Circuit Board** — advanced_electronics [PARAMETERIZED]
- **High-Speed Connector** — advanced_electronics [PLACEHOLDER]
- **Supercomputer** — advanced_electronics [PLACEHOLDER]
- **Radio Control Unit** — advanced_electronics [PLACEHOLDER]

### District interfaces
- `import` **Advanced intermediates** via `rail` →/from `rocky_desert_c;rocky_desert_d;rocky_desert_e;rocky_desert_f` [DEFINED] — G depends on multi-district convergence.
- `export` **Advanced manufactured parts** via `rail/drone` →/from `regional` [PLACEHOLDER] — Late-game distribution.

## Key topology transitions

- **B:** coal + water converge on autonomous power generation; later coal release is conditional rather than assumed.
- **D:** early Plastic/Rubber create Heavy Oil Residue that must drain to Petroleum Coke; permanent oil shifts to HOR/Fuel/Recycled Plastic/Recycled Rubber architecture.
- **E:** Modular Frames + Concrete + imported/local steel-side inputs converge on Heavy Modular Frames; Fused Frames remain a later extension.
- **F:** Bauxite extraction and water-side processing are intentionally separated. Bauxite-to-water is a major future pathing problem.
- **G:** functions primarily as a logistics-facing advanced manufacturing campus, importing from several districts rather than anchoring on a single local raw-resource chain.

## Storage/overflow

The Rocky strategy profile still defaults produced materials to centralized terminal storage with downstream consumers before storage, then overflow from full storage toward a shared sink manifold. Resource feeds and power generation are exceptions.

## Expansion

Same-line/manifold extension remains the default. Duplicated/parallel lines are added only after belt capacity, physical line length, terrain, or logistics make further extension undesirable.