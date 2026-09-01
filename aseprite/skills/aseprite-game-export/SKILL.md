---
name: aseprite-game-export
description: Prepare and export editable Aseprite assets for a game engine. Use when tags, slices, pivots, properties, frame dimensions, sprite sheets, and machine-readable metadata must be validated and handed off consistently.
---

# Aseprite Game Export

Treat the editable document as the source artifact and exports as reproducible outputs.

1. Inspect dimensions, frame durations, tags, slices, color mode, and layer visibility.
2. Confirm the engine contract: fixed or trimmed frames, origin/pivot convention, animation names, repeat behavior, padding, extrusion, and metadata format.
3. Add or correct slices and scalar properties only when the requested contract requires them.
4. Validate animation bounds, baselines, empty frames, and duplicates. Resolve errors before export; document intentional warnings.
5. Export PNG and JSON together with `aseprite_export_sprite_sheet`. Use explicit padding and layout values rather than relying on remembered defaults.
6. Report document hash, sheet and metadata paths, frame dimensions/count, tag ranges, pivots, and validation status.

Never overwrite source or exports implicitly. Do not invent engine-specific keys when no schema was provided; request or clearly state the assumed contract.
