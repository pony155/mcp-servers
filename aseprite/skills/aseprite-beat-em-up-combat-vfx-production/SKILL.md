---
name: aseprite-beat-em-up-combat-vfx-production
description: Produce synchronized pixel-art combat effects for beat-'em-ups in Aseprite. Use for hit sparks, trails, dust, shockwaves, projectiles, impact flashes, charge effects, and anchor/event timing tied to combat actions.
---

# Aseprite Beat-'em-up Combat VFX Production

Start from the gameplay event and attachment contract: source action, trigger frame, anchor, lifetime, layering, facing behavior, and whether the effect follows or detaches. Keep effect timing independent from character frame count when the runtime plays it as a separate asset.

Use `aseprite_edit_animation_events` for spawn cues and `aseprite_edit_frame_anchors` for `vfx`, `weapon`, `impact`, or projectile origins. Match the effect's brightest frame to contact or release, keep trails from obscuring hurt poses, and preserve silhouettes for multiple overlapping enemies.

Review the character with combat overlays and preview the VFX animation separately. Validate loops only for persistent effects. Export separate bundles when VFX are reusable; bake effects into character sheets only when the engine contract explicitly requires it.
