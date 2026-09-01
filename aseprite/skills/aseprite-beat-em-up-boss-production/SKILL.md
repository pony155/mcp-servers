---
name: aseprite-beat-em-up-boss-production
description: Produce and validate large multi-phase boss sprite sets for pixel-art beat-'em-ups in Aseprite. Use for boss tells, phase transitions, armor, grabs, arena attacks, reactions, combat metadata, and engine handoff rather than ordinary enemy-roster work.
---

# Aseprite Beat-'em-up Boss Production

Define phases, health thresholds, arena constraints, required action tags, and transition rules before increasing frame count. Make dangerous attacks readable through distinct anticipation silhouettes and timing; reserve shared poses only where they do not conceal a phase or attack choice.

Author action contracts with `aseprite_edit_action_metadata`, explicit displacement with `aseprite_edit_root_motion`, and intentional chains with `aseprite_edit_cancel_windows`. Add body, armor, grab, throw, and attack boxes only after animation timing stabilizes. Use named anchors for targets, held characters, shadows, and VFX origins.

Review complete actions with `aseprite_preview_combat_animation`. Validate individual high-risk moves and then the full document with `aseprite_validate_combat_set`; treat missing hurtboxes, targets, and metadata as release blockers. Export an `aseprite_export_beat_em_up_bundle` only after phase transitions and return states are explicit.
