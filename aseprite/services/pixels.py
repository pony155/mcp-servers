"""Typed, policy-enforcing adapter around the Aseprite CLI and Lua bridge."""

from __future__ import annotations
import logging
from typing import Any, Literal
from ..errors import AsepriteMCPError
from ..models import (
    CompositedPixelReadResult,
    MutationResult,
    PaletteColorInput,
    PixelInput,
    PixelReadResult,
    PixelRunInput,
    RectangleInput,
    SelectionEditOperation,
    ShapeInput,
    StrokeInput,
)
from ..paths import (
    SPRITE_DOCUMENT_EXTENSIONS,
    SPRITE_INPUT_EXTENSIONS,
    publish_file,
    sha256_file,
    temporary_sibling,
)
from .runtime import (
    AsepriteRuntime,
    MAX_CANVAS_DIMENSION,
    MAX_PIXEL_EDITS,
    MAX_PIXEL_READS,
    MAX_PIXEL_RUN_EDITS,
    MAX_VALIDATION_PIXEL_VISITS,
)

logger = logging.getLogger(__name__)


class PixelsService(AsepriteRuntime):
    """Pixels Aseprite operations."""

    async def set_pixels(
        self,
        source_path: str,
        output_path: str,
        *,
        layer: str,
        frame: int,
        pixels: list[PixelInput],
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        if not pixels:
            raise AsepriteMCPError("INVALID_INPUT", "pixels must not be empty")
        if len(pixels) > MAX_PIXEL_EDITS:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", f"At most {MAX_PIXEL_EDITS} pixels may be edited per call"
            )
        if frame < 0:
            raise AsepriteMCPError("INVALID_SELECTOR", "frame must be zero or greater")
        source = self.paths.existing_file(source_path, extensions=SPRITE_DOCUMENT_EXTENSIONS)
        output = self.paths.output_file(
            output_path, extensions=SPRITE_DOCUMENT_EXTENSIONS, overwrite=overwrite
        )
        if source == output and not overwrite:
            raise AsepriteMCPError(
                "OUTPUT_EXISTS", "Editing the source in place requires overwrite=true"
            )
        temporary = temporary_sibling(output)
        logger.info(
            "Editing sprite pixels source=%s output=%s layer=%s frame=%d pixels=%d "
            "overwrite=%s hash_guard=%s",
            source,
            output,
            layer,
            frame,
            len(pixels),
            overwrite,
            expected_source_hash is not None,
        )
        async with self._locked([source, output]):
            source_hash = self._validate_source_hash(source, expected_source_hash)
            try:
                await self._bridge(
                    "set_pixels",
                    {
                        "source_path": self._process_path(source),
                        "output_path": self._process_path(temporary),
                        "layer": layer,
                        "frame": frame,
                        "pixels": [pixel.model_dump() for pixel in pixels],
                    },
                )
                if not temporary.is_file():
                    raise AsepriteMCPError(
                        "ASEPRITE_FAILED", "Aseprite did not create the edited sprite"
                    )
                publish_file(temporary, output)
            finally:
                temporary.unlink(missing_ok=True)
        sprite = await self.inspect_sprite(str(output))
        mutation = MutationResult(
            **self._file_result(output).model_dump(),
            source_sha256=source_hash,
            sprite=sprite,
        )
        logger.info("Pixel edit completed output=%s bytes=%d", output, mutation.byte_size)
        return mutation

    async def read_pixels(
        self,
        source_path: str,
        *,
        layer: str,
        frame: int,
        x: int,
        y: int,
        width: int,
        height: int,
        include_transparent: bool,
    ) -> PixelReadResult:
        if min(frame, x, y) < 0 or width < 1 or height < 1:
            raise AsepriteMCPError(
                "INVALID_SELECTOR",
                "frame and position must be non-negative; size must be positive",
            )
        if width * height > MAX_PIXEL_READS:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", f"At most {MAX_PIXEL_READS} pixels may be read per call"
            )
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        logger.info(
            "Reading pixels source=%s layer=%s frame=%d bounds=%d,%d %dx%d",
            source, layer, frame, x, y, width, height,
        )
        async with self._locked([source]):
            result = await self._bridge(
                "read_pixels",
                {
                    "source_path": self._process_path(source), "layer": layer,
                    "frame": frame, "x": x, "y": y, "width": width, "height": height,
                    "include_transparent": include_transparent,
                },
            )
            result["source_path"] = str(source)
            result["sha256"] = sha256_file(source)
        return PixelReadResult.model_validate(result)

    async def transform_cel(
        self, source_path: str, output_path: str, *, layer: str, frame: int,
        action: Literal[
            "translate", "flip_horizontal", "flip_vertical", "rotate_90_cw", "rotate_90_ccw"
        ],
        offset_x: int, offset_y: int, overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        if frame < 0:
            raise AsepriteMCPError("INVALID_SELECTOR", "frame must be zero or greater")
        x_in_range = -MAX_CANVAS_DIMENSION <= offset_x <= MAX_CANVAS_DIMENSION
        y_in_range = -MAX_CANVAS_DIMENSION <= offset_y <= MAX_CANVAS_DIMENSION
        if not x_in_range or not y_in_range:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "offsets exceed the canvas dimension limit")
        if action != "translate" and (offset_x or offset_y):
            raise AsepriteMCPError("INVALID_INPUT", "offsets are only valid for translate")
        return await self._bridge_mutation(
            "transform_cel", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"layer": layer, "frame": frame, "action": action,
                     "offset_x": offset_x, "offset_y": offset_y},
        )

    async def read_composited_pixels(
        self,
        source_path: str,
        *,
        frame: int,
        x: int,
        y: int,
        width: int,
        height: int,
        include_transparent: bool,
    ) -> CompositedPixelReadResult:
        if min(frame, x, y) < 0 or width < 1 or height < 1:
            raise AsepriteMCPError("INVALID_SELECTOR", "invalid frame or pixel rectangle")
        if width * height > MAX_PIXEL_READS:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", f"At most {MAX_PIXEL_READS} pixels may be read per call"
            )
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        async with self._locked([source]):
            result = await self._bridge(
                "read_composited_pixels",
                {
                    "source_path": self._process_path(source),
                    "frame": frame,
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "include_transparent": include_transparent,
                },
            )
            result["source_path"] = str(source)
            result["sha256"] = sha256_file(source)
        return CompositedPixelReadResult.model_validate(result)

    async def set_pixel_runs(
        self,
        source_path: str,
        output_path: str,
        *,
        layer: str,
        frame: int,
        runs: list[PixelRunInput],
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        pixel_count = sum(run.length for run in runs)
        if not runs:
            raise AsepriteMCPError("INVALID_INPUT", "runs must not be empty")
        if pixel_count > MAX_PIXEL_RUN_EDITS:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED",
                f"At most {MAX_PIXEL_RUN_EDITS} pixels may be written per call",
            )
        return await self._bridge_mutation(
            "set_pixel_runs",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={
                "layer": layer,
                "frame": frame,
                "runs": [run.model_dump() for run in runs],
            },
        )

    async def fill_region(
        self, source_path: str, output_path: str, **kwargs: Any
    ) -> MutationResult:
        return await self._bridge_mutation("fill_region", source_path, output_path, **kwargs)

    async def draw_shapes(
        self, source_path: str, output_path: str, *, shapes: list[ShapeInput],
        overwrite: bool, expected_source_hash: str | None, layer: str, frame: int,
    ) -> MutationResult:
        if not shapes or len(shapes) > 256:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "shapes must contain 1 to 256 items")
        return await self._bridge_mutation(
            "draw_shapes", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"layer": layer, "frame": frame,
                     "shapes": [shape.model_dump() for shape in shapes]},
        )

    async def edit_selection(
        self, source_path: str, output_path: str, *, operations: list[SelectionEditOperation],
        overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        return await self._bridge_mutation(
            "edit_selection", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": [operation.model_dump() for operation in operations]},
        )

    async def apply_outline(
        self, source_path: str, output_path: str, **kwargs: Any
    ) -> MutationResult:
        return await self._bridge_mutation("apply_outline", source_path, output_path, **kwargs)

    async def draw_strokes(
        self,
        source_path: str,
        output_path: str,
        *,
        layer: str,
        frame: int,
        strokes: list[StrokeInput],
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        total_points = sum(len(stroke.points) for stroke in strokes)
        if not strokes or len(strokes) > 256 or total_points > 100_000:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", "strokes must contain 1 to 256 strokes and at most 100000 points"
            )
        return await self._bridge_mutation(
            "draw_strokes",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={
                "layer": layer,
                "frame": frame,
                "strokes": [stroke.model_dump() for stroke in strokes],
            },
        )

    async def transform_selection(
        self,
        source_path: str,
        output_path: str,
        *,
        layer: str,
        frame: int,
        bounds: RectangleInput,
        action: Literal[
            "move", "copy", "flip_horizontal", "flip_vertical", "rotate_90_cw",
            "rotate_90_ccw", "scale_nearest"
        ],
        offset_x: int,
        offset_y: int,
        scale_x: int,
        scale_y: int,
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        return await self._bridge_mutation(
            "transform_selection",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={
                "layer": layer,
                "frame": frame,
                "bounds": bounds.model_dump(),
                "action": action,
                "offset_x": offset_x,
                "offset_y": offset_y,
                "scale_x": scale_x,
                "scale_y": scale_y,
                "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS,
            },
        )

    async def select_by_color(
        self, source_path: str, output_path: str, *, colors: list[PaletteColorInput],
        frame: int, layer: str | None, tolerance: int,
        selection_mode: Literal["replace", "add", "subtract", "intersect"],
        include_alpha: bool, overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        if not 1 <= len(colors) <= 256:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "colors must contain 1 to 256 entries")
        return await self._bridge_mutation(
            "select_by_color", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"colors": [item.color for item in colors], "frame": frame,
                     "layer": layer, "tolerance": tolerance,
                     "selection_mode": selection_mode, "include_alpha": include_alpha,
                     "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS},
        )
