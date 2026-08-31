"""Translate filesystem paths at the WSL-to-Windows process boundary."""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from .errors import AsepriteMCPError

ExecutionMode = Literal["auto", "native", "wsl-windows"]
EffectiveExecutionMode = Literal["native", "wsl-windows"]

_WINDOWS_MOUNT_PATTERN = re.compile(r"^/mnt/([a-zA-Z])(?:/(.*))?$")


def translate_wsl_path(posix_path: str, distro: str) -> str:
    """Translate an absolute WSL path to a Windows drive or WSL UNC path."""

    if not posix_path.startswith("/"):
        raise AsepriteMCPError(
            "PATH_TRANSLATION_FAILED", "WSL process paths must be absolute Linux paths"
        )
    mounted = _WINDOWS_MOUNT_PATTERN.fullmatch(posix_path)
    if mounted:
        drive = mounted.group(1).upper()
        remainder = (mounted.group(2) or "").replace("/", "\\")
        return f"{drive}:\\{remainder}" if remainder else f"{drive}:\\"
    if not distro or "\\" in distro or "/" in distro:
        raise AsepriteMCPError(
            "PATH_TRANSLATION_FAILED",
            "WSL_DISTRO_NAME is required to expose Linux filesystem paths to Windows Aseprite",
        )
    remainder = posix_path.lstrip("/").replace("/", "\\")
    base = f"\\\\wsl.localhost\\{distro}"
    return f"{base}\\{remainder}" if remainder else f"{base}\\"


def is_wsl(
    *,
    platform: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> bool:
    """Return whether the current Python process is running under WSL."""

    current_platform = sys.platform if platform is None else platform
    current_environment = os.environ if environment is None else environment
    return current_platform.startswith("linux") and any(
        current_environment.get(name) for name in ("WSL_DISTRO_NAME", "WSL_INTEROP")
    )


def resolve_execution_mode(
    requested: ExecutionMode,
    executable: Path | None,
    *,
    platform: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> EffectiveExecutionMode:
    """Resolve automatic mode from the host and configured executable."""

    if requested != "auto":
        return requested
    if executable is not None and executable.suffix.lower() == ".exe" and is_wsl(
        platform=platform, environment=environment
    ):
        return "wsl-windows"
    return "native"


class ProcessPathMapper:
    """Present local paths in the syntax expected by the Aseprite process."""

    def __init__(
        self,
        mode: EffectiveExecutionMode,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.mode = mode
        self._environment = os.environ if environment is None else environment

    def map(self, path: Path) -> str:
        """Convert an absolute local path into an Aseprite process argument."""

        resolved = path.resolve(strict=False)
        if self.mode == "native":
            return str(resolved)

        distro = self._environment.get("WSL_DISTRO_NAME", "").strip()
        return translate_wsl_path(resolved.as_posix(), distro)

    @staticmethod
    def is_windows_mounted(path: Path) -> bool:
        """Return whether a local path is below WSL's conventional /mnt/<drive> mount."""

        return _WINDOWS_MOUNT_PATTERN.fullmatch(path.resolve(strict=False).as_posix()) is not None
