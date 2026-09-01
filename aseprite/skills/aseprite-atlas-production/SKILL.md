---
name: aseprite-atlas-production
description: Normalize, validate, and pack multiple Aseprite assets into deterministic atlases. Use when a bounded asset set must share export rules and produce one PNG texture with machine-readable metadata.
---

# Aseprite Atlas Production

Confirm the source list, profile, trimming policy, padding, extrusion, maximum texture size, naming rules, and overwrite authority. Validate each asset and cross-asset consistency before packing; do not silently omit a failed source.

Use stable source ordering and explicit atlas output paths. Inspect the generated metadata and verify its frame count against the sources. Report texture dimensions, hashes, failures, and whether the engine requires a metadata conversion after Aseprite's JSON export.
