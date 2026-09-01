"""MCP tools for beat-'em-up combat metadata and production checks."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver import Image
from pydantic import Field

from ..adapter import AsepriteAdapter
from ..capabilities import CapabilityRegistry, ToolRegistrar
from ..models import (
    ActionMetadataEditOperation,
    BeatEmUpBundleResult,
    CancelWindowEditOperation,
    CharacterRosterValidationResult,
    CombatActionValidationResult,
    CombatBoxEditOperation,
    CombatManifestResult,
    CombatSetValidationResult,
    FrameAnchorEditOperation,
    MutationResult,
    RootMotionEditOperation,
    StageGameplayValidationResult,
    StageGameplayZoneEditOperation,
)
from .inputs import ExpectedSourceHash, OutputPath, Overwrite, SpriteOutputPath, SpriteSourcePath


def register_combat_tools(
    server: MCPServer, adapter: AsepriteAdapter, registry: CapabilityRegistry, *, enabled: bool
) -> int:
    """Register combat-authoring tools and return the number registered."""

    tools = ToolRegistrar(server, registry, "combat", enabled=enabled)

    @tools.tool()
    async def aseprite_edit_combat_boxes(
        source_path: SpriteSourcePath,
        output_path: SpriteOutputPath,
        operations: Annotated[list[CombatBoxEditOperation], Field(min_length=1, max_length=2048)],
        overwrite: Overwrite = False,
        expected_source_hash: ExpectedSourceHash = None,
    ) -> MutationResult:
        """Set or remove frame-specific offensive, defensive, and occupancy boxes."""
        return await adapter.edit_combat_boxes(
            source_path, output_path, operations=operations, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_edit_frame_anchors(
        source_path: SpriteSourcePath,
        output_path: SpriteOutputPath,
        operations: Annotated[list[FrameAnchorEditOperation], Field(min_length=1, max_length=2048)],
        overwrite: Overwrite = False,
        expected_source_hash: ExpectedSourceHash = None,
    ) -> MutationResult:
        """Set or remove named per-frame gameplay and attachment anchors."""
        return await adapter.edit_frame_anchors(
            source_path, output_path, operations=operations, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_edit_action_metadata(
        source_path: SpriteSourcePath,
        output_path: SpriteOutputPath,
        operations: Annotated[
            list[ActionMetadataEditOperation], Field(min_length=1, max_length=256)
        ],
        overwrite: Overwrite = False,
        expected_source_hash: ExpectedSourceHash = None,
    ) -> MutationResult:
        """Set or remove tagged action type, facing, movement, transition, and speed metadata."""
        return await adapter.edit_action_metadata(
            source_path, output_path, operations=operations, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_edit_cancel_windows(
        source_path: SpriteSourcePath,
        output_path: SpriteOutputPath,
        operations: Annotated[list[CancelWindowEditOperation], Field(min_length=1, max_length=512)],
        overwrite: Overwrite = False,
        expected_source_hash: ExpectedSourceHash = None,
    ) -> MutationResult:
        """Set or remove conditional frame ranges and their permitted action transitions."""
        return await adapter.edit_cancel_windows(
            source_path, output_path, operations=operations, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_edit_root_motion(
        source_path: SpriteSourcePath,
        output_path: SpriteOutputPath,
        operations: Annotated[list[RootMotionEditOperation], Field(min_length=1, max_length=2048)],
        overwrite: Overwrite = False,
        expected_source_hash: ExpectedSourceHash = None,
    ) -> MutationResult:
        """Set or remove explicit per-frame screen, vertical, and lane displacement."""
        return await adapter.edit_root_motion(
            source_path, output_path, operations=operations, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_edit_stage_gameplay_zones(
        source_path: SpriteSourcePath,
        output_path: SpriteOutputPath,
        operations: Annotated[
            list[StageGameplayZoneEditOperation], Field(min_length=1, max_length=1024)
        ],
        overwrite: Overwrite = False,
        expected_source_hash: ExpectedSourceHash = None,
    ) -> MutationResult:
        """Set or remove stage lanes, camera bounds, encounters, exits, and hazards."""
        return await adapter.edit_stage_gameplay_zones(
            source_path, output_path, operations=operations, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_preview_combat_overlay(
        source_path: SpriteSourcePath,
        action_tag: Annotated[str, Field(min_length=1, max_length=128)],
        frame: Annotated[int, Field(ge=0)],
        kinds: Annotated[list[Literal[
            "hurt", "hit", "push", "grab", "throw", "armor", "invulnerable"
        ]] | None, Field(max_length=7)] = None,
        scale: Annotated[int, Field(ge=1, le=16)] = 4,
    ) -> Image:
        """Return an inline PNG of one action frame with color-coded combat boxes and anchors."""
        selected = kinds or ["hurt", "hit", "push", "grab", "throw", "armor", "invulnerable"]
        return Image(data=await adapter.preview_combat_overlay(
            source_path, action_tag=action_tag, frame=frame, kinds=selected, scale=scale,
        ), format="png")

    @tools.tool()
    async def aseprite_preview_combat_animation(
        source_path: SpriteSourcePath,
        action_tag: Annotated[str, Field(min_length=1, max_length=128)],
        kinds: Annotated[list[Literal[
            "hurt", "hit", "push", "grab", "throw", "armor", "invulnerable"
        ]] | None, Field(max_length=7)] = None,
        scale: Annotated[int, Field(ge=1, le=16)] = 4,
    ) -> Image:
        """Return an inline animated GIF with combat boxes and anchors over an entire action tag."""
        selected = kinds or ["hurt", "hit", "push", "grab", "throw", "armor", "invulnerable"]
        return Image(data=await adapter.preview_combat_animation(
            source_path, action_tag=action_tag, kinds=selected, scale=scale,
        ), format="gif")

    @tools.tool()
    async def aseprite_validate_combat_action(
        source_path: SpriteSourcePath,
        action_tag: Annotated[str, Field(min_length=1, max_length=128)],
        require_hurtbox: bool = True,
        require_active_frames: bool = True,
        required_anchors: Annotated[list[str] | None, Field(max_length=32)] = None,
    ) -> CombatActionValidationResult:
        """Validate one action's phases, combat boxes, and required frame anchors."""
        return await adapter.validate_combat_action(
            source_path, action_tag=action_tag, require_hurtbox=require_hurtbox,
            require_active_frames=require_active_frames, required_anchors=required_anchors or [],
        )

    @tools.tool()
    async def aseprite_validate_combat_set(
        source_path: SpriteSourcePath,
        action_tags: Annotated[list[str] | None, Field(max_length=256)] = None,
        require_hurtbox: bool = True,
        require_active_frames: bool = False,
        required_anchors: Annotated[list[str] | None, Field(max_length=32)] = None,
        require_action_metadata: bool = True,
    ) -> CombatSetValidationResult:
        """Validate selected or authored actions together, including metadata and cancel targets."""
        return await adapter.validate_combat_set(
            source_path, action_tags=action_tags or [], require_hurtbox=require_hurtbox,
            require_active_frames=require_active_frames, required_anchors=required_anchors or [],
            require_action_metadata=require_action_metadata,
        )

    @tools.tool()
    async def aseprite_validate_stage_gameplay(
        source_path: SpriteSourcePath,
        require_spawn: bool = True,
        require_exit: bool = True,
        require_camera: bool = True,
    ) -> StageGameplayValidationResult:
        """Validate stage zones, required markers, encounter order, and walkable containment."""
        return await adapter.validate_stage_gameplay(
            source_path, require_spawn=require_spawn, require_exit=require_exit,
            require_camera=require_camera,
        )

    @tools.tool()
    async def aseprite_export_combat_manifest(
        source_path: SpriteSourcePath,
        output_path: OutputPath,
        action_tag: Annotated[str | None, Field(min_length=1, max_length=128)] = None,
        overwrite: Overwrite = False,
    ) -> CombatManifestResult:
        """Export versioned action timing, events, combat boxes, and anchors as JSON."""
        return await adapter.export_combat_manifest(
            source_path, output_path, action_tag=action_tag, overwrite=overwrite,
        )

    @tools.tool()
    async def aseprite_export_beat_em_up_bundle(
        source_path: SpriteSourcePath,
        output_path: OutputPath,
        layout: Literal["horizontal", "vertical", "rows", "columns", "packed"] = "packed",
        tag: Annotated[str | None, Field(min_length=1, max_length=128)] = None,
        layers: Annotated[list[str] | None, Field(max_length=128)] = None,
        trim: bool = False,
        extrude: bool = False,
        border_padding: Annotated[int, Field(ge=0, le=1024)] = 0,
        shape_padding: Annotated[int, Field(ge=0, le=1024)] = 0,
        inner_padding: Annotated[int, Field(ge=0, le=1024)] = 0,
        overwrite: Overwrite = False,
    ) -> BeatEmUpBundleResult:
        """Export one ZIP containing sheet.png, frames.json, and the versioned gameplay manifest."""
        return await adapter.export_beat_em_up_bundle(
            source_path, output_path, layout=layout, tag=tag, layers=layers or [],
            trim=trim, extrude=extrude, border_padding=border_padding,
            shape_padding=shape_padding, inner_padding=inner_padding,
            overwrite=overwrite,
        )

    @tools.tool()
    async def aseprite_validate_character_roster(
        source_paths: Annotated[list[SpriteSourcePath], Field(min_length=1, max_length=64)],
        required_actions: Annotated[list[str] | None, Field(max_length=64)] = None,
        required_anchors: Annotated[list[str] | None, Field(max_length=32)] = None,
        require_consistent_canvas: bool = True,
        require_consistent_color_mode: bool = True,
    ) -> CharacterRosterValidationResult:
        """Check roster action tags, anchors, canvas sizes, and color modes."""
        return await adapter.validate_character_roster(
            source_paths, required_actions=required_actions or [],
            required_anchors=required_anchors or [],
            require_consistent_canvas=require_consistent_canvas,
            require_consistent_color_mode=require_consistent_color_mode,
        )

    return tools.registered_count


__all__ = ["register_combat_tools"]
