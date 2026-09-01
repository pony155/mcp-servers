"""Validated tool inputs and structured results."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_hex_color(value: str) -> str:
    normalized = value.upper()
    if len(normalized) not in (7, 9) or not normalized.startswith("#"):
        raise ValueError("color must be #RRGGBB or #RRGGBBAA")
    try:
        int(normalized[1:], 16)
    except ValueError as exc:
        raise ValueError("color must contain hexadecimal digits") from exc
    return normalized


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class HealthResult(StrictModel):
    ok: bool
    server_version: str
    executable_path: str | None
    aseprite_version: str | None
    api_version: int | None
    allowed_roots: list[str]
    timeout_seconds: float
    max_concurrency: int
    execution_mode: Literal["native", "wsl-windows"]
    bridge_temp_root: str | None
    error: str | None = None


class PixelRatio(StrictModel):
    width: int
    height: int


class FrameInfo(StrictModel):
    index: int
    duration_ms: int


class LayerInfo(StrictModel):
    name: str
    path: str
    type: Literal["image", "group", "tilemap", "background"]
    visible: bool
    editable: bool
    opacity: int
    blend_mode: str
    cel_count: int
    children: list[LayerInfo] = Field(default_factory=list)


class TagInfo(StrictModel):
    name: str
    from_frame: int
    to_frame: int
    direction: str
    repeats: int


class RectangleInfo(StrictModel):
    x: int
    y: int
    width: int
    height: int


class PointInfo(StrictModel):
    x: int
    y: int


class SliceKeyInfo(StrictModel):
    frame: int
    bounds: RectangleInfo
    center: RectangleInfo | None = None
    pivot: PointInfo | None = None


class SliceInfo(StrictModel):
    name: str
    keys: list[SliceKeyInfo]


class ColorInfo(StrictModel):
    red: int
    green: int
    blue: int
    alpha: int
    hex: str


class PaletteInfo(StrictModel):
    frame: int
    size: int
    colors: list[ColorInfo] | None = None


class SpriteInfo(StrictModel):
    source_path: str
    sha256: str
    width: int
    height: int
    color_mode: str
    transparent_color: int
    pixel_ratio: PixelRatio
    frame_count: int
    frames: list[FrameInfo]
    layers: list[LayerInfo]
    tags: list[TagInfo]
    slices: list[SliceInfo]
    palettes: list[PaletteInfo]


class FileResult(StrictModel):
    output_path: str
    byte_size: int
    sha256: str


class RenderResult(FileResult):
    format: Literal["png", "gif"]
    frame: int | None = None
    tag: str | None = None
    scale: float


class SpriteSheetResult(StrictModel):
    image: FileResult
    data: FileResult
    layout: Literal["horizontal", "vertical", "rows", "columns", "packed"]
    frame_count: int


class MutationResult(FileResult):
    source_sha256: str | None
    sprite: SpriteInfo


class AnimationFrameBounds(StrictModel):
    frame: int
    bounds: RectangleInfo | None
    opaque_pixels: int
    baseline: int | None


class AnimationValidationIssue(StrictModel):
    code: str
    severity: Literal["warning", "error"]
    message: str
    frames: list[int] = Field(default_factory=list)


class AnimationValidationResult(StrictModel):
    source_path: str
    sha256: str
    valid: bool
    width: int
    height: int
    frame_count: int
    durations_ms: list[int]
    frame_bounds: list[AnimationFrameBounds]
    empty_frames: list[int]
    duplicate_groups: list[list[int]]
    baseline_drift: int
    bounds_width_drift: int
    bounds_height_drift: int
    issues: list[AnimationValidationIssue]


class PixelInput(StrictModel):
    x: Annotated[int, Field(ge=0)]
    y: Annotated[int, Field(ge=0)]
    color: str

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        return _validate_hex_color(value)


class PaletteColorInput(StrictModel):
    color: str

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        return _validate_hex_color(value)


class PixelRun(StrictModel):
    x: int
    y: int
    length: Annotated[int, Field(ge=1)]
    color: str


class PixelRunInput(StrictModel):
    x: Annotated[int, Field(ge=0)]
    y: Annotated[int, Field(ge=0)]
    length: Annotated[int, Field(ge=1, le=4096)]
    color: str

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        return _validate_hex_color(value)


class PixelReadResult(StrictModel):
    source_path: str
    sha256: str
    layer: str
    frame: int
    bounds: RectangleInfo
    encoding: Literal["rgba_runs"] = "rgba_runs"
    runs: list[PixelRun]
    pixel_count: int


class CompositedPixelReadResult(StrictModel):
    source_path: str
    sha256: str
    frame: int
    bounds: RectangleInfo
    encoding: Literal["rgba_runs"] = "rgba_runs"
    runs: list[PixelRun]
    pixel_count: int


class FrameComparisonResult(StrictModel):
    source_path: str
    sha256: str
    first_frame: int
    second_frame: int
    changed_pixel_count: int
    changed_bounds: RectangleInfo | None
    first_baseline: int | None
    second_baseline: int | None
    baseline_delta: int | None
    difference: FileResult | None = None


class ContactSheetResult(FileResult):
    frame_count: int
    columns: int
    rows: int
    scale: int


class RectangleInput(StrictModel):
    x: int
    y: int
    width: Annotated[int, Field(ge=1, le=4096)]
    height: Annotated[int, Field(ge=1, le=4096)]


class PointInput(StrictModel):
    x: int
    y: int


class SliceEditOperation(StrictModel):
    action: Literal["set", "remove"]
    name: Annotated[str, Field(min_length=1, max_length=128)]
    frame: Annotated[int, Field(ge=0)] = 0
    bounds: RectangleInput | None = None
    center: RectangleInput | None = None
    pivot: PointInput | None = None


class PropertyEditOperation(StrictModel):
    action: Literal["set", "remove"]
    target: Literal["sprite", "layer", "tag", "slice", "cel"]
    key: Annotated[str, Field(min_length=1, max_length=128)]
    value: str | int | float | bool | None = None
    layer: Annotated[str | None, Field(min_length=1, max_length=256)] = None
    name: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    frame: Annotated[int | None, Field(ge=0)] = None


class TilesetEditOperation(StrictModel):
    action: Literal["add", "rename", "add_tile", "remove_tile", "set_tile_pixels"]
    tileset: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    name: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    tile_width: Annotated[int | None, Field(ge=1, le=4096)] = None
    tile_height: Annotated[int | None, Field(ge=1, le=4096)] = None
    tile_index: Annotated[int | None, Field(ge=1, le=4096)] = None
    pixels: Annotated[list[PixelInput], Field(max_length=10_000)] = Field(default_factory=list)


class CelDetail(StrictModel):
    layer: str
    frame: int
    position: PointInfo
    bounds: RectangleInfo
    opacity: int
    z_index: int
    image_id: int
    linked_group: int


class CelInspectionResult(StrictModel):
    source_path: str
    sha256: str
    cels: list[CelDetail]


class ColorUsage(StrictModel):
    color: str
    pixels: int
    frames: int


class PaletteAnalysisResult(StrictModel):
    source_path: str
    sha256: str
    unique_colors: int
    transparent_pixels: int
    usages: list[ColorUsage]
    unused_palette_colors: list[str]
    near_duplicate_groups: list[list[str]]


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


class ShapeInput(StrictModel):
    shape: Literal["line", "rectangle", "filled_rectangle", "ellipse", "filled_ellipse"]
    x1: int
    y1: int
    x2: int
    y2: int
    color: str

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        return _validate_hex_color(value)


class SelectionEditOperation(StrictModel):
    action: Literal["replace", "add", "subtract", "intersect", "clear", "all"]
    bounds: RectangleInput | None = None


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


class FrameEditOperation(StrictModel):
    action: Literal["add", "duplicate", "remove", "set_duration"]
    frame: Annotated[int, Field(ge=0)]
    duration_ms: Annotated[int | None, Field(ge=1, le=60_000)] = None


class LayerEditOperation(StrictModel):
    action: Literal[
        "add", "add_group", "remove", "rename", "set_visibility", "set_opacity", "move"
    ]
    layer: Annotated[str | None, Field(min_length=1, max_length=256)] = None
    name: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    parent: Annotated[str | None, Field(min_length=1, max_length=256)] = None
    visible: bool | None = None
    opacity: Annotated[int | None, Field(ge=0, le=255)] = None
    stack_index: Annotated[int | None, Field(ge=1, le=128)] = None


class TagEditOperation(StrictModel):
    action: Literal["set", "remove"]
    name: Annotated[str, Field(min_length=1, max_length=128)]
    from_frame: Annotated[int | None, Field(ge=0)] = None
    to_frame: Annotated[int | None, Field(ge=0)] = None
    direction: Literal["forward", "reverse", "ping_pong", "ping_pong_reverse"] | None = None
    repeats: Annotated[int | None, Field(ge=0, le=65_535)] = None


class AnimationCelDefinition(StrictModel):
    layer: Annotated[str, Field(min_length=1, max_length=128)]
    pixels: Annotated[list[PixelInput], Field(min_length=1, max_length=10_000)]


class AnimationFrameDefinition(StrictModel):
    duration_ms: Annotated[int, Field(ge=1, le=60_000)] = 100
    cels: Annotated[list[AnimationCelDefinition], Field(max_length=128)] = Field(
        default_factory=list
    )


class AnimationTagDefinition(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=128)]
    from_frame: Annotated[int, Field(ge=0)]
    to_frame: Annotated[int, Field(ge=0)]
    direction: Literal["forward", "reverse", "ping_pong", "ping_pong_reverse"] = "forward"
    repeats: Annotated[int, Field(ge=0, le=65_535)] = 0


class LayerDefinition(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=128)]


class FrameDefinition(StrictModel):
    duration_ms: Annotated[int, Field(ge=1, le=60_000)] = 100
