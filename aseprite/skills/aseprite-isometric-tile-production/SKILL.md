---
name: aseprite-isometric-tile-production
description: Build and validate isometric pixel-art tile families in Aseprite. Use when diamond projection, elevation steps, shared edges, occlusion, anchors, and engine-specific tile ordering must remain consistent.
---

# Aseprite Isometric Tile Production

Confirm the projection ratio, tile footprint, elevation increment, origin, draw order, and required adjacency cases before editing. Treat those values as a grid contract; do not correct apparent perspective by moving individual edge endpoints off-grid.

Produce ground, walls, inner/outer corners, slopes, transitions, and occluders in stable index order. Inspect exact edge pixels and render representative tilemap previews. Validate duplicates and empty tiles, then report the index map, anchor convention, elevation units, and missing combinations.
