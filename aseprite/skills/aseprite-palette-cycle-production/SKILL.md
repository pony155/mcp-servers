---
name: aseprite-palette-cycle-production
description: Build and verify indexed-color palette-cycle animations in Aseprite. Use for water, fire, lights, energy, conveyor, or ambient motion driven by rotating palette indices instead of redrawing pixels.
---

# Aseprite Palette Cycle Production

Confirm that the target runtime supports palette cycling; otherwise produce ordinary frames. Work on an indexed-color revision and reserve one ordered, contiguous semantic ramp per effect. Do not cycle shared outline, transparency, UI, or character colors unless their motion is intentional.

Inspect and analyze the palette before choosing indices. Apply the smallest cycle range, preview the animation, and verify that linked cels outside the requested frame range retain their appearance. Check the loop transition and document the index order, step, direction, frame range, and expected playback rate for engine integration.
