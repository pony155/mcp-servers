"""Typed, policy-enforcing adapter around the Aseprite CLI and Lua bridge."""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Literal
from ..errors import AsepriteMCPError
from ..models import (
    AnimationValidationResult,
    AssetSetValidationResult,
    AssetValidationItem,
    CelInspectionResult,
    CollisionMaskResult,
    CollisionPolygonResult,
    ExportProfile,
    ExportProfileIssue,
    ExportProfileValidationResult,
    FrameComparisonResult,
    LoopTransitionValidationResult,
    MotionReportResult,
    PaletteColorInput,
    PixelArtValidationResult,
    SpriteComparisonResult,
    SpriteInfo,
)
from ..paths import SPRITE_INPUT_EXTENSIONS, publish_file, sha256_file, temporary_sibling
from .runtime import (
    AsepriteRuntime,
    MAX_CANVAS_DIMENSION,
    MAX_FRAMES,
    MAX_VALIDATION_PIXEL_VISITS,
)

logger = logging.getLogger(__name__)


class ValidationService(AsepriteRuntime):
    """Validation Aseprite operations."""

    async def validate_animation(
        self,
        source_path: str,
        *,
        baseline_tolerance: int,
        bounds_tolerance: int,
        check_duplicates: bool,
    ) -> AnimationValidationResult:
        if not 0 <= baseline_tolerance <= MAX_CANVAS_DIMENSION:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "baseline_tolerance is outside the limit")
        if not 0 <= bounds_tolerance <= MAX_CANVAS_DIMENSION:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "bounds_tolerance is outside the limit")
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        logger.info(
            "Validating animation source=%s baseline_tolerance=%d bounds_tolerance=%d "
            "check_duplicates=%s",
            source,
            baseline_tolerance,
            bounds_tolerance,
            check_duplicates,
        )
        async with self._locked([source]):
            result = await self._bridge(
                "validate_animation",
                {
                    "source_path": self._process_path(source),
                    "baseline_tolerance": baseline_tolerance,
                    "bounds_tolerance": bounds_tolerance,
                    "check_duplicates": check_duplicates,
                    "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS,
                },
            )
            result["source_path"] = str(source)
            result["sha256"] = sha256_file(source)
        validation = AnimationValidationResult.model_validate(result)
        logger.info(
            "Animation validation completed source=%s valid=%s issues=%d",
            source,
            validation.valid,
            len(validation.issues),
        )
        return validation

    async def compare_frames(
        self,
        source_path: str,
        *,
        first_frame: int,
        second_frame: int,
        difference_output_path: str | None,
        overwrite: bool,
    ) -> FrameComparisonResult:
        if min(first_frame, second_frame) < 0:
            raise AsepriteMCPError("INVALID_SELECTOR", "frame indices must be non-negative")
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        output = None
        temporary = None
        if difference_output_path is not None:
            output = self.paths.output_file(
                difference_output_path, extensions=frozenset({".png"}), overwrite=overwrite
            )
            temporary = temporary_sibling(output)
        lock_paths = [source] if output is None else [source, output]
        async with self._locked(lock_paths):
            try:
                result = await self._bridge(
                    "compare_frames",
                    {
                        "source_path": self._process_path(source),
                        "first_frame": first_frame,
                        "second_frame": second_frame,
                        "difference_output_path": (
                            self._process_path(temporary) if temporary is not None else None
                        ),
                        "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS,
                    },
                )
                if temporary is not None and output is not None:
                    if not temporary.is_file():
                        raise AsepriteMCPError(
                            "ASEPRITE_FAILED", "Aseprite did not create the difference image"
                        )
                    publish_file(temporary, output)
                    result["difference"] = self._file_result(output).model_dump()
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        result["source_path"] = str(source)
        result["sha256"] = sha256_file(source)
        return FrameComparisonResult.model_validate(result)

    async def inspect_cels(self, source_path: str) -> CelInspectionResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        async with self._locked([source]):
            result = await self._bridge("inspect_cels", {"source_path": self._process_path(source)})
            result.update(source_path=str(source), sha256=sha256_file(source))
        return CelInspectionResult.model_validate(result)

    async def compare_sprites(
        self, first_source_path: str, second_source_path: str
    ) -> SpriteComparisonResult:
        first = self.paths.existing_file(
            first_source_path, extensions=SPRITE_INPUT_EXTENSIONS
        )
        second = self.paths.existing_file(
            second_source_path, extensions=SPRITE_INPUT_EXTENSIONS
        )
        async with self._locked([first, second]):
            result = await self._bridge(
                "compare_sprites",
                {
                    "first_source_path": self._process_path(first),
                    "second_source_path": self._process_path(second),
                    "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS,
                },
            )
            result.update(
                first_source_path=str(first),
                first_sha256=sha256_file(first),
                second_source_path=str(second),
                second_sha256=sha256_file(second),
            )
        return SpriteComparisonResult.model_validate(result)

    async def validate_export_profile(
        self, source_path: str, *, profile: ExportProfile
    ) -> ExportProfileValidationResult:
        sprite = await self.inspect_sprite(source_path)
        issues: list[ExportProfileIssue] = []

        def add(code: str, message: str) -> None:
            issues.append(ExportProfileIssue(code=code, severity="error", message=message))

        if profile.canvas_width is not None and sprite.width != profile.canvas_width:
            add("CANVAS_WIDTH", f"Expected width {profile.canvas_width}, found {sprite.width}")
        if profile.canvas_height is not None and sprite.height != profile.canvas_height:
            add("CANVAS_HEIGHT", f"Expected height {profile.canvas_height}, found {sprite.height}")
        if profile.max_width is not None and sprite.width > profile.max_width:
            add("MAX_WIDTH", f"Width {sprite.width} exceeds {profile.max_width}")
        if profile.max_height is not None and sprite.height > profile.max_height:
            add("MAX_HEIGHT", f"Height {sprite.height} exceeds {profile.max_height}")
        if profile.require_power_of_two and (
            sprite.width & (sprite.width - 1) or sprite.height & (sprite.height - 1)
        ):
            add("POWER_OF_TWO", "Canvas width and height must both be powers of two")
        if profile.color_mode is not None and sprite.color_mode != profile.color_mode:
            add("COLOR_MODE", f"Expected {profile.color_mode}, found {sprite.color_mode}")
        if profile.frame_count is not None and sprite.frame_count != profile.frame_count:
            add("FRAME_COUNT", f"Expected {profile.frame_count} frames, found {sprite.frame_count}")

        layer_paths: set[str] = set()
        stack = list(sprite.layers)
        while stack:
            layer = stack.pop()
            layer_paths.add(layer.path)
            stack.extend(layer.children)
        tag_names = {tag.name for tag in sprite.tags}
        slice_names = {slice_info.name for slice_info in sprite.slices}
        for required in profile.required_layers:
            if required not in layer_paths:
                add("MISSING_LAYER", f"Required layer is missing: {required}")
        for required in profile.required_tags:
            if required not in tag_names:
                add("MISSING_TAG", f"Required tag is missing: {required}")
        for required in profile.required_slices:
            if required not in slice_names:
                add("MISSING_SLICE", f"Required slice is missing: {required}")
        palette_size = max((palette.size for palette in sprite.palettes), default=0)
        if profile.max_palette_colors is not None and palette_size > profile.max_palette_colors:
            add(
                "PALETTE_SIZE",
                f"Palette size {palette_size} exceeds {profile.max_palette_colors}",
            )
        return ExportProfileValidationResult(
            source_path=sprite.source_path,
            sha256=sprite.sha256,
            profile_name=profile.name,
            valid=not issues,
            issues=issues,
        )

    async def generate_collision_masks(
        self, source_path: str, *, frames: list[int], layer: str | None,
        mode: Literal["bounds", "components"], alpha_threshold: int, max_components: int,
    ) -> CollisionMaskResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        async with self._locked([source]):
            result = await self._bridge("generate_collision_masks", {
                "source_path": self._process_path(source), "frames": frames,
                "layer": layer, "mode": mode, "alpha_threshold": alpha_threshold,
                "max_components": max_components,
                "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS,
            })
            result.update(source_path=str(source), sha256=sha256_file(source), mode=mode)
        return CollisionMaskResult.model_validate(result)

    async def validate_asset_set(
        self, source_paths: list[str], *, profile: ExportProfile,
        require_consistent_dimensions: bool, require_consistent_color_mode: bool,
    ) -> AssetSetValidationResult:
        if not 1 <= len(source_paths) <= 64:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "source_paths must contain 1 to 64 files")
        items: list[AssetValidationItem] = []
        infos: list[SpriteInfo] = []
        for path in source_paths:
            infos.append(await self.inspect_sprite(path))
            items.append(AssetValidationItem(
                source_path=path, result=await self.validate_export_profile(path, profile=profile)
            ))
        issues: list[ExportProfileIssue] = []
        if len({Path(info.source_path).name.casefold() for info in infos}) != len(infos):
            issues.append(ExportProfileIssue(
                code="DUPLICATE_NAME", severity="error",
                message="Asset set contains duplicate case-insensitive filenames",
            ))
        if require_consistent_dimensions and len({(info.width, info.height) for info in infos}) > 1:
            issues.append(ExportProfileIssue(
                code="INCONSISTENT_DIMENSIONS", severity="error",
                message="Asset set contains different canvas dimensions",
            ))
        if require_consistent_color_mode and len({info.color_mode for info in infos}) > 1:
            issues.append(ExportProfileIssue(
                code="INCONSISTENT_COLOR_MODE", severity="error",
                message="Asset set contains different color modes",
            ))
        valid = not issues and all(item.result.valid for item in items)
        return AssetSetValidationResult(
            valid=valid, profile_name=profile.name, items=items, issues=issues
        )

    async def validate_pixel_art(
        self, source_path: str, *, frames: list[int], max_colors: int | None,
        require_binary_alpha: bool, detect_isolated_pixels: bool,
        allowed_palette: list[PaletteColorInput],
    ) -> PixelArtValidationResult:
        if len(frames) > MAX_FRAMES or len(allowed_palette) > 256:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "validation input exceeds its limit")
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        async with self._locked([source]):
            result = await self._bridge("validate_pixel_art", {
                "source_path": self._process_path(source), "frames": frames,
                "max_colors": max_colors, "require_binary_alpha": require_binary_alpha,
                "detect_isolated_pixels": detect_isolated_pixels,
                "allowed_palette": [item.color for item in allowed_palette],
                "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS,
            })
            result.update(source_path=str(source), sha256=sha256_file(source))
        return PixelArtValidationResult.model_validate(result)

    async def validate_loop_transition(
        self, source_path: str, *, tag: str | None, first_frame: int,
        last_frame: int | None, max_changed_pixels: int, require_equal_duration: bool,
    ) -> LoopTransitionValidationResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        async with self._locked([source]):
            result = await self._bridge("validate_loop_transition", {
                "source_path": self._process_path(source), "tag": tag,
                "first_frame": first_frame, "last_frame": last_frame,
                "max_changed_pixels": max_changed_pixels,
                "require_equal_duration": require_equal_duration,
                "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS,
            })
            result.update(source_path=str(source), sha256=sha256_file(source))
        return LoopTransitionValidationResult.model_validate(result)

    async def generate_motion_report(
        self, source_path: str, *, tag: str | None, layer: str | None,
        alpha_threshold: int,
    ) -> MotionReportResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        async with self._locked([source]):
            result = await self._bridge("generate_motion_report", {
                "source_path": self._process_path(source), "tag": tag, "layer": layer,
                "alpha_threshold": alpha_threshold,
                "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS,
            })
            result.update(source_path=str(source), sha256=sha256_file(source))
        return MotionReportResult.model_validate(result)

    async def generate_collision_polygons(
        self, source_path: str, *, frames: list[int], layer: str | None,
        alpha_threshold: int, simplify_tolerance: int, max_polygons: int,
        max_points_per_polygon: int,
    ) -> CollisionPolygonResult:
        if len(frames) > MAX_FRAMES:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "frames may contain at most 256 values")
        if len(set(frames)) != len(frames):
            raise AsepriteMCPError("INVALID_INPUT", "frames must not contain duplicates")
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        async with self._locked([source]):
            result = await self._bridge("generate_collision_polygons", {
                "source_path": self._process_path(source), "frames": frames,
                "layer": layer, "alpha_threshold": alpha_threshold,
                "simplify_tolerance": simplify_tolerance, "max_polygons": max_polygons,
                "max_points_per_polygon": max_points_per_polygon,
                "max_pixel_visits": MAX_VALIDATION_PIXEL_VISITS,
            })
            result.update(source_path=str(source), sha256=sha256_file(source))
        return CollisionPolygonResult.model_validate(result)
