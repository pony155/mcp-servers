"""Typed, policy-enforcing adapter around the Aseprite CLI and Lua bridge."""

from __future__ import annotations
from typing import Any, Literal
from ..errors import AsepriteMCPError
from ..models import (
    FileResult,
    MutationResult,
    PaletteAnalysisResult,
    PaletteColorInput,
    PaletteEntryEditOperation,
)
from ..paths import SPRITE_INPUT_EXTENSIONS, publish_file, sha256_file, temporary_sibling
from .runtime import AsepriteRuntime, MAX_VALIDATION_PIXEL_VISITS, PALETTE_EXTENSIONS


class PalettesService(AsepriteRuntime):
    """Palettes Aseprite operations."""

    async def apply_palette(
        self, source_path: str, output_path: str, *, colors: list[PaletteColorInput],
        preserve_alpha: bool, overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        if not colors or len(colors) > 256:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "colors must contain 1 to 256 entries")
        return await self._bridge_mutation(
            "apply_palette", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"colors": [item.color for item in colors], "preserve_alpha": preserve_alpha,
                     "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS},
        )

    async def analyze_palette(
        self, source_path: str, *, near_duplicate_distance: int
    ) -> PaletteAnalysisResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        async with self._locked([source]):
            result = await self._bridge(
                "analyze_palette",
                {"source_path": self._process_path(source),
                 "near_duplicate_distance": near_duplicate_distance,
                 "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS},
            )
            result.update(source_path=str(source), sha256=sha256_file(source))
        return PaletteAnalysisResult.model_validate(result)

    async def replace_color(
        self, source_path: str, output_path: str, **kwargs: Any
    ) -> MutationResult:
        return await self._bridge_mutation("replace_color", source_path, output_path, **kwargs)

    async def edit_palette_entries(
        self,
        source_path: str,
        output_path: str,
        *,
        operations: list[PaletteEntryEditOperation],
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        if not operations or len(operations) > 256:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "operations must contain 1 to 256 items")
        for operation in operations:
            if operation.action in {"set", "remove", "swap"} and operation.index is None:
                raise AsepriteMCPError("INVALID_INPUT", f"{operation.action} requires index")
            if operation.action in {"set", "append"} and operation.color is None:
                raise AsepriteMCPError("INVALID_INPUT", f"{operation.action} requires color")
            if operation.action == "remove" and operation.replacement_index is None:
                raise AsepriteMCPError("INVALID_INPUT", "remove requires replacement_index")
            if operation.action == "swap" and operation.other_index is None:
                raise AsepriteMCPError("INVALID_INPUT", "swap requires other_index")
        return await self._bridge_mutation(
            "edit_palette_entries",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={
                "operations": [operation.model_dump() for operation in operations],
                "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS,
            },
        )

    async def quantize_palette(
        self, source_path: str, output_path: str, *, color_count: int,
        algorithm: Literal["default", "octree", "rgb5a3"],
        dithering: Literal["none", "ordered", "error-diffusion"],
        dithering_matrix: Literal["bayer2x2", "bayer4x4", "bayer8x8"],
        include_alpha: bool, overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        return await self._bridge_mutation(
            "quantize_palette", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"color_count": color_count, "algorithm": algorithm,
                     "dithering": dithering, "dithering_matrix": dithering_matrix,
                     "include_alpha": include_alpha},
        )

    async def import_palette(
        self, source_path: str, palette_path: str, output_path: str, *,
        overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        palette = self.paths.existing_file(palette_path, extensions=PALETTE_EXTENSIONS)
        return await self._bridge_mutation(
            "import_palette", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"palette_path": self._process_path(palette)},
            additional_lock_paths=[palette],
        )

    async def export_palette(
        self, source_path: str, output_path: str, *, overwrite: bool,
    ) -> FileResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        output = self.paths.output_file(
            output_path, extensions=PALETTE_EXTENSIONS - {".png"}, overwrite=overwrite
        )
        temporary = temporary_sibling(output)
        async with self._locked([source, output]):
            try:
                await self._bridge("export_palette", {
                    "source_path": self._process_path(source),
                    "output_path": self._process_path(temporary),
                })
                if not temporary.is_file():
                    raise AsepriteMCPError("ASEPRITE_FAILED", "Aseprite did not export the palette")
                publish_file(temporary, output)
            finally:
                temporary.unlink(missing_ok=True)
        return self._file_result(output)

    async def palette_cycle(
        self, source_path: str, output_path: str, *, indices: list[int],
        first_frame: int, last_frame: int, step: int, overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        if not 2 <= len(indices) <= 256 or len(set(indices)) != len(indices):
            raise AsepriteMCPError(
                "INVALID_INPUT", "indices must contain 2 to 256 unique palette indices"
            )
        if first_frame > last_frame:
            raise AsepriteMCPError("INVALID_SELECTOR", "first_frame must not exceed last_frame")
        return await self._bridge_mutation(
            "palette_cycle", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"indices": indices, "first_frame": first_frame,
                     "last_frame": last_frame, "step": step,
                     "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS},
        )
