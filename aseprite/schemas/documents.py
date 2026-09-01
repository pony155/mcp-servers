"""Documents schemas for the Aseprite MCP server."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import StrictModel


class PropertyEditOperation(StrictModel):
    action: Literal["set", "remove"]
    target: Literal["sprite", "layer", "tag", "slice", "cel"]
    key: Annotated[str, Field(min_length=1, max_length=128)]
    value: str | int | float | bool | None = None
    layer: Annotated[str | None, Field(min_length=1, max_length=256)] = None
    name: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    frame: Annotated[int | None, Field(ge=0)] = None

class BlendModeEditOperation(StrictModel):
    layer: Annotated[str, Field(min_length=1, max_length=256)]
    blend_mode: Literal[
        "normal", "multiply", "screen", "overlay", "darken", "lighten",
        "color_dodge", "color_burn", "hard_light", "soft_light", "difference",
        "exclusion", "hsl_hue", "hsl_saturation", "hsl_color", "hsl_luminosity",
        "addition", "subtract", "divide"
    ]

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
