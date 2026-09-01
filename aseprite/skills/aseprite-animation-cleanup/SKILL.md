---
name: aseprite-animation-cleanup
description: Clean and stabilize existing Aseprite animation frames. Use for jitter, inconsistent timing, stray pixels, rough inbetweens, broken arcs, baseline drift, or loop seams after the main motion is authored.
---

# Aseprite Animation Cleanup

Lock the intended key poses before cleanup. Inspect frame timing and cel geometry, validate the animation, and use an onion-skin preview to separate intentional overshoot from accidental jitter. Correct timing and cel position before redrawing pixels because spatial or exposure changes can eliminate apparent defects.

Generate inbetweens only between approved endpoints and choose hold or nearest interpolation for crisp pixel motion; use crossfade only when blended colors are acceptable. Use the motion report to locate discontinuities before changing pixels, and use bounded retiming when the defect is cadence rather than drawing. Compare adjacent problem frames, preserve arcs and volume, then validate both the full motion and its loop transition. Review gameplay events after inserting, baking, removing, or retiming frames because their indices or timing may shift.
