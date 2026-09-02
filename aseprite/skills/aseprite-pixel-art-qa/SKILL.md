---
name: aseprite-pixel-art-qa
description: Audit and restore Aseprite pixel art for clusters, stray pixels, silhouettes, accessibility, palette consistency, frame continuity, scaling damage, document weight, and release defects. Use for evidence-based QA rather than initial art direction.
---

# Aseprite Pixel Art QA

Inspect the sprite, cels, and palette before judging it. Review native-scale previews and contact sheets, then use exact pixel reads, palette analysis, frame comparison, and animation validation to substantiate findings.

Report defects by severity with layer/frame coordinates when available. Distinguish intentional texture, asymmetry, squash, and anticipation from accidental noise. When correction is requested, make small hashed output revisions and re-run the relevant checks.

Include contrast, color-only communication, rapid flashing, and crowded silhouette checks when accessibility matters. For restoration, remove resampling and compression artifacts without redesigning the source. For optimization, link identical cels, trim transparent bounds, and remove unused palette entries only when visual output and timing remain unchanged.
