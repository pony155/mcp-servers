from pathlib import Path

import pytest

from aseprite_mcp.config import discover_aseprite, parse_settings
from aseprite_mcp.errors import AsepriteMCPError


def test_discover_explicit_executable(tmp_path: Path) -> None:
    executable = tmp_path / "aseprite.exe"
    executable.touch()

    assert discover_aseprite(executable) == executable.resolve()


def test_discover_missing_explicit_executable(tmp_path: Path) -> None:
    assert discover_aseprite(tmp_path / "missing.exe") is None


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--timeout-seconds", "301"),
        ("--max-concurrency", "9"),
        ("--max-capture-bytes", "16777217"),
    ],
)
def test_configuration_upper_bounds(option: str, value: str) -> None:
    with pytest.raises(SystemExit):
        parse_settings([option, value])


def test_parses_wsl_interop_configuration(tmp_path: Path) -> None:
    settings = parse_settings(
        [
            "--execution-mode",
            "wsl-windows",
            "--bridge-temp-root",
            str(tmp_path),
        ]
    )

    assert settings.execution_mode == "wsl-windows"
    assert settings.bridge_temp_root == tmp_path.resolve()


def test_rejects_missing_bridge_temp_root(tmp_path: Path) -> None:
    with pytest.raises(AsepriteMCPError, match="Bridge temporary root does not exist"):
        parse_settings(["--bridge-temp-root", str(tmp_path / "missing")])
