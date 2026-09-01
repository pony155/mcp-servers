"""Declarative metadata and registration helpers for Aseprite MCP tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Literal, TypeVar


ToolMutability = Literal["read", "write"]
ToolOutput = Literal["structured", "inline-image", "file"]

READ_TOOL_NAMES = frozenset(
    {
        "aseprite_analyze_palette",
        "aseprite_compare_sprites",
        "aseprite_generate_collision_masks",
        "aseprite_generate_collision_polygons",
        "aseprite_generate_motion_report",
        "aseprite_health",
        "aseprite_inspect_cels",
        "aseprite_inspect_properties",
        "aseprite_inspect_sprite",
        "aseprite_inspect_tile_metadata",
        "aseprite_inspect_tilesets",
        "aseprite_list_capabilities",
        "aseprite_preview",
        "aseprite_preview_animation",
        "aseprite_preview_nine_slice",
        "aseprite_preview_onion_skin",
        "aseprite_read_composited_pixels",
        "aseprite_read_pixels",
        "aseprite_render_tilemap_preview",
        "aseprite_validate_animation",
        "aseprite_validate_asset_set",
        "aseprite_validate_export_profile",
        "aseprite_validate_loop_transition",
        "aseprite_validate_pixel_art",
        "aseprite_validate_tileset",
        "aseprite_preview_combat_overlay",
        "aseprite_validate_combat_action",
        "aseprite_validate_character_roster",
        "aseprite_preview_combat_animation",
        "aseprite_validate_combat_set",
        "aseprite_validate_stage_gameplay",
    }
)

WRITE_TOOL_NAMES = frozenset(
    {
        "aseprite_apply_outline",
        "aseprite_apply_palette",
        "aseprite_bake_tag_direction",
        "aseprite_batch_export",
        "aseprite_compare_frames",
        "aseprite_convert_color_mode",
        "aseprite_copy_cel",
        "aseprite_copy_layer_tree",
        "aseprite_create_animation",
        "aseprite_create_sprite",
        "aseprite_create_tileset_from_sheet",
        "aseprite_crop_sprite",
        "aseprite_draw_shapes",
        "aseprite_draw_strokes",
        "aseprite_edit_animation_events",
        "aseprite_edit_blend_modes",
        "aseprite_edit_cels",
        "aseprite_edit_color_space",
        "aseprite_edit_frames",
        "aseprite_edit_grid",
        "aseprite_edit_layers",
        "aseprite_edit_palette_entries",
        "aseprite_edit_properties",
        "aseprite_edit_selection",
        "aseprite_edit_slices",
        "aseprite_edit_tags",
        "aseprite_edit_tile_metadata",
        "aseprite_edit_tilemap",
        "aseprite_edit_tileset",
        "aseprite_export_bitmap_font",
        "aseprite_export_frames",
        "aseprite_export_tilemap_data",
        "aseprite_export_palette",
        "aseprite_export_sprite_sheet",
        "aseprite_export_tileset",
        "aseprite_extract_slices",
        "aseprite_fill_region",
        "aseprite_generate_inbetweens",
        "aseprite_import_frames",
        "aseprite_import_tilemap_data",
        "aseprite_import_palette",
        "aseprite_import_sprite_sheet",
        "aseprite_merge_layers",
        "aseprite_pack_atlas",
        "aseprite_optimize_linked_cels",
        "aseprite_palette_cycle",
        "aseprite_quantize_palette",
        "aseprite_render",
        "aseprite_render_contact_sheet",
        "aseprite_render_layer_variants",
        "aseprite_replace_color",
        "aseprite_resize_canvas",
        "aseprite_resize_sprite",
        "aseprite_retime_animation",
        "aseprite_select_by_color",
        "aseprite_set_pixel_runs",
        "aseprite_set_pixels",
        "aseprite_transform_cel",
        "aseprite_transform_selection",
        "aseprite_trim_cels",
        "aseprite_edit_combat_boxes",
        "aseprite_edit_frame_anchors",
        "aseprite_export_combat_manifest",
        "aseprite_edit_action_metadata",
        "aseprite_edit_cancel_windows",
        "aseprite_edit_root_motion",
        "aseprite_edit_stage_gameplay_zones",
        "aseprite_export_beat_em_up_bundle",
    }
)

INLINE_IMAGE_TOOL_NAMES = frozenset(
    {
        "aseprite_preview",
        "aseprite_preview_animation",
        "aseprite_preview_nine_slice",
        "aseprite_preview_onion_skin",
        "aseprite_render_tilemap_preview",
        "aseprite_preview_combat_overlay",
        "aseprite_preview_combat_animation",
    }
)

NO_ASEPRITE_TOOL_NAMES = frozenset(
    {"aseprite_health", "aseprite_list_capabilities"}
)

CORE_TOOL_NAMES = frozenset(
    {"aseprite_health", "aseprite_inspect_sprite", "aseprite_list_capabilities"}
)

PROFILE_TOOL_NAMES = {
    "core": CORE_TOOL_NAMES,
    "sprite-authoring": CORE_TOOL_NAMES | frozenset({
        "aseprite_analyze_palette", "aseprite_apply_outline", "aseprite_apply_palette",
        "aseprite_convert_color_mode", "aseprite_create_sprite", "aseprite_crop_sprite",
        "aseprite_draw_shapes", "aseprite_draw_strokes", "aseprite_edit_cels",
        "aseprite_edit_layers", "aseprite_edit_properties", "aseprite_edit_selection",
        "aseprite_edit_slices", "aseprite_export_sprite_sheet", "aseprite_fill_region",
        "aseprite_import_sprite_sheet", "aseprite_inspect_properties", "aseprite_preview",
        "aseprite_read_composited_pixels", "aseprite_read_pixels", "aseprite_replace_color",
        "aseprite_resize_canvas", "aseprite_resize_sprite", "aseprite_set_pixel_runs",
        "aseprite_set_pixels", "aseprite_transform_cel", "aseprite_transform_selection",
    }),
    "animation-authoring": CORE_TOOL_NAMES | frozenset({
        "aseprite_analyze_palette", "aseprite_apply_palette", "aseprite_copy_cel",
        "aseprite_create_animation", "aseprite_edit_animation_events", "aseprite_edit_cels",
        "aseprite_edit_frames", "aseprite_edit_layers", "aseprite_edit_tags",
        "aseprite_export_frames", "aseprite_export_sprite_sheet",
        "aseprite_generate_inbetweens", "aseprite_generate_motion_report",
        "aseprite_import_sprite_sheet", "aseprite_inspect_cels",
        "aseprite_preview_animation", "aseprite_preview_onion_skin", "aseprite_read_pixels",
        "aseprite_render_contact_sheet", "aseprite_resize_canvas", "aseprite_resize_sprite",
        "aseprite_retime_animation", "aseprite_set_pixel_runs", "aseprite_transform_cel",
        "aseprite_validate_animation", "aseprite_validate_loop_transition",
    }),
    "combat-authoring": CORE_TOOL_NAMES | frozenset({
        "aseprite_copy_cel", "aseprite_create_animation", "aseprite_edit_action_metadata",
        "aseprite_edit_animation_events", "aseprite_edit_cancel_windows", "aseprite_edit_cels",
        "aseprite_edit_combat_boxes", "aseprite_edit_frame_anchors", "aseprite_edit_frames",
        "aseprite_edit_layers", "aseprite_edit_root_motion", "aseprite_edit_tags",
        "aseprite_export_beat_em_up_bundle", "aseprite_export_combat_manifest",
        "aseprite_generate_motion_report", "aseprite_import_sprite_sheet",
        "aseprite_inspect_cels", "aseprite_preview_animation",
        "aseprite_preview_combat_animation", "aseprite_preview_combat_overlay",
        "aseprite_read_pixels", "aseprite_set_pixel_runs", "aseprite_transform_cel",
        "aseprite_validate_animation", "aseprite_validate_character_roster",
        "aseprite_validate_combat_action", "aseprite_validate_combat_set",
    }),
    "stage-authoring": CORE_TOOL_NAMES | frozenset({
        "aseprite_create_sprite", "aseprite_create_tileset_from_sheet", "aseprite_draw_shapes",
        "aseprite_draw_strokes", "aseprite_edit_grid", "aseprite_edit_layers",
        "aseprite_edit_properties", "aseprite_edit_stage_gameplay_zones",
        "aseprite_edit_tile_metadata", "aseprite_edit_tilemap", "aseprite_edit_tileset",
        "aseprite_export_sprite_sheet", "aseprite_export_tilemap_data",
        "aseprite_export_tileset", "aseprite_fill_region", "aseprite_import_tilemap_data",
        "aseprite_inspect_tile_metadata", "aseprite_inspect_tilesets", "aseprite_preview",
        "aseprite_read_pixels", "aseprite_render_layer_variants",
        "aseprite_render_tilemap_preview", "aseprite_transform_selection",
        "aseprite_validate_stage_gameplay", "aseprite_validate_tileset",
    }),
    "export-qa": CORE_TOOL_NAMES | frozenset({
        "aseprite_batch_export", "aseprite_compare_frames", "aseprite_compare_sprites",
        "aseprite_export_bitmap_font", "aseprite_export_frames", "aseprite_export_sprite_sheet",
        "aseprite_extract_slices", "aseprite_generate_collision_masks",
        "aseprite_generate_collision_polygons", "aseprite_generate_motion_report",
        "aseprite_inspect_cels", "aseprite_pack_atlas", "aseprite_preview",
        "aseprite_render", "aseprite_render_contact_sheet", "aseprite_render_layer_variants",
        "aseprite_validate_animation", "aseprite_validate_asset_set",
        "aseprite_validate_export_profile", "aseprite_validate_loop_transition",
        "aseprite_validate_pixel_art", "aseprite_validate_tileset",
    }),
}
PROFILE_TOOL_NAMES["full"] = READ_TOOL_NAMES | WRITE_TOOL_NAMES

PROFILE_ALIASES = {
    "sprite": "sprite-authoring",
    "animation": "animation-authoring",
    "tiles": "stage-authoring",
    "export": "export-qa",
    "qa": "export-qa",
    "combat": "combat-authoring",
}
TOOL_PROFILES = tuple(PROFILE_TOOL_NAMES) + tuple(PROFILE_ALIASES)


def canonical_profile(profile: str) -> str:
    """Resolve a backward-compatible profile alias."""

    return PROFILE_ALIASES.get(profile, profile)


def tools_for_profiles(profiles: tuple[str, ...]) -> frozenset[str]:
    """Return the union of explicitly curated tools for selected profiles."""

    selected = set(CORE_TOOL_NAMES)
    for profile in profiles:
        selected.update(PROFILE_TOOL_NAMES[canonical_profile(profile)])
    return frozenset(selected)


@dataclass(frozen=True, slots=True)
class ToolMetadata:
    """Client-facing metadata for one narrow MCP tool."""

    name: str
    category: str
    profiles: tuple[str, ...]
    mutability: ToolMutability
    output: ToolOutput
    requires_aseprite: bool
    description: str
    enabled: bool


def tool_policy(name: str) -> tuple[ToolMutability, ToolOutput, bool]:
    """Return explicit policy metadata, rejecting unclassified tools."""

    if name in READ_TOOL_NAMES:
        mutability: ToolMutability = "read"
    elif name in WRITE_TOOL_NAMES:
        mutability = "write"
    else:
        raise ValueError(f"tool is missing an explicit read/write policy: {name}")
    if name in INLINE_IMAGE_TOOL_NAMES:
        output: ToolOutput = "inline-image"
    elif mutability == "write":
        output = "file"
    else:
        output = "structured"
    return mutability, output, name not in NO_ASEPRITE_TOOL_NAMES


def profiles_for_tool(name: str) -> tuple[str, ...]:
    """Return canonical profiles that expose a tool in stable display order."""

    return tuple(profile for profile, tools in PROFILE_TOOL_NAMES.items() if name in tools)


class CapabilityRegistry:
    """Collect metadata for all tools while registering only enabled categories."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolMetadata] = {}

    def add(self, metadata: ToolMetadata) -> None:
        if metadata.name in self._tools:
            raise ValueError(f"duplicate Aseprite MCP tool: {metadata.name}")
        self._tools[metadata.name] = metadata

    def describe(self, active_profiles: tuple[str, ...]) -> dict[str, Any]:
        tools = sorted(self._tools.values(), key=lambda item: item.name)
        profiles = [
            {
                "name": profile,
                "categories": sorted({
                    tool.category for tool in tools if tool.name in profile_tools
                }),
                "tool_count": len(profile_tools),
            }
            for profile, profile_tools in PROFILE_TOOL_NAMES.items()
        ]
        return {
            "active_profiles": list(active_profiles),
            "active_categories": sorted(
                {tool.category for tool in tools if tool.enabled}
            ),
            "available_tool_count": len(tools),
            "enabled_tool_count": sum(tool.enabled for tool in tools),
            "profiles": profiles,
            "tools": [asdict(tool) for tool in tools],
        }


Function = TypeVar("Function", bound=Callable[..., Any])


class ToolRegistrar:
    """Register functions and collect their declarative capability metadata."""

    def __init__(
        self,
        server: Any,
        registry: CapabilityRegistry,
        category: str,
        *,
        enabled_tools: frozenset[str],
    ) -> None:
        self.server = server
        self.registry = registry
        self.category = category
        self.enabled_tools = enabled_tools
        self.registered_count = 0

    def tool(self) -> Callable[[Function], Function]:
        def decorate(function: Function) -> Function:
            mutability, output, requires_aseprite = tool_policy(function.__name__)
            description = (function.__doc__ or "").strip()
            enabled = function.__name__ in self.enabled_tools
            self.registry.add(
                ToolMetadata(
                    name=function.__name__,
                    category=self.category,
                    profiles=profiles_for_tool(function.__name__),
                    mutability=mutability,
                    output=output,
                    requires_aseprite=requires_aseprite,
                    description=description,
                    enabled=enabled,
                )
            )
            if enabled:
                self.server.tool()(function)
                self.registered_count += 1
            return function

        return decorate
