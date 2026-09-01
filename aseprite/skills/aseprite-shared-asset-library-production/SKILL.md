---
name: aseprite-shared-asset-library-production
description: Maintain reusable Aseprite layer and group libraries. Use when effects, equipment, UI parts, poses, or other image-layer trees must move safely between compatible documents.
---

# Aseprite Shared Asset Library Production

Define library compatibility through canvas dimensions, color mode, frame meanings, layer naming,
metadata keys, anchors, and ownership. Inspect both documents before copying. Copy the smallest
useful layer tree, choose the target parent explicitly, and rename the root only when required by
the destination contract.

Reject implicit conversion between incompatible documents. Treat tilemaps as a separate exchange
workflow because their tilesets are document-owned. After copying, verify frame timing, cel
positions, opacity, z-index, blend modes, properties, and layer order, then compare or preview the
result. Keep the source library unchanged and publish a new destination revision.
