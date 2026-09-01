# Aseprite MCP Server Implementation Plan

**Status:** v0.1 core and sprite-production editing surface implemented
**Last updated:** 2026-09-01
**Target location:** `aseprite/`

## 1. Objective

Build a local Model Context Protocol (MCP) server that lets an MCP client inspect, create, edit, render, and export Aseprite documents through a small set of safe, structured tools.

The first release should favor predictable file-based workflows over control of the currently open Aseprite UI. Aseprite will run as a child process in batch mode, using its documented CLI and Lua scripting API. The server will not bundle Aseprite; users must install it separately and comply with its license.

## 2. Scope

### Initial release

- Detect the Aseprite executable and report its version.
- Inspect sprite metadata, including dimensions, color mode, frames, layers, tags, slices, and palettes.
- Render a frame or animation to a supported image format.
- Export sprite sheets and their JSON metadata.
- Create a basic sprite document.
- Apply bounded pixel, frame, layer, tag, and palette edits.
- Operate over MCP stdio for local clients.
- Support Windows first, while keeping process and path abstractions portable to macOS and Linux.

### Not in the initial release

- Driving Aseprite through keyboard or mouse automation.
- Editing an unsaved document in an already-running Aseprite UI.
- Remote HTTP hosting, authentication, or multi-user operation.
- Arbitrary Lua, shell, or Aseprite command execution supplied by a client.
- General image generation or semantic interpretation of artwork.
- Bundling or downloading the Aseprite executable.

## 3. Proposed technical baseline

The initial implementation should use:

- Python 3.10 through 3.14.
- The stable v2 `mcp` package and its high-level `MCPServer` API.
- MCP stdio via `mcp.run()`, retaining compatible protocol negotiation unless testing identifies a reason to reject legacy clients.
- Pydantic models and the SDK's generated schemas for runtime input and output validation.
- `uv` for project and dependency management.
- A dedicated Lua bridge checked into the server directory.
- AnyIO-compatible subprocess APIs with argument sequences and no command shell.

This is the proposed baseline, not permission to add a repository-wide framework. The Aseprite server should remain independently buildable. Root workspace tooling should be added only when another server or package needs it.

## 4. Architecture

```text
MCP client
    |
    | stdio / MCP
    v
Python MCP server
    |
    +-- tool schemas and handlers
    +-- path policy and operation limits
    +-- native / WSL-to-Windows path boundary
    +-- Aseprite adapter
            |
            | child process, no shell
            v
      aseprite --batch --script bridge.lua
            |
            +-- reads request JSON from a temporary file
            +-- uses the Aseprite Lua API
            +-- writes response JSON to a temporary file
```

### Component responsibilities

`server`

- Builds the MCP server and registers tools.
- Converts domain results into MCP structured content.
- Maps internal failures to stable public error codes.
- Writes protocol messages only to stdout; diagnostics go to stderr.

`configuration`

- Resolves command-line arguments and environment settings.
- Locates and validates the Aseprite executable.
- Establishes allowed filesystem roots and operational limits.

`Aseprite adapter`

- Exposes typed operations such as `inspect`, `render`, and `createSprite`.
- Does not know about MCP request or response types.
- Chooses between a direct documented CLI operation and the Lua bridge.

`process runner`

- Starts Aseprite without a command shell.
- Captures stdout and stderr instead of inheriting them.
- Enforces timeouts, cancellation, exit-code checks, and output-size limits.
- Cleans temporary files in a `finally` path.

`process path boundary`

- Detects Windows `Aseprite.exe` execution from WSL or honors an explicit execution mode.
- Keeps authorization, hashing, publication, and MCP results in native WSL paths.
- Converts `/mnt/<drive>/...` to a Windows drive path only when constructing Aseprite arguments.
- Converts other WSL paths to `\\wsl.localhost\<distribution>\...` paths.
- Places the Lua bridge and its request/response files on a Windows-mounted allowed root when one
  is available.

`Lua bridge`

- Implements a fixed allowlist of versioned operations.
- Validates the bridge request again before touching a sprite.
- Uses `app.open`, sprite APIs, transactions, and save-copy operations.
- Returns JSON only through the response file.
- Never evaluates client-provided Lua source or arbitrary command names.

## 5. Proposed repository layout

```text
servers/aseprite/
  README.md
  pyproject.toml
  uv.lock
  src/
    aseprite_mcp/
      __init__.py
      __main__.py
      adapter.py
      server.py
      config.py
      errors.py
      models.py
      paths.py
      process_runner.py
      scripts/
        __init__.py
        bridge.lua
  tests/
    fixtures/
    test_config.py
    test_integration.py
    test_models.py
    test_paths.py
    test_server.py
```

Tool modules may be split further when they become difficult to test in isolation. Keep the package importable without starting the server, and put the blocking `mcp.run()` call behind the `if __name__ == "__main__"` guard in `__main__.py`. Do not introduce `packages/` until code is genuinely shared by another server.

## 6. Execution protocol with Aseprite

Each bridge-backed operation should follow this sequence:

1. Validate the MCP input schema.
2. Resolve and authorize every input and output path.
3. Acquire an operation lock for each affected sprite path.
4. Create a unique temporary directory.
5. Write a bridge request containing a protocol version, operation name, and validated payload.
6. Launch Aseprite with `--batch`, `--script-param`, and the checked-in `bridge.lua` script.
7. Capture the child process output and wait with a configurable timeout.
8. Read and validate the bridge response schema.
9. Move a completed output into place only after the operation succeeds.
10. Release locks and remove temporary data.

Example bridge envelope:

```json
{
  "protocolVersion": 1,
  "operation": "inspect",
  "input": {
    "source_path": "C:/art/hero.aseprite"
  }
}
```

Example response envelope:

```json
{
  "ok": true,
  "result": {
    "width": 32,
    "height": 32,
    "frameCount": 8
  }
}
```

Use temporary JSON files rather than stdout for bridge data. This keeps Aseprite diagnostics separate from MCP messages and avoids quoting complex JSON in process arguments. Only the request and response file paths should be passed through `--script-param`.

## 7. Configuration

Configuration precedence should be command-line argument, environment variable, then platform-specific discovery.

| Setting | Command-line form | Environment form | Behavior |
| --- | --- | --- | --- |
| Aseprite executable | `--aseprite <path>` | `ASEPRITE_EXECUTABLE` | Required if discovery fails. |
| Allowed root | `--allow-root <path>` | `ASEPRITE_MCP_ROOTS` | Repeatable; all file access must remain within a root. |
| Timeout | `--timeout-seconds <n>` | `ASEPRITE_MCP_TIMEOUT_SECONDS` | Capped at 300 seconds. |
| Concurrency | `--max-concurrency <n>` | `ASEPRITE_MCP_MAX_CONCURRENCY` | Limits simultaneous Aseprite processes. |
| Diagnostic capture | `--max-capture-bytes <n>` | `ASEPRITE_MCP_MAX_CAPTURE_BYTES` | Caps captured process and bridge output. |
| Execution mode | `--execution-mode <mode>` | `ASEPRITE_MCP_EXECUTION_MODE` | `auto`, `native`, or `wsl-windows`. |
| Bridge temporary root | `--bridge-temp-root <path>` | `ASEPRITE_MCP_BRIDGE_TEMP_ROOT` | Existing local directory for Lua control files. |

Discovery inspects explicit configuration, `PATH`, and documented installation locations. The health tool reports an actionable error when discovery fails. The Lua bridge requires Aseprite 1.3-rc5 or newer because it uses the built-in JSON API; Aseprite 1.3.18.3 with scripting API version 41 is the initial tested version.

Under WSL, discovery additionally checks common Aseprite and Steam installation paths on the
`C:` drive. Automatic execution mode selects `wsl-windows` only when the server is running under
WSL and the resolved executable ends in `.exe`. A user may override the mode for unusual launchers.
The recommended deployment keeps Python and its virtual environment in the WSL filesystem and
sprite data on a Windows volume mounted below `/mnt`.

## 8. MCP tool surface

Tool names are prefixed so they remain recognizable when a client combines multiple servers.

### `aseprite_health`

Verifies configuration without modifying files.

Input: no fields.

Output:

- Server version.
- Resolved Aseprite path.
- Aseprite version and scripting API version, when available.
- Allowed roots and effective operational limits.

### `aseprite_inspect_sprite`

Reads a sprite and returns normalized metadata.

Input:

- `source_path`.
- Optional inclusion flags for palettes, cel bounds, tilesets, and user properties.

Output:

- Canvas width, height, color mode, pixel ratio, and frame count.
- Frame indices and durations.
- Layer hierarchy with type, visibility, opacity, blend mode, and cel presence.
- Tags with frame ranges and animation direction.
- Slices with frame-specific bounds, centers, and pivots.
- Palette summaries and optional color values.

The default response should omit raw pixel data and other potentially large fields.

### `aseprite_render`

Renders a selected frame, tag, slice, or layer set.

Input:

- `source_path`.
- Optional `frame`, `tag`, `slice`, `layers`, `scale`, and background options.
- `format`: initially `png` or `gif`.
- An authorized `output_path`.
- `overwrite`, defaulting to `false`.

Output:

- Format, dimensions, byte size, and selected frame range.
- The written path and output metadata. Inline image delivery is deferred.

### `aseprite_export_sprite_sheet`

Exports a sprite sheet plus machine-readable frame data.

Input:

- `source_path`, `image_output_path`, and `data_output_path`.
- Layout: rows, columns, horizontal, vertical, or packed where supported.
- Optional frame/tag/layer filtering, trimming, padding, extrusion, and scale.
- `overwrite`, defaulting to `false`.

Output:

- Paths and sizes of both artifacts.
- Frame count, layout, and normalized export metadata.

Prefer documented Aseprite CLI export flags for this operation. Use the Lua bridge only for behavior the CLI cannot express consistently.

### `aseprite_create_sprite`

Creates a new `.aseprite` document.

Input:

- `output_path`, width, height, and color mode.
- Optional palette, transparent/background color, layer definitions, frame durations, tags, and initial pixel data.
- `overwrite`, defaulting to `false`.

Output:

- A summary in the same normalized shape used by inspection.
- The written path and byte size.

Apply strict limits to canvas dimensions, frame count, layer count, palette size, and total pixels.

### Editing tools

Editing uses narrow tools instead of a generic `execute` operation:

- `aseprite_set_pixels` writes bounded RGBA pixels to a specific layer and frame.
- `aseprite_edit_frames` adds, duplicates, removes, or retimes frames using ordered operations.
- `aseprite_edit_layers` adds, removes, renames, shows, hides, reorders, or regroups layers.
- `aseprite_edit_tags` creates, updates, or removes animation tags.
- `aseprite_apply_palette` remaps RGB or indexed cel colors to at most 256 supplied colors.
- `aseprite_transform_cel` translates, flips, or quarter-turns one image cel.

Every edit input should include:

- `source_path`.
- `output_path`; it may equal the source only when `overwrite: true` is explicit.
- Stable selectors such as layer path plus frame index. IDs may be returned where Aseprite exposes durable IDs, but names alone must not silently select among duplicates.
- Optional `expected_source_hash` for optimistic concurrency.

Every edit should be performed in an Aseprite transaction when supported, saved to a temporary destination, and published only after success. Return the resulting file hash and normalized summary.

### Implemented animation workflow tools

- `aseprite_create_animation` creates a complete bounded animation with per-frame duration,
  per-layer cel pixels, and optional named playback tags in one atomic operation.
- `aseprite_import_sprite_sheet` imports a bounded PNG grid into a new editable animation. It
  supports explicit cell dimensions, optional column and frame counts, margin, spacing, uniform
  frame duration, layer naming, optional tag creation, and exact color-key transparency.
- `aseprite_resize_canvas` expands or crops the canvas around one of nine anchors without scaling
  cel pixels.
- `aseprite_resize_sprite` scales the canvas and cel artwork. The initial public method is limited
  to nearest-neighbor scaling so pixel-art behavior remains deterministic.
- `aseprite_validate_animation` performs a bounded, read-only scan for empty frames, visible bounds,
  baseline drift, width/height drift, and possible duplicate frames. Tilemaps use a documented
  bounds approximation.
- `aseprite_preview` returns a bounded inline PNG for one frame or a sprite-sheet selection without
  publishing an output file.
- `aseprite_read_pixels` returns up to 65,536 pixels from one image layer/frame as compact,
  row-based `#RRGGBBAA` runs.
- `aseprite_edit_frames`, `aseprite_edit_layers`, and `aseprite_edit_tags` apply ordered structural
  edits, so selectors in later operations observe earlier changes.
- `aseprite_apply_palette` performs bounded nearest-color remapping; grayscale documents are not
  supported by this operation.
- `aseprite_transform_cel` supports translation, horizontal/vertical flip, and clockwise or
  counter-clockwise 90-degree rotation.
- `aseprite_read_composited_pixels` provides exact final-frame RGBA runs for review and comparison.
- `aseprite_set_pixel_runs` writes bounded horizontal spans without a per-pixel request object.
- `aseprite_copy_cel` copies or links cel images and requires explicit replacement of an existing
  target.
- `aseprite_compare_frames` reports changed pixels, bounds, and baseline movement, with an optional
  difference PNG.
- `aseprite_edit_slices` manages frame-specific bounds, nine-slice centers, and pivots.
- `aseprite_trim_cels` removes transparent image borders while retaining absolute cel placement.
- `aseprite_edit_properties` manages scalar user metadata on sprites, layers, tags, slices, and cels.
- `aseprite_convert_color_mode` wraps the documented batch-capable conversion command with explicit
  color mode and dithering options.
- `aseprite_edit_tileset` manages bounded tileset and tile-image operations; the separate
  `aseprite_edit_tilemap` tool applies bounded tile-cell layout edits.
- `aseprite_render_contact_sheet` writes a bounded, zero-based labelled frame-review grid.
- Cel inspection and palette analysis expose linked-image identity and exact color usage.
- Fixed color replacement, filling, shape drawing, selections, and outlining provide bounded
  higher-level pixel operations without accepting scripts or arbitrary commands.
- Tileset inspection, tilemap cell editing, validation, and PNG/JSON export complete the first
  tile-production workflow.
- `aseprite_preview_animation` returns a bounded inline GIF for direct client review.
- `aseprite_crop_sprite`, `aseprite_draw_strokes`, and `aseprite_transform_selection` add bounded
  canvas cleanup, freehand pixel work, and deterministic rectangular transforms.
- `aseprite_edit_palette_entries` provides index-aware palette maintenance with explicit
  replacement behavior for removals.
- `aseprite_compare_sprites` reports structural, metadata, and composited-pixel regressions between
  two authorized documents.
- `aseprite_validate_export_profile` checks normalized sprite metadata against an explicit,
  client-supplied engine handoff contract.

All mutation tools use authorized paths, temporary sibling output, explicit overwrite permission,
normalized mutation results, and optimistic source-hash guards where a source document is edited.

Versioned Codex skills live under `aseprite/skills`. The general `aseprite-sprite-production` skill
is complemented by focused animation-review, concept-to-sprite, game-export, tileset-production,
and palette-design skills. Additional QA, autotile, UI, fighting-game, color-variant, and batch
pipeline skills orchestrate the narrow MCP tools without adding new file authority.

## 9. Resources

Resources are optional for the first milestone. Add them only after the tool workflows are stable.

A later release may expose server-generated previews through opaque URIs such as `aseprite-preview://<id>`. These resources should be read-only, bounded in size, tied to a short-lived cache entry, and must not reveal absolute filesystem paths in the URI.

Source sprite files should not be exposed through a broad arbitrary-file resource template.

## 10. Filesystem and process safety

- Require at least one allowed root before enabling file tools.
- Canonicalize existing input paths and verify their resolved targets remain under an allowed root.
- For new outputs, canonicalize the nearest existing parent and reject symlink or junction escapes.
- Reject device paths, named pipes, URLs, and unsupported extensions.
- Pass process arguments as an array and never enable shell interpretation.
- Never accept executable paths, script paths, raw CLI flags, Lua code, or environment overrides through a tool call.
- Keep source documents unchanged unless `overwrite: true` is explicit.
- For replacement, write a temporary sibling file and use the safest atomic replacement available on the platform.
- Bound file size, canvas area, frames, layers, cels, palette entries, edit count, process runtime, captured output, and inline response bytes.
- Serialize writes to the same canonical path. Reads may run concurrently only when no writer targets that path.
- Honor MCP cancellation by terminating the child process and removing temporary artifacts.
- Redact paths from unexpected internal error details when they fall outside configured roots.

## 11. Error model

Expose stable domain error codes in structured tool results:

| Code | Meaning |
| --- | --- |
| `ASEPRITE_NOT_FOUND` | Executable discovery failed. |
| `ASEPRITE_VERSION_UNSUPPORTED` | Installed version lacks a required capability. |
| `PATH_NOT_ALLOWED` | A path is outside configured roots or escapes through a link. |
| `FILE_NOT_FOUND` | An input sprite does not exist. |
| `OUTPUT_EXISTS` | Output exists and overwrite was not authorized. |
| `INVALID_SPRITE` | Aseprite could not load or validate the document. |
| `INVALID_SELECTOR` | A frame, tag, slice, layer, or palette selector is invalid or ambiguous. |
| `LIMIT_EXCEEDED` | Input or generated output exceeds an operational limit. |
| `OPERATION_TIMEOUT` | Aseprite exceeded the configured deadline. |
| `OPERATION_CANCELLED` | The client cancelled the request. |
| `ASEPRITE_FAILED` | Aseprite exited unsuccessfully. |
| `BRIDGE_PROTOCOL_ERROR` | The bridge response was missing, malformed, or incompatible. |

Expected operational failures should be returned as tool errors with a concise message, the stable code, and recovery guidance. Unexpected stack traces belong only in stderr diagnostics and test output.

## 12. Implementation phases

### Phase 0: Compatibility spike

- Test executable discovery on the initial Windows development environment.
- Verify batch Lua execution and request/response files with paths containing spaces and non-ASCII characters.
- Record `aseprite --version` and `app.apiVersion` behavior.
- Confirm metadata available for layers, frames, tags, slices, palettes, tilemaps, and linked cels.
- Confirm save-copy and sprite-sheet export behavior without modifying fixtures.
- Select and document the minimum supported Aseprite version.

Exit criteria: a small standalone Lua script can inspect a copied fixture and return validated JSON without writing protocol data to stdout.

### Phase 1: Server scaffold

- Create the independent Python package with `pyproject.toml` and a locked environment.
- Add strict type-check, lint, format, test, build, and package-validation commands.
- Implement configuration parsing, executable discovery, stderr logging, and `aseprite_health`.
- Build the MCP server factory and serve it over stdio.
- Add a contract test that spawns the packaged server and completes an MCP handshake and tool call.
- Write `servers/aseprite/README.md` with installation and client configuration examples.

Exit criteria: a client can launch the server and receive a health result on Windows.

### Phase 2: Read-only inspection

- Define the bridge protocol and Python/Lua validation boundaries.
- Implement path authorization, temporary workspace management, process timeouts, and cancellation.
- Implement `aseprite_inspect_sprite` and normalized metadata types.
- Add fixtures covering RGB, indexed, grayscale, animation, nested layers, slices, and tags.

Exit criteria: inspection is deterministic across repeated runs and all source fixture hashes remain unchanged.

### Phase 3: Rendering and export

- Implement `aseprite_render` using documented CLI flags where practical.
- Implement `aseprite_export_sprite_sheet` and validate both the image and JSON outputs.
- Add overwrite protection, atomic publication, inline result limits, and operation locks.
- Test layer, tag, frame, trim, scale, and layout combinations.

Exit criteria: exports match golden metadata and no partial destination files remain after failure, timeout, or cancellation.

### Phase 4: Creation and editing

- Implement `aseprite_create_sprite`.
- Add bounded pixel-span encoding and `aseprite_set_pixels`.
- Add frame, layer, tag, and palette tools incrementally.
- Add transactions, optimistic source hashes, and save-to-new-file defaults.
- Test duplicate names, linked cels, locked layers, indexed palettes, and boundary coordinates.

Exit criteria: edits produce the expected document while failure cases leave both source and destination in their prior state.

### Phase 5: Hardening and release

- Exercise the full suite on supported operating systems and Aseprite versions.
- Add package metadata, license notices, changelog, and reproducible release steps.
- Document all configuration, schemas, limits, platform differences, and troubleshooting paths.
- Run a security review of path handling, process creation, temporary files, and overwrite behavior.
- Measure startup and common-operation latency and set evidence-based defaults.

Exit criteria: the package can be installed, configured in a representative MCP client, and used end-to-end from a clean environment.

## 13. Test strategy

### Unit tests

- Tool input and output schemas.
- Configuration precedence and invalid values.
- Windows, POSIX, UNC, relative, Unicode, and space-containing paths.
- WSL detection, `/mnt/<drive>` conversion, WSL UNC conversion, and explicit mode overrides.
- Allowed-root checks, including symlink and junction escapes.
- Command argument construction without invoking Aseprite.
- Error mapping, timeouts, cancellation, locks, limits, and cleanup.
- Bridge response validation and incompatible protocol versions.

### Contract tests

- Spawn the built stdio server through an MCP client.
- Verify initialization, tool discovery, valid calls, invalid inputs, cancellation, and clean shutdown.
- Assert that non-MCP text never appears on server stdout.

### Integration tests

- Gate Aseprite-dependent tests behind `ASEPRITE_EXECUTABLE`.
- Copy every fixture into a unique temporary directory before invoking Aseprite.
- Inspect documents and compare normalized metadata.
- Create, reopen, modify, render, and export representative sprites.
- Verify source hashes before and after every test.
- Cover missing executable, unsupported version, corrupt input, denied access, timeout, and occupied output paths.

### Golden artifacts

Keep only small, purpose-built, legally distributable fixtures. Prefer assertions over complete binary snapshots. When a rendered PNG must be compared, compare dimensions and decoded pixels or a documented content hash rather than relying only on file bytes that may vary by encoder version.

## 14. Documentation deliverables

Before the first release, `servers/aseprite/README.md` should include:

- Supported platforms and Aseprite versions.
- Installation and executable discovery.
- Allowed-root configuration and its security implications.
- MCP client configuration examples for Windows, macOS, and Linux.
- Complete tool summaries with overwrite behavior.
- File-size and operation limits.
- Troubleshooting for Steam installs, missing executables, permission failures, and malformed sprites.
- A statement that Aseprite is a separate dependency and is not distributed by this project.

## 15. Open decisions

Resolve these during the relevant phase and record the result in the server README or an architecture decision record:

1. Whether client-provided MCP roots can supplement configured roots or only narrow them.
2. Whether inline images are useful enough to support in a later release.
3. Pixel-edit encoding beyond the implemented bounded point list: rectangles, row runs, indexed palette values, or a combination.
4. Maximum safe concurrency for separate Aseprite batch processes on each platform.
5. Which edit operations behave consistently for tilemap layers and linked cels.

## 16. Definition of done for version 0.1

- The server installs and launches through stdio from a documented MCP client configuration.
- Health, inspection, render, sprite-sheet export, basic creation, and at least one bounded pixel-edit workflow are implemented.
- No tool accepts raw commands, raw Lua, unrestricted paths, or implicit overwrite behavior.
- Inputs and structured outputs have runtime schemas and representative tests.
- Aseprite process failures, timeouts, and cancellations clean up temporary files.
- Unit and contract suites pass without Aseprite; integration tests pass when a supported executable is configured.
- The supported versions, setup, tools, limits, and platform caveats are documented.
- Fixture source hashes demonstrate that tests do not modify repository assets.

## 17. Primary references

- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Python SDK installation](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/get-started/installation.md)
- [MCP Python SDK server execution and stdio guidance](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/index.md)
- [Aseprite command-line interface](https://www.aseprite.org/docs/cli/)
- [Aseprite scripting API](https://www.aseprite.org/api/)
- [Aseprite `app` API](https://www.aseprite.org/api/app)
- [Aseprite scripting API changes](https://www.aseprite.org/api/Changes)
