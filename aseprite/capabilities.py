"""Declarative metadata and registration helpers for Aseprite MCP tools."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Literal, TypeVar


ToolMutability = Literal["read", "write"]
ToolOutput = Literal["structured", "inline-image", "file"]

PROFILE_CATEGORIES = {
    "core": frozenset({"core"}),
    "sprite": frozenset({"core", "documents", "pixels", "palettes", "export"}),
    "animation": frozenset(
        {"core", "documents", "pixels", "palettes", "animation", "export", "validation"}
    ),
    "tiles": frozenset(
        {"core", "documents", "pixels", "palettes", "tiles", "export", "validation"}
    ),
    "export": frozenset({"core", "export"}),
    "qa": frozenset({"core", "validation"}),
    "full": frozenset(
        {"core", "documents", "pixels", "palettes", "animation", "tiles", "export", "validation"}
    ),
}
TOOL_PROFILES = tuple(PROFILE_CATEGORIES)

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
    }
)

INLINE_IMAGE_TOOL_NAMES = frozenset(
    {
        "aseprite_preview",
        "aseprite_preview_animation",
        "aseprite_preview_nine_slice",
        "aseprite_preview_onion_skin",
        "aseprite_render_tilemap_preview",
    }
)

NO_ASEPRITE_TOOL_NAMES = frozenset(
    {"aseprite_health", "aseprite_list_capabilities"}
)


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


def profiles_for_category(category: str) -> tuple[str, ...]:
    """Return profiles that expose a category in stable display order."""

    return tuple(
        profile for profile, categories in PROFILE_CATEGORIES.items() if category in categories
    )


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
                "categories": sorted(categories),
                "tool_count": sum(
                    1 for tool in tools if tool.category in categories
                ),
            }
            for profile, categories in PROFILE_CATEGORIES.items()
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
        enabled: bool,
    ) -> None:
        self.server = server
        self.registry = registry
        self.category = category
        self.enabled = enabled
        self.registered_count = 0

    def tool(self) -> Callable[[Function], Function]:
        def decorate(function: Function) -> Function:
            mutability, output, requires_aseprite = tool_policy(function.__name__)
            description = (function.__doc__ or "").strip()
            self.registry.add(
                ToolMetadata(
                    name=function.__name__,
                    category=self.category,
                    profiles=profiles_for_category(self.category),
                    mutability=mutability,
                    output=output,
                    requires_aseprite=requires_aseprite,
                    description=description,
                    enabled=self.enabled,
                )
            )
            if self.enabled:
                self.server.tool()(function)
                self.registered_count += 1
            return function

        return decorate
