---
name: aseprite-tile-metadata-authoring
description: Author engine-facing properties on Aseprite tiles and tilesets. Use when terrain types, collisions, costs, variants, triggers, or adjacency semantics must accompany tile pixels.
---

# Aseprite Tile Metadata Authoring

Obtain the engine property schema, types, defaults, and reserved names before editing. Treat tile index zero as the tileset's empty tile unless the target engine explicitly defines another convention. Prefer stable semantic properties over encoding meaning only in tile order or timeline colors.

Inspect existing metadata first, modify only named scalar properties, and preserve unrelated extension namespaces. Validate that referenced tile indices exist and that every required terrain, collision, navigation, or adjacency field is present with the correct scalar type. Deliver an index-to-property mapping with the exported tileset.
