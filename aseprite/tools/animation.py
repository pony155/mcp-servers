"""MCP server construction and tool registration."""

from __future__ import annotations
from typing import Annotated, Literal
from mcp.server import MCPServer
from mcp.server.mcpserver import Image
from pydantic import Field
from ..adapter import AsepriteAdapter
from ..capabilities import CapabilityRegistry, ToolRegistrar
from ..models import (
    AnimationFrameDefinition,
    AnimationEventEditOperation,
    AnimationTagDefinition,
    FrameEditOperation,
    LayerDefinition,
    MutationResult,
    TagEditOperation,
)
from .inputs import ExpectedSourceHash, Overwrite, SpriteOutputPath, SpriteSourcePath


def register_animation_tools(
    server: MCPServer, adapter: AsepriteAdapter, registry: CapabilityRegistry, *, enabled: bool
) -> int:
    """Register animation tools and return the number registered."""

    tools = ToolRegistrar(server, registry, "animation", enabled=enabled)

    @tools.tool()
    async def aseprite_create_animation(
        output_path: SpriteOutputPath,
        width: Annotated[int, Field(ge=1, le=4096)],
        height: Annotated[int, Field(ge=1, le=4096)],
        frames: Annotated[list[AnimationFrameDefinition], Field(min_length=1, max_length=256)],
        color_mode: Literal["rgb", "grayscale", "indexed"] = "rgb",
        layers: Annotated[list[LayerDefinition] | None, Field(max_length=128)] = None,
        tags: Annotated[list[AnimationTagDefinition] | None, Field(max_length=256)] = None,
        overwrite: Overwrite = False,
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

    @tools.tool()
    async def aseprite_edit_frames(
        source_path: SpriteSourcePath,
        output_path: SpriteOutputPath,
        operations: Annotated[list[FrameEditOperation], Field(min_length=1, max_length=256)],
        overwrite: Overwrite = False,
        expected_source_hash: ExpectedSourceHash = None,
    ) -> MutationResult:
        """Add, duplicate, remove, or retime frames in sequential operation order."""

        return await adapter.edit_frames(
            source_path, output_path, operations=operations, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
    async def aseprite_preview_animation(
        source_path: str, tag: str | None = None,
        scale: Annotated[float, Field(ge=0.1, le=16)] = 1.0,
    ) -> Image:
        """Return an inline animated GIF for all frames or one tag."""
        return Image(data=await adapter.preview_animation(source_path, tag=tag, scale=scale),
                     format="gif")

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
    async def aseprite_optimize_linked_cels(
        source_path: SpriteSourcePath,
        output_path: SpriteOutputPath,
        layers: Annotated[list[str] | None, Field(max_length=128)] = None,
        frames: Annotated[
            list[Annotated[int, Field(ge=0)]] | None,
            Field(max_length=256),
        ] = None,
        overwrite: Overwrite = False,
        expected_source_hash: ExpectedSourceHash = None,
    ) -> MutationResult:
        """Link exactly identical selected cel images without deleting animation frames."""

        return await adapter.optimize_linked_cels(
            source_path,
            output_path,
            layers=layers or [],
            frames=frames or [],
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    return tools.registered_count
