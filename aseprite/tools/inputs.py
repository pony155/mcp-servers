"""Reusable MCP parameter annotations for common filesystem mutation inputs."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field


SourcePath = Annotated[str, Field(description="Authorized source sprite or image path")]
SpriteSourcePath = Annotated[str, Field(description="Authorized source sprite document")]
OutputPath = Annotated[str, Field(description="Authorized destination file path")]
SpriteOutputPath = Annotated[str, Field(description="Authorized destination sprite document")]
Overwrite = Annotated[bool, Field(description="Explicitly allow replacing existing output files")]
ExpectedSourceHash = Annotated[
    str | None,
    Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
        description="Optional SHA-256 guard against concurrent source changes",
    ),
]


__all__ = [
    "ExpectedSourceHash",
    "OutputPath",
    "Overwrite",
    "SourcePath",
    "SpriteOutputPath",
    "SpriteSourcePath",
]
