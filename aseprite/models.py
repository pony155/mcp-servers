"""Validated tool inputs and structured results."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
        normalized = value.upper()
        if len(normalized) not in (7, 9) or not normalized.startswith("#"):
            raise ValueError("color must be #RRGGBB or #RRGGBBAA")
        try:
            int(normalized[1:], 16)
        except ValueError as exc:
            raise ValueError("color must contain hexadecimal digits") from exc
        return normalized


class LayerDefinition(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=128)]


class FrameDefinition(StrictModel):
    duration_ms: Annotated[int, Field(ge=1, le=60_000)] = 100
