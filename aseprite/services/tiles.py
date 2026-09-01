"""Typed, policy-enforcing adapter around the Aseprite CLI and Lua bridge."""

from __future__ import annotations
import tempfile
from pathlib import Path
from ..errors import AsepriteMCPError
from ..models import (
    MutationResult,
    TilemapCellInput,
    TileMetadataEditOperation,
    TileMetadataResult,
    TilesetEditOperation,
    TilesetExportResult,
    TilesetInspectionResult,
    TilesetValidationResult,
)
from ..paths import SPRITE_DOCUMENT_EXTENSIONS, publish_file, sha256_file, temporary_sibling
from .runtime import (
    AsepriteRuntime,
    MAX_ANIMATION_PIXEL_EDITS,
    MAX_CANVAS_PIXELS,
    MAX_VALIDATION_PIXEL_VISITS,
)


class TilesService(AsepriteRuntime):
    """Tiles Aseprite operations."""

    async def edit_tileset(
        self,
        source_path: str,
        output_path: str,
        *,
        operations: list[TilesetEditOperation],
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        if not operations or len(operations) > 256:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "operations must contain 1 to 256 items")
        total_pixels = sum(len(operation.pixels) for operation in operations)
        if total_pixels > MAX_ANIMATION_PIXEL_EDITS:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "tileset pixel edits exceed the limit")
        for operation in operations:
            if operation.action == "add":
                if None in (operation.name, operation.tile_width, operation.tile_height):
                    raise AsepriteMCPError(
                        "INVALID_INPUT", "add requires name, tile_width, and tile_height"
                    )
            elif operation.tileset is None:
                raise AsepriteMCPError("INVALID_INPUT", f"{operation.action} requires tileset")
            if operation.action == "rename" and operation.name is None:
                raise AsepriteMCPError("INVALID_INPUT", "rename requires name")
            needs_tile_index = operation.action in {"remove_tile", "set_tile_pixels"}
            if needs_tile_index and operation.tile_index is None:
                raise AsepriteMCPError("INVALID_INPUT", f"{operation.action} requires tile_index")
        return await self._bridge_mutation(
            "edit_tileset",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": [operation.model_dump() for operation in operations]},
        )

    async def inspect_tilesets(self, source_path: str) -> TilesetInspectionResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_DOCUMENT_EXTENSIONS)
        async with self._locked([source]):
            result = await self._bridge(
                "inspect_tilesets", {"source_path": self._process_path(source)}
            )
            result.update(source_path=str(source), sha256=sha256_file(source))
        return TilesetInspectionResult.model_validate(result)

    async def edit_tilemap(
        self, source_path: str, output_path: str, *, layer: str, tileset: str,
        frame: int, create_layer: bool, cells: list[TilemapCellInput], overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        if not cells or len(cells) > 100_000:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "cells must contain 1 to 100000 items")
        return await self._bridge_mutation(
            "edit_tilemap", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"layer": layer, "tileset": tileset, "frame": frame,
                     "create_layer": create_layer,
                     "cells": [cell.model_dump() for cell in cells]},
        )

    async def validate_tileset(
        self, source_path: str, *, tileset: str, check_edges: bool,
    ) -> TilesetValidationResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_DOCUMENT_EXTENSIONS)
        async with self._locked([source]):
            result = await self._bridge(
                "validate_tileset", {"source_path": self._process_path(source),
                                     "tileset": tileset, "check_edges": check_edges,
                                     "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS},
            )
            result.update(source_path=str(source), sha256=sha256_file(source))
        return TilesetValidationResult.model_validate(result)

    async def export_tileset(
        self, source_path: str, image_output_path: str, data_output_path: str, *,
        tileset: str, columns: int, overwrite: bool,
    ) -> TilesetExportResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_DOCUMENT_EXTENSIONS)
        image_output = self.paths.output_file(
            image_output_path, extensions=frozenset({".png"}), overwrite=overwrite
        )
        data_output = self.paths.output_file(
            data_output_path, extensions=frozenset({".json"}), overwrite=overwrite
        )
        image_temp, data_temp = temporary_sibling(image_output), temporary_sibling(data_output)
        async with self._locked([source, image_output, data_output]):
            try:
                await self._bridge("export_tileset", {"source_path": self._process_path(source),
                    "image_output_path": self._process_path(image_temp),
                    "data_output_path": self._process_path(data_temp),
                    "tileset": tileset, "columns": columns, "max_pixels": MAX_CANVAS_PIXELS})
                if not image_temp.is_file() or not data_temp.is_file():
                    raise AsepriteMCPError("ASEPRITE_FAILED", "tileset outputs were not created")
                publish_file(image_temp, image_output)
                publish_file(data_temp, data_output)
            finally:
                image_temp.unlink(missing_ok=True)
                data_temp.unlink(missing_ok=True)
        return TilesetExportResult(image=self._file_result(image_output),
                                   data=self._file_result(data_output), tileset=tileset)

    async def render_tilemap_preview(
        self, source_path: str, *, tileset: str, width_cells: int, height_cells: int,
        cells: list[TilemapCellInput],
    ) -> bytes:
        if len(cells) > 100_000:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "tilemap preview exceeds 100000 cells")
        source = self.paths.existing_file(source_path, extensions=SPRITE_DOCUMENT_EXTENSIONS)
        with tempfile.TemporaryDirectory(
            prefix="aseprite-tilemap-preview-", dir=self.bridge_temp_root
        ) as directory:
            output = Path(directory) / "preview.png"
            async with self._locked([source]):
                await self._bridge("render_tilemap_preview", {
                    "source_path": self._process_path(source), "tileset": tileset,
                    "width_cells": width_cells, "height_cells": height_cells,
                    "cells": [cell.model_dump() for cell in cells],
                    "output_path": self._process_path(output),
                    "max_pixels": MAX_CANVAS_PIXELS,
                })
            if not output.is_file():
                raise AsepriteMCPError("ASEPRITE_FAILED", "tilemap preview was not created")
            if output.stat().st_size > self.settings.max_capture_bytes:
                raise AsepriteMCPError("LIMIT_EXCEEDED", "tilemap preview exceeds inline limit")
            return output.read_bytes()

    async def create_tileset_from_sheet(
        self, source_path: str, output_path: str, *, layer: str, frame: int,
        name: str, tile_width: int, tile_height: int, margin: int, spacing: int,
        columns: int | None, tile_count: int | None, deduplicate: bool,
        overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        self._validate_canvas_dimensions(tile_width, tile_height)
        return await self._bridge_mutation(
            "create_tileset_from_sheet", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"layer": layer, "frame": frame, "name": name,
                     "tile_width": tile_width, "tile_height": tile_height,
                     "margin": margin, "spacing": spacing, "columns": columns,
                     "tile_count": tile_count, "deduplicate": deduplicate,
                     "max_tiles": 4096, "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS},
        )

    async def inspect_tile_metadata(
        self, source_path: str, *, tileset: str, tile_indices: list[int],
    ) -> TileMetadataResult:
        if len(tile_indices) > 4096 or len(set(tile_indices)) != len(tile_indices):
            raise AsepriteMCPError(
                "INVALID_INPUT", "tile_indices must contain at most 4096 unique values"
            )
        source = self.paths.existing_file(source_path, extensions=SPRITE_DOCUMENT_EXTENSIONS)
        async with self._locked([source]):
            result = await self._bridge("inspect_tile_metadata", {
                "source_path": self._process_path(source), "tileset": tileset,
                "tile_indices": tile_indices, "max_tiles": 4096,
            })
            result.update(source_path=str(source), sha256=sha256_file(source))
        return TileMetadataResult.model_validate(result)

    async def edit_tile_metadata(
        self, source_path: str, output_path: str, *, tileset: str,
        operations: list[TileMetadataEditOperation], overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        if not 1 <= len(operations) <= 512:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "operations must contain 1 to 512 items")
        for operation in operations:
            if operation.action == "set" and operation.value is None:
                raise AsepriteMCPError("INVALID_INPUT", "set requires a scalar value")
            if operation.target == "tile" and operation.tile_index is None:
                raise AsepriteMCPError("INVALID_INPUT", "tile metadata requires tile_index")
        return await self._bridge_mutation(
            "edit_tile_metadata", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"tileset": tileset,
                     "operations": [operation.model_dump() for operation in operations]},
        )
