from __future__ import annotations

from pathlib import Path
import numpy as np
import trimesh

from .geometry import regular_surface_mesh, surface_overlay_cells
from .io import load_membership

COLORS = {
    "terrain": [138, 136, 128, 255],
    "water": [62, 140, 199, 150],
    "small": [115, 199, 133, 190],
    "medium": [237, 201, 87, 190],
    "large": [242, 122, 64, 190],
    "very_large": [171, 115, 224, 190],
    "resources": [240, 240, 240, 255],
}


def _mesh(grid, color):
    m = trimesh.Trimesh(vertices=grid.points, faces=grid.faces, process=False)
    m.visual.face_colors = np.tile(np.array(color, dtype=np.uint8), (len(m.faces), 1))
    return m


def export_glb(world, resources, surfaces, surface_dir: Path, output: Path, resolution_m: float,
               platform_elevation_m: float | None = None, terrain_spacing_m: float = 32.0, size_filter: set[str] | None = None,
               include_water: bool = True, include_resources: bool = True, vertical_exaggeration: float = 1.0):
    size_filter = size_filter or {"small", "medium", "large", "very_large"}
    scene = trimesh.Scene()
    terrain = regular_surface_mesh(world, terrain_spacing_m, vertical_exaggeration)
    scene.add_geometry(_mesh(terrain, COLORS["terrain"]), node_name="terrain", geom_name="terrain")

    if include_water:
        water = regular_surface_mesh(world, terrain_spacing_m, vertical_exaggeration, source="water")
        if len(water.faces): scene.add_geometry(_mesh(water, COLORS["water"]), node_name="water", geom_name="water")

    labels = load_membership(surface_dir, resolution_m, platform_elevation_m)
    for size in ["small", "medium", "large", "very_large"]:
        if size not in size_filter: continue
        pts, quads, _, _, _ = surface_overlay_cells(world, labels, surfaces, resolution_m, {size}, z_offset_m=2.0 / max(vertical_exaggeration, 1e-6), platform_elevation_m=platform_elevation_m)
        if len(quads) == 0: continue
        pts[:,2] *= vertical_exaggeration
        faces = np.vstack([quads[:,[0,1,2]], quads[:,[0,2,3]]])
        grid = type("M", (), {"points":pts, "faces":faces})
        scene.add_geometry(_mesh(grid, COLORS[size]), node_name=f"surfaces_{size}", geom_name=f"surfaces_{size}")

    if include_resources and len(resources):
        markers = []
        for r in resources.itertuples(index=False):
            s = trimesh.creation.icosphere(subdivisions=1, radius=6.0)
            s.apply_translation([float(r.east_m), float(r.north_m), (float(r.elevation_m)+4.0)*vertical_exaggeration])
            markers.append(s)
        rm = trimesh.util.concatenate(markers); rm.visual.face_colors = np.tile(np.array(COLORS["resources"],dtype=np.uint8),(len(rm.faces),1))
        scene.add_geometry(rm, node_name="resources", geom_name="resources")

    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(scene.export(file_type="glb"))
    return output
