---
name: aseprite-beat-em-up-weapon-and-pickup-production
description: Produce pixel-art weapons, pickups, carried props, and their character interactions for beat-'em-ups in Aseprite. Use for ground, held, attack, thrown, impact, broken, collected, and attachment states rather than general environment props.
---

# Aseprite Beat-'em-up Weapon and Pickup Production

Define the asset's ground footprint, held orientation, pickup origin, character hand anchor, attack reach, thrown pivot, impact state, and disposal rule. Keep ground and held forms recognizably related while allowing the held silhouette to prioritize combat readability.

Use tags for state animations and frame anchors such as `grip`, `pickup`, `throw`, and `impact`. Align character-side `weapon` anchors with the asset's `grip` origin before producing variants. Use animation events for collection, release, impact, breakage, and despawn cues; use combat boxes only when the weapon itself owns gameplay collision.

Preview held and thrown sequences at gameplay scale. Validate action metadata and required anchors, then export bundles with stable identifiers. Palette variants may change rank or ownership, but must not be the only distinction between mechanically different pickups.
