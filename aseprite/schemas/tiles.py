"""Tiles schemas for the Aseprite MCP server."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import FileResult, StrictModel

from .pixels import PixelInput


class TilesetEditOperation(StrictModel):
    action: Literal["add", "rename", "add_tile", "remove_tile", "set_tile_pixels"]
    tileset: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    name: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    tile_width: Annotated[int | None, Field(ge=1, le=4096)] = None
    tile_height: Annotated[int | None, Field(ge=1, le=4096)] = None
    tile_index: Annotated[int | None, Field(ge=1, le=4096)] = None
    pixels: Annotated[list[PixelInput], Field(max_length=10_000)] = Field(default_factory=list)

class TilesetDetail(StrictModel):
    name: str
    tile_width: int
    tile_height: int
    tile_count: int
    base_index: int

class TilesetInspectionResult(StrictModel):
    source_path: str
    sha256: str
    tilesets: list[TilesetDetail]
    tilemap_layers: list[str]

class TilesetValidationIssue(StrictModel):
    code: str
    severity: Literal["warning", "error"]
    message: str
    tile_indices: list[int] = Field(default_factory=list)

class TilesetValidationResult(StrictModel):
    source_path: str
    sha256: str
    tileset: str
    valid: bool
    issues: list[TilesetValidationIssue]
    empty_tiles: list[int]
    duplicate_groups: list[list[int]]

class TilemapCellInput(StrictModel):
    x: Annotated[int, Field(ge=0, le=4096)]
    y: Annotated[int, Field(ge=0, le=4096)]
    tile_index: Annotated[int, Field(ge=0, le=4096)]
    flip_x: bool = False
    flip_y: bool = False
    flip_diagonal: bool = False

class TilesetExportResult(StrictModel):
    image: FileResult
    data: FileResult
    tileset: str

class TileMetadataItem(StrictModel):
    index: int
    data: str
    color: str
    properties: dict[str, str | int | float | bool]

class TileMetadataResult(StrictModel):
    source_path: str
    sha256: str
    tileset: str
    base_index: int
    data: str
    properties: dict[str, str | int | float | bool]
    tiles: list[TileMetadataItem]

class TileMetadataEditOperation(StrictModel):
    action: Literal["set", "remove"]
    target: Literal["tileset", "tile"]
    key: Annotated[str, Field(min_length=1, max_length=128)]
    value: str | int | float | bool | None = None
    tile_index: Annotated[int | None, Field(ge=0, le=4096)] = None
