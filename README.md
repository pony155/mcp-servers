# MCP Servers

A collection of [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) servers for connecting AI clients to creative and developer tools.

## First server: Aseprite

The first server in this collection integrates with [Aseprite](https://www.aseprite.org/), enabling MCP clients to work with pixel-art projects through a focused set of tools.

Available capabilities include:

- Inspecting sprites, frames, layers, tags, slices, and palettes.
- Creating and editing sprite documents.
- Importing and exporting images and sprite sheets.
- Running safe, explicit Aseprite automation workflows.

The initial Python implementation is available under [`aseprite`](aseprite). See its [README](aseprite/README.md) for setup, tools, safety behavior, and current limitations.

The server uses Python 3.10 through 3.14, uv with a committed dependency lockfile, and Hatchling for
packaging. Install and start it from the repository root:

```console
uv sync --project aseprite --locked --extra dev
uv run --project aseprite --locked aseprite-mcp --aseprite "/path/to/Aseprite" --allow-root "/path/to/sprites"
```

## Repository layout

The current implementation uses this layout (the original `servers/aseprite` layout has been
flattened). Server code, Lua scripts, skills, and packaging configuration stay inside `aseprite/`:

```text
aseprite/
  pyproject.toml
  uv.lock
  scripts/
  services/
  tools/
  skills/
main.py               # Optional source-checkout launcher
```

The installed Python package is `aseprite`, and the console command is `aseprite-mcp`.
Build a wheel and source distribution with `uv build aseprite`. See the server README for
static checks and explicitly requested test workflows.

Shared packages may be introduced under `packages/` when more than one server needs them.

## Project principles

- Keep each server independently understandable and testable.
- Prefer small, task-oriented MCP tools with clear input schemas.
- Treat file writes and application automation as explicit, auditable operations.
- Return actionable MCP errors instead of leaking implementation details.
- Document setup, permissions, and platform limitations for every integration.

## Contributing

The project is in its initial setup phase. See [AGENTS.md](AGENTS.md) for implementation guidance and repository conventions.

## License

No license has been selected yet.
