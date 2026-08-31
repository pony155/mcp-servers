$ErrorActionPreference = "Stop"

$codexExecutable = Get-Command codex.exe -ErrorAction SilentlyContinue |
  Select-Object -First 1 -ExpandProperty Source

if (-not $codexExecutable) {
  $extensionRoots = @(
    (Join-Path $env:USERPROFILE ".vscode\extensions"),
    (Join-Path $env:USERPROFILE ".vscode-insiders\extensions")
  )

  $codexExecutable = $extensionRoots |
    Where-Object { Test-Path -LiteralPath $_ -PathType Container } |
    ForEach-Object {
      Get-ChildItem -LiteralPath $_ -Directory -Filter "openai.chatgpt-*-win32-x64"
    } |
    Sort-Object LastWriteTime -Descending |
    ForEach-Object {
      Join-Path $_.FullName "bin\windows-x86_64\codex.exe"
    } |
    Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    Select-Object -First 1
}

if (-not $codexExecutable) {
  throw "codex.exe was not found on PATH or in the VS Code Codex extension directory."
}

$codexDirectory = Split-Path -Parent $codexExecutable
$pathEntries = $env:PATH -split [IO.Path]::PathSeparator
if ($codexDirectory -notin $pathEntries) {
  $env:PATH = $codexDirectory + [IO.Path]::PathSeparator + $env:PATH
}

Write-Host "Codex CLI enabled for this PowerShell session: $codexExecutable"
