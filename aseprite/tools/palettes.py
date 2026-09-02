"""MCP server construction and tool registration."""

from __future__ import annotations
from typing import Annotated, Literal
from mcp.server import MCPServer
from pydantic import Field
from ..adapter import AsepriteAdapter
from ..capabilities import CapabilityRegistry, ToolRegistrar
from ..models import (
    FileResult,
    MutationResult,
    PaletteAnalysisResult,
    PaletteColorInput,
    PaletteEntryEditOperation,
)
from .inputs import ExpectedSourceHash, Overwrite, SpriteOutputPath, SpriteSourcePath


def register_palettes_tools(
    server: MCPServer, adapter: AsepriteAdapter, registry: CapabilityRegistry, *, enabled_tools: frozenset[str]
) -> int:
    """Register palettes tools and return the number registered."""

    tools = ToolRegistrar(server, registry, "palettes", enabled_tools=enabled_tools)

    @tools.tool()
    async def aseprite_apply_palette(
        source_path: SpriteSourcePath,
        output_path: SpriteOutputPath,
        colors: Annotated[list[PaletteColorInput], Field(min_length=1, max_length=256)],
        preserve_alpha: Annotated[
            bool, Field(description="Preserve RGB-sprite pixel alpha")
        ] = True,
        overwrite: Overwrite = False,
        expected_source_hash: ExpectedSourceHash = None,
    ) -> MutationResult:
        """Remap cel colors to the nearest supplied palette colors."""

        return await adapter.apply_palette(
            source_path, output_path, colors=colors, preserve_alpha=preserve_alpha,
            overwrite=overwrite, expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_analyze_palette(
        source_path: str,
        near_duplicate_distance: Annotated[int, Field(ge=0, le=765)] = 24,
    ) -> PaletteAnalysisResult:
        """Analyze exact color usage, unused entries, and nearby colors."""
        return await adapter.analyze_palette(
            source_path, near_duplicate_distance=near_duplicate_distance
        )

    @tools.tool()
    async def aseprite_replace_color(
        source_path: str, output_path: str,
        from_color: Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")],
        to_color: Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")],
        tolerance: Annotated[int, Field(ge=0, le=1020)] = 0,
        layers: list[str] | None = None, frames: list[int] | None = None,
        overwrite: bool = False, expected_source_hash: str | None = None,
    ) -> MutationResult:
        """Replace a color across selected image layers and frames."""
        return await adapter.replace_color(source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"from_color":from_color,"to_color":to_color,"tolerance":tolerance,
                     "layers":layers or [],"frames":frames or []})

    @tools.tool()
    async def aseprite_edit_palette_entries(
        source_path: str,
        output_path: str,
        operations: Annotated[
            list[PaletteEntryEditOperation], Field(min_length=1, max_length=256)
        ],
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Set, append, remove, or swap indexed palette entries safely."""
        return await adapter.edit_palette_entries(
            source_path,
            output_path,
            operations=operations,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_quantize_palette(
        source_path: str,
        output_path: str,
        color_count: Annotated[int, Field(ge=2, le=256)] = 32,
        algorithm: Literal["default", "octree", "rgb5a3"] = "octree",
        dithering: Literal["none", "ordered", "error-diffusion"] = "none",
        dithering_matrix: Literal["bayer2x2", "bayer4x4", "bayer8x8"] = "bayer4x4",
        include_alpha: bool = True,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Create a bounded palette and convert a document to indexed color."""
        return await adapter.quantize_palette(
            source_path, output_path, color_count=color_count, algorithm=algorithm,
            dithering=dithering, dithering_matrix=dithering_matrix,
            include_alpha=include_alpha, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_import_palette(
        source_path: str,
        palette_path: str,
        output_path: str,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Load a supported palette file into a new sprite-document revision."""
        return await adapter.import_palette(
            source_path, palette_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    @tools.tool()
    async def aseprite_export_palette(
        source_path: str,
        output_path: str,
        overwrite: bool = False,
    ) -> FileResult:
        """Export the first sprite palette to an authorized palette file."""
        return await adapter.export_palette(source_path, output_path, overwrite=overwrite)

    @tools.tool()
    async def aseprite_palette_cycle(
        source_path: str,
        output_path: str,
        indices: Annotated[
            list[Annotated[int, Field(ge=0, le=255)]], Field(min_length=2, max_length=256)
        ],
        first_frame: Annotated[int, Field(ge=0)],
        last_frame: Annotated[int, Field(ge=0)],
        step: Annotated[int, Field(ge=-255, le=255)] = 1,
        overwrite: bool = False,
        expected_source_hash: Annotated[
            str | None, Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$")
        ] = None,
    ) -> MutationResult:
        """Rotate selected indexed-color entries progressively across an existing frame range."""
        return await adapter.palette_cycle(
            source_path, output_path, indices=indices, first_frame=first_frame,
            last_frame=last_frame, step=step, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
        )

    return tools.registered_count
