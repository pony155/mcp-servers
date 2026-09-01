---
name: aseprite-beat-em-up-combat-authoring
description: Author and review engine-neutral combat timing, boxes, anchors, and events for pixel-art beat-'em-up actions. Use for hitboxes, hurtboxes, pushboxes, grabs, throws, armor, invulnerability, startup, active, recovery, hitstop, hitstun, and knockback.
---

# Aseprite Beat-'em-up Combat Authoring

Start from an existing, stable animation tag. Confirm its frame range and durations, then record the action's type, facing policy, movement mode, return state, startup, active, and recovery phases. Use zero-based document frame indexes consistently. Author per-frame displacement with `aseprite_edit_root_motion`; do not derive gameplay movement from visual centroids.

Author enabled hurt and push boxes for body occupancy first. Add hit, grab, or throw boxes only to active frames; keep each box identifier stable within its action. Set damage, hitstop, hitstun, knockback, and priority only when the gameplay design provides them. Use armor or invulnerable boxes deliberately and do not treat missing hurtboxes as implicit invulnerability.

Place `feet` on the ground contact point and add `grab`, `weapon`, `shadow`, or `vfx` anchors when consumers need them. Use `aseprite_edit_combat_boxes` and `aseprite_edit_frame_anchors` to write a new document. Preview every active frame with `aseprite_preview_combat_overlay`; box colors are diagnostic, not runtime art.

Add cancel windows only from an explicit transition design, including on-hit, on-block, and on-whiff conditions. Run `aseprite_validate_combat_action` while iterating and `aseprite_validate_combat_set` before handoff. Resolve errors before warnings. Treat the manifest's schema version and source hash as part of the engine import contract.
