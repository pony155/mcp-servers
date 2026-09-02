"""MCP server construction and tool registration."""

from __future__ import annotations
from typing import Annotated, Literal
from mcp.server import MCPServer
from mcp.server.mcpserver import Image
from pydantic import Field
from ..adapter import AsepriteAdapter
from ..capabilities import CapabilityRegistry, ToolRegistrar
from ..models import (
    AtlasResult,
    BatchExportJob,
    BatchExportResult,
    BitmapFontResult,
    BitmapGlyphInput,
    ContactSheetResult,
    FrameExportInput,
    FrameExportResult,
    LayerVariantInput,
    LayerVariantResult,
    RenderResult,
    SliceExtractionInput,
    SliceExtractionResult,
    SpriteSheetResult,
)
from .inputs import OutputPath, Overwrite, SourcePath


def register_export_tools(
    server: MCPServer, adapter: AsepriteAdapter, registry: CapabilityRegistry, *, enabled_tools: frozenset[str]
) -> int:
    """Register export tools and return the number registered."""

    tools = ToolRegistrar(server, registry, "export", enabled_tools=enabled_tools)

    @tools.tool()
    async def aseprite_render(
        source_path: SourcePath,
        output_path: OutputPath,
        frame: Annotated[int | None, Field(ge=0, description="Zero-based frame index")] = None,
        tag: Annotated[str | None, Field(min_length=1, description="Animation tag name")] = None,
        layers: Annotated[
            list[str] | None,
            Field(description="Layer paths to include; all visible layers by default"),
        ] = None,
        scale: Annotated[float, Field(ge=0.1, le=16)] = 1.0,
        overwrite: Overwrite = False,
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

    @tools.tool()
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

    @tools.tool()
    async def aseprite_preview(
        source_path: Annotated[str, Field(description="Authorized sprite or image path")],
        mode: Literal["frame", "sheet"] = "frame",
        frame: Annotated[int, Field(ge=0, description="Zero-based frame for frame mode")] = 0,
        layout: Literal["horizontal", "vertical", "rows", "columns", "packed"] = "horizontal",
        tag: Annotated[
            str | None, Field(min_length=1, description="Optional tag for sheet mode")
        ] = None,
        layers: Annotated[
            list[str] | None, Field(description="Exact layer paths to include")
        ] = None,
        scale: Annotated[float, Field(ge=0.1, le=16)] = 1.0,
    ) -> Image:
        """Return an inline PNG preview of one frame or a sprite sheet."""

        data = await adapter.preview(
            source_path, mode=mode, frame=frame, layout=layout, tag=tag,
            layers=layers or [], scale=scale,
        )
        return Image(data=data, format="png")

    @tools.tool()
    async def aseprite_render_contact_sheet(
        source_path: Annotated[str, Field(description="Authorized sprite or image path")],
        output_path: Annotated[str, Field(description="Authorized PNG output path")],
        columns: Annotated[int, Field(ge=1, le=64)] = 8,
        scale: Annotated[int, Field(ge=1, le=16)] = 1,
        overwrite: bool = False,
    ) -> ContactSheetResult:
        """Render every frame into a labelled PNG review grid."""

        return await adapter.render_contact_sheet(
            source_path,
            output_path,
            columns=columns,
            scale=scale,
            overwrite=overwrite,
        )

    @tools.tool()
    async def aseprite_pack_atlas(
        source_paths: Annotated[list[str], Field(min_length=1, max_length=64)],
        image_output_path: str,
        data_output_path: str,
        width: Annotated[int | None, Field(ge=1, le=16384)] = None,
        height: Annotated[int | None, Field(ge=1, le=16384)] = None,
        trim: bool = True,
        extrude: bool = False,
        border_padding: Annotated[int, Field(ge=0, le=1024)] = 0,
        shape_padding: Annotated[int, Field(ge=0, le=1024)] = 1,
        inner_padding: Annotated[int, Field(ge=0, le=1024)] = 0,
        overwrite: bool = False,
    ) -> AtlasResult:
        """Pack up to 64 authorized sprite files into a PNG atlas and JSON metadata."""
        return await adapter.pack_atlas(
            source_paths, image_output_path, data_output_path, width=width, height=height,
            trim=trim, extrude=extrude, border_padding=border_padding,
            shape_padding=shape_padding, inner_padding=inner_padding, overwrite=overwrite,
        )

    @tools.tool()
    async def aseprite_extract_slices(
        source_path: str,
        extractions: Annotated[list[SliceExtractionInput], Field(min_length=1, max_length=256)],
        overwrite: bool = False,
    ) -> SliceExtractionResult:
        """Render explicitly named slice/frame pairs to explicit PNG output paths."""
        return await adapter.extract_slices(
            source_path, extractions=extractions, overwrite=overwrite
        )

    @tools.tool()
    async def aseprite_batch_export(
        jobs: Annotated[list[BatchExportJob], Field(min_length=1, max_length=64)],
    ) -> BatchExportResult:
        """Export bounded sprite-sheet jobs independently and report per-job failures."""
        return await adapter.batch_export(jobs)

    @tools.tool()
    async def aseprite_export_frames(
        source_path: str,
        exports: Annotated[list[FrameExportInput], Field(min_length=1, max_length=256)],
        overwrite: bool = False,
    ) -> FrameExportResult:
        """Export explicit zero-based frames to explicit PNG output paths."""
        return await adapter.export_frames(source_path, exports=exports, overwrite=overwrite)

    @tools.tool()
    async def aseprite_preview_nine_slice(
        source_path: str,
        slice_name: Annotated[str, Field(min_length=1, max_length=128)],
        frame: Annotated[int, Field(ge=0)],
        width: Annotated[int, Field(ge=1, le=4096)],
        height: Annotated[int, Field(ge=1, le=4096)],
    ) -> Image:
        """Return an inline PNG showing a named nine-slice at a requested size."""
        return Image(data=await adapter.preview_nine_slice(
            source_path, slice_name=slice_name, frame=frame, width=width, height=height,
        ), format="png")

    @tools.tool()
    async def aseprite_export_bitmap_font(
        source_path: str,
        image_output_path: str,
        data_output_path: str,
        glyphs: Annotated[list[BitmapGlyphInput], Field(min_length=1, max_length=512)],
        font_name: Annotated[str, Field(min_length=1, max_length=128)],
        line_height: Annotated[int, Field(ge=1, le=4096)],
        columns: Annotated[int, Field(ge=1, le=64)] = 16,
        padding: Annotated[int, Field(ge=0, le=64)] = 1,
        overwrite: bool = False,
    ) -> BitmapFontResult:
        """Export explicit glyph rectangles as a PNG atlas and deterministic JSON metrics."""
        return await adapter.export_bitmap_font(
            source_path, image_output_path, data_output_path, glyphs=glyphs,
            font_name=font_name, line_height=line_height, columns=columns,
            padding=padding, overwrite=overwrite,
        )

    @tools.tool()
    async def aseprite_render_layer_variants(
        source_path: SourcePath,
        variants: Annotated[list[LayerVariantInput], Field(min_length=1, max_length=128)],
        overwrite: Overwrite = False,
    ) -> LayerVariantResult:
        """Render named layer combinations to explicit PNG or GIF outputs."""

        return await adapter.render_layer_variants(
            source_path, variants=variants, overwrite=overwrite
        )

    return tools.registered_count
