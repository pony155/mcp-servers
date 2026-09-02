---
name: aseprite-beat-em-up-enemy-roster-production
description: Design, produce, and audit coherent pixel-art enemy rosters for lane-based beat-'em-ups in Aseprite. Use for shared action contracts, silhouettes, rank variants, bosses, combat reach, anchors, palettes, and roster consistency.
---

# Aseprite Beat-'em-up Enemy Roster Production

Write a roster matrix before production. Give every enemy the required locomotion, attack, hurt, knockdown, get-up, and defeat tags; list optional grab, block, dodge, ranged, weapon, elite, and boss actions separately. Decide which canvas, ground line, color mode, anchor names, and export contract are shared.

Differentiate roles through silhouette, stance, reach, tempo, lane control, and attack tells rather than palette swaps alone. Reuse palettes or modular parts only where this preserves readable identity. Keep ordinary enemies cheaper than bosses in frame count and effect complexity.

For each document, use the character-production workflow, preview complete combat actions, and run `aseprite_validate_combat_set`. Then run `aseprite_validate_character_roster` across the complete set with explicit required actions and anchors. Fix per-character contract errors first, then resolve shared canvas or color-mode mismatches.

Export one combat manifest per approved character. Use batch and atlas workflows only after roster validation passes, and keep character identifiers outside display names so localization or naming changes do not break engine references.
