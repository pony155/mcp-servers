"""MCP tool registration grouped by capability domain."""

from .core import register_core_tools
from .pixels import register_pixels_tools
from .documents import register_documents_tools
from .animation import register_animation_tools
from .palettes import register_palettes_tools
from .tiles import register_tiles_tools
from .export import register_export_tools
from .validation import register_validation_tools
from .combat import register_combat_tools

REGISTRARS = {
    "core": register_core_tools,
    "pixels": register_pixels_tools,
    "documents": register_documents_tools,
    "animation": register_animation_tools,
    "palettes": register_palettes_tools,
    "tiles": register_tiles_tools,
    "export": register_export_tools,
    "validation": register_validation_tools,
    "combat": register_combat_tools,
}

__all__ = ["REGISTRARS"]
