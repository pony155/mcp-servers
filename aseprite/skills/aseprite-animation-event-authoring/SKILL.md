---
name: aseprite-animation-event-authoring
description: Author structured gameplay and audio events on Aseprite animation frames. Use when footsteps, impacts, hitboxes, projectiles, sounds, particles, or state transitions must align with final frame timing.
---

# Aseprite Animation Event Authoring

Obtain the engine's event names and payload schema before editing. Treat events as gameplay metadata, not visual guesses: confirm whether a trigger belongs at anticipation, first contact, peak overlap, or recovery and whether looping tags should fire it every cycle.

Use stable event names, zero-based frames, optional exact layer context, and compact string payloads. Reinspect the sprite after edits, verify events remain inside their intended tags, and recheck them whenever frames are inserted, removed, reordered, or retimed.
