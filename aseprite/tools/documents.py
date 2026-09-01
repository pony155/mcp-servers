"""MCP server construction and tool registration."""

from __future__ import annotations
from typing import Annotated, Literal
from mcp.server import MCPServer
from pydantic import Field
from ..adapter import AsepriteAdapter
from ..capabilities import CapabilityRegistry, ToolRegistrar
from ..models import (
    BlendModeEditOperation,
    CelEditOperation,
    FrameDefinition,
    LayerDefinition,
    LayerEditOperation,
    MutationResult,
    PixelInput,
    PropertyEditOperation,
    SliceEditOperation,
)
from .inputs import Overwrite, SpriteOutputPath


def register_documents_tools(
    server: MCPServer, adapter: AsepriteAdapter, registry: CapabilityRegistry, *, enabled: bool
) -> int:
    """Register documents tools and return the number registered."""

    tools = ToolRegistrar(server, registry, "documents", enabled=enabled)

    @tools.tool()
    async def aseprite_create_sprite(
        output_path: SpriteOutputPath,
        width: Annotated[int, Field(ge=1, le=4096)],
        height: Annotated[int, Field(ge=1, le=4096)],
        color_mode: Literal["rgb", "grayscale", "indexed"] = "rgb",
        layers: list[LayerDefinition] | None = None,
        frames: list[FrameDefinition] | None = None,
        pixels: list[PixelInput] | None = None,
        overwrite: Overwrite = False,
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    return tools.registered_count
