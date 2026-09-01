"""MCP server construction and profile-aware tool registration."""

from __future__ import annotations

import logging

from mcp.server import MCPServer

from . import __version__
from .adapter import AsepriteAdapter
from .capabilities import CapabilityRegistry, PROFILE_TOOL_NAMES, tools_for_profiles
from .config import Settings
from .tools import REGISTRARS

logger = logging.getLogger(__name__)

def build_server(settings: Settings) -> MCPServer:
    """Build a configured server without starting a transport."""

    if not PROFILE_TOOL_NAMES["full"]:
        raise RuntimeError("the full capability profile cannot be empty")
    logger.info("Building Aseprite MCP server version %s", __version__)
    server = MCPServer(
        "aseprite",
        title="Aseprite MCP Server",
        description="Inspect, create, edit, render, and export local Aseprite sprites.",
        instructions=(
            "Use only paths inside the server's configured roots. Writes never overwrite existing "
            "files unless overwrite=true is explicitly supplied. Frame indices are zero-based."
        ),
        version=__version__,
    )
    adapter = AsepriteAdapter(settings)
    registry = CapabilityRegistry()
    enabled_tools = tools_for_profiles(settings.tool_profiles)
    registered = 0
    for category, registrar in REGISTRARS.items():
        registered += registrar(
            server,
            adapter,
            registry,
            enabled_tools=enabled_tools,
        )
    logger.info(
        "Registered %d Aseprite MCP tools profiles=%s",
        registered,
        ",".join(settings.tool_profiles),
    )
    return server
