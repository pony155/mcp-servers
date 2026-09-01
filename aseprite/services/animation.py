"""Typed, policy-enforcing adapter around the Aseprite CLI and Lua bridge."""

from __future__ import annotations
import logging
import tempfile
from pathlib import Path
from typing import Literal
from ..errors import AsepriteMCPError
from ..models import (
    AnimationFrameDefinition,
    AnimationEventEditOperation,
    AnimationTagDefinition,
    FrameEditOperation,
    LayerDefinition,
    MutationResult,
    TagEditOperation,
)
from ..paths import (
    SPRITE_DOCUMENT_EXTENSIONS,
    SPRITE_INPUT_EXTENSIONS,
    publish_file,
    temporary_sibling,
)
from .runtime import (
    AsepriteRuntime,
    MAX_CANVAS_PIXELS,
    MAX_FRAMES,
    MAX_VALIDATION_PIXEL_VISITS,
)

logger = logging.getLogger(__name__)


class AnimationService(AsepriteRuntime):
    """Animation Aseprite operations."""

    async def create_animation(
        self,
        output_path: str,
        *,
        width: int,
        height: int,
        color_mode: Literal["rgb", "grayscale", "indexed"],
        layers: list[LayerDefinition],
        frames: list[AnimationFrameDefinition],
        tags: list[AnimationTagDefinition],
        overwrite: bool,
    ) -> MutationResult:
        self._validate_animation_creation(width, height, layers, frames, tags)
        output = self.paths.output_file(
            output_path, extensions=SPRITE_DOCUMENT_EXTENSIONS, overwrite=overwrite
        )
        temporary = temporary_sibling(output)
        total_cels = sum(len(frame.cels) for frame in frames)
        total_pixels = sum(len(cel.pixels) for frame in frames for cel in frame.cels)
        logger.info(
            "Creating animation output=%s size=%dx%d mode=%s layers=%d frames=%d "
            "cels=%d pixels=%d tags=%d overwrite=%s",
            output,
            width,
            height,
            color_mode,
            len(layers),
            len(frames),
            total_cels,
            total_pixels,
            len(tags),
            overwrite,
        )
        async with self._locked([output]):
            try:
                await self._bridge(
                    "create_animation",
                    {
                        "output_path": self._process_path(temporary),
                        "width": width,
                        "height": height,
                        "color_mode": color_mode,
                        "layers": [layer.model_dump() for layer in layers],
                        "frames": [frame.model_dump() for frame in frames],
                        "tags": [tag.model_dump() for tag in tags],
                    },
                )
                if not temporary.is_file():
                    raise AsepriteMCPError(
                        "ASEPRITE_FAILED", "Aseprite did not create the animation document"
                    )
                publish_file(temporary, output)
            finally:
                temporary.unlink(missing_ok=True)
        sprite = await self.inspect_sprite(str(output))
        mutation = MutationResult(
            **self._file_result(output).model_dump(), source_sha256=None, sprite=sprite
        )
        logger.info(
            "Animation creation completed output=%s frames=%d bytes=%d",
            output,
            sprite.frame_count,
            mutation.byte_size,
        )
        return mutation

    async def edit_frames(
        self, source_path: str, output_path: str, *, operations: list[FrameEditOperation],
        overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        if not operations or len(operations) > MAX_FRAMES:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", f"operations must contain 1 to {MAX_FRAMES} items"
            )
        for operation in operations:
            if operation.action == "set_duration" and operation.duration_ms is None:
                raise AsepriteMCPError("INVALID_INPUT", "set_duration requires duration_ms")
            if operation.action != "set_duration" and operation.duration_ms is not None:
                raise AsepriteMCPError(
                    "INVALID_INPUT", "duration_ms is only valid for set_duration"
                )
        return await self._bridge_mutation(
            "edit_frames", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={
                "operations": [item.model_dump() for item in operations],
                "max_frames": MAX_FRAMES,
            },
        )

    async def edit_tags(
        self, source_path: str, output_path: str, *, operations: list[TagEditOperation],
        overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        if not operations or len(operations) > MAX_FRAMES:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", f"operations must contain 1 to {MAX_FRAMES} items"
            )
        for operation in operations:
            if operation.action == "set":
                if operation.from_frame is None or operation.to_frame is None:
                    raise AsepriteMCPError("INVALID_INPUT", "set requires from_frame and to_frame")
                if operation.from_frame > operation.to_frame:
                    raise AsepriteMCPError("INVALID_SELECTOR", "tag starts after it ends")
        return await self._bridge_mutation(
            "edit_tags", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": [item.model_dump() for item in operations]},
        )

    async def copy_cel(
        self,
        source_path: str,
        output_path: str,
        *,
        source_layer: str,
        source_frame: int,
        target_layer: str,
        target_frame: int,
        linked: bool,
        replace: bool,
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        if min(source_frame, target_frame) < 0:
            raise AsepriteMCPError("INVALID_SELECTOR", "frame indices must be non-negative")
        return await self._bridge_mutation(
            "copy_cel",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={
                "source_layer": source_layer,
                "source_frame": source_frame,
                "target_layer": target_layer,
                "target_frame": target_frame,
                "linked": linked,
                "replace": replace,
            },
        )

    async def preview_animation(
        self, source_path: str, *, tag: str | None, scale: float,
    ) -> bytes:
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        with tempfile.TemporaryDirectory(prefix="aseprite-animation-preview-",
                                         dir=self.bridge_temp_root) as directory:
            output = Path(directory) / "preview.gif"
            arguments = ["--batch", "--noinapp"]
            if tag is not None: arguments.extend(["--tag", tag])
            arguments.append(self._process_path(source))
            if scale != 1: arguments.extend(["--scale", f"{scale:g}"])
            arguments.extend(["--save-as", self._process_path(output)])
            async with self._locked([source]):
                await self._run(arguments, operation="preview_animation")
            if not output.is_file():
                raise AsepriteMCPError("ASEPRITE_FAILED", "GIF preview was not created")
            if output.stat().st_size > self.settings.max_capture_bytes:
                raise AsepriteMCPError("LIMIT_EXCEEDED", "GIF preview exceeds inline size limit")
            return output.read_bytes()

    async def edit_animation_events(
        self, source_path: str, output_path: str, *,
        operations: list[AnimationEventEditOperation], overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        if not 1 <= len(operations) <= 256:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "operations must contain 1 to 256 items")
        return await self._bridge_mutation(
            "edit_animation_events", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": [operation.model_dump() for operation in operations]},
        )

    async def generate_inbetweens(
        self, source_path: str, output_path: str, *, layer: str, first_frame: int,
        last_frame: int, count: int, interpolation: Literal["hold", "nearest", "crossfade"],
        overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        if first_frame >= last_frame:
            raise AsepriteMCPError("INVALID_SELECTOR", "first_frame must precede last_frame")
        if count < 1 or count > 64:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "count must be between 1 and 64")
        return await self._bridge_mutation(
            "generate_inbetweens", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"layer": layer, "first_frame": first_frame, "last_frame": last_frame,
                     "count": count, "interpolation": interpolation,
                     "max_frames": MAX_FRAMES,
                     "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS},
        )

    async def preview_onion_skin(
        self, source_path: str, *, frame: int, before: int, after: int, opacity: int,
        scale: int,
    ) -> bytes:
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        with tempfile.TemporaryDirectory(
            prefix="aseprite-onion-preview-", dir=self.bridge_temp_root
        ) as directory:
            output = Path(directory) / "preview.png"
            async with self._locked([source]):
                await self._bridge("preview_onion_skin", {
                    "source_path": self._process_path(source), "frame": frame,
                    "before": before, "after": after, "opacity": opacity,
                    "scale": scale, "output_path": self._process_path(output),
                    "max_pixels": MAX_CANVAS_PIXELS,
                })
            if not output.is_file():
                raise AsepriteMCPError("ASEPRITE_FAILED", "onion-skin preview was not created")
            if output.stat().st_size > self.settings.max_capture_bytes:
                raise AsepriteMCPError("LIMIT_EXCEEDED", "onion-skin preview exceeds inline limit")
            return output.read_bytes()

    async def retime_animation(
        self, source_path: str, output_path: str, *, tag: str | None,
        mode: Literal["fps", "total_duration", "scale"], target_fps: float | None,
        target_total_duration_ms: int | None, scale: float | None,
        distribution: Literal["preserve", "uniform", "ease_in", "ease_out", "ease_in_out"],
        overwrite: bool, expected_source_hash: str | None,
    ) -> MutationResult:
        supplied = sum(value is not None for value in (target_fps, target_total_duration_ms, scale))
        expected = {"fps": target_fps, "total_duration": target_total_duration_ms,
                    "scale": scale}[mode]
        if supplied != 1 or expected is None:
            raise AsepriteMCPError("INVALID_INPUT", "supply only the target selected by mode")
        return await self._bridge_mutation(
            "retime_animation", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"tag": tag, "mode": mode, "target_fps": target_fps,
                     "target_total_duration_ms": target_total_duration_ms,
                     "scale": scale, "distribution": distribution},
        )

    async def bake_tag_direction(
        self, source_path: str, output_path: str, *, tag: str, output_tag: str,
        repetitions: int, link_images: bool, overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        return await self._bridge_mutation(
            "bake_tag_direction", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"tag": tag, "output_tag": output_tag, "repetitions": repetitions,
                     "link_images": link_images, "max_frames": MAX_FRAMES},
        )

    async def optimize_linked_cels(
        self,
        source_path: str,
        output_path: str,
        *,
        layers: list[str],
        frames: list[int],
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        if len(layers) > 128 or len(frames) > MAX_FRAMES or any(frame < 0 for frame in frames):
            raise AsepriteMCPError("LIMIT_EXCEEDED", "cel selection exceeds limits")
        return await self._bridge_mutation(
            "optimize_linked_cels",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={
                "layers": layers,
                "frames": frames,
                "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS,
            },
        )
