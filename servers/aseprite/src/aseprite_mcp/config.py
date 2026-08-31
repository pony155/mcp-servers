"""Command-line, environment, and executable discovery configuration."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from .errors import AsepriteMCPError
from .interop import ExecutionMode, is_wsl

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_CONCURRENCY = 2
DEFAULT_MAX_CAPTURE_BYTES = 1_048_576
MAX_TIMEOUT_SECONDS = 300.0
MAX_CONCURRENCY = 8
MAX_CAPTURE_BYTES = 16_777_216


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated server settings."""

    aseprite_executable: Path | None
    allowed_roots: tuple[Path, ...]
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY
    max_capture_bytes: int = DEFAULT_MAX_CAPTURE_BYTES
    execution_mode: ExecutionMode = "auto"
    bridge_temp_root: Path | None = None


def _common_aseprite_paths() -> tuple[Path, ...]:
    if sys.platform == "win32":
        candidates: list[Path] = []
        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            base = os.environ.get(variable)
            if not base:
                continue
            root = Path(base)
            candidates.extend(
                (
                    root / "Aseprite" / "Aseprite.exe",
                    root / "Steam" / "steamapps" / "common" / "Aseprite" / "Aseprite.exe",
                )
            )
        return tuple(candidates)
    if sys.platform == "darwin":
        return (Path("/Applications/Aseprite.app/Contents/MacOS/aseprite"),)
    candidates = [Path("/usr/bin/aseprite"), Path("/usr/local/bin/aseprite")]
    if is_wsl():
        for program_directory in ("Program Files", "Program Files (x86)"):
            root = Path("/mnt/c") / program_directory
            candidates.extend(
                (
                    root / "Aseprite" / "Aseprite.exe",
                    root / "Steam" / "steamapps" / "common" / "Aseprite" / "Aseprite.exe",
                )
            )
    return tuple(candidates)


def discover_aseprite(explicit: str | os.PathLike[str] | None = None) -> Path | None:
    """Locate Aseprite without launching it."""

    configured = explicit or os.environ.get("ASEPRITE_EXECUTABLE")
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return candidate.resolve(strict=True)
        return None

    located = shutil.which("aseprite") or shutil.which("aseprite.exe")
    if located:
        return Path(located).resolve(strict=True)

    for candidate in _common_aseprite_paths():
        if candidate.is_file():
            return candidate.resolve(strict=True)
    return None


def _environment_roots() -> list[str]:
    value = os.environ.get("ASEPRITE_MCP_ROOTS", "")
    return [entry for entry in value.split(os.pathsep) if entry]


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def parse_settings(argv: list[str] | None = None) -> Settings:
    """Parse and validate settings for the console entry point."""

    parser = argparse.ArgumentParser(description="Run the local Aseprite MCP server")
    parser.add_argument("--aseprite", help="Path to the Aseprite executable")
    parser.add_argument(
        "--allow-root",
        action="append",
        default=None,
        metavar="PATH",
        help="Allow file operations inside PATH; repeat for multiple roots",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=_positive_float,
        default=float(os.environ.get("ASEPRITE_MCP_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)),
    )
    parser.add_argument(
        "--max-concurrency",
        type=_positive_int,
        default=int(os.environ.get("ASEPRITE_MCP_MAX_CONCURRENCY", DEFAULT_MAX_CONCURRENCY)),
    )
    parser.add_argument(
        "--max-capture-bytes",
        type=_positive_int,
        default=int(os.environ.get("ASEPRITE_MCP_MAX_CAPTURE_BYTES", DEFAULT_MAX_CAPTURE_BYTES)),
    )
    parser.add_argument(
        "--execution-mode",
        choices=("auto", "native", "wsl-windows"),
        default=os.environ.get("ASEPRITE_MCP_EXECUTION_MODE", "auto"),
        help="How process-facing paths are represented; auto detects Windows Aseprite under WSL",
    )
    parser.add_argument(
        "--bridge-temp-root",
        default=os.environ.get("ASEPRITE_MCP_BRIDGE_TEMP_ROOT"),
        metavar="PATH",
        help="Existing directory for temporary Lua bridge files",
    )
    args = parser.parse_args(argv)
    if args.timeout_seconds > MAX_TIMEOUT_SECONDS:
        parser.error(f"--timeout-seconds may not exceed {MAX_TIMEOUT_SECONDS:g}")
    if args.max_concurrency > MAX_CONCURRENCY:
        parser.error(f"--max-concurrency may not exceed {MAX_CONCURRENCY}")
    if args.max_capture_bytes > MAX_CAPTURE_BYTES:
        parser.error(f"--max-capture-bytes may not exceed {MAX_CAPTURE_BYTES}")

    roots: list[Path] = []
    for raw_root in args.allow_root if args.allow_root is not None else _environment_roots():
        candidate = Path(raw_root).expanduser()
        if not candidate.is_dir():
            raise AsepriteMCPError(
                "PATH_NOT_ALLOWED",
                f"Allowed root does not exist or is not a directory: {candidate}",
            )
        resolved = candidate.resolve(strict=True)
        if resolved not in roots:
            roots.append(resolved)

    bridge_temp_root: Path | None = None
    if args.bridge_temp_root:
        candidate = Path(args.bridge_temp_root).expanduser()
        if not candidate.is_dir():
            raise AsepriteMCPError(
                "INVALID_CONFIGURATION",
                f"Bridge temporary root does not exist or is not a directory: {candidate}",
            )
        bridge_temp_root = candidate.resolve(strict=True)

    return Settings(
        aseprite_executable=discover_aseprite(args.aseprite),
        allowed_roots=tuple(roots),
        timeout_seconds=args.timeout_seconds,
        max_concurrency=args.max_concurrency,
        max_capture_bytes=args.max_capture_bytes,
        execution_mode=args.execution_mode,
        bridge_temp_root=bridge_temp_root,
    )
