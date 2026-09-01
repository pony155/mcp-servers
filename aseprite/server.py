"""MCP server construction and tool registration."""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver import Image
from pydantic import Field

from . import __version__
from .adapter import AsepriteAdapter
from .config import Settings
from .models import (
    AnimationFrameDefinition,
    AnimationEventEditOperation,
    AnimationTagDefinition,
    AnimationValidationResult,
    AssetSetValidationResult,
    AtlasResult,
    BatchExportJob,
    BatchExportResult,
    BitmapFontResult,
    BitmapGlyphInput,
    BlendModeEditOperation,
    CelEditOperation,
    CelInspectionResult,
    CompositedPixelReadResult,
    ContactSheetResult,
    CollisionMaskResult,
    CollisionPolygonResult,
    ExportProfile,
    ExportProfileValidationResult,
    FrameComparisonResult,
    FrameExportInput,
    FrameExportResult,
    FrameEditOperation,
    FrameDefinition,
    FileResult,
    HealthResult,
    LayerDefinition,
    LayerEditOperation,
    LoopTransitionValidationResult,
    MotionReportResult,
    MutationResult,
    PaletteAnalysisResult,
    PaletteColorInput,
    PaletteEntryEditOperation,
    PixelInput,
    PixelArtValidationResult,
    PixelReadResult,
    PixelRunInput,
    PropertyEditOperation,
    RectangleInput,
    RenderResult,
    SelectionEditOperation,
    ShapeInput,
    SliceEditOperation,
    SliceExtractionInput,
    SliceExtractionResult,
    SpriteComparisonResult,
    SpriteInfo,
    SpriteSheetResult,
    StrokeInput,
    TagEditOperation,
    TilemapCellInput,
    TileMetadataEditOperation,
    TileMetadataResult,
    TilesetEditOperation,
    TilesetExportResult,
    TilesetInspectionResult,
    TilesetValidationResult,
)

logger = logging.getLogger(__name__)


def build_server(settings: Settings) -> MCPServer:
    """Build a configured server without starting a transport."""

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
    async def aseprite_create_animation(
        output_path: Annotated[str, Field(description="Authorized .ase or .aseprite output path")],
        width: Annotated[int, Field(ge=1, le=4096)],
        height: Annotated[int, Field(ge=1, le=4096)],
        frames: Annotated[list[AnimationFrameDefinition], Field(min_length=1, max_length=256)],
        color_mode: Literal["rgb", "grayscale", "indexed"] = "rgb",
        layers: Annotated[list[LayerDefinition] | None, Field(max_length=128)] = None,
        tags: Annotated[list[AnimationTagDefinition] | None, Field(max_length=256)] = None,
        overwrite: Annotated[
            bool, Field(description="Explicitly allow replacing output_path")
        ] = False,
    ) -> MutationResult:
        """Create an animation with per-frame durations, layer cels, pixels, and tags."""

        return await adapter.create_animation(
            output_path,
            width=width,
            height=height,
            color_mode=color_mode,
            layers=layers if layers is not None else [LayerDefinition(name="Layer 1")],
            frames=frames,
            tags=tags or [],
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

    @server.tool()
    async def aseprite_import_sprite_sheet(
        source_path: Annotated[str, Field(description="Authorized source PNG sprite sheet")],
        output_path: Annotated[
            str, Field(description="Authorized destination .ase or .aseprite path")
        ],
        frame_width: Annotated[int, Field(ge=1, le=4096)],
        frame_height: Annotated[int, Field(ge=1, le=4096)],
        columns: Annotated[
            int | None,
            Field(ge=1, le=256, description="Grid columns; inferred from image width by default"),
        ] = None,
        frame_count: Annotated[
            int | None,
            Field(ge=1, le=256, description="Frames to import; all complete cells by default"),
        ] = None,
        margin: Annotated[int, Field(ge=0, le=4096)] = 0,
        spacing: Annotated[int, Field(ge=0, le=4096)] = 0,
        duration_ms: Annotated[int, Field(ge=1, le=60_000)] = 100,
        layer_name: Annotated[str, Field(min_length=1, max_length=128)] = "Layer 1",
        tag_name: Annotated[str | None, Field(min_length=1, max_length=128)] = None,
        transparent_color: Annotated[
            str | None,
            Field(
                pattern=r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$",
                description="Optional #RRGGBB or #RRGGBBAA color key",
            ),
        ] = None,
        overwrite: Annotated[
            bool, Field(description="Explicitly allow replacing output_path")
        ] = False,
    ) -> MutationResult:
        """Import a PNG grid as an editable Aseprite animation with one cel per frame."""

        return await adapter.import_sprite_sheet(
            source_path,
            output_path,
            frame_width=frame_width,
            frame_height=frame_height,
            columns=columns,
            frame_count=frame_count,
            margin=margin,
            spacing=spacing,
            duration_ms=duration_ms,
            layer_name=layer_name,
            tag_name=tag_name,
            transparent_color=transparent_color,
            overwrite=overwrite,
        )

    @server.tool()
    async def aseprite_resize_canvas(
        source_path: Annotated[str, Field(description="Authorized source sprite document")],
        output_path: Annotated[
            str, Field(description="Authorized destination .ase or .aseprite path")
        ],
        width: Annotated[int, Field(ge=1, le=4096)],
        height: Annotated[int, Field(ge=1, le=4096)],
        anchor: Literal[
            "top-left",
            "top",
            "top-right",
            "left",
            "center",
            "right",
            "bottom-left",
            "bottom",
            "bottom-right",
        ] = "center",
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
        """Resize the transparent canvas without scaling sprite artwork."""

        return await adapter.resize_canvas(
            source_path,
            output_path,
            width=width,
            height=height,
            anchor=anchor,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_resize_sprite(
        source_path: Annotated[str, Field(description="Authorized source sprite document")],
        output_path: Annotated[
            str, Field(description="Authorized destination .ase or .aseprite path")
        ],
        width: Annotated[int, Field(ge=1, le=4096)],
        height: Annotated[int, Field(ge=1, le=4096)],
        method: Literal["nearest"] = "nearest",
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
        """Scale an Aseprite document and its cels using nearest-neighbor pixel scaling."""

        return await adapter.resize_sprite(
            source_path,
            output_path,
            width=width,
            height=height,
            method=method,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_validate_animation(
        source_path: Annotated[str, Field(description="Authorized sprite or image path")],
        baseline_tolerance: Annotated[
            int,
            Field(ge=0, le=4096, description="Allowed difference between frame baselines"),
        ] = 0,
        bounds_tolerance: Annotated[
            int,
            Field(ge=0, le=4096, description="Allowed width and height drift across frames"),
        ] = 0,
        check_duplicates: Annotated[
            bool, Field(description="Detect frames with matching visible-pixel signatures")
        ] = True,
    ) -> AnimationValidationResult:
        """Validate frame occupancy, bounds, baseline consistency, sizing, and duplicates."""

        return await adapter.validate_animation(
            source_path,
            baseline_tolerance=baseline_tolerance,
            bounds_tolerance=bounds_tolerance,
            check_duplicates=check_duplicates,
        )

    @server.tool()
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

    @server.tool()
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

    @server.tool()
    async def aseprite_edit_frames(
        source_path: Annotated[str, Field(description="Authorized source sprite document")],
        output_path: Annotated[str, Field(description="Authorized destination sprite document")],
        operations: Annotated[list[FrameEditOperation], Field(min_length=1, max_length=256)],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Add, duplicate, remove, or retime frames in sequential operation order."""

        return await adapter.edit_frames(
            source_path, output_path, operations=operations, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_edit_layers(
        source_path: Annotated[str, Field(description="Authorized source sprite document")],
        output_path: Annotated[str, Field(description="Authorized destination sprite document")],
        operations: Annotated[list[LayerEditOperation], Field(min_length=1, max_length=128)],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Add, remove, rename, show, hide, reorder, or regroup layers sequentially."""

        return await adapter.edit_layers(
            source_path, output_path, operations=operations, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_edit_tags(
        source_path: Annotated[str, Field(description="Authorized source sprite document")],
        output_path: Annotated[str, Field(description="Authorized destination sprite document")],
        operations: Annotated[list[TagEditOperation], Field(min_length=1, max_length=256)],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Create/update or remove animation tags in sequential operation order."""

        return await adapter.edit_tags(
            source_path, output_path, operations=operations, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_apply_palette(
        source_path: Annotated[str, Field(description="Authorized source sprite document")],
        output_path: Annotated[str, Field(description="Authorized destination sprite document")],
        colors: Annotated[list[PaletteColorInput], Field(min_length=1, max_length=256)],
        preserve_alpha: Annotated[
            bool, Field(description="Preserve RGB-sprite pixel alpha")
        ] = True,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Remap cel colors to the nearest supplied palette colors."""

        return await adapter.apply_palette(
            source_path, output_path, colors=colors, preserve_alpha=preserve_alpha,
            overwrite=overwrite, expected_source_hash=expected_source_hash,
        )

    @server.tool()
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

    @server.tool()
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

    @server.tool()
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

    @server.tool()
    async def aseprite_copy_cel(
        source_path: Annotated[str, Field(description="Authorized source sprite document")],
        output_path: Annotated[str, Field(description="Authorized destination sprite document")],
        source_layer: Annotated[str, Field(min_length=1, max_length=256)],
        source_frame: Annotated[int, Field(ge=0)],
        target_layer: Annotated[str, Field(min_length=1, max_length=256)],
        target_frame: Annotated[int, Field(ge=0)],
        linked: Annotated[bool, Field(description="Share image data between the two cels")] = False,
        replace: Annotated[
            bool, Field(description="Explicitly replace an existing target cel")
        ] = False,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Copy or link an existing image cel to another layer/frame location."""

        return await adapter.copy_cel(
            source_path,
            output_path,
            source_layer=source_layer,
            source_frame=source_frame,
            target_layer=target_layer,
            target_frame=target_frame,
            linked=linked,
            replace=replace,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_compare_frames(
        source_path: Annotated[str, Field(description="Authorized sprite or image path")],
        first_frame: Annotated[int, Field(ge=0)],
        second_frame: Annotated[int, Field(ge=0)],
        difference_output_path: Annotated[
            str | None, Field(description="Optional authorized PNG difference path")
        ] = None,
        overwrite: bool = False,
    ) -> FrameComparisonResult:
        """Compare composited frames and optionally write a magenta difference image."""

        return await adapter.compare_frames(
            source_path,
            first_frame=first_frame,
            second_frame=second_frame,
            difference_output_path=difference_output_path,
            overwrite=overwrite,
        )

    @server.tool()
    async def aseprite_edit_slices(
        source_path: Annotated[str, Field(description="Authorized source sprite document")],
        output_path: Annotated[str, Field(description="Authorized destination sprite document")],
        operations: Annotated[list[SliceEditOperation], Field(min_length=1, max_length=256)],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Create/update frame-specific slices or remove named slices."""

        return await adapter.edit_slices(
            source_path,
            output_path,
            operations=operations,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_trim_cels(
        source_path: Annotated[str, Field(description="Authorized source sprite document")],
        output_path: Annotated[str, Field(description="Authorized destination sprite document")],
        layers: Annotated[list[str] | None, Field(max_length=128)] = None,
        frames: Annotated[list[int] | None, Field(max_length=256)] = None,
        remove_empty: Annotated[
            bool, Field(description="Delete selected empty transparent cels")
        ] = False,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Trim transparent cel borders while preserving canvas placement."""

        return await adapter.trim_cels(
            source_path,
            output_path,
            layers=layers or [],
            frames=frames or [],
            remove_empty=remove_empty,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_edit_properties(
        source_path: Annotated[str, Field(description="Authorized source sprite document")],
        output_path: Annotated[str, Field(description="Authorized destination sprite document")],
        operations: Annotated[list[PropertyEditOperation], Field(min_length=1, max_length=256)],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Set or remove scalar user properties on sprite production objects."""

        return await adapter.edit_properties(
            source_path,
            output_path,
            operations=operations,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_convert_color_mode(
        source_path: Annotated[str, Field(description="Authorized source sprite document")],
        output_path: Annotated[str, Field(description="Authorized destination sprite document")],
        color_mode: Literal["rgb", "grayscale", "indexed"],
        dithering: Literal["none", "ordered", "error-diffusion"] = "none",
        dithering_matrix: Literal["bayer2x2", "bayer4x4", "bayer8x8"] = "bayer8x8",
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Convert a sprite color mode with an explicit bounded dithering choice."""

        return await adapter.convert_color_mode(
            source_path,
            output_path,
            color_mode=color_mode,
            dithering=dithering,
            dithering_matrix=dithering_matrix,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_edit_tileset(
        source_path: Annotated[str, Field(description="Authorized source sprite document")],
        output_path: Annotated[str, Field(description="Authorized destination sprite document")],
        operations: Annotated[list[TilesetEditOperation], Field(min_length=1, max_length=256)],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Create or rename tilesets and add, remove, or repaint their tiles."""

        return await adapter.edit_tileset(
            source_path,
            output_path,
            operations=operations,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
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

    @server.tool()
    async def aseprite_inspect_cels(source_path: str) -> CelInspectionResult:
        """Inspect cel geometry, opacity, z-index, image identity, and linked groups."""
        return await adapter.inspect_cels(source_path)

    @server.tool()
    async def aseprite_analyze_palette(
        source_path: str,
        near_duplicate_distance: Annotated[int, Field(ge=0, le=765)] = 24,
    ) -> PaletteAnalysisResult:
        """Analyze exact color usage, unused entries, and nearby colors."""
        return await adapter.analyze_palette(
            source_path, near_duplicate_distance=near_duplicate_distance
        )

    @server.tool()
    async def aseprite_replace_color(
        source_path: str, output_path: str,
        from_color: Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")],
        to_color: Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")],
        tolerance: Annotated[int, Field(ge=0, le=1020)] = 0,
        layers: list[str] | None = None, frames: list[int] | None = None,
        overwrite: bool = False, expected_source_hash: str | None = None,
    ) -> MutationResult:
        """Replace a color across selected image layers and frames."""
        return await adapter.replace_color(source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"from_color":from_color,"to_color":to_color,"tolerance":tolerance,
                     "layers":layers or [],"frames":frames or []})

    @server.tool()
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

    @server.tool()
    async def aseprite_draw_shapes(
        source_path: str, output_path: str, layer: str,
        frame: Annotated[int, Field(ge=0)],
        shapes: Annotated[list[ShapeInput], Field(min_length=1, max_length=256)],
        overwrite: bool = False, expected_source_hash: str | None = None,
    ) -> MutationResult:
        """Draw fixed lines, rectangles, and ellipses on one layer/frame."""
        return await adapter.draw_shapes(source_path, output_path, layer=layer, frame=frame,
            shapes=shapes, overwrite=overwrite, expected_source_hash=expected_source_hash)

    @server.tool()
    async def aseprite_edit_selection(
        source_path: str, output_path: str,
        operations: Annotated[list[SelectionEditOperation], Field(min_length=1, max_length=256)],
        overwrite: bool = False, expected_source_hash: str | None = None,
    ) -> MutationResult:
        """Replace, combine, clear, or select all of the document selection mask."""
        return await adapter.edit_selection(source_path, output_path, operations=operations,
            overwrite=overwrite, expected_source_hash=expected_source_hash)

    @server.tool()
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

    @server.tool()
    async def aseprite_inspect_tilesets(source_path: str) -> TilesetInspectionResult:
        """Inspect tileset dimensions/counts and tilemap layer paths."""
        return await adapter.inspect_tilesets(source_path)

    @server.tool()
    async def aseprite_edit_tilemap(
        source_path: str, output_path: str, layer: str, tileset: str,
        frame: Annotated[int, Field(ge=0)],
        cells: Annotated[list[TilemapCellInput], Field(min_length=1, max_length=100_000)],
        create_layer: bool = False, overwrite: bool = False,
        expected_source_hash: str | None = None,
    ) -> MutationResult:
        """Create or edit a tilemap layer using bounded tile-cell records."""
        return await adapter.edit_tilemap(source_path, output_path, layer=layer, tileset=tileset,
            frame=frame, create_layer=create_layer, cells=cells, overwrite=overwrite,
            expected_source_hash=expected_source_hash)

    @server.tool()
    async def aseprite_validate_tileset(
        source_path: str, tileset: str, check_edges: bool = True,
    ) -> TilesetValidationResult:
        """Detect empty, duplicate, and non-seamless tiles."""
        return await adapter.validate_tileset(
            source_path, tileset=tileset, check_edges=check_edges
        )

    @server.tool()
    async def aseprite_export_tileset(
        source_path: str, image_output_path: str, data_output_path: str, tileset: str,
        columns: Annotated[int, Field(ge=1, le=256)] = 16, overwrite: bool = False,
    ) -> TilesetExportResult:
        """Export one tileset to a PNG grid and JSON metadata."""
        return await adapter.export_tileset(source_path, image_output_path, data_output_path,
            tileset=tileset, columns=columns, overwrite=overwrite)

    @server.tool()
    async def aseprite_preview_animation(
        source_path: str, tag: str | None = None,
        scale: Annotated[float, Field(ge=0.1, le=16)] = 1.0,
    ) -> Image:
        """Return an inline animated GIF for all frames or one tag."""
        return Image(data=await adapter.preview_animation(source_path, tag=tag, scale=scale),
                     format="gif")

    @server.tool()
    async def aseprite_crop_sprite(
        source_path: str,
        output_path: str,
        padding: Annotated[int, Field(ge=0, le=4096)] = 0,
        frames: Annotated[
            list[Annotated[int, Field(ge=0)]] | None, Field(max_length=256)
        ] = None,
        layers: Annotated[
            list[Annotated[str, Field(min_length=1, max_length=256)]] | None,
            Field(max_length=128),
        ] = None,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Crop the canvas to visible pixels in selected frames and layers, with padding."""
        return await adapter.crop_sprite(
            source_path,
            output_path,
            padding=padding,
            frames=frames or [],
            layers=layers or [],
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
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

    @server.tool()
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

    @server.tool()
    async def aseprite_edit_palette_entries(
        source_path: str,
        output_path: str,
        operations: Annotated[
            list[PaletteEntryEditOperation], Field(min_length=1, max_length=256)
        ],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Set, append, remove, or swap indexed palette entries safely."""
        return await adapter.edit_palette_entries(
            source_path,
            output_path,
            operations=operations,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_compare_sprites(
        first_source_path: str,
        second_source_path: str,
    ) -> SpriteComparisonResult:
        """Compare two sprites' structure, metadata, and composited frame pixels."""
        return await adapter.compare_sprites(first_source_path, second_source_path)

    @server.tool()
    async def aseprite_validate_export_profile(
        source_path: str,
        profile: ExportProfile,
    ) -> ExportProfileValidationResult:
        """Validate a sprite against explicit engine-facing dimensions and naming requirements."""
        return await adapter.validate_export_profile(source_path, profile=profile)

    @server.tool()
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

    @server.tool()
    async def aseprite_quantize_palette(
        source_path: str,
        output_path: str,
        color_count: Annotated[int, Field(ge=2, le=256)] = 32,
        algorithm: Literal["default", "octree", "rgb5a3"] = "octree",
        dithering: Literal["none", "ordered", "error-diffusion"] = "none",
        dithering_matrix: Literal["bayer2x2", "bayer4x4", "bayer8x8"] = "bayer4x4",
        include_alpha: bool = True,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Create a bounded palette and convert a document to indexed color."""
        return await adapter.quantize_palette(
            source_path, output_path, color_count=color_count, algorithm=algorithm,
            dithering=dithering, dithering_matrix=dithering_matrix,
            include_alpha=include_alpha, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_import_palette(
        source_path: str,
        palette_path: str,
        output_path: str,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Load a supported palette file into a new sprite-document revision."""
        return await adapter.import_palette(
            source_path, palette_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_export_palette(
        source_path: str,
        output_path: str,
        overwrite: bool = False,
    ) -> FileResult:
        """Export the first sprite palette to an authorized palette file."""
        return await adapter.export_palette(source_path, output_path, overwrite=overwrite)

    @server.tool()
    async def aseprite_extract_slices(
        source_path: str,
        extractions: Annotated[list[SliceExtractionInput], Field(min_length=1, max_length=256)],
        overwrite: bool = False,
    ) -> SliceExtractionResult:
        """Render explicitly named slice/frame pairs to explicit PNG output paths."""
        return await adapter.extract_slices(
            source_path, extractions=extractions, overwrite=overwrite
        )

    @server.tool()
    async def aseprite_generate_collision_masks(
        source_path: str,
        frames: Annotated[
            list[Annotated[int, Field(ge=0)]] | None, Field(max_length=256)
        ] = None,
        layer: Annotated[str | None, Field(min_length=1, max_length=256)] = None,
        mode: Literal["bounds", "components"] = "components",
        alpha_threshold: Annotated[int, Field(ge=1, le=255)] = 1,
        max_components: Annotated[int, Field(ge=1, le=1024)] = 128,
    ) -> CollisionMaskResult:
        """Derive per-frame collision rectangles from composited or layer alpha."""
        return await adapter.generate_collision_masks(
            source_path, frames=frames or [], layer=layer, mode=mode,
            alpha_threshold=alpha_threshold, max_components=max_components,
        )

    @server.tool()
    async def aseprite_batch_export(
        jobs: Annotated[list[BatchExportJob], Field(min_length=1, max_length=64)],
    ) -> BatchExportResult:
        """Export bounded sprite-sheet jobs independently and report per-job failures."""
        return await adapter.batch_export(jobs)

    @server.tool()
    async def aseprite_validate_asset_set(
        source_paths: Annotated[list[str], Field(min_length=1, max_length=64)],
        profile: ExportProfile,
        require_consistent_dimensions: bool = True,
        require_consistent_color_mode: bool = True,
    ) -> AssetSetValidationResult:
        """Validate multiple assets against one profile and cross-asset consistency rules."""
        return await adapter.validate_asset_set(
            source_paths, profile=profile,
            require_consistent_dimensions=require_consistent_dimensions,
            require_consistent_color_mode=require_consistent_color_mode,
        )

    @server.tool()
    async def aseprite_merge_layers(
        source_path: str,
        output_path: str,
        mode: Literal["merge_down", "flatten"],
        layer: Annotated[str | None, Field(min_length=1, max_length=256)] = None,
        visible_only: bool = True,
        output_layer_name: Annotated[str | None, Field(min_length=1, max_length=128)] = None,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Merge one layer downward or flatten all/visible layers in an output revision."""
        return await adapter.merge_layers(
            source_path, output_path, mode=mode, layer=layer, visible_only=visible_only,
            output_layer_name=output_layer_name, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_export_frames(
        source_path: str,
        exports: Annotated[list[FrameExportInput], Field(min_length=1, max_length=256)],
        overwrite: bool = False,
    ) -> FrameExportResult:
        """Export explicit zero-based frames to explicit PNG output paths."""
        return await adapter.export_frames(source_path, exports=exports, overwrite=overwrite)

    @server.tool()
    async def aseprite_import_frames(
        source_path: str,
        output_path: str,
        frame_paths: Annotated[list[str], Field(min_length=1, max_length=256)],
        layer: Annotated[str, Field(min_length=1, max_length=256)],
        insert_at: Annotated[int | None, Field(ge=0)] = None,
        duration_ms: Annotated[int, Field(ge=1, le=60_000)] = 100,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Append or insert explicit same-size PNG files as frames on one image layer."""
        return await adapter.import_frames(
            source_path, output_path, frame_paths=frame_paths, layer=layer,
            insert_at=insert_at, duration_ms=duration_ms, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_render_tilemap_preview(
        source_path: str,
        tileset: Annotated[str, Field(min_length=1, max_length=128)],
        width_cells: Annotated[int, Field(ge=1, le=512)],
        height_cells: Annotated[int, Field(ge=1, le=512)],
        cells: Annotated[list[TilemapCellInput], Field(max_length=100_000)],
    ) -> Image:
        """Return an inline PNG for an explicit arrangement of tileset cells."""
        return Image(data=await adapter.render_tilemap_preview(
            source_path, tileset=tileset, width_cells=width_cells,
            height_cells=height_cells, cells=cells,
        ), format="png")

    @server.tool()
    async def aseprite_edit_grid(
        source_path: str,
        output_path: str,
        x: Annotated[int, Field(ge=-4096, le=4096)],
        y: Annotated[int, Field(ge=-4096, le=4096)],
        width: Annotated[int, Field(ge=1, le=4096)],
        height: Annotated[int, Field(ge=1, le=4096)],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Set sprite grid origin and cell dimensions in a new document revision."""
        return await adapter.edit_grid(
            source_path, output_path, x=x, y=y, width=width, height=height,
            overwrite=overwrite, expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_edit_blend_modes(
        source_path: str,
        output_path: str,
        operations: Annotated[list[BlendModeEditOperation], Field(min_length=1, max_length=128)],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Apply validated blend modes to exact non-group layer paths."""
        return await adapter.edit_blend_modes(
            source_path, output_path, operations=operations, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_edit_animation_events(
        source_path: str,
        output_path: str,
        operations: Annotated[
            list[AnimationEventEditOperation], Field(min_length=1, max_length=256)
        ],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Set or remove structured frame events stored in sprite metadata."""
        return await adapter.edit_animation_events(
            source_path, output_path, operations=operations, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
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

    @server.tool()
    async def aseprite_edit_cels(
        source_path: str,
        output_path: str,
        operations: Annotated[list[CelEditOperation], Field(min_length=1, max_length=256)],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Move, fade, reorder, unlink, or remove exact layer/frame cels."""
        return await adapter.edit_cels(
            source_path, output_path, operations=operations, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_generate_inbetweens(
        source_path: str,
        output_path: str,
        layer: Annotated[str, Field(min_length=1, max_length=256)],
        first_frame: Annotated[int, Field(ge=0)],
        last_frame: Annotated[int, Field(ge=1)],
        count: Annotated[int, Field(ge=1, le=64)],
        interpolation: Literal["hold", "nearest", "crossfade"] = "nearest",
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Insert bounded tween frames for one cel while preserving the starting frame's layers."""
        return await adapter.generate_inbetweens(
            source_path, output_path, layer=layer, first_frame=first_frame,
            last_frame=last_frame, count=count, interpolation=interpolation,
            overwrite=overwrite, expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_palette_cycle(
        source_path: str,
        output_path: str,
        indices: Annotated[
            list[Annotated[int, Field(ge=0, le=255)]], Field(min_length=2, max_length=256)
        ],
        first_frame: Annotated[int, Field(ge=0)],
        last_frame: Annotated[int, Field(ge=0)],
        step: Annotated[int, Field(ge=-255, le=255)] = 1,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Rotate selected indexed-color entries progressively across an existing frame range."""
        return await adapter.palette_cycle(
            source_path, output_path, indices=indices, first_frame=first_frame,
            last_frame=last_frame, step=step, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_preview_onion_skin(
        source_path: str,
        frame: Annotated[int, Field(ge=0)],
        before: Annotated[int, Field(ge=0, le=8)] = 1,
        after: Annotated[int, Field(ge=0, le=8)] = 1,
        opacity: Annotated[int, Field(ge=1, le=255)] = 96,
        scale: Annotated[int, Field(ge=1, le=16)] = 1,
    ) -> Image:
        """Return a PNG with earlier frames tinted red and later frames tinted blue."""
        return Image(data=await adapter.preview_onion_skin(
            source_path, frame=frame, before=before, after=after,
            opacity=opacity, scale=scale,
        ), format="png")

    @server.tool()
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

    @server.tool()
    async def aseprite_create_tileset_from_sheet(
        source_path: str,
        output_path: str,
        layer: Annotated[str, Field(min_length=1, max_length=256)],
        frame: Annotated[int, Field(ge=0)],
        name: Annotated[str, Field(min_length=1, max_length=128)],
        tile_width: Annotated[int, Field(ge=1, le=4096)],
        tile_height: Annotated[int, Field(ge=1, le=4096)],
        margin: Annotated[int, Field(ge=0, le=4096)] = 0,
        spacing: Annotated[int, Field(ge=0, le=4096)] = 0,
        columns: Annotated[int | None, Field(ge=1, le=4096)] = None,
        tile_count: Annotated[int | None, Field(ge=1, le=4096)] = None,
        deduplicate: bool = True,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Slice one image-layer cel into a named tileset with optional deduplication."""
        return await adapter.create_tileset_from_sheet(
            source_path, output_path, layer=layer, frame=frame, name=name,
            tile_width=tile_width, tile_height=tile_height, margin=margin,
            spacing=spacing, columns=columns, tile_count=tile_count,
            deduplicate=deduplicate, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_validate_pixel_art(
        source_path: str,
        frames: Annotated[
            list[Annotated[int, Field(ge=0)]] | None, Field(max_length=256)
        ] = None,
        max_colors: Annotated[int | None, Field(ge=1, le=256)] = None,
        require_binary_alpha: bool = True,
        detect_isolated_pixels: bool = True,
        allowed_palette: Annotated[
            list[PaletteColorInput] | None, Field(max_length=256)
        ] = None,
    ) -> PixelArtValidationResult:
        """Check color count, alpha, palette compliance, and isolated opaque pixels."""
        return await adapter.validate_pixel_art(
            source_path, frames=frames or [], max_colors=max_colors,
            require_binary_alpha=require_binary_alpha,
            detect_isolated_pixels=detect_isolated_pixels,
            allowed_palette=allowed_palette or [],
        )

    @server.tool()
    async def aseprite_validate_loop_transition(
        source_path: str,
        tag: Annotated[str | None, Field(min_length=1, max_length=128)] = None,
        first_frame: Annotated[int, Field(ge=0)] = 0,
        last_frame: Annotated[int | None, Field(ge=0)] = None,
        max_changed_pixels: Annotated[int, Field(ge=0, le=16_777_216)] = 0,
        require_equal_duration: bool = False,
    ) -> LoopTransitionValidationResult:
        """Validate visual and optional timing continuity between loop endpoints."""
        return await adapter.validate_loop_transition(
            source_path, tag=tag, first_frame=first_frame, last_frame=last_frame,
            max_changed_pixels=max_changed_pixels,
            require_equal_duration=require_equal_duration,
        )

    @server.tool()
    async def aseprite_inspect_tile_metadata(
        source_path: str,
        tileset: Annotated[str, Field(min_length=1, max_length=128)],
        tile_indices: Annotated[
            list[Annotated[int, Field(ge=0, le=4096)]] | None, Field(max_length=4096)
        ] = None,
    ) -> TileMetadataResult:
        """Read scalar properties and user metadata from a tileset and selected tiles."""
        return await adapter.inspect_tile_metadata(
            source_path, tileset=tileset, tile_indices=tile_indices or []
        )

    @server.tool()
    async def aseprite_edit_tile_metadata(
        source_path: str,
        output_path: str,
        tileset: Annotated[str, Field(min_length=1, max_length=128)],
        operations: Annotated[
            list[TileMetadataEditOperation], Field(min_length=1, max_length=512)
        ],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Set or remove scalar properties on an exact tileset or tile index."""
        return await adapter.edit_tile_metadata(
            source_path, output_path, tileset=tileset, operations=operations,
            overwrite=overwrite, expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_edit_color_space(
        source_path: str,
        output_path: str,
        mode: Literal[
            "assign_srgb", "assign_none", "assign_icc", "convert_srgb", "convert_icc"
        ],
        profile_path: str | None = None,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Assign or convert a document color space using sRGB or an authorized ICC profile."""
        return await adapter.edit_color_space(
            source_path, output_path, mode=mode, profile_path=profile_path,
            overwrite=overwrite, expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_retime_animation(
        source_path: str,
        output_path: str,
        mode: Literal["fps", "total_duration", "scale"],
        tag: Annotated[str | None, Field(min_length=1, max_length=128)] = None,
        target_fps: Annotated[float | None, Field(gt=0.01, le=1000)] = None,
        target_total_duration_ms: Annotated[
            int | None, Field(ge=1, le=3_600_000)
        ] = None,
        scale: Annotated[float | None, Field(gt=0.001, le=1000)] = None,
        distribution: Literal[
            "preserve", "uniform", "ease_in", "ease_out", "ease_in_out"
        ] = "preserve",
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Retime all frames or one tag to an FPS, total duration, or scale factor."""
        return await adapter.retime_animation(
            source_path, output_path, tag=tag, mode=mode, target_fps=target_fps,
            target_total_duration_ms=target_total_duration_ms, scale=scale,
            distribution=distribution, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_bake_tag_direction(
        source_path: str,
        output_path: str,
        tag: Annotated[str, Field(min_length=1, max_length=128)],
        output_tag: Annotated[str, Field(min_length=1, max_length=128)],
        repetitions: Annotated[int, Field(ge=1, le=16)] = 1,
        link_images: bool = False,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Append a forward frame sequence that materializes a tag's playback direction."""
        return await adapter.bake_tag_direction(
            source_path, output_path, tag=tag, output_tag=output_tag,
            repetitions=repetitions, link_images=link_images, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @server.tool()
    async def aseprite_generate_motion_report(
        source_path: str,
        tag: Annotated[str | None, Field(min_length=1, max_length=128)] = None,
        layer: Annotated[str | None, Field(min_length=1, max_length=256)] = None,
        alpha_threshold: Annotated[int, Field(ge=1, le=255)] = 1,
    ) -> MotionReportResult:
        """Measure bounds, centroid, velocity, acceleration, travel, and peak speed."""
        return await adapter.generate_motion_report(
            source_path, tag=tag, layer=layer, alpha_threshold=alpha_threshold
        )

    @server.tool()
    async def aseprite_generate_collision_polygons(
        source_path: str,
        frames: Annotated[
            list[Annotated[int, Field(ge=0)]] | None, Field(max_length=256)
        ] = None,
        layer: Annotated[str | None, Field(min_length=1, max_length=256)] = None,
        alpha_threshold: Annotated[int, Field(ge=1, le=255)] = 1,
        simplify_tolerance: Annotated[int, Field(ge=0, le=64)] = 0,
        max_polygons: Annotated[int, Field(ge=1, le=1024)] = 128,
        max_points_per_polygon: Annotated[int, Field(ge=3, le=8192)] = 2048,
    ) -> CollisionPolygonResult:
        """Trace bounded outer collision contours from composited or layer alpha."""
        return await adapter.generate_collision_polygons(
            source_path, frames=frames or [], layer=layer,
            alpha_threshold=alpha_threshold, simplify_tolerance=simplify_tolerance,
            max_polygons=max_polygons, max_points_per_polygon=max_points_per_polygon,
        )

    @server.tool()
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

    logger.info("Registered 78 Aseprite MCP tools")
    return server
