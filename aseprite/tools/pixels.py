"""MCP server construction and tool registration."""

from __future__ import annotations
from typing import Annotated, Literal
from mcp.server import MCPServer
from pydantic import Field
from ..adapter import AsepriteAdapter
from ..capabilities import CapabilityRegistry, ToolRegistrar
from ..models import (
    CompositedPixelReadResult,
    MutationResult,
    PaletteColorInput,
    PixelInput,
    PixelReadResult,
    PixelRunInput,
    RectangleInput,
    SelectionEditOperation,
    ShapeInput,
    StrokeInput,
)
from .inputs import ExpectedSourceHash, Overwrite, SpriteOutputPath, SpriteSourcePath


def register_pixels_tools(
    server: MCPServer, adapter: AsepriteAdapter, registry: CapabilityRegistry, *, enabled_tools: frozenset[str]
) -> int:
    """Register pixels tools and return the number registered."""

    tools = ToolRegistrar(server, registry, "pixels", enabled_tools=enabled_tools)

    @tools.tool()
    async def aseprite_set_pixels(
        source_path: SpriteSourcePath,
        output_path: SpriteOutputPath,
        layer: Annotated[str, Field(min_length=1, max_length=1024, description="Exact layer path")],
        frame: Annotated[int, Field(ge=0, description="Zero-based frame index")],
        pixels: Annotated[list[PixelInput], Field(min_length=1, max_length=10_000)],
        overwrite: Overwrite = False,
        expected_source_hash: ExpectedSourceHash = None,
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

    @tools.tool()
    async def aseprite_read_pixels(
        source_path: Annotated[str, Field(description="Authorized sprite or image path")],
        layer: Annotated[str, Field(min_length=1, max_length=256, description="Exact layer path")],
        frame: Annotated[int, Field(ge=0, description="Zero-based frame index")],
        x: Annotated[int, Field(ge=0)],
        y: Annotated[int, Field(ge=0)],
        width: Annotated[int, Field(ge=1, le=4096)],
        height: Annotated[int, Field(ge=1, le=4096)],
        include_transparent: bool = False,
    ) -> PixelReadResult:
        """Read a bounded rectangle as compact row-based #RRGGBBAA runs."""

        return await adapter.read_pixels(
            source_path, layer=layer, frame=frame, x=x, y=y, width=width,
            height=height, include_transparent=include_transparent,
        )

    @tools.tool()
    async def aseprite_transform_cel(
        source_path: Annotated[str, Field(description="Authorized source sprite document")],
        output_path: Annotated[str, Field(description="Authorized destination sprite document")],
        layer: Annotated[str, Field(min_length=1, max_length=256, description="Exact layer path")],
        frame: Annotated[int, Field(ge=0, description="Zero-based frame index")],
        action: Literal[
            "translate", "flip_horizontal", "flip_vertical", "rotate_90_cw", "rotate_90_ccw"
        ],
        offset_x: Annotated[int, Field(ge=-4096, le=4096)] = 0,
        offset_y: Annotated[int, Field(ge=-4096, le=4096)] = 0,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Translate, flip, or quarter-turn one image cel."""

        return await adapter.transform_cel(
            source_path, output_path, layer=layer, frame=frame, action=action,
            offset_x=offset_x, offset_y=offset_y, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_read_composited_pixels(
        source_path: Annotated[str, Field(description="Authorized sprite or image path")],
        frame: Annotated[int, Field(ge=0, description="Zero-based frame index")],
        x: Annotated[int, Field(ge=0)],
        y: Annotated[int, Field(ge=0)],
        width: Annotated[int, Field(ge=1, le=4096)],
        height: Annotated[int, Field(ge=1, le=4096)],
        include_transparent: bool = False,
    ) -> CompositedPixelReadResult:
        """Read final visible frame pixels as compact row-based RGBA runs."""

        return await adapter.read_composited_pixels(
            source_path,
            frame=frame,
            x=x,
            y=y,
            width=width,
            height=height,
            include_transparent=include_transparent,
        )

    @tools.tool()
    async def aseprite_set_pixel_runs(
        source_path: Annotated[str, Field(description="Authorized source sprite document")],
        output_path: Annotated[str, Field(description="Authorized destination sprite document")],
        layer: Annotated[str, Field(min_length=1, max_length=256)],
        frame: Annotated[int, Field(ge=0)],
        runs: Annotated[list[PixelRunInput], Field(min_length=1, max_length=10_000)],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Write horizontal RGBA pixel runs efficiently to one layer and frame."""

        return await adapter.set_pixel_runs(
            source_path,
            output_path,
            layer=layer,
            frame=frame,
            runs=runs,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_fill_region(
        source_path: str, output_path: str, layer: str,
        frame: Annotated[int, Field(ge=0)], x: Annotated[int, Field(ge=0)],
        y: Annotated[int, Field(ge=0)],
        color: Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")],
        contiguous: bool = True, overwrite: bool = False,
        expected_source_hash: str | None = None,
    ) -> MutationResult:
        """Flood-fill a bounded layer/frame region from one coordinate."""
        return await adapter.fill_region(source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"layer":layer,"frame":frame,"x":x,"y":y,"color":color,
                     "contiguous":contiguous,"max_pixel_visits":16_777_216})

    @tools.tool()
    async def aseprite_draw_shapes(
        source_path: str, output_path: str, layer: str,
        frame: Annotated[int, Field(ge=0)],
        shapes: Annotated[list[ShapeInput], Field(min_length=1, max_length=256)],
        overwrite: bool = False, expected_source_hash: str | None = None,
    ) -> MutationResult:
        """Draw fixed lines, rectangles, and ellipses on one layer/frame."""
        return await adapter.draw_shapes(source_path, output_path, layer=layer, frame=frame,
            shapes=shapes, overwrite=overwrite, expected_source_hash=expected_source_hash)

    @tools.tool()
    async def aseprite_edit_selection(
        source_path: str, output_path: str,
        operations: Annotated[list[SelectionEditOperation], Field(min_length=1, max_length=256)],
        overwrite: bool = False, expected_source_hash: str | None = None,
    ) -> MutationResult:
        """Replace, combine, clear, or select all of the document selection mask."""
        return await adapter.edit_selection(source_path, output_path, operations=operations,
            overwrite=overwrite, expected_source_hash=expected_source_hash)

    @tools.tool()
    async def aseprite_apply_outline(
        source_path: str, output_path: str, layer: str,
        frame: Annotated[int, Field(ge=0)],
        color: Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")],
        place: Literal["inside", "outside"] = "outside",
        matrix: Literal["circle", "square", "horizontal", "vertical"] = "circle",
        overwrite: bool = False, expected_source_hash: str | None = None,
    ) -> MutationResult:
        """Apply a fixed inside or outside outline to one cel."""
        return await adapter.apply_outline(source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"layer":layer,"frame":frame,"color":color,"place":place,"matrix":matrix})

    @tools.tool()
    async def aseprite_draw_strokes(
        source_path: str,
        output_path: str,
        layer: Annotated[str, Field(min_length=1, max_length=256)],
        frame: Annotated[int, Field(ge=0)],
        strokes: Annotated[list[StrokeInput], Field(min_length=1, max_length=256)],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Draw bounded pencil strokes with explicit points, brush size, and opacity."""
        return await adapter.draw_strokes(
            source_path,
            output_path,
            layer=layer,
            frame=frame,
            strokes=strokes,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_transform_selection(
        source_path: str,
        output_path: str,
        layer: Annotated[str, Field(min_length=1, max_length=256)],
        frame: Annotated[int, Field(ge=0)],
        bounds: RectangleInput,
        action: Literal[
            "move", "copy", "flip_horizontal", "flip_vertical", "rotate_90_cw",
            "rotate_90_ccw", "scale_nearest"
        ],
        offset_x: Annotated[int, Field(ge=-4096, le=4096)] = 0,
        offset_y: Annotated[int, Field(ge=-4096, le=4096)] = 0,
        scale_x: Annotated[int, Field(ge=1, le=16)] = 1,
        scale_y: Annotated[int, Field(ge=1, le=16)] = 1,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Move, copy, flip, quarter-turn, or nearest-neighbor scale a rectangular pixel region."""
        return await adapter.transform_selection(
            source_path,
            output_path,
            layer=layer,
            frame=frame,
            bounds=bounds,
            action=action,
            offset_x=offset_x,
            offset_y=offset_y,
            scale_x=scale_x,
            scale_y=scale_y,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_select_by_color(
        source_path: str,
        output_path: str,
        colors: Annotated[list[PaletteColorInput], Field(min_length=1, max_length=256)],
        frame: Annotated[int, Field(ge=0)] = 0,
        layer: Annotated[str | None, Field(min_length=1, max_length=256)] = None,
        tolerance: Annotated[int, Field(ge=0, le=510)] = 0,
        selection_mode: Literal["replace", "add", "subtract", "intersect"] = "replace",
        include_alpha: bool = True,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Build a document selection from matching layer or composited frame colors."""
        return await adapter.select_by_color(
            source_path, output_path, colors=colors, frame=frame, layer=layer,
            tolerance=tolerance, selection_mode=selection_mode, include_alpha=include_alpha,
            overwrite=overwrite, expected_source_hash=expected_source_hash,
        )

    return tools.registered_count
