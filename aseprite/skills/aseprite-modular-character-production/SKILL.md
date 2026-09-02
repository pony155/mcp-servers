---
name: aseprite-modular-character-production
description: Produce layer-compatible modular characters in Aseprite. Use for paper dolls, equipment swaps, armor sets, hair variants, or independently composited body parts.
---

# Aseprite Modular Character Production

Confirm the shared canvas, anchor, draw order, animation tags, equipment slots, and runtime composition rules. Establish one reference body and keep every interchangeable part aligned to its silhouette, pivots, baselines, and frame timing. Use stable layer paths and metadata identifiers; visual layer names alone are not a durable engine contract.

Review combinations, not just isolated parts. Detect clipping at motion extremes, palette conflicts, missing directional variants, and equipment that changes the intended collision silhouette. Compare motion reports and cel positions across modules, then validate dimensions, tags, events, and export naming as a complete set.

Use `aseprite_edit_modular_part_metadata` to give every interchangeable layer a stable part ID,
slot, draw order, compatibility contract, and attachment anchors. Preview representative and edge
case combinations with `aseprite_preview_modular_variant`; do not infer compatibility from layer
names or current visibility. Run `aseprite_validate_modular_character` before export, treating
missing required slots, contradictory references, invalid anchors, and requested frame-coverage
failures as blockers. Publish the runtime contract with `aseprite_export_modular_manifest`.
