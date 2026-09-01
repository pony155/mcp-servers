---
name: aseprite-release-asset-audit
description: Perform final release audits of Aseprite asset sets. Use when documents, palettes, animation events, frames, slices, collisions, exports, atlases, and manifests must be checked before handoff.
---

# Aseprite Release Asset Audit

Freeze the source list and release profile before auditing. Validate every document independently, compare expected revisions where available, then check cross-asset dimensions, color modes, naming, tags, slices, events, palettes, and collision conventions.

Run exports only after validation errors are resolved or explicitly waived. Treat partial batch success as partial release failure until reviewed. Report source and output hashes, warnings, failures, atlas counts, intentional exceptions, and exact retry actions; never silently repair release assets during an audit-only request.
