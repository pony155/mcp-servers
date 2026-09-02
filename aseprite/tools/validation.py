"""MCP server construction and tool registration."""

from __future__ import annotations
from typing import Annotated, Literal
from mcp.server import MCPServer
from pydantic import Field
from ..adapter import AsepriteAdapter
from ..capabilities import CapabilityRegistry, ToolRegistrar
from ..models import (
    AnimationValidationResult,
    AssetSetValidationResult,
    CelInspectionResult,
    CollisionMaskResult,
    CollisionPolygonResult,
    ExportProfile,
    ExportProfileValidationResult,
    FrameComparisonResult,
    LoopTransitionValidationResult,
    MotionReportResult,
    PaletteColorInput,
    PixelArtValidationResult,
    SpriteComparisonResult,
)
from .inputs import Overwrite, SourcePath


def register_validation_tools(
    server: MCPServer, adapter: AsepriteAdapter, registry: CapabilityRegistry, *, enabled_tools: frozenset[str]
) -> int:
    """Register validation tools and return the number registered."""

    tools = ToolRegistrar(server, registry, "validation", enabled_tools=enabled_tools)

    @tools.tool()
    async def aseprite_validate_animation(
        source_path: SourcePath,
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

    @tools.tool()
    async def aseprite_compare_frames(
        source_path: SourcePath,
        first_frame: Annotated[int, Field(ge=0)],
        second_frame: Annotated[int, Field(ge=0)],
        difference_output_path: Annotated[
            str | None, Field(description="Optional authorized PNG difference path")
        ] = None,
        overwrite: Overwrite = False,
    ) -> FrameComparisonResult:
        """Compare composited frames and optionally write a magenta difference image."""

        return await adapter.compare_frames(
            source_path,
            first_frame=first_frame,
            second_frame=second_frame,
            difference_output_path=difference_output_path,
            overwrite=overwrite,
        )

    @tools.tool()
    async def aseprite_inspect_cels(source_path: str) -> CelInspectionResult:
        """Inspect cel geometry, opacity, z-index, image identity, and linked groups."""
        return await adapter.inspect_cels(source_path)

    @tools.tool()
    async def aseprite_compare_sprites(
        first_source_path: str,
        second_source_path: str,
    ) -> SpriteComparisonResult:
        """Compare two sprites' structure, metadata, and composited frame pixels."""
        return await adapter.compare_sprites(first_source_path, second_source_path)

    @tools.tool()
    async def aseprite_validate_export_profile(
        source_path: str,
        profile: ExportProfile,
    ) -> ExportProfileValidationResult:
        """Validate a sprite against explicit engine-facing dimensions and naming requirements."""
        return await adapter.validate_export_profile(source_path, profile=profile)

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    return tools.registered_count
