---
name: aseprite-tilemap-level-production
description: Build and exchange tilemap level layouts in Aseprite. Use when tile layers, transforms, engine JSON, round trips, or level-data validation matter beyond tileset artwork itself.
---

# Aseprite Tilemap Level Production

Establish the engine grid, empty-tile convention, tileset identifiers, layer paths, coordinate
origin, flip semantics, and frame usage before editing. Keep visual tileset work separate from level
layout data, and preserve tile index zero unless the target engine explicitly uses another value.

Inspect tilesets and tile metadata before authoring cells. Use versioned tilemap JSON for handoff;
review layer-to-tileset mappings and transformed cells before importing it into another document.
Create missing layers only when top-level placement is intended. After a round trip, compare cell
counts, grid dimensions, layer paths, tile flags, and a rendered preview. Deliver the JSON schema
version and any engine-side coordinate conversion with the asset.
