---
name: aseprite-beat-em-up-character-production
description: Produce and validate player, enemy, elite, and boss sprite sets for lane-based pixel-art beat-'em-ups. Use for shared action contracts, movement, attacks, reactions, phases, anchors, timing, variants, and roster consistency.
---

# Aseprite Beat-'em-up Character Production

Define the gameplay contract before drawing: canvas, ground line, facing policy, lane depth, action tags, frame durations, and the `feet`, `grab`, `shadow`, `weapon`, and `vfx` anchors the engine consumes. Keep one stable world-contact point while poses change height or reach.

Build readable silhouettes for idle, walk, run, turn, light/heavy attacks, grab/throw, hurt, knockdown, get-up, and death. Add optional jump, block, dodge, weapons, and specials only when the design requires them. Separate anticipation, contact, follow-through, and recovery with explicit timing; never infer gameplay timing solely from the drawing.

Use `aseprite_edit_tags` and `aseprite_edit_animation_events` after timing stabilizes. Add action contracts, explicit root motion, and intentional cancel windows before combat boxes. Author hurt/push boxes before offensive boxes; place named origins with `aseprite_edit_frame_anchors`. Review complete moves with `aseprite_preview_combat_animation`, validate the document with `aseprite_validate_combat_set`, and publish the approved revision with `aseprite_export_beat_em_up_bundle`.

Do not overwrite the source while iterating. Write a new `.aseprite` document, inspect the mutation result, and promote it only after visual and combat validation pass.

For enemy rosters, share required tags and anchors while differentiating silhouette, reach, cadence, and palette. For bosses, add explicit phase transitions, armor or invulnerability states, large-attack tells, grabs, arena interactions, and return-state contracts; do not force boss-only complexity into ordinary enemy assets.
