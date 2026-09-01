---
name: aseprite-collision-shape-authoring
description: Derive and refine game collision geometry from Aseprite assets. Use when rectangles or contour polygons must balance visual fit, stability, and runtime cost.
---

# Aseprite Collision Shape Authoring

Obtain the engine coordinate origin, winding convention, polygon limits, alpha threshold, and distinction between hurtboxes, hitboxes, solids, and triggers. Visual alpha is evidence, not final gameplay intent: exclude hair, particles, weapon trails, and other decorative pixels unless the design requires contact.

Generate rectangles for stable broad-phase shapes and polygons only where tighter contours materially help. Simplify consistently across frames, avoid self-intersections and excessive point churn, and compare adjacent shapes for gameplay jitter. Store semantic type and event timing separately from geometry, then report coordinate space, threshold, simplification tolerance, and per-frame point counts.
