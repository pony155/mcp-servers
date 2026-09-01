---
name: aseprite-beat-em-up-stage-gameplay-authoring
description: Author gameplay zones and encounter metadata for lane-based pixel-art beat-'em-up stages in Aseprite. Use for walkable lanes, camera bounds, spawns, encounters, exits, hazards, pits, and foreground occlusion after stage art exists.
---

# Aseprite Beat-'em-up Stage Gameplay Authoring

Treat stage art and gameplay zones as separate contracts. Establish enabled `walkable` and `camera` regions first, then place spawn, encounter, exit, hazard, pit, and foreground regions in stage coordinates. Give encounter zones stable IDs and deterministic order values; use `target` only for engine identifiers such as the next stage or spawn group.

Write zones with `aseprite_edit_stage_gameplay_zones` to a new document. Keep spawn, exit, and encounter centers inside a walkable region, and ensure camera zones frame every required combat lane. Foreground regions should describe intentional occlusion rather than decorative layer bounds.

Run `aseprite_validate_stage_gameplay` after layout changes and inspect a rendered tilemap preview at gameplay scale. Resolve containment and missing-zone errors before exporting a bundle or tilemap manifest.
