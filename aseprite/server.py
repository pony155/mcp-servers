"""MCP server construction and profile-aware tool registration."""

from __future__ import annotations

import logging

from mcp.server import MCPServer

from . import __version__
from .adapter import AsepriteAdapter
from .capabilities import CapabilityRegistry, PROFILE_CATEGORIES
from .config import Settings
from .tools import REGISTRARS

logger = logging.getLogger(__name__)

def _selected_categories(profiles: tuple[str, ...]) -> set[str]:
    selected = {"core"}
    for profile in profiles:
        selected.update(PROFILE_CATEGORIES[profile])
    return selected


def build_server(settings: Settings) -> MCPServer:
    """Build a configured server without starting a transport."""

    if set(REGISTRARS) != set(PROFILE_CATEGORIES["full"]):
        raise RuntimeError("tool registrars and the full capability profile are inconsistent")
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
    categories = _selected_categories(settings.tool_profiles)
    registered = 0
    for category, registrar in REGISTRARS.items():
        registered += registrar(
            server,
            adapter,
            registry,
            enabled=category in categories,
        )
    logger.info(
        "Registered %d Aseprite MCP tools profiles=%s categories=%s",
        registered,
        ",".join(settings.tool_profiles),
        ",".join(sorted(categories)),
    )
    return server
