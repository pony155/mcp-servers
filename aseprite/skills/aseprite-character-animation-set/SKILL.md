---
name: aseprite-character-animation-set
description: Produce coherent character animation families in Aseprite across directions and game genres. Use when movement, combat, reactions, modular parts, anchors, timing, and export conventions must remain consistent.
---

# Aseprite Character Animation Set

Define the state list, direction count, frame budgets, baseline, pivot, silhouette constraints, and engine naming contract before drawing. Reuse established layers, palette roles, and proportions across every state.

Build one representative direction and motion family first, review it at native scale and as a contact sheet, then propagate its conventions. Validate every tag, transition pose, frame duration, baseline, and export profile. Report intentional asymmetry or reused/mirrored directions rather than hiding them.

Choose the relevant mode instead of loading a separate overlapping skill: directional sets require matching phase and anchor contracts; platformer sets require grounded, airborne, landing, and collision phases; top-down sets require camera-consistent silhouettes; fighting-game sets require explicit startup, active, recovery, and reaction timing. Modular characters additionally require layer-compatible body and equipment silhouettes across every authored frame.
