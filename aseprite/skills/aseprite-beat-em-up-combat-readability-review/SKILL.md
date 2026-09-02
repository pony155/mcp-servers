---
name: aseprite-beat-em-up-combat-readability-review
description: Review completed beat-'em-up animations for gameplay readability in Aseprite. Use to diagnose attack tells, active timing, reach, hurt reactions, overlapping boxes, anchors, crowd legibility, and recovery clarity without redesigning unrelated game logic.
---

# Aseprite Beat-'em-up Combat Readability Review

Review at intended gameplay scale and against representative stage contrast. Check idle recognition, anticipation silhouette, contact pose, follow-through, recovery, foot stability, lane depth, and whether attacks remain distinguishable in a crowd.

Use `aseprite_preview_combat_animation` for temporal review and the single-frame overlay for exact active frames. Compare the visible limb or weapon reach with hit boxes, verify hurt and push boxes do not jump unexpectedly, and confirm anchors follow their intended attachment points. Use motion reports when visible displacement disagrees with authored root motion.

Run `aseprite_validate_combat_set` and separate deterministic contract errors from artistic observations. Report issues by action and zero-based frame, explain gameplay impact, and recommend the smallest animation or metadata change that restores clarity.
