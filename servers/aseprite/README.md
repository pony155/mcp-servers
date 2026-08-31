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

## Tools

| Tool | Purpose | Writes files |
| --- | --- | --- |
| `aseprite_health` | Report server, executable, and Aseprite API status. | No |
| `aseprite_inspect_sprite` | Read dimensions, frames, layers, tags, slices, and palettes. | No |
| `aseprite_render` | Render a PNG frame or GIF animation selection. | Yes |
| `aseprite_export_sprite_sheet` | Export a PNG sheet and JSON-array metadata. | Yes |
| `aseprite_create_sprite` | Create a bounded `.ase` or `.aseprite` document. | Yes |
| `aseprite_set_pixels` | Set up to 10,000 RGBA pixels on one layer/frame. | Yes |

Frame indices are zero-based. Layer selectors are exact hierarchy paths such as `Character/Outline`.

## Safety behavior

- File tools are disabled until an allowed root is configured.
- Canonical path checks reject access outside configured roots, including link traversal.
- Existing outputs are rejected unless `overwrite=true` is explicit.
- Edits default to a different output file and support an optional SHA-256 source guard.
- Aseprite runs with argument arrays and no command shell.
- WSL-to-Windows path conversion occurs only after local path authorization.
- Tool calls cannot supply raw Aseprite flags, executable paths, scripts, or Lua source.
- Completed files are written to temporary sibling paths before publication.
- Requests are bounded by time, process concurrency, diagnostic output, dimensions, frames, layers, and pixel count.

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
