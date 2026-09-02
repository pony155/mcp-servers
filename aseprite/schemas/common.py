"""Shared Aseprite MCP schemas."""

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

class ToolCapability(StrictModel):
    name: str
    category: str
    profiles: list[str]
    mutability: Literal["read", "write"]
    output: Literal["structured", "inline-image", "file"]
    requires_aseprite: bool
    description: str
    enabled: bool

class ToolProfileCapability(StrictModel):
    name: str
    categories: list[str]
    tool_count: int

class CapabilitiesResult(StrictModel):
    active_profiles: list[str]
    active_categories: list[str]
    available_tool_count: int
    enabled_tool_count: int
    profiles: list[ToolProfileCapability]
    tools: list[ToolCapability]

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

class FloatPointInfo(StrictModel):
    x: float
    y: float

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

class AnimationEventInfo(StrictModel):
    name: str
    frame: int
    layer: str | None = None
    data: str | None = None

class SpriteInfo(StrictModel):
    source_path: str
    sha256: str
    width: int
    height: int
    color_mode: str
    color_space: str
    transparent_color: int
    pixel_ratio: PixelRatio
    grid: RectangleInfo
    frame_count: int
    frames: list[FrameInfo]
    layers: list[LayerInfo]
    tags: list[TagInfo]
    slices: list[SliceInfo]
    palettes: list[PaletteInfo]
    animation_events: list[AnimationEventInfo] = Field(default_factory=list)

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

class RectangleInput(StrictModel):
    x: int
    y: int
    width: Annotated[int, Field(ge=1, le=4096)]
    height: Annotated[int, Field(ge=1, le=4096)]

class PointInput(StrictModel):
    x: int
    y: int
