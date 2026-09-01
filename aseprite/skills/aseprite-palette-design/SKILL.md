---
name: aseprite-palette-design
description: Design, apply, and review compact role-based palettes for Aseprite pixel art. Use when reducing colors, establishing ramps, improving contrast, creating variants, or converting an asset to indexed color.
---

# Aseprite Palette Design

Inspect existing palette colors and composited pixels before proposing replacements. Identify functional roles—outline, deepest shadow, material ramps, skin, highlight, and accent—rather than choosing colors independently.

Prefer compact ramps with intentional hue and value movement. Preserve silhouette contrast against the intended background and reserve the strongest accent contrast for important details.

Use this workflow:

1. Record the source hash and current color mode.
2. Propose the palette as explicit `#RRGGBB` or `#RRGGBBAA` values with role labels.
3. Apply it to a new document with `aseprite_apply_palette`.
4. Preview representative and extreme frames; compare exact pixels where remapping is ambiguous.
5. If indexed output is needed, call `aseprite_convert_color_mode` with an explicit dithering decision.
6. Validate and report lost distinctions, transparency handling, and final palette size.

Avoid dithering on small sprites unless it improves a specifically reviewed gradient. Palette application does not support grayscale documents; convert an output copy to RGB first when necessary.
