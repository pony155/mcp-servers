---
name: aseprite-tileset-production
description: Build and refine bounded Aseprite tilesets for tile-based games. Use when creating tile dimensions, reusable tile images, seamless variants, palette consistency, or tileset metadata; do not use for ordinary character animation.
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
