---
name: aseprite-animation-review
description: Review Aseprite pixel-art animations for timing, motion, visual consistency, duplicate or empty frames, baseline drift, and export readiness. Use when evaluating or correcting an existing animation rather than creating its initial art direction.
---

# Aseprite Animation Review

Inspect the document before judging it. Use its frame durations, tags, layers, and canvas dimensions as the factual basis for review.

1. Call `aseprite_preview` in sheet mode and `aseprite_render_contact_sheet` for an overview.
2. Run `aseprite_validate_animation` with tolerances appropriate to the motion. Treat deliberate jumps and squash-and-stretch as intent, not automatic defects.
3. Use `aseprite_compare_frames` on adjacent and loop-boundary frames. Use `aseprite_read_composited_pixels` only when exact bounds or colors are disputed.
4. Report findings by severity and frame number. Separate structural problems, motion discontinuities, silhouette noise, palette inconsistency, and timing issues.
5. When correction is requested, make small output revisions using the narrow edit tools, preview again, and preserve the source with hash guards.

For idle loops, prioritize foot-baseline stability, restrained volume changes, a clean last-to-first transition, and readable secondary motion. Finish with validation and a concise list of intentional remaining warnings.
