---
name: aseprite-pixel-art-restoration
description: Restore damaged, scaled, compressed, or off-palette pixel art in Aseprite while preserving the original design. Use when cleanup must remove resampling artifacts without stylistic redesign.
---

# Aseprite Pixel Art Restoration

Establish the intended canvas, grid, palette, transparency policy, and nearest surviving reference before editing. Preserve silhouette, clusters, proportions, and deliberate asymmetry; treat redesign, added detail, and palette expansion as separate user decisions.

Inspect pixels at native scale, validate binary alpha and palette membership, then repair in small revisions. Prefer exact color replacement and bounded pixel runs for mechanical damage; use direct pixel or cel edits for ambiguous edges. Revalidate after each pass, review isolated pixels rather than deleting them automatically, and compare the restored sprite against the source so every changed region is explainable.
