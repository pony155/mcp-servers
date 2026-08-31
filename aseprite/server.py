"""MCP server construction and tool registration."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server import MCPServer
from pydantic import Field

from . import __version__
from .adapter import AsepriteAdapter
from .config import Settings
from .models import (
    FrameDefinition,
    HealthResult,
    LayerDefinition,
    MutationResult,
    PixelInput,
    RenderResult,
    SpriteInfo,
    SpriteSheetResult,
)


def build_server(settings: Settings) -> MCPServer:
    """Build a configured server without starting a transport."""

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

    @server.tool()
    async def aseprite_health() -> HealthResult:
        """Check the server configuration and installed Aseprite version without modifying files."""

        return await adapter.health(__version__)

    @server.tool()
    async def aseprite_inspect_sprite(
        source_path: Annotated[str, Field(description="Authorized sprite file path")],
        include_palette_colors: Annotated[
            bool, Field(description="Include every palette color in the response")
        ] = False,
    ) -> SpriteInfo:
        """Inspect sprite dimensions, frames, layers, tags, slices, and palettes."""

        return await adapter.inspect_sprite(
            source_path, include_palette_colors=include_palette_colors
        )

    @server.tool()
    async def aseprite_render(
        source_path: Annotated[str, Field(description="Authorized source sprite path")],
        output_path: Annotated[str, Field(description="Authorized .png or .gif output path")],
        frame: Annotated[int | None, Field(ge=0, description="Zero-based frame index")] = None,
        tag: Annotated[str | None, Field(min_length=1, description="Animation tag name")] = None,
        layers: Annotated[
            list[str] | None,
            Field(description="Layer paths to include; all visible layers by default"),
        ] = None,
        scale: Annotated[float, Field(ge=0.1, le=16)] = 1.0,
        overwrite: Annotated[
            bool, Field(description="Explicitly allow replacing output_path")
        ] = False,
    ) -> RenderResult:
        """Render one frame to PNG or a frame/tag selection to GIF."""

        return await adapter.render(
            source_path,
            output_path,
            frame=frame,
            tag=tag,
            layers=layers or [],
            scale=scale,
            overwrite=overwrite,
        )

    @server.tool()
    async def aseprite_export_sprite_sheet(
        source_path: Annotated[str, Field(description="Authorized source sprite path")],
        image_output_path: Annotated[str, Field(description="Authorized .png sheet path")],
        data_output_path: Annotated[str, Field(description="Authorized .json metadata path")],
        layout: Literal["horizontal", "vertical", "rows", "columns", "packed"] = "packed",
        tag: Annotated[str | None, Field(min_length=1)] = None,
        layers: list[str] | None = None,
        trim: bool = False,
        extrude: bool = False,
        border_padding: Annotated[int, Field(ge=0, le=1024)] = 0,
        shape_padding: Annotated[int, Field(ge=0, le=1024)] = 0,
        inner_padding: Annotated[int, Field(ge=0, le=1024)] = 0,
        overwrite: Annotated[
            bool, Field(description="Explicitly allow replacing both outputs")
        ] = False,
    ) -> SpriteSheetResult:
        """Export a PNG sprite sheet and JSON-array frame metadata."""

        return await adapter.export_sprite_sheet(
            source_path,
            image_output_path,
            data_output_path,
            layout=layout,
            tag=tag,
            layers=layers or [],
            trim=trim,
            extrude=extrude,
            border_padding=border_padding,
            shape_padding=shape_padding,
            inner_padding=inner_padding,
            overwrite=overwrite,
        )

    @server.tool()
    async def aseprite_create_sprite(
        output_path: Annotated[str, Field(description="Authorized .ase or .aseprite output path")],
        width: Annotated[int, Field(ge=1, le=4096)],
        height: Annotated[int, Field(ge=1, le=4096)],
        color_mode: Literal["rgb", "grayscale", "indexed"] = "rgb",
        layers: list[LayerDefinition] | None = None,
        frames: list[FrameDefinition] | None = None,
        pixels: list[PixelInput] | None = None,
        overwrite: Annotated[
            bool, Field(description="Explicitly allow replacing output_path")
        ] = False,
    ) -> MutationResult:
        """Create a bounded Aseprite document with optional initial pixels."""

        return await adapter.create_sprite(
            output_path,
            width=width,
            height=height,
            color_mode=color_mode,
            layers=layers or [LayerDefinition(name="Layer 1")],
            frames=frames or [FrameDefinition()],
            pixels=pixels or [],
            overwrite=overwrite,
        )

    @server.tool()
    async def aseprite_set_pixels(
        source_path: Annotated[str, Field(description="Authorized source .ase or .aseprite path")],
        output_path: Annotated[
            str, Field(description="Authorized destination .ase or .aseprite path")
        ],
        layer: Annotated[str, Field(min_length=1, max_length=1024, description="Exact layer path")],
        frame: Annotated[int, Field(ge=0, description="Zero-based frame index")],
        pixels: Annotated[list[PixelInput], Field(min_length=1, max_length=10_000)],
        overwrite: Annotated[
            bool, Field(description="Explicitly allow replacing output_path")
        ] = False,
        expected_source_hash: Annotated[
            str | None,
            Field(
                min_length=64,
                max_length=64,
                pattern=r"^[0-9a-fA-F]{64}$",
                description="Optional SHA-256 guard against concurrent source changes",
            ),
        ] = None,
    ) -> MutationResult:
        """Set bounded RGBA pixels on one image layer and frame, saving to output_path."""

        return await adapter.set_pixels(
            source_path,
            output_path,
            layer=layer,
            frame=frame,
            pixels=pixels,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    return server
