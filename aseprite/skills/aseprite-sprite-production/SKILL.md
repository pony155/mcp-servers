---
name: aseprite-sprite-production
description: Produce and refine editable pixel-art sprites and animations with the Aseprite MCP server. Use when creating an Aseprite document, importing a sprite sheet, matching concept art, editing pixels/frames/layers/tags, applying a palette, transforming cels, reviewing animation quality, or exporting game-ready sprite sheets.
---

# Aseprite Sprite Production

Treat the `.aseprite` document as the source of truth. Keep intermediate revisions as editable sprite documents and export PNG/GIF artifacts only after review.

## Production workflow

1. Call `aseprite_health` before the first operation if server availability is unknown.
2. Inspect an existing source with `aseprite_inspect_sprite`. For a new asset, choose one of:
   - `aseprite_create_animation` when frames, layers, durations, and initial pixels are already known.
   - `aseprite_create_sprite` for a simple starting document.
   - `aseprite_import_sprite_sheet` when the source is a regular PNG frame grid.
3. Establish the intended canvas, frame size, palette, silhouette, anchor point, layer plan, frame count, and timing before detailed edits.
4. Make small, reviewable passes. Use `aseprite_set_pixels` for sparse edits and `aseprite_set_pixel_runs` for spans. Copy or link cels instead of resending unchanged art.
5. Use `aseprite_preview` after meaningful visual changes and a contact sheet for whole-animation review. Use layer or composited pixel reads when exact colors or coordinates matter; do not infer pixel values from a scaled preview.
6. Call `aseprite_validate_animation` before final export. Address errors and explain any intentional warnings.
7. Export with `aseprite_export_sprite_sheet`, or use `aseprite_render` for a standalone PNG/GIF.

## Editing rules

- Frame indices are zero-based. Layer selectors are exact paths such as `Body/Outline`.
- Write each meaningful revision to a new `.aseprite` output path. Only set `overwrite=true` when the user explicitly wants replacement.
- After inspecting a source, pass its `sha256` as `expected_source_hash` to mutation tools when available.
- Edit operations in `aseprite_edit_frames`, `aseprite_edit_layers`, and `aseprite_edit_tags` run sequentially; later indices and paths refer to the state produced by earlier operations.
- Keep pixel reads tightly bounded. They return row-based RGBA runs, not a full image matrix.
- Compare adjacent frames and the loop boundary before final validation.
- Prefer nearest-neighbor sprite resizing. Use canvas resize when changing framing without scaling artwork.
- Preserve transparent padding and a consistent foot baseline unless motion intentionally changes them.

## Pixel-art quality

- Match silhouette and proportions before shading or texture.
- Use deliberate clusters and connected contours; remove isolated noise pixels.
- Keep the palette compact and assign consistent roles to outline, shadow, midtone, highlight, and accents.
- Preserve readable negative space between limbs and torso.
- For idle loops, favor restrained breathing, cloth, braid, or hand motion. Avoid unintentional body-volume changes and baseline jitter.
- Preview at native scale and at an integer zoom. Judge animation both frame-by-frame and as a loop.

## Final handoff

Report the editable document path, preview or render path when one was written, exported sheet and metadata paths, frame dimensions/count, tag names, and validation result. Mention limitations such as unsupported grayscale palette remapping or intentional validation warnings.
