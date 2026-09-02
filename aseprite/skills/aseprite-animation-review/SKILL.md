---
name: aseprite-animation-review
description: Review and clean Aseprite animations for timing, jitter, arcs, continuity, duplicate frames, baseline drift, loop seams, and export readiness. Use after the main motion and art direction exist.
---

# Aseprite Animation Review

Inspect the document before judging it. Use its frame durations, tags, layers, and canvas dimensions as the factual basis for review.

1. Call `aseprite_preview` in sheet mode and `aseprite_render_contact_sheet` for an overview.
2. Run `aseprite_validate_animation` with tolerances appropriate to the motion. Treat deliberate jumps and squash-and-stretch as intent, not automatic defects.
3. Use `aseprite_compare_frames` on adjacent and loop-boundary frames. Use `aseprite_read_composited_pixels` only when exact bounds or colors are disputed.
4. Report findings by severity and frame number. Separate structural problems, motion discontinuities, silhouette noise, palette inconsistency, and timing issues.
5. When correction is requested, make small output revisions using the narrow edit tools, preview again, and preserve the source with hash guards.

For idle loops, prioritize foot-baseline stability, restrained volume changes, a clean last-to-first transition, and readable secondary motion. Finish with validation and a concise list of intentional remaining warnings.

When cleanup is requested, distinguish cadence defects from drawing defects. Retime before redrawing when durations are the cause; generate inbetweens only between approved endpoints; preserve frame events when indexes change; and use motion reports plus adjacent-frame comparisons to verify arcs and volume after correction.
