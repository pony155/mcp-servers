"""Pixels schemas for the Aseprite MCP server."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator

from .common import PointInput, RectangleInfo, RectangleInput, StrictModel

from .common import _validate_hex_color


class PixelInput(StrictModel):
    x: Annotated[int, Field(ge=0)]
    y: Annotated[int, Field(ge=0)]
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

class StrokeInput(StrictModel):
    points: Annotated[list[PointInput], Field(min_length=1, max_length=4096)]
    color: str
    brush_size: Annotated[int, Field(ge=1, le=64)] = 1
    opacity: Annotated[int, Field(ge=1, le=255)] = 255
    pixel_perfect: bool = True

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        return _validate_hex_color(value)
