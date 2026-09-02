
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "enable_codex.ps1")

codex mcp add aseprite -- wsl.exe -d Debian -- `
  /usr/bin/env `
  "ASEPRITE_MCP_TOOL_PROFILES=modular-character-authoring" `
  /home/pony/.venv/bin/python `
  /mnt/c/Users/ppony/workspace/development/mcp-servers/main.py `
  --aseprite "/mnt/c/Program Files (x86)/Steam/steamapps/common/Aseprite/Aseprite.exe" `
  --allow-root /mnt/c/Users/ppony/workspace/Sprites `
  --log-level INFO
  
exit $LASTEXITCODE
