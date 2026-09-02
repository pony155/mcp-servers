---
name: aseprite-retro-hardware-constraint-production
description: Produce Aseprite assets for explicit retro hardware limits. Use when palettes, tile budgets, sprite sizes, scanline limits, banks, or attribute regions must match a target platform.
---

# Aseprite Retro Hardware Constraint Production

Identify the exact target hardware or emulator contract; never infer limits from a general console era. Record native tile size, sprite dimensions, colors per palette, palette banks, transparency index, attribute regions, per-scanline sprite limits, memory layout, and export encoding.

Design within those limits from the first revision. Validate indexed palettes and tile reuse, inspect tile metadata for bank or attribute assignments, and use contact sheets or tilemap previews to expose scanline and adjacency conflicts. Avoid modern alpha, color-profile conversion, or blended inbetweens when the target cannot represent them. Report any visual compromise required to meet the verified budget.
