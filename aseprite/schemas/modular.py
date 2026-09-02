"""Schemas for modular character metadata, validation, and export."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import FileResult, StrictModel


ModularIdentifier = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$",
    ),
]


class ModularAnchorInput(StrictModel):
    name: ModularIdentifier
    x: Annotated[int, Field(ge=-4096, le=4096)]
    y: Annotated[int, Field(ge=-4096, le=4096)]


class ModularPartEditOperation(StrictModel):
    action: Literal["set", "remove"]
    layer: Annotated[str, Field(min_length=1, max_length=256)]
    part_id: ModularIdentifier | None = None
    slot: ModularIdentifier | None = None
    draw_order: Annotated[int, Field(ge=-4096, le=4096)] = 0
    compatibility_tags: Annotated[list[ModularIdentifier], Field(max_length=32)] = Field(
        default_factory=list
    )
    requires_part_ids: Annotated[list[ModularIdentifier], Field(max_length=32)] = Field(
        default_factory=list
    )
    conflicts_part_ids: Annotated[list[ModularIdentifier], Field(max_length=32)] = Field(
        default_factory=list
    )
    anchors: Annotated[list[ModularAnchorInput], Field(max_length=16)] = Field(
        default_factory=list
    )


class ModularPartInfo(StrictModel):
    layer: str
    part_id: str
    slot: str
    draw_order: int
    compatibility_tags: list[str]
    requires_part_ids: list[str]
    conflicts_part_ids: list[str]
    anchors: list[ModularAnchorInput]


class ModularValidationIssue(StrictModel):
    code: str
    severity: Literal["warning", "error"]
    message: str
    layer: str | None = None
    part_id: str | None = None


class ModularCharacterValidationResult(StrictModel):
    source_path: str
    sha256: str
    valid: bool
    parts: list[ModularPartInfo]
    slots: list[str]
    issues: list[ModularValidationIssue]


class ModularManifestResult(StrictModel):
    source_path: str
    source_sha256: str
    manifest: FileResult
    part_count: int
    slot_count: int


__all__ = [
    "ModularAnchorInput",
    "ModularCharacterValidationResult",
    "ModularManifestResult",
    "ModularPartEditOperation",
    "ModularPartInfo",
    "ModularValidationIssue",
]
