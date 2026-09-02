---
name: aseprite-concept-to-sprite
description: Translate reference or concept art into an editable Aseprite pixel-art sprite or animation. Use when proportions, silhouette, palette roles, layers, and motion must be planned from a visual reference before production edits begin.
---

# Aseprite Concept To Sprite

Extract a production specification before drawing: canvas and occupied bounds, viewing angle, anatomy proportions, anchor/baseline, palette roles, layer structure, animation tags, frame count, and timing.

Preserve the reference's defining silhouette and large color masses before adding texture. Reduce detail according to the target sprite size; do not copy high-resolution noise pixel-for-pixel.

Create the editable document with `aseprite_create_animation` or `aseprite_create_sprite`. Work in reviewable passes:

1. Block silhouette and negative spaces.
2. Establish outline, shadow, midtone, highlight, and accent clusters.
3. Add identity details only where they remain readable at native size.
4. Build motion with copied cels and focused pixel-run edits.
5. Preview at native and integer zoom, compare frames, and validate the loop.

Write revisions to new files and use `expected_source_hash`. State any necessary departure from the reference caused by canvas size or animation readability.
