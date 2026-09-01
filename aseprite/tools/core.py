"""MCP server construction and tool registration."""

from __future__ import annotations
from typing import Annotated
from mcp.server import MCPServer
from pydantic import Field
from .. import __version__
from ..adapter import AsepriteAdapter
from ..capabilities import CapabilityRegistry, ToolRegistrar
from ..models import CapabilitiesResult, HealthResult, SpriteInfo
from .inputs import SourcePath


def register_core_tools(
    server: MCPServer,
    adapter: AsepriteAdapter,
    registry: CapabilityRegistry,
    *,
    enabled_tools: frozenset[str],
) -> int:
    """Register core tools and return the number registered."""

    tools = ToolRegistrar(server, registry, "core", enabled_tools=enabled_tools)

    @tools.tool()
    async def aseprite_health() -> HealthResult:
        """Check the server configuration and installed Aseprite version without modifying files."""

        return await adapter.health(__version__)

    @tools.tool()
    async def aseprite_list_capabilities() -> CapabilitiesResult:
        """List supported tools, profiles, mutability, output kinds, and availability."""

        return CapabilitiesResult.model_validate(
            registry.describe(adapter.settings.tool_profiles)
        )

    @tools.tool()
    async def aseprite_inspect_sprite(
        source_path: SourcePath,
        include_palette_colors: Annotated[
            bool, Field(description="Include every palette color in the response")
        ] = False,
    ) -> SpriteInfo:
        """Inspect sprite dimensions, frames, layers, tags, slices, and palettes."""

        return await adapter.inspect_sprite(
            source_path, include_palette_colors=include_palette_colors
        )

    return tools.registered_count
