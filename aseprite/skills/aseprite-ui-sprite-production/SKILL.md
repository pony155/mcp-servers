---
name: aseprite-ui-sprite-production
description: Produce pixel-art UI icons, controls, panels, state animations, pivots, and nine-slice metadata in Aseprite. Use for interface assets where fixed borders and scalable centers matter.
---

# Aseprite UI Sprite Production

Establish native display scale, background contrast, interaction states, border thickness, and engine slice conventions first. Keep corners fixed and define the stretchable center in local slice coordinates.

Create states on explicit frames or tags, reuse linked cels for unchanged regions, and use slices for bounds, center, and pivot. Preview at intended integer scale, check icon silhouettes and state contrast, then export PNG/JSON with documented padding.
