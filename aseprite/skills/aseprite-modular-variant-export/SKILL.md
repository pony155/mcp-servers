---
name: aseprite-modular-variant-export
description: Export controlled layer combinations from Aseprite. Use for equipment sets, paper dolls, portraits, skins, UI states, or other named variants composed from shared layers.
---

# Aseprite Modular Variant Export

Define a variant matrix before rendering: stable name, exact included layer paths, frame or tag,
scale, output path, and filename contract. Treat the base body, anchors, draw order, timing, and
canvas as shared invariants. Do not infer runtime-valid combinations solely from layer names.

Render variants as a bounded batch and retain per-variant failures instead of silently omitting
outputs. Review combinations at motion extremes for clipping, missing coverage, palette conflicts,
and accidental visibility. Require unique variant names and output paths, then deliver the variant
matrix alongside the exported files so the build can be reproduced.
