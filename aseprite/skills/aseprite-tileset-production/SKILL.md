---
name: aseprite-tileset-production
description: Build Aseprite tilesets including ordinary, autotile, isometric, transition, and metadata-driven variants. Use when tile geometry, adjacency, reuse, projection, palettes, or engine properties must remain consistent.
---

# Aseprite Tileset Production

Establish tile width, height, palette, projection, edge rules, and required variants before editing. Keep tile index zero reserved for emptiness and assign stable semantic roles to later indices.

Use `aseprite_edit_tileset` for tileset structure and tile pixels. Build in this order:

1. Base fill and boundary tiles.
2. Corners and transition tiles.
3. Variants that break repetition without changing collision meaning.
4. Metadata properties required by the target engine.

Check opposite edges at exact pixel level and preview repeated arrangements where possible. Reuse colors and clusters across neighboring tiles. Avoid features that terminate at an edge unless a complementary tile exists.

Keep each revision in a new document, use source hashes, and report tile dimensions, named tileset, modified indices, palette, and any missing adjacency cases.

For autotiles, define the adjacency bit contract before drawing edge and corner combinations. For isometric sets, lock projection, elevation, and shared diamond edges. Store collision, terrain, cost, trigger, or variant semantics as explicit tile metadata rather than inferring them from decorative pixels.
