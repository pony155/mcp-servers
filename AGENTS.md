# AGENTS.md

## Project purpose

This repository is a collection of Model Context Protocol (MCP) servers. The first integration targets Aseprite.

These instructions apply to the entire repository. A server directory may add its own `AGENTS.md` with more specific guidance.

## Current state

The repository is being bootstrapped. Do not assume a language, package manager, build system, or test framework until one is committed. When introducing foundational tooling, keep the choice minimal and document it in the root `README.md` and the affected server's README.

## Intended structure

```text
servers/
  aseprite/
    README.md
packages/            # Optional shared code; add only when genuinely reused.
```

Keep server-specific code, fixtures, tests, and documentation inside that server's directory. Avoid creating shared abstractions in anticipation of future servers.

## Implementation guidelines

- Follow the current MCP specification and the official SDK conventions for the chosen language.
- Give tools narrow responsibilities, descriptive names, and strict input schemas.
- Separate MCP transport and protocol handling from Aseprite-specific application logic.
- Keep external process execution behind a small, testable boundary.
- Validate and normalize paths before reading or writing files.
- Require explicit arguments for destructive or overwriting operations; do not silently replace user data.
- Use structured error responses with useful recovery guidance. Do not expose secrets, environment variables, or unnecessary stack traces.
- Keep behavior deterministic where practical and document any dependency on the active Aseprite document or UI state.

## Aseprite integration

- Use the product name **Aseprite** in code and documentation.
- Prefer documented Aseprite CLI and scripting APIs over simulated keyboard or mouse input.
- Keep Lua scripts, if used, versioned alongside the server and keep their protocol-facing wrappers independently verifiable.
- Detect missing executables and incompatible Aseprite versions early, with clear setup instructions.
- Treat source sprite files as user data. Tests that modify files must operate on temporary copies of fixtures.
- Document whether each capability requires Aseprite to be installed, running, or licensed.

## Testing and verification

- Do not add unit tests or run unit test suites unless the user explicitly requests them.
- Do not add or run Aseprite integration tests unless the user explicitly requests them.
- Prefer focused static checks, type checks, or manual inspection when verification is useful and available.
- Keep code structured so schemas, path handling, command construction, response conversion, and failure paths remain independently verifiable if tests are requested later.
- Update documentation whenever setup, tool schemas, or observable behavior changes.

## Change discipline

- Keep changes scoped to the requested server or shared component.
- Preserve unrelated user changes and avoid destructive Git operations.
- Do not commit generated output, credentials, local configuration, or proprietary sprite assets.
- Explain noteworthy design decisions close to the code or in the relevant README.
