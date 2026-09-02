---
name: aseprite-document-optimization
description: Reduce avoidable Aseprite document weight without changing intended artwork or timing. Use for duplicate cel images, empty bounds, excess palette entries, or release-size cleanup.
---

# Aseprite Document Optimization

Capture the source hash and inspect frames, cels, linked groups, palette usage, and visible bounds
before changing anything. Preserve canvas, frame order, durations, tags, events, layer hierarchy,
cel positions, and rendered appearance unless the user explicitly permits a semantic change.

Link only exactly identical cel images; position and opacity may remain independent. Use trimming,
palette cleanup, or color-mode conversion only when they satisfy the delivery contract. Save to a
new revision, compare the result against the source, validate loop and export constraints, and
report which changes reduced duplication or file size. Stop if visual comparison reveals a change
that was not explicitly authorized.
