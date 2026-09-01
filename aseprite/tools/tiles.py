"""MCP server construction and tool registration."""

from __future__ import annotations
from typing import Annotated
from mcp.server import MCPServer
from mcp.server.mcpserver import Image
from pydantic import Field
from ..adapter import AsepriteAdapter
from ..capabilities import CapabilityRegistry, ToolRegistrar
from ..models import (
    MutationResult,
    TilemapCellInput,
    TilemapDataExportResult,
    TileMetadataEditOperation,
    TileMetadataResult,
    TilesetEditOperation,
    TilesetExportResult,
    TilesetInspectionResult,
    TilesetValidationResult,
)
from .inputs import (
    ExpectedSourceHash,
    OutputPath,
    Overwrite,
    SourcePath,
    SpriteOutputPath,
    SpriteSourcePath,
)


def register_tiles_tools(
    server: MCPServer, adapter: AsepriteAdapter, registry: CapabilityRegistry, *, enabled: bool
) -> int:
    """Register tiles tools and return the number registered."""

    tools = ToolRegistrar(server, registry, "tiles", enabled=enabled)

    @tools.tool()
    async def aseprite_edit_tileset(
        source_path: SpriteSourcePath,
        output_path: SpriteOutputPath,
        operations: Annotated[list[TilesetEditOperation], Field(min_length=1, max_length=256)],
        overwrite: Overwrite = False,
        expected_source_hash: ExpectedSourceHash = None,
    ) -> MutationResult:
        """Create or rename tilesets and add, remove, or repaint their tiles."""

        return await adapter.edit_tileset(
            source_path,
            output_path,
            operations=operations,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_inspect_tilesets(source_path: str) -> TilesetInspectionResult:
        """Inspect tileset dimensions/counts and tilemap layer paths."""
        return await adapter.inspect_tilesets(source_path)

    @tools.tool()
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

    @tools.tool()
    async def aseprite_validate_tileset(
        source_path: str, tileset: str, check_edges: bool = True,
    ) -> TilesetValidationResult:
        """Detect empty, duplicate, and non-seamless tiles."""
        return await adapter.validate_tileset(
            source_path, tileset=tileset, check_edges=check_edges
        )

    @tools.tool()
    async def aseprite_export_tileset(
        source_path: str, image_output_path: str, data_output_path: str, tileset: str,
        columns: Annotated[int, Field(ge=1, le=256)] = 16, overwrite: bool = False,
    ) -> TilesetExportResult:
        """Export one tileset to a PNG grid and JSON metadata."""
        return await adapter.export_tileset(source_path, image_output_path, data_output_path,
            tileset=tileset, columns=columns, overwrite=overwrite)

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
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

    @tools.tool()
    async def aseprite_export_tilemap_data(
        source_path: SpriteSourcePath,
        data_output_path: OutputPath,
        layers: Annotated[list[str] | None, Field(max_length=128)] = None,
        frames: Annotated[
            list[Annotated[int, Field(ge=0)]] | None,
            Field(max_length=256),
        ] = None,
        overwrite: Overwrite = False,
    ) -> TilemapDataExportResult:
        """Export selected tilemap layers and frames as deterministic versioned JSON."""

        return await adapter.export_tilemap_data(
            source_path,
            data_output_path,
            layers=layers or [],
            frames=frames or [],
            overwrite=overwrite,
        )

    @tools.tool()
    async def aseprite_import_tilemap_data(
        source_path: SpriteSourcePath,
        data_path: SourcePath,
        output_path: SpriteOutputPath,
        create_missing_layers: bool = False,
        clear_existing: bool = True,
        overwrite: Overwrite = False,
        expected_source_hash: ExpectedSourceHash = None,
    ) -> MutationResult:
        """Apply validated versioned tilemap JSON to existing or new top-level tilemap layers."""

        return await adapter.import_tilemap_data(
            source_path,
            data_path,
            output_path,
            create_missing_layers=create_missing_layers,
            clear_existing=clear_existing,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    return tools.registered_count
