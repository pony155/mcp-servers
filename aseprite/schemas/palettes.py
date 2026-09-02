"""Palettes schemas for the Aseprite MCP server."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, field_validator

from .common import StrictModel

from .common import _validate_hex_color


class PaletteColorInput(StrictModel):
    color: str

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        return _validate_hex_color(value)

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

class PaletteEntryEditOperation(StrictModel):
    action: Literal["set", "append", "remove", "swap"]
    index: Annotated[int | None, Field(ge=0, le=255)] = None
    other_index: Annotated[int | None, Field(ge=0, le=255)] = None
    replacement_index: Annotated[int | None, Field(ge=0, le=255)] = None
    color: str | None = None
    preserve_appearance: bool = True

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str | None) -> str | None:
        return _validate_hex_color(value) if value is not None else None
