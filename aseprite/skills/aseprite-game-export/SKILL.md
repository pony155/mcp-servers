---
name: aseprite-game-export
description: Validate, batch, atlas-pack, audit, and export Aseprite assets under an explicit game-engine contract. Use for sprite sheets, metadata, collision shapes, profiles, release checks, and reproducible multi-asset handoff.
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

For batches, apply one naming, validation, and failure-isolation policy to every job. For atlases, normalize trim and padding rules before packing. Include collision geometry only when the runtime schema requests it. Finish release work with cross-asset validation, deterministic hashes, texture-size checks, and a recorded engine profile.
