"""Animation schemas for the Aseprite MCP server."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import (
    FileResult,
    FloatPointInfo,
    PointInfo,
    PointInput,
    RectangleInfo,
    RectangleInput,
    StrictModel,
)

from .pixels import PixelInput


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

class SliceEditOperation(StrictModel):
    action: Literal["set", "remove"]
    name: Annotated[str, Field(min_length=1, max_length=128)]
    frame: Annotated[int, Field(ge=0)] = 0
    bounds: RectangleInput | None = None
    center: RectangleInput | None = None
    pivot: PointInput | None = None

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

class AnimationEventEditOperation(StrictModel):
    action: Literal["set", "remove"]
    name: Annotated[str, Field(min_length=1, max_length=128)]
    frame: Annotated[int, Field(ge=0)]
    layer: Annotated[str | None, Field(min_length=1, max_length=256)] = None
    data: Annotated[str | None, Field(max_length=4096)] = None

class CelEditOperation(StrictModel):
    action: Literal["set_position", "set_opacity", "set_z_index", "unlink", "remove"]
    layer: Annotated[str, Field(min_length=1, max_length=256)]
    frame: Annotated[int, Field(ge=0)]
    x: Annotated[int | None, Field(ge=-8192, le=8192)] = None
    y: Annotated[int | None, Field(ge=-8192, le=8192)] = None
    opacity: Annotated[int | None, Field(ge=0, le=255)] = None
    z_index: Annotated[int | None, Field(ge=-32768, le=32767)] = None

class MotionFrameMetric(StrictModel):
    frame: int
    duration_ms: int
    bounds: RectangleInfo | None
    opaque_pixels: int
    centroid: FloatPointInfo | None
    velocity_x: float | None
    velocity_y: float | None
    acceleration_x: float | None
    acceleration_y: float | None

class MotionReportResult(StrictModel):
    source_path: str
    sha256: str
    tag: str | None
    layer: str | None
    frames: list[MotionFrameMetric]
    total_distance: float
    maximum_speed: float

class FrameEditOperation(StrictModel):
    action: Literal["add", "duplicate", "remove", "set_duration"]
    frame: Annotated[int, Field(ge=0)]
    duration_ms: Annotated[int | None, Field(ge=1, le=60_000)] = None

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
