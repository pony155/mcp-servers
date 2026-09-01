---
name: aseprite-platformer-character-production
description: Produce and validate pixel-art platformer character animation sets in Aseprite. Use for grounded movement, jump phases, attacks, reactions, collision, pivots, and gameplay event timing.
---

# Aseprite Platformer Character Production

Establish canvas size, baseline, collision footprint, facing policy, movement speed, and the complete state graph before drawing. Separate jump anticipation, ascent, apex, fall, and landing when gameplay uses those phases; do not force visual timing to imply physics that the controller does not implement.

Keep foot contacts, body volume, weapon reach, and pivots consistent across idle, run, jump, attack, hurt, and death tags. Author events only after frame timing stabilizes, then validate transitions, collision masks, tags, and the engine export profile.
