"""Export schemas for the Aseprite MCP server."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import (
    FileResult,
    PointInfo,
    RectangleInfo,
    RectangleInput,
    RenderResult,
    SpriteSheetResult,
    StrictModel,
)


class ContactSheetResult(FileResult):
    frame_count: int
    columns: int
    rows: int
    scale: int

class ExportProfile(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=128)] = "custom"
    canvas_width: Annotated[int | None, Field(ge=1, le=4096)] = None
    canvas_height: Annotated[int | None, Field(ge=1, le=4096)] = None
    max_width: Annotated[int | None, Field(ge=1, le=4096)] = None
    max_height: Annotated[int | None, Field(ge=1, le=4096)] = None
    require_power_of_two: bool = False
    color_mode: Literal["rgb", "grayscale", "indexed"] | None = None
    frame_count: Annotated[int | None, Field(ge=1, le=256)] = None
    required_layers: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=256)]], Field(max_length=128)
    ] = Field(default_factory=list)
    required_tags: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=128)]], Field(max_length=256)
    ] = Field(default_factory=list)
    required_slices: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=128)]], Field(max_length=256)
    ] = Field(default_factory=list)
    max_palette_colors: Annotated[int | None, Field(ge=1, le=256)] = None

class ExportProfileIssue(StrictModel):
    code: str
    severity: Literal["warning", "error"]
    message: str

class ExportProfileValidationResult(StrictModel):
    source_path: str
    sha256: str
    profile_name: str
    valid: bool
    issues: list[ExportProfileIssue]

class AtlasResult(StrictModel):
    image: FileResult
    data: FileResult
    source_count: int
    frame_count: int

class SliceExtractionInput(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=128)]
    frame: Annotated[int, Field(ge=0)] = 0
    output_path: str

class SliceExtractionItem(StrictModel):
    name: str
    frame: int
    file: FileResult
    bounds: RectangleInfo
    pivot: PointInfo | None = None

class SliceExtractionResult(StrictModel):
    source_path: str
    sha256: str
    items: list[SliceExtractionItem]

class BatchExportJob(StrictModel):
    source_path: str
    image_output_path: str
    data_output_path: str
    layout: Literal["horizontal", "vertical", "rows", "columns", "packed"] = "packed"
    tag: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    layers: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=256)]], Field(max_length=128)
    ] = Field(default_factory=list)
    trim: bool = False
    extrude: bool = False
    border_padding: Annotated[int, Field(ge=0, le=1024)] = 0
    shape_padding: Annotated[int, Field(ge=0, le=1024)] = 0
    inner_padding: Annotated[int, Field(ge=0, le=1024)] = 0
    overwrite: bool = False

class BatchExportItem(StrictModel):
    source_path: str
    ok: bool
    result: SpriteSheetResult | None = None
    error_code: str | None = None
    error_message: str | None = None

class BatchExportResult(StrictModel):
    succeeded: int
    failed: int
    items: list[BatchExportItem]

class AssetValidationItem(StrictModel):
    source_path: str
    result: ExportProfileValidationResult

class AssetSetValidationResult(StrictModel):
    valid: bool
    profile_name: str
    items: list[AssetValidationItem]
    issues: list[ExportProfileIssue]

class FrameExportInput(StrictModel):
    frame: Annotated[int, Field(ge=0)]
    output_path: str

class FrameExportItem(StrictModel):
    frame: int
    file: FileResult

class FrameExportResult(StrictModel):
    source_path: str
    sha256: str
    items: list[FrameExportItem]

class BitmapGlyphInput(StrictModel):
    codepoint: Annotated[int, Field(ge=0, le=1_114_111)]
    frame: Annotated[int, Field(ge=0)] = 0
    bounds: RectangleInput
    advance: Annotated[int | None, Field(ge=0, le=4096)] = None
    bearing_x: Annotated[int, Field(ge=-4096, le=4096)] = 0
    bearing_y: Annotated[int, Field(ge=-4096, le=4096)] = 0

class BitmapFontResult(StrictModel):
    image: FileResult
    data: FileResult
    glyph_count: int
    line_height: int


class LayerVariantInput(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=128)]
    output_path: str
    layers: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=256)]],
        Field(min_length=1, max_length=128),
    ]
    frame: Annotated[int | None, Field(ge=0)] = None
    tag: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    scale: Annotated[float, Field(ge=0.1, le=16)] = 1.0


class LayerVariantItem(StrictModel):
    name: str
    ok: bool
    result: RenderResult | None = None
    error_code: str | None = None
    error_message: str | None = None


class LayerVariantResult(StrictModel):
    source_path: str
    succeeded: int
    failed: int
    items: list[LayerVariantItem]
