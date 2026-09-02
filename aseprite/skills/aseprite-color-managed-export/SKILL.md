---
name: aseprite-color-managed-export
description: Prepare color-managed Aseprite assets for reliable handoff. Use when sRGB assignment, ICC conversion, profile provenance, or cross-application color consistency matters.
---

# Aseprite Color-Managed Export

Determine the source profile and the destination's required color space before changing metadata. Assigning a profile reinterprets existing channel values; converting a profile changes channel values to preserve appearance. Never substitute one operation for the other without confirming the source assumption.

Keep ICC files inside authorized project roots and retain their name or checksum in handoff notes. Work on a new revision, compare representative colors before and after conversion, and validate the final export profile. For pixel art, review whether conversion introduced off-palette colors or partial alpha and requantize only with explicit approval.
