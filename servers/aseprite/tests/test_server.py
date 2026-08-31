import sys

import pytest
from mcp import Client, StdioServerParameters

from aseprite_mcp.config import Settings
from aseprite_mcp.server import build_server


@pytest.mark.asyncio
async def test_server_lists_expected_tools() -> None:
    server = build_server(Settings(aseprite_executable=None, allowed_roots=()))

    async with Client(server) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}

    assert names == {
        "aseprite_health",
        "aseprite_inspect_sprite",
        "aseprite_render",
        "aseprite_export_sprite_sheet",
        "aseprite_create_sprite",
        "aseprite_set_pixels",
    }


@pytest.mark.asyncio
async def test_health_reports_missing_executable() -> None:
    server = build_server(Settings(aseprite_executable=None, allowed_roots=()))

    async with Client(server) as client:
        result = await client.call_tool("aseprite_health", {})

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["ok"] is False
    assert "ASEPRITE_NOT_FOUND" in result.structured_content["error"]


@pytest.mark.asyncio
async def test_stdio_entry_point_lists_tools() -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "aseprite_mcp"],
    )

    async with Client(parameters) as client:
        tools = await client.list_tools()

    assert "aseprite_health" in {tool.name for tool in tools.tools}
