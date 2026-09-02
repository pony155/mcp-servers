---
name: aseprite-ui-sprite-production
description: Produce pixel-art UI systems in Aseprite, including icons, controls, panels, state animations, RPG icon families, pivots, and nine-slice metadata. Use when interface assets must share grid, contrast, and scaling rules.
---

# Aseprite UI Sprite Production

Establish native display scale, background contrast, interaction states, border thickness, and engine slice conventions first. Keep corners fixed and define the stretchable center in local slice coordinates.

Create states on explicit frames or tags, reuse linked cels for unchanged regions, and use slices for bounds, center, and pivot. Preview at intended integer scale, check icon silhouettes and state contrast, then export PNG/JSON with documented padding.

For icon sets, establish a common cell grid, silhouette language, padding, and palette budget before variants. For nine-slice panels, keep corners immutable and verify border/center behavior at multiple requested sizes.
