---
name: aseprite-batch-asset-pipeline
description: Apply a consistent inspection, validation, naming, and export contract across multiple Aseprite assets. Use for bounded asset batches with an explicit output convention, not for unrelated bulk filesystem changes.
---

# Aseprite Batch Asset Pipeline

Confirm allowed roots, source list, naming convention, engine schema, overwrite policy, and stopping behavior before mutation. Process each source independently so one failure does not obscure prior results.

For every document, record its hash, inspect structure, run the appropriate animation/palette/tileset checks, export to deterministic distinct paths, and record outputs. Never infer permission to overwrite an entire batch. Finish with a manifest-style summary of successes, warnings, failures, and retry guidance.
