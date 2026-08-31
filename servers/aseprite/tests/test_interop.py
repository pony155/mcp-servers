from pathlib import Path

import pytest

from aseprite_mcp.errors import AsepriteMCPError
from aseprite_mcp.interop import (
    ProcessPathMapper,
    is_wsl,
    resolve_execution_mode,
    translate_wsl_path,
)


def test_detects_wsl_from_environment() -> None:
    assert is_wsl(platform="linux", environment={"WSL_DISTRO_NAME": "Ubuntu"})
    assert not is_wsl(platform="linux", environment={})
    assert not is_wsl(platform="win32", environment={"WSL_DISTRO_NAME": "Ubuntu"})


def test_auto_mode_selects_wsl_windows_for_exe() -> None:
    mode = resolve_execution_mode(
        "auto",
        Path("/mnt/c/Program Files/Aseprite/Aseprite.exe"),
        platform="linux",
        environment={"WSL_DISTRO_NAME": "Ubuntu"},
    )

    assert mode == "wsl-windows"


def test_auto_mode_keeps_linux_aseprite_native() -> None:
    mode = resolve_execution_mode(
        "auto",
        Path("/usr/bin/aseprite"),
        platform="linux",
        environment={"WSL_DISTRO_NAME": "Ubuntu"},
    )

    assert mode == "native"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("/mnt/c/Users/Ada/My Sprites/hero.aseprite", r"C:\Users\Ada\My Sprites\hero.aseprite"),
        ("/mnt/d", "D:\\"),
        ("/home/ada/mcp/bridge.lua", r"\\wsl.localhost\Ubuntu\home\ada\mcp\bridge.lua"),
    ],
)
def test_translates_wsl_paths(source: str, expected: str) -> None:
    assert translate_wsl_path(source, "Ubuntu") == expected


def test_rejects_unc_translation_without_distro() -> None:
    with pytest.raises(AsepriteMCPError, match="WSL_DISTRO_NAME"):
        translate_wsl_path("/home/ada/sprite.aseprite", "")


def test_native_mapper_preserves_resolved_local_path(tmp_path: Path) -> None:
    mapper = ProcessPathMapper("native")
    path = tmp_path / "sprite.aseprite"

    assert mapper.map(path) == str(path.resolve())
