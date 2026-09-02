"""MCP tools for modular character metadata and asset assembly."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver import Image
from pydantic import Field

from ..adapter import AsepriteAdapter
from ..capabilities import CapabilityRegistry, ToolRegistrar
from ..models import (
    ModularCharacterValidationResult,
    ModularManifestResult,
    ModularPartEditOperation,
    MutationResult,
)
from .inputs import ExpectedSourceHash, OutputPath, Overwrite, SpriteOutputPath, SpriteSourcePath

ModularIdentifier = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$"),
]
LayerPath = Annotated[str, Field(min_length=1, max_length=256)]


def register_modular_tools(
    server: MCPServer,
    adapter: AsepriteAdapter,
    registry: CapabilityRegistry,
    *,
    enabled_tools: frozenset[str],
) -> int:
    """Register modular-character tools and return the number registered."""

    tools = ToolRegistrar(server, registry, "modular", enabled_tools=enabled_tools)

    @tools.tool()
    async def aseprite_edit_modular_part_metadata(
        source_path: SpriteSourcePath,
        output_path: SpriteOutputPath,
        operations: Annotated[list[ModularPartEditOperation], Field(min_length=1, max_length=32)],
        overwrite: Overwrite = False,
        expected_source_hash: ExpectedSourceHash = None,
    ) -> MutationResult:
        """Set or remove structured slot, compatibility, draw-order, and anchor metadata."""

        return await adapter.edit_modular_part_metadata(
            source_path, output_path, operations=operations, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_preview_modular_variant(
        source_path: SpriteSourcePath,
        part_ids: Annotated[list[ModularIdentifier], Field(min_length=1, max_length=64)],
        include_layers: Annotated[list[LayerPath] | None, Field(max_length=32)] = None,
        mode: Literal["frame", "sheet"] = "frame",
        frame: Annotated[int, Field(ge=0)] = 0,
        layout: Literal["horizontal", "vertical", "rows", "columns", "packed"] = "horizontal",
        tag: Annotated[str | None, Field(min_length=1, max_length=128)] = None,
        scale: Annotated[float, Field(ge=0.1, le=16)] = 1.0,
        allow_multiple_per_slot: bool = False,
    ) -> Image:
        """Return an inline preview of a metadata-selected modular part combination."""

        data = await adapter.preview_modular_variant(
            source_path, part_ids=part_ids, include_layers=include_layers or [],
            mode=mode, frame=frame, layout=layout, tag=tag, scale=scale,
            allow_multiple_per_slot=allow_multiple_per_slot,
        )
        return Image(data=data, format="png")

    @tools.tool()
    async def aseprite_validate_modular_character(
        source_path: SpriteSourcePath,
        required_slots: Annotated[list[ModularIdentifier] | None, Field(max_length=32)] = None,
        required_tags: Annotated[
            list[Annotated[str, Field(min_length=1, max_length=128)]] | None,
            Field(max_length=64),
        ] = None,
        required_anchor_names: Annotated[
            list[ModularIdentifier] | None, Field(max_length=32)
        ] = None,
        require_complete_frame_coverage: bool = False,
        strict_references: bool = False,
    ) -> ModularCharacterValidationResult:
        """Validate modular slots, identifiers, references, anchors, tags, and frame coverage."""

        return await adapter.validate_modular_character(
            source_path, required_slots=required_slots or [], required_tags=required_tags or [],
            required_anchor_names=required_anchor_names or [],
            require_complete_frame_coverage=require_complete_frame_coverage,
            strict_references=strict_references,
        )

    @tools.tool()
    async def aseprite_export_modular_manifest(
        source_path: SpriteSourcePath,
        output_path: OutputPath,
        overwrite: Overwrite = False,
    ) -> ModularManifestResult:
        """Export deterministic modular parts, slots, anchors, and compatibility metadata as JSON."""

        return await adapter.export_modular_manifest(
            source_path, output_path, overwrite=overwrite
        )

    return tools.registered_count
