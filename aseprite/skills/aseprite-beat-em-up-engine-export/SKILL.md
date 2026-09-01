---
name: aseprite-beat-em-up-engine-export
description: Validate and package Aseprite character, combat, VFX, prop, or stage assets for a beat-'em-up game engine. Use for reproducible sprite-sheet, frame-data, gameplay-manifest, and ZIP bundle handoff after authoring is complete.
---

# Aseprite Beat-'em-up Engine Export

Confirm the engine's frame indexing, coordinate origin, lane-axis convention, action identifiers, trimming policy, atlas layout, and schema-version support before export. Do not rename tags, anchors, zones, or cancel targets during packaging.

Run the relevant combat-set, stage, animation, pixel-art, and export-profile validators first. Export with `aseprite_export_beat_em_up_bundle`; it publishes one ZIP containing `sheet.png`, `frames.json`, and `manifest.json`. Record the returned source hash and reject bundles produced from an unapproved source revision.

Inspect the archive manifest's schema and bundle-format versions in the importer. Keep source documents outside runtime packages and avoid engine-specific undocumented properties when the versioned manifest already represents the data.
