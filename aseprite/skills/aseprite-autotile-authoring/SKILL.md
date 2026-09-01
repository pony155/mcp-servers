---
name: aseprite-autotile-authoring
description: Plan and author seamless Aseprite terrain autotiles with complete edge, corner, transition, and adjacency coverage. Use for rule-driven terrain sets, not ordinary standalone tiles.
---

# Aseprite Autotile Authoring

Confirm the target adjacency system before drawing: 4-way, 8-way, Wang edges, blob/bitmask, or an engine-specific ordering. Do not invent an index layout when the engine contract is unknown.

Build base, edges, outer corners, inner corners, junctions, and variants in stable index order. Use exact tile and palette inspection, edit tiles and tilemaps in new revisions, then validate duplicate/empty tiles and opposite edges. Report missing adjacency cases and the final index mapping.
