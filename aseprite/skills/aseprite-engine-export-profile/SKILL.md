---
name: aseprite-engine-export-profile
description: Translate an explicit game-engine asset schema into Aseprite validation and export operations. Use for Godot, Unity, or custom pipelines with required dimensions, names, tags, pivots, slices, palettes, and atlas metadata.
---

# Aseprite Engine Export Profile

Obtain the actual engine contract before mutation: coordinate origin, pivot units, trimming, padding, extrusion, naming, animation ranges, metadata format, and overwrite policy. Do not invent engine keys or assume a default importer configuration.

Represent enforceable requirements with an export profile, validate documents before export, and keep warnings distinct from failures. For sets, validate cross-asset dimensions and color modes before batch export or atlas packing. Report output hashes and any schema fields that still require engine-side transformation.
