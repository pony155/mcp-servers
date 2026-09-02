"""Validation schemas for the Aseprite MCP server."""

from __future__ import annotations

from typing import Literal

from .animation import AnimationValidationIssue

from .common import PointInfo, RectangleInfo, StrictModel


class SpriteFrameDifference(StrictModel):
    frame: int
    changed_pixel_count: int
    changed_bounds: RectangleInfo | None

class SpriteComparisonResult(StrictModel):
    first_source_path: str
    first_sha256: str
    second_source_path: str
    second_sha256: str
    identical: bool
    same_dimensions: bool
    same_frame_count: bool
    same_color_mode: bool
    same_palette: bool
    same_layer_structure: bool
    same_tags: bool
    same_slices: bool
    changed_pixel_count: int
    changed_frames: list[SpriteFrameDifference]

class CollisionRectangle(StrictModel):
    x: int
    y: int
    width: int
    height: int

class CollisionFrame(StrictModel):
    frame: int
    rectangles: list[CollisionRectangle]

class CollisionMaskResult(StrictModel):
    source_path: str
    sha256: str
    mode: Literal["bounds", "components"]
    frames: list[CollisionFrame]

class PixelArtValidationIssue(StrictModel):
    code: str
    severity: Literal["warning", "error"]
    message: str
    frame: int | None = None
    x: int | None = None
    y: int | None = None

class PixelArtValidationResult(StrictModel):
    source_path: str
    sha256: str
    valid: bool
    frames: list[int]
    unique_colors: int
    semi_transparent_pixels: int
    off_palette_pixels: int
    isolated_pixels: int
    issues: list[PixelArtValidationIssue]

class LoopTransitionValidationResult(StrictModel):
    source_path: str
    sha256: str
    valid: bool
    tag: str | None
    first_frame: int
    last_frame: int
    changed_pixel_count: int
    changed_ratio: float
    changed_bounds: RectangleInfo | None
    first_duration_ms: int
    last_duration_ms: int
    duration_delta_ms: int
    issues: list[AnimationValidationIssue]

class CollisionPolygon(StrictModel):
    points: list[PointInfo]
    area: float

class CollisionPolygonFrame(StrictModel):
    frame: int
    polygons: list[CollisionPolygon]

class CollisionPolygonResult(StrictModel):
    source_path: str
    sha256: str
    frames: list[CollisionPolygonFrame]
