# Satisfactory terrain geometry model

The game does not appear to present one monolithic terrain TIN.

The terrain source used by SatisfactoryMCP is hybrid:

1. **UE Landscape** — a regular sampled height surface. The generator reads 128×128 uint16
   samples per LandscapeComponent at one sample per 1 m quad.
2. **Placed rock/cave static meshes** — cliffs, mesas, boulders and cave geometry are separate
   triangle meshes. The extractor can read LOD vertex/index buffers, cooked collision hulls,
   and Nanite resources/pages.
3. **Water actors** — separate world geometry/volumes supply water-surface levels.
4. **Interface height raster** — lower-resolution fill where higher-quality geometry is absent.

`gen_world_heightmap.py` chooses triangle sources in order (`nanite`, `lod0`, `hull`) and rasterizes
the selected terrain meshes into the common 1 m grid. The resulting heightfield is therefore a
derived query surface, not evidence that the underlying world has no triangle geometry.

For planner use, the 1 m field is preferable for fast route scoring. A retained/global triangle
mesh would be useful only if we later need true 3D questions such as overhangs, cave floors versus
roofs, tunnel clearance, or exact obstacle collision. A single-valued heightfield necessarily
collapses multiple Z surfaces at one X/Y.
