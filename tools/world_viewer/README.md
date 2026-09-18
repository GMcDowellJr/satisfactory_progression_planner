# Satisfactory World Viewer

VTK QA viewer for versioned terrain, resources, build surfaces, and related world-analysis artifacts.

## V8 flat-pad view

The current build-surface view separates concrete placement geometry from contextual suitability:

- subdued colored fill = union of physical footprints supported by qualifying centers;
- thin boundaries = suitability envelope boundaries;
- strong white rectangles = actual candidate factory footprints at their fitted single horizontal platform Z.

Every rectangle is rendered from `width_foundations` and `length_foundations` using an 8 m foundation size. Analysis resolution only controls terrain sampling and candidate-center spacing; it cannot resize a factory footprint.

The default clearance tolerance is 4 m when available. Use `;` and `'` to cycle generated clearance variants. `[` and `]` cycle horizontal resolutions.

```cmd
python scripts\world_viewer.py view --resolution 16 --terrain-spacing 24
```

Or inspect an explicit tolerance:

```cmd
python scripts\world_viewer.py view --resolution 16 --clearance-tolerance 4 --terrain-spacing 24
```

Controls include mouse orbit/pan/zoom, compact live navigation sliders, `S`/`M`/`L`/`V` size-class toggles, `B` rectangle toggle, `D` center-region diagnostic outline, `P` orbit-pivot cycling (View/Cursor/Selection), `I` isolate selected, `F` focus selected, `Esc` clear selection, and `C`/Home north-up plan reset. Oblique interaction is roll-corrected so world Z remains up; plan view remains north-up.

The viewer remains backward-compatible with v6/v5 plane-fit, v4 local-relief, and v3 elevation-sweep result folders.

V8 also wraps the bottom status/help text to the viewport and shrinks the live slider strip to roughly one quarter of its prior width. The normal dark outline follows the same footprint-union coverage as the green fill; the older valid-center boundary is available only as the `D` diagnostic layer.
