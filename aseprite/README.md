# Aseprite MCP Server

A local Python Model Context Protocol server for inspecting, creating, editing, rendering, and exporting Aseprite documents.

## Requirements

- Python 3.10 through 3.14.
- Aseprite 1.3-rc5 or newer. Aseprite 1.3.18.3 is the currently tested version.
- [`uv`](https://docs.astral.sh/uv/) for the documented development workflow.

Aseprite is a separate application and is not included with this project. Install it through an official distribution channel and comply with its license.

## Install from source

```console
cd servers/aseprite
uv sync --extra dev
```

Run the server with at least one directory in which it may access files:

```console
uv run aseprite-mcp --allow-root C:\path\to\sprites
```

If Aseprite is not discovered automatically:

```console
uv run aseprite-mcp --aseprite "C:\Program Files\Aseprite\Aseprite.exe" --allow-root C:\path\to\sprites
```

## MCP client configuration

From a source checkout on Windows:

```json
{
  "mcpServers": {
    "aseprite": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/path/to/mcp-servers/servers/aseprite",
        "run",
        "aseprite-mcp",
        "--allow-root",
        "C:/path/to/sprites"
      ]
    }
  }
}
```

### WSL Python with Windows Aseprite

The server can run in a Linux virtual environment under WSL while launching the Windows
`Aseprite.exe`. WSL interoperability must be enabled, and all paths supplied to MCP tools must use
the WSL view of the filesystem (for example, `/mnt/c/Users/ada/Sprites/hero.aseprite`). The server
keeps validation and result paths in that form and translates only the arguments passed to
Aseprite.

For the best file-I/O performance and compatibility, keep sprite inputs and outputs on a Windows
drive mounted under `/mnt`, while keeping the repository and virtual environment in the WSL Linux
filesystem:

```console
cd ~/src/mcp-servers/servers/aseprite
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
aseprite-mcp \
  --aseprite "/mnt/c/Program Files (x86)/Steam/steamapps/common/Aseprite/Aseprite.exe" \
  --allow-root "/mnt/c/Users/ada/Sprites"
```

With `--execution-mode auto`, which is the default, a `.exe` launched under WSL activates Windows
path translation. Use `--execution-mode wsl-windows` to force it or `--execution-mode native` when
running a Linux build of Aseprite under WSL.

Bridge control files are automatically created inside the first allowed root mounted below
`/mnt/<drive>`, then removed after each operation. To use a dedicated existing directory instead:

```console
aseprite-mcp \
  --aseprite "/mnt/c/Program Files/Aseprite/Aseprite.exe" \
  --allow-root "/mnt/c/Users/ada/Sprites" \
  --bridge-temp-root "/mnt/c/Users/ada/AppData/Local/Temp"
```

Files in the WSL Linux filesystem are exposed to Aseprite through a
`\\wsl.localhost\<distribution>\...` path. This requires `WSL_DISTRO_NAME`; using `/mnt/c` for
artwork avoids that UNC path and is recommended.

Example MCP client configuration when the client launches commands inside WSL:

```json
{
  "mcpServers": {
    "aseprite": {
      "command": "/home/ada/src/mcp-servers/servers/aseprite/.venv/bin/aseprite-mcp",
      "args": [
        "--aseprite",
        "/mnt/c/Program Files/Aseprite/Aseprite.exe",
        "--allow-root",
        "/mnt/c/Users/ada/Sprites"
      ]
    }
  }
}
```

Repeat `--allow-root` to authorize more than one directory. The equivalent environment settings are:

- `ASEPRITE_EXECUTABLE`
- `ASEPRITE_MCP_ROOTS`, separated by the operating system path separator
- `ASEPRITE_MCP_TIMEOUT_SECONDS`
- `ASEPRITE_MCP_MAX_CONCURRENCY`
- `ASEPRITE_MCP_MAX_CAPTURE_BYTES`
- `ASEPRITE_MCP_EXECUTION_MODE`
- `ASEPRITE_MCP_BRIDGE_TEMP_ROOT`
- `ASEPRITE_MCP_LOG_LEVEL`
- `ASEPRITE_MCP_TOOL_PROFILES`, as a comma-separated profile list

## Tool profiles

The default `full` profile exposes every tool and preserves existing client behavior. Smaller
profiles reduce the schemas placed in an MCP client's context:

| Profile | Intended surface |
| --- | --- |
| `core` | Health and normalized sprite inspection. |
| `sprite` | General document, pixel, palette, preview, and export work. |
| `animation` | Sprite tools plus animation editing, review, and validation. |
| `tiles` | Sprite tools plus tilesets, tilemaps, metadata, and validation. |
| `export` | Inspection plus render and export tools. |
| `qa` | Inspection plus read-only comparison and validation tools. |
| `full` | Every registered tool. |

Repeat `--tool-profile` to combine profiles. Core tools are always available:

```console
python main.py --allow-root /path/to/sprites \
  --tool-profile animation --tool-profile tiles
```

Profiles affect tool discovery only. They do not broaden allowed roots, overwrite permission, or
the fixed Lua-operation allowlist.

Call `aseprite_list_capabilities` to inspect every supported tool, its domain, read/write policy,
output kind, Aseprite requirement, profile membership, and whether it is enabled by the running
server. The checked-in [`tools/TOOLS.md`](tools/TOOLS.md) and
[`tools/catalog.json`](tools/catalog.json) contain the same build-time catalog. Regenerate them
after changing tools:

```console
python aseprite/tools/generate_catalog.py
```

Common path, overwrite, and optimistic-concurrency parameter schemas live in `tools/inputs.py`.
New tools must also receive an explicit policy in `capabilities.py`; unclassified tools are rejected
during server construction and catalog generation.

## Logging

Diagnostics are written to stderr so MCP protocol traffic on stdout remains valid. The default
level is `INFO`. Use `DEBUG` to include executable discovery candidates, authorized roots,
translated process arguments, bridge workspace paths, and captured Aseprite diagnostics:

```console
python main.py --log-level DEBUG --allow-root /path/to/sprites
```

Supported levels are `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`. Pixel values and complete
bridge request payloads are not logged.

## Tools

| Tool | Purpose | Writes files |
| --- | --- | --- |
| `aseprite_health` | Report server, executable, and Aseprite API status. | No |
| `aseprite_inspect_sprite` | Read dimensions, frames, layers, tags, slices, and palettes. | No |
| `aseprite_render` | Render a PNG frame or GIF animation selection. | Yes |
| `aseprite_export_sprite_sheet` | Export a PNG sheet and JSON-array metadata. | Yes |
| `aseprite_create_sprite` | Create a bounded `.ase` or `.aseprite` document. | Yes |
| `aseprite_create_animation` | Create frames, layer cels, pixels, durations, and animation tags in one call. | Yes |
| `aseprite_set_pixels` | Set up to 10,000 RGBA pixels on one layer/frame. | Yes |
| `aseprite_import_sprite_sheet` | Import a PNG grid as an editable animation with one cel per frame. | Yes |
| `aseprite_resize_canvas` | Change canvas dimensions and anchor artwork without scaling it. | Yes |
| `aseprite_resize_sprite` | Scale a document and its cels with nearest-neighbor sampling. | Yes |
| `aseprite_validate_animation` | Report empty or duplicate frames, visible bounds, baseline drift, and size drift. | No |
| `aseprite_preview` | Return an inline PNG for one frame or a sprite-sheet selection. | No |
| `aseprite_read_pixels` | Read a bounded rectangle as compact row-based RGBA runs. | No |
| `aseprite_edit_frames` | Add, duplicate, remove, or retime frames sequentially. | Yes |
| `aseprite_edit_layers` | Add, remove, rename, show, hide, reorder, or regroup layers. | Yes |
| `aseprite_edit_tags` | Create, update, or remove animation tags. | Yes |
| `aseprite_apply_palette` | Remap cel colors to the nearest supplied palette. | Yes |
| `aseprite_transform_cel` | Translate, flip, or rotate one image cel. | Yes |
| `aseprite_read_composited_pixels` | Read exact final visible frame pixels as RGBA runs. | No |
| `aseprite_set_pixel_runs` | Write bounded horizontal color runs efficiently. | Yes |
| `aseprite_copy_cel` | Copy or link a cel to another layer and frame. | Yes |
| `aseprite_compare_frames` | Measure composited frame differences and optionally write a diff PNG. | Optional |
| `aseprite_edit_slices` | Create/update frame-specific slices or remove named slices. | Yes |
| `aseprite_trim_cels` | Trim transparent cel borders without changing canvas placement. | Yes |
| `aseprite_edit_properties` | Set or remove scalar user properties on production objects. | Yes |
| `aseprite_convert_color_mode` | Convert RGB, grayscale, or indexed mode with explicit dithering. | Yes |
| `aseprite_edit_tileset` | Create/rename tilesets and add, remove, or repaint tiles. | Yes |
| `aseprite_render_contact_sheet` | Write a labelled PNG grid containing every frame. | Yes |
| `aseprite_inspect_cels` | Inspect cel geometry, z-order, image identity, and links. | No |
| `aseprite_analyze_palette` | Report color usage, unused entries, and near-duplicates. | No |
| `aseprite_replace_color` | Replace colors across selected layers and frames. | Yes |
| `aseprite_fill_region` | Fill a contiguous region or every matching pixel. | Yes |
| `aseprite_draw_shapes` | Draw validated lines, rectangles, and ellipses. | Yes |
| `aseprite_edit_selection` | Combine or clear rectangular document selections. | Yes |
| `aseprite_apply_outline` | Apply a bounded inside or outside cel outline. | Yes |
| `aseprite_inspect_tilesets` | Inspect tilesets and tilemap layer paths. | No |
| `aseprite_edit_tilemap` | Create or update bounded tilemap cells. | Yes |
| `aseprite_validate_tileset` | Detect empty, duplicate, and edge-mismatched tiles. | No |
| `aseprite_export_tileset` | Export a tileset PNG grid and JSON metadata. | Yes |
| `aseprite_preview_animation` | Return an inline animated GIF. | No |
| `aseprite_crop_sprite` | Crop the canvas to selected visible content with padding. | Yes |
| `aseprite_draw_strokes` | Draw bounded pencil strokes with explicit brush settings. | Yes |
| `aseprite_transform_selection` | Transform an explicit rectangular pixel region. | Yes |
| `aseprite_edit_palette_entries` | Set, append, remove, or swap palette entries. | Yes |
| `aseprite_compare_sprites` | Compare sprite structure, metadata, and frame pixels. | No |
| `aseprite_validate_export_profile` | Check an asset against an explicit export contract. | No |
| `aseprite_pack_atlas` | Pack multiple authorized sprites into a PNG/JSON atlas. | Yes |
| `aseprite_quantize_palette` | Quantize and convert a document to indexed color. | Yes |
| `aseprite_import_palette` | Load a supported palette into a document revision. | Yes |
| `aseprite_export_palette` | Export the first sprite palette to a standard file. | Yes |
| `aseprite_extract_slices` | Render named slice/frame pairs to explicit PNG paths. | Yes |
| `aseprite_generate_collision_masks` | Derive bounds or component rectangles from alpha. | No |
| `aseprite_batch_export` | Run bounded sprite-sheet exports independently. | Yes |
| `aseprite_validate_asset_set` | Validate a bounded set and cross-asset consistency. | No |
| `aseprite_merge_layers` | Merge one layer downward or flatten an output revision. | Yes |
| `aseprite_export_frames` | Export explicit frames to explicit PNG paths. | Yes |
| `aseprite_import_frames` | Insert or append same-size PNG files as frames. | Yes |
| `aseprite_render_tilemap_preview` | Return an inline preview of explicit tile cells. | No |
| `aseprite_edit_grid` | Set sprite grid origin and cell dimensions. | Yes |
| `aseprite_edit_blend_modes` | Set validated blend modes on exact layer paths. | Yes |
| `aseprite_edit_animation_events` | Manage structured frame-event metadata. | Yes |
| `aseprite_preview_nine_slice` | Preview a named nine-slice at a target size. | No |
| `aseprite_edit_cels` | Move, fade, reorder, unlink, or remove exact cels. | Yes |
| `aseprite_generate_inbetweens` | Insert bounded cel tweens between approved endpoints. | Yes |
| `aseprite_palette_cycle` | Rotate indexed-color entries across an existing frame range. | Yes |
| `aseprite_preview_onion_skin` | Preview surrounding frames with directional tinting. | No |
| `aseprite_select_by_color` | Build a document selection from matching colors. | Yes |
| `aseprite_create_tileset_from_sheet` | Slice an image-layer sheet into a named tileset. | Yes |
| `aseprite_validate_pixel_art` | Check alpha, palette, color-count, and isolated-pixel rules. | No |
| `aseprite_validate_loop_transition` | Check pixel and timing continuity at loop endpoints. | No |
| `aseprite_inspect_tile_metadata` | Read scalar properties from a tileset and selected tiles. | No |
| `aseprite_edit_tile_metadata` | Set or remove scalar tileset and tile properties. | Yes |
| `aseprite_edit_color_space` | Assign or convert sRGB and authorized ICC profiles. | Yes |
| `aseprite_retime_animation` | Retime all frames or one tag to a deterministic duration. | Yes |
| `aseprite_bake_tag_direction` | Materialize directional tag playback as appended frames. | Yes |
| `aseprite_generate_motion_report` | Measure bounds, centroid, velocity, and acceleration. | No |
| `aseprite_generate_collision_polygons` | Trace simplified outer contours from sprite alpha. | No |
| `aseprite_export_bitmap_font` | Export explicit glyphs as a PNG atlas and JSON metrics. | Yes |

Frame indices are zero-based. Layer selectors are exact hierarchy paths such as `Character/Outline`.

### Animation creation

`aseprite_create_animation` creates a complete animation in one atomic operation. Define flat,
uniquely named `layers`, then supply `frames` containing a duration and zero or more cels. Each cel
selects one declared layer and contains bounded `#RRGGBB` or `#RRGGBBAA` pixels. A frame may contain
at most one cel for each layer. Optional tags use zero-based inclusive frame ranges and support
`forward`, `reverse`, `ping_pong`, and `ping_pong_reverse` directions.

The operation allows at most 256 frames, 128 layers, 10,000 pixels per cel, and 100,000 supplied
pixels across the animation. Empty frames are allowed intentionally and can be detected later with
`aseprite_validate_animation`.

### Sprite-sheet import

`aseprite_import_sprite_sheet` accepts a PNG containing a regular grid. `frame_width` and
`frame_height` are required. The server infers the number of columns from the image width unless
`columns` is supplied, and imports all complete grid cells unless `frame_count` limits the result.
`margin` describes transparent or decorative space around the grid, while `spacing` describes the
gap between cells. PNG alpha is preserved; `transparent_color` can additionally remove an exact
`#RRGGBB` or `#RRGGBBAA` color. Every imported frame receives the same `duration_ms` value.

### Resize behavior

`aseprite_resize_canvas` changes the canvas without resampling artwork. Its nine-position `anchor`
controls where existing cels remain when space is added or removed. `aseprite_resize_sprite`
changes both canvas and artwork dimensions; version 0.1 supports the deterministic `nearest`
method only. Both tools accept `expected_source_hash` and require `overwrite=true` for in-place
replacement.

### Animation validation

`aseprite_validate_animation` scans visible image-layer pixels and returns per-frame bounds, opaque
pixel counts, baselines, durations, empty frames, possible duplicate groups, and drift measurements.
`baseline_tolerance` and `bounds_tolerance` control when drift becomes an issue. Tilemap cel bounds
are approximated and identified by a warning. Validation stops when its bounded pixel-visit budget
would be exceeded.

### Production editing

`aseprite_preview` returns PNG image content directly to an MCP client and does not write a user
file. Frame mode selects one zero-based frame; sheet mode supports a layout, tag, and layer
selection. The preview must fit within `ASEPRITE_MCP_MAX_CAPTURE_BYTES`.

`aseprite_read_pixels` reads at most 65,536 canvas pixels from one exact image-layer path and frame.
Its `rgba_runs` response compresses consecutive pixels of the same `#RRGGBBAA` color on each row;
transparent runs are omitted unless requested.

Frame, layer, and tag edits accept ordered operation lists. Operations run sequentially, so later
indices and layer paths refer to the document state produced by earlier operations. Palette
application supports RGB and indexed documents, remaps to at most 256 nearest colors, and rejects
grayscale documents. For indexed sprites, transparent indices remain transparent; per-pixel alpha
preservation is available only for RGB sprites. Cel transforms operate on one image-layer cel and
support translation, horizontal/vertical flips, and 90-degree turns.

Every mutation writes through a temporary sibling, uses explicit overwrite behavior, and accepts
`expected_source_hash` to reject stale edits.

### Advanced production tools

`aseprite_read_composited_pixels` reads the final visible frame rather than an individual layer.
`aseprite_compare_frames` measures exact composited changes, changed bounds, and baseline movement;
an optional magenta PNG identifies changed pixels. `aseprite_render_contact_sheet` creates a bounded
review grid with zero-based frame labels.

`aseprite_set_pixel_runs` accepts horizontal spans and permits at most 100,000 written pixels per
call. `aseprite_copy_cel` creates either an independent image copy or a linked cel; replacing an
existing target cel requires `replace=true`. `aseprite_trim_cels` preserves absolute canvas
placement while reducing transparent image borders.

Slices support frame-specific bounds, optional local nine-slice centers, and local pivots. Scalar
user properties can target sprites, layers, tags, slices, and cels. Color-mode conversion uses the
documented Aseprite conversion command with explicit dithering choices. Tileset editing supports
bounded tileset creation, renaming, tile insertion/removal, and tile pixel replacement. Tilemap
cell editing is available separately through `aseprite_edit_tilemap`.

Cropping derives a union of visible non-tilemap pixels across optional frame and layer selections,
then applies clipped transparent padding. Stroke drawing accepts only bounded pencil point lists.
Selection transforms use explicit rectangular bounds and support move, copy, flips, quarter-turns,
and integer nearest-neighbor scaling without depending on Aseprite's interactive selection UI.

Palette-entry edits run sequentially. Removing an entry requires a replacement index; indexed
pixels and the transparent index are remapped to retain valid indices. Swaps preserve indexed
appearance by default. Sprite comparison checks dimensions, frame count, color mode, layer
structure, tags, slices, and composited RGBA pixels. Export profiles can require exact or maximum
dimensions, power-of-two canvases, color mode, frame count, named layers/tags/slices, and a maximum
palette size.

Atlas packing accepts up to 64 explicit sources and uses Aseprite's deterministic packed-sheet
export. Palette quantization uses Aseprite's documented quantizer and indexed conversion options.
Palette import replaces palette entries; on indexed sprites, existing pixel indices are retained,
so colors can change intentionally. Slice extraction requires every output path explicitly and
publishes files only after all requested slices render successfully.

Collision masks are rectangular approximations derived from a composited frame or exact image
layer. Batch export reports each job independently and does not roll back already published jobs.
Asset-set validation applies one export profile per document and can additionally require matching
dimensions and color modes across the set.

Layer merging supports an exact `merge_down` target or whole-document flattening. Frame interchange
uses explicit PNG paths and requires imported images to match the existing canvas. Grid bounds and
validated non-group blend modes are stored in editable document revisions.

Animation events are stored as structured JSON in the `mcp.animation_events` sprite property and
are returned by `aseprite_inspect_sprite`. Tilemap previews compose explicit tile cells without
editing the source. Nine-slice previews preserve fixed corners and borders while nearest-neighbor
scaling the center and edge regions into a bounded inline PNG.

Property inspection now provides the read side of scalar metadata workflows across sprite, layer,
cel, tag, slice, tileset, and tile objects. Versioned tilemap JSON can be exported and imported with
explicit cell transforms and bounded top-level layer creation. Named layer variants render through
the existing safe export boundary. Exact duplicate cel images can be linked without deleting
frames, and compatible transparent image-layer trees can be copied between documents; background
and tilemap layer copying is intentionally rejected.

### Sprite-production skill

Distributable Codex skills are under [`skills`](skills). Use the generated
[`skills/CATALOG.md`](skills/CATALOG.md) to choose among the six workflow families and resolve
overlap between related skills. Its machine-readable companion, [`skills/catalog.json`](skills/catalog.json),
records every skill's recommended MCP tool profile.

After adding, removing, or renaming a skill, regenerate the catalog with
`python aseprite/skills/generate_catalog.py`. Copy only the desired skill directories into your
Codex skills directory (normally `$CODEX_HOME/skills`) and restart Codex to make them available.

## Safety behavior

- File tools are disabled until an allowed root is configured.
- Canonical path checks reject access outside configured roots, including link traversal.
- Existing outputs are rejected unless `overwrite=true` is explicit.
- Edits default to a different output file and support an optional SHA-256 source guard.
- Aseprite runs with argument arrays and no command shell.
- WSL-to-Windows path conversion occurs only after local path authorization.
- Tool calls cannot supply raw Aseprite flags, executable paths, scripts, or Lua source.
- Completed files are written to temporary sibling paths before publication.
- Requests are bounded by time, process concurrency, diagnostic output, dimensions, frames, layers,
  per-cel and total animation pixel edits, pixel runs, pixel reads, preview bytes, contact-sheet
  dimensions, and validation/palette/comparison pixel visits.

## Development

```console
uv run ruff check .
uv run mypy src
uv run pytest
uv build
```

Integration tests run only when `ASEPRITE_EXECUTABLE` points to an installed Aseprite executable:

```console
$env:ASEPRITE_EXECUTABLE = "C:\Program Files\Aseprite\Aseprite.exe"
uv run pytest -m integration
```

Under WSL, configure the executable and keep pytest's temporary directory on a Windows mount so
the integration suite exercises drive-path translation:

```console
ASEPRITE_EXECUTABLE="/mnt/c/Program Files/Aseprite/Aseprite.exe" \
  uv run pytest -m integration --basetemp=/mnt/c/Users/ada/AppData/Local/Temp/aseprite-mcp-tests
```

Tests always copy or create documents in temporary directories; they do not modify source fixtures.

## Current limitations

- The server uses batch processes and cannot manipulate an unsaved document in an existing Aseprite UI.
- Some Windows installations refuse a concurrent batch process while the interactive Aseprite UI
  is open. If health reports exit code 1 without diagnostics, close the desktop instance and retry.
- Render output is file-based; inline MCP image delivery is not implemented yet.
- Pixel editing targets image layers, not groups or tilemaps.
- Inspection reports the Lua API's current slice geometry. Use sprite-sheet JSON when complete animated slice keys are required.
- Only PNG/GIF render outputs and PNG/JSON sprite-sheet outputs are supported.
- WSL interoperability targets WSL 2 with Windows drives mounted at `/mnt/<drive>`; custom mount
  layouts require artwork paths reachable through the `\\wsl.localhost` share.

See the broader [implementation plan](../../Docs/Aseprite.md) for future phases and design rationale.
