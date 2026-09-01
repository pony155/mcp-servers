"""Typed, policy-enforcing adapter around the Aseprite CLI and Lua bridge."""

from __future__ import annotations
import logging
from typing import Literal
from ..errors import AsepriteMCPError
from ..models import (
    BlendModeEditOperation,
    CelEditOperation,
    FrameDefinition,
    LayerDefinition,
    LayerEditOperation,
    MutationResult,
    PixelInput,
    PropertyEditOperation,
    SliceEditOperation,
)
from ..paths import SPRITE_DOCUMENT_EXTENSIONS, publish_file, sha256_file, temporary_sibling
from .runtime import (
    AsepriteRuntime,
    CANVAS_ANCHORS,
    MAX_CANVAS_DIMENSION,
    MAX_CANVAS_PIXELS,
    MAX_FRAMES,
    MAX_LAYERS,
    MAX_VALIDATION_PIXEL_VISITS,
)

logger = logging.getLogger(__name__)


class DocumentsService(AsepriteRuntime):
    """Documents Aseprite operations."""

    async def create_sprite(
        self,
        output_path: str,
        *,
        width: int | None,
        height: int | None,
        color_mode: Literal["rgb", "grayscale", "indexed"],
        layers: list[LayerDefinition],
        frames: list[FrameDefinition],
        pixels: list[PixelInput],
        overwrite: bool,
    ) -> MutationResult:
        self._validate_creation_limits(width, height, layers, frames, pixels)
        output = self.paths.output_file(
            output_path, extensions=SPRITE_DOCUMENT_EXTENSIONS, overwrite=overwrite
        )
        temporary = temporary_sibling(output)
        logger.info(
            "Creating sprite output=%s size=%dx%d mode=%s layers=%d frames=%d "
            "pixels=%d overwrite=%s",
            output,
            width,
            height,
            color_mode,
            len(layers),
            len(frames),
            len(pixels),
            overwrite,
        )
        async with self._locked([output]):
            try:
                await self._bridge(
                    "create",
                    {
                        "output_path": self._process_path(temporary),
                        "width": width,
                        "height": height,
                        "color_mode": color_mode,
                        "layers": [layer.model_dump() for layer in layers],
                        "frames": [frame.model_dump() for frame in frames],
                        "pixels": [pixel.model_dump() for pixel in pixels],
                    },
                )
                if not temporary.is_file():
                    raise AsepriteMCPError(
                        "ASEPRITE_FAILED", "Aseprite did not create the sprite document"
                    )
                publish_file(temporary, output)
            finally:
                temporary.unlink(missing_ok=True)
        sprite = await self.inspect_sprite(str(output))
        mutation = MutationResult(
            **self._file_result(output).model_dump(), source_sha256=None, sprite=sprite
        )
        logger.info("Sprite creation completed output=%s bytes=%d", output, mutation.byte_size)
        return mutation

    async def import_sprite_sheet(
        self,
        source_path: str,
        output_path: str,
        *,
        frame_width: int,
        frame_height: int,
        columns: int | None,
        frame_count: int | None,
        margin: int,
        spacing: int,
        duration_ms: int,
        layer_name: str,
        tag_name: str | None,
        transparent_color: str | None,
        overwrite: bool,
    ) -> MutationResult:
        self._validate_canvas_dimensions(frame_width, frame_height)
        if columns is not None and not 1 <= columns <= MAX_FRAMES:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", f"columns must be between 1 and {MAX_FRAMES}"
            )
        if frame_count is not None and not 1 <= frame_count <= MAX_FRAMES:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", f"frame_count must be between 1 and {MAX_FRAMES}"
            )
        if not 0 <= margin <= MAX_CANVAS_DIMENSION or not 0 <= spacing <= MAX_CANVAS_DIMENSION:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", f"margin and spacing may not exceed {MAX_CANVAS_DIMENSION}"
            )
        if not 1 <= duration_ms <= 60_000:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "duration_ms must be between 1 and 60000")

        source = self.paths.existing_file(source_path, extensions=frozenset({".png"}))
        output = self.paths.output_file(
            output_path, extensions=SPRITE_DOCUMENT_EXTENSIONS, overwrite=overwrite
        )
        temporary = temporary_sibling(output)
        logger.info(
            "Importing sprite sheet source=%s output=%s frame=%dx%d columns=%s "
            "frames=%s margin=%d spacing=%d overwrite=%s",
            source,
            output,
            frame_width,
            frame_height,
            columns,
            frame_count,
            margin,
            spacing,
            overwrite,
        )
        async with self._locked([source, output]):
            source_hash = sha256_file(source)
            try:
                await self._bridge(
                    "import_sprite_sheet",
                    {
                        "source_path": self._process_path(source),
                        "output_path": self._process_path(temporary),
                        "frame_width": frame_width,
                        "frame_height": frame_height,
                        "columns": columns,
                        "frame_count": frame_count,
                        "margin": margin,
                        "spacing": spacing,
                        "duration_ms": duration_ms,
                        "layer_name": layer_name,
                        "tag_name": tag_name,
                        "transparent_color": transparent_color,
                        "max_frames": MAX_FRAMES,
                        "max_total_pixels": MAX_CANVAS_PIXELS,
                    },
                )
                if not temporary.is_file():
                    raise AsepriteMCPError(
                        "ASEPRITE_FAILED", "Aseprite did not create the imported sprite document"
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
        logger.info("Sprite-sheet import completed output=%s frames=%d", output, sprite.frame_count)
        return mutation

    async def resize_canvas(
        self,
        source_path: str,
        output_path: str,
        *,
        width: int,
        height: int,
        anchor: str,
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        self._validate_canvas_dimensions(width, height)
        if anchor not in CANVAS_ANCHORS:
            raise AsepriteMCPError("INVALID_INPUT", "unsupported canvas anchor")
        return await self._bridge_mutation(
            "resize_canvas",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"width": width, "height": height, "anchor": anchor},
        )

    async def resize_sprite(
        self,
        source_path: str,
        output_path: str,
        *,
        width: int,
        height: int,
        method: Literal["nearest"],
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        self._validate_canvas_dimensions(width, height)
        return await self._bridge_mutation(
            "resize_sprite",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"width": width, "height": height, "method": method},
        )

    async def edit_layers(
        self, source_path: str, output_path: str, *, operations: list[LayerEditOperation],
        overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        if not operations or len(operations) > MAX_LAYERS:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", f"operations must contain 1 to {MAX_LAYERS} items"
            )
        for operation in operations:
            action = operation.action
            if action in {"add", "add_group"} and operation.name is None:
                raise AsepriteMCPError("INVALID_INPUT", f"{action} requires name")
            if action not in {"add", "add_group"} and operation.layer is None:
                raise AsepriteMCPError("INVALID_INPUT", f"{action} requires layer")
            if action == "rename" and operation.name is None:
                raise AsepriteMCPError("INVALID_INPUT", "rename requires name")
            if action == "set_visibility" and operation.visible is None:
                raise AsepriteMCPError("INVALID_INPUT", "set_visibility requires visible")
            if action == "set_opacity" and operation.opacity is None:
                raise AsepriteMCPError("INVALID_INPUT", "set_opacity requires opacity")
            if action == "move" and operation.parent is None and operation.stack_index is None:
                raise AsepriteMCPError("INVALID_INPUT", "move requires parent or stack_index")
        return await self._bridge_mutation(
            "edit_layers", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={
                "operations": [item.model_dump() for item in operations],
                "max_layers": MAX_LAYERS,
            },
        )

    async def trim_cels(
        self,
        source_path: str,
        output_path: str,
        *,
        layers: list[str],
        frames: list[int],
        remove_empty: bool,
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        if len(layers) > MAX_LAYERS or len(frames) > MAX_FRAMES or any(x < 0 for x in frames):
            raise AsepriteMCPError("LIMIT_EXCEEDED", "layer or frame selection exceeds limits")
        return await self._bridge_mutation(
            "trim_cels",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"layers": layers, "frames": frames, "remove_empty": remove_empty},
        )

    async def edit_slices(
        self,
        source_path: str,
        output_path: str,
        *,
        operations: list[SliceEditOperation],
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        if not operations or len(operations) > 256:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "operations must contain 1 to 256 items")
        for operation in operations:
            if operation.action == "set" and operation.bounds is None:
                raise AsepriteMCPError("INVALID_INPUT", "set requires bounds")
            if operation.action == "remove" and any(
                value is not None for value in (operation.bounds, operation.center, operation.pivot)
            ):
                raise AsepriteMCPError("INVALID_INPUT", "remove accepts only name and frame")
        return await self._bridge_mutation(
            "edit_slices",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": [operation.model_dump() for operation in operations]},
        )

    async def edit_properties(
        self,
        source_path: str,
        output_path: str,
        *,
        operations: list[PropertyEditOperation],
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        if not operations or len(operations) > 256:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "operations must contain 1 to 256 items")
        for operation in operations:
            if operation.action == "set" and operation.value is None:
                raise AsepriteMCPError("INVALID_INPUT", "set requires a scalar value")
            if operation.target in {"layer", "cel"} and operation.layer is None:
                raise AsepriteMCPError("INVALID_INPUT", f"{operation.target} requires layer")
            if operation.target in {"tag", "slice"} and operation.name is None:
                raise AsepriteMCPError("INVALID_INPUT", f"{operation.target} requires name")
            if operation.target == "cel" and operation.frame is None:
                raise AsepriteMCPError("INVALID_INPUT", "cel requires frame")
        return await self._bridge_mutation(
            "edit_properties",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": [operation.model_dump() for operation in operations]},
        )

    async def convert_color_mode(
        self,
        source_path: str,
        output_path: str,
        *,
        color_mode: Literal["rgb", "grayscale", "indexed"],
        dithering: Literal["none", "ordered", "error-diffusion"],
        dithering_matrix: Literal["bayer2x2", "bayer4x4", "bayer8x8"],
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        return await self._bridge_mutation(
            "convert_color_mode",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={
                "color_mode": color_mode,
                "dithering": dithering,
                "dithering_matrix": dithering_matrix,
            },
        )

    async def crop_sprite(
        self,
        source_path: str,
        output_path: str,
        *,
        padding: int,
        frames: list[int],
        layers: list[str],
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        return await self._bridge_mutation(
            "crop_sprite",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={
                "padding": padding,
                "frames": frames,
                "layers": layers,
                "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS,
            },
        )

    async def merge_layers(
        self, source_path: str, output_path: str, *, mode: Literal["merge_down", "flatten"],
        layer: str | None, visible_only: bool, output_layer_name: str | None,
        overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        if mode == "merge_down" and layer is None:
            raise AsepriteMCPError("INVALID_INPUT", "merge_down requires a layer path")
        return await self._bridge_mutation(
            "merge_layers", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"mode": mode, "layer": layer, "visible_only": visible_only,
                     "output_layer_name": output_layer_name},
        )

    async def import_frames(
        self, source_path: str, output_path: str, *, frame_paths: list[str], layer: str,
        insert_at: int | None, duration_ms: int, overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        if not 1 <= len(frame_paths) <= 256:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "frame_paths must contain 1 to 256 files")
        frames = [self.paths.existing_file(path, extensions=frozenset({".png"}))
                  for path in frame_paths]
        return await self._bridge_mutation(
            "import_frames", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"frame_paths": [self._process_path(path) for path in frames],
                     "layer": layer, "insert_at": insert_at, "duration_ms": duration_ms},
            additional_lock_paths=frames,
        )

    async def edit_grid(
        self, source_path: str, output_path: str, *, x: int, y: int, width: int,
        height: int, overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        return await self._bridge_mutation(
            "edit_grid", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"x": x, "y": y, "width": width, "height": height},
        )

    async def edit_blend_modes(
        self, source_path: str, output_path: str, *, operations: list[BlendModeEditOperation],
        overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        if not 1 <= len(operations) <= 128:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "operations must contain 1 to 128 items")
        return await self._bridge_mutation(
            "edit_blend_modes", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": [operation.model_dump() for operation in operations]},
        )

    async def edit_cels(
        self, source_path: str, output_path: str, *, operations: list[CelEditOperation],
        overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        if not 1 <= len(operations) <= 256:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "operations must contain 1 to 256 items")
        for operation in operations:
            if operation.action == "set_position" and None in (operation.x, operation.y):
                raise AsepriteMCPError("INVALID_INPUT", "set_position requires x and y")
            if operation.action == "set_opacity" and operation.opacity is None:
                raise AsepriteMCPError("INVALID_INPUT", "set_opacity requires opacity")
            if operation.action == "set_z_index" and operation.z_index is None:
                raise AsepriteMCPError("INVALID_INPUT", "set_z_index requires z_index")
        return await self._bridge_mutation(
            "edit_cels", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": [operation.model_dump() for operation in operations]},
        )

    async def edit_color_space(
        self, source_path: str, output_path: str, *,
        mode: Literal["assign_srgb", "assign_none", "assign_icc", "convert_srgb", "convert_icc"],
        profile_path: str | None, overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        needs_profile = mode in {"assign_icc", "convert_icc"}
        if needs_profile != (profile_path is not None):
            raise AsepriteMCPError(
                "INVALID_INPUT", "profile_path is required only for assign_icc or convert_icc"
            )
        profile = None
        if profile_path is not None:
            profile = self.paths.existing_file(
                profile_path, extensions=frozenset({".icc", ".icm"})
            )
        return await self._bridge_mutation(
            "edit_color_space", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"mode": mode,
                     "profile_path": self._process_path(profile) if profile else None},
            additional_lock_paths=[profile] if profile else None,
        )
