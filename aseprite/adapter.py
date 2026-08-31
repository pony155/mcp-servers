"""Typed, policy-enforcing adapter around the Aseprite CLI and Lua bridge."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal, cast

from .config import Settings
from .errors import AsepriteMCPError
from .interop import ProcessPathMapper, resolve_execution_mode
from .models import (
    AnimationValidationResult,
    FileResult,
    FrameDefinition,
    HealthResult,
    LayerDefinition,
    MutationResult,
    PixelInput,
    RenderResult,
    SpriteInfo,
    SpriteSheetResult,
)
from .paths import (
    RENDER_EXTENSIONS,
    SPRITE_DOCUMENT_EXTENSIONS,
    SPRITE_INPUT_EXTENSIONS,
    PathPolicy,
    publish_file,
    sha256_file,
    temporary_sibling,
)
from .process_runner import ProcessResult, ProcessRunner

logger = logging.getLogger(__name__)

BRIDGE_PROTOCOL_VERSION = 1
MAX_CANVAS_DIMENSION = 4096
MAX_CANVAS_PIXELS = 16_777_216
MAX_FRAMES = 256
MAX_LAYERS = 128
MAX_PIXEL_EDITS = 10_000
MAX_VALIDATION_PIXEL_VISITS = 16_777_216
CANVAS_ANCHORS = frozenset(
    {
        "top-left",
        "top",
        "top-right",
        "left",
        "center",
        "right",
        "bottom-left",
        "bottom",
        "bottom-right",
    }
)


class AsepriteAdapter:
    """Execute supported Aseprite operations behind safety boundaries."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.paths = PathPolicy(settings.allowed_roots)
        self.runner = ProcessRunner(settings.timeout_seconds, settings.max_capture_bytes)
        self.bridge_path = Path(__file__).with_name("scripts") / "bridge.lua"
        self.execution_mode = resolve_execution_mode(
            settings.execution_mode, settings.aseprite_executable
        )
        self.process_paths = ProcessPathMapper(self.execution_mode)
        self.bridge_temp_root = self._select_bridge_temp_root()
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        self._path_locks: dict[Path, asyncio.Lock] = {}
        logger.info(
            "Aseprite adapter initialized execution_mode=%s executable=%s allowed_roots=%d",
            self.execution_mode,
            settings.aseprite_executable or "not found",
            len(settings.allowed_roots),
        )
        logger.debug(
            "Aseprite adapter paths bridge=%s bridge_temp_root=%s",
            self.bridge_path,
            self.bridge_temp_root or "system default",
        )

    def _select_bridge_temp_root(self) -> Path | None:
        if self.settings.bridge_temp_root is not None:
            return self.settings.bridge_temp_root
        if self.execution_mode == "wsl-windows":
            for root in self.settings.allowed_roots:
                if ProcessPathMapper.is_windows_mounted(root):
                    return root
        return None

    def _process_path(self, path: Path) -> str:
        return self.process_paths.map(path)

    def _executable(self) -> Path:
        executable = self.settings.aseprite_executable
        if executable is None:
            raise AsepriteMCPError(
                "ASEPRITE_NOT_FOUND",
                "Aseprite was not found; configure --aseprite or ASEPRITE_EXECUTABLE",
            )
        return executable

    async def _run(self, arguments: list[str], *, operation: str) -> ProcessResult:
        logger.debug("Waiting for Aseprite process slot operation=%s", operation)
        async with self._semaphore:
            logger.debug("Acquired Aseprite process slot operation=%s", operation)
            return await self.runner.run(
                self._executable(), arguments, operation=operation
            )

    @asynccontextmanager
    async def _locked(self, paths: Iterable[Path]) -> AsyncIterator[None]:
        locks = [self._path_locks.setdefault(path, asyncio.Lock()) for path in sorted(set(paths))]
        for lock in locks:
            await lock.acquire()
        try:
            yield
        finally:
            for lock in reversed(locks):
                lock.release()

    async def _bridge(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.bridge_path.is_file():
            raise AsepriteMCPError("BRIDGE_PROTOCOL_ERROR", "Packaged Lua bridge is missing")

        logger.info("Starting Lua bridge operation=%s", operation)
        with tempfile.TemporaryDirectory(
            prefix="aseprite-mcp-", dir=self.bridge_temp_root
        ) as temporary_directory:
            temp_root = Path(temporary_directory)
            request_path = temp_root / "request.json"
            response_path = temp_root / "response.json"
            runtime_bridge_path = self.bridge_path
            if self.execution_mode == "wsl-windows":
                runtime_bridge_path = temp_root / "bridge.lua"
                shutil.copyfile(self.bridge_path, runtime_bridge_path)
            logger.debug(
                "Prepared bridge workspace operation=%s directory=%s runtime_script=%s",
                operation,
                temp_root,
                runtime_bridge_path,
            )
            request_characters = request_path.write_text(
                json.dumps(
                    {
                        "protocol_version": BRIDGE_PROTOCOL_VERSION,
                        "operation": operation,
                        "input": payload,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            logger.debug(
                "Wrote bridge request operation=%s characters=%d",
                operation,
                request_characters,
            )
            result = await self._run(
                [
                    "--batch",
                    "--noinapp",
                    "--script-param",
                    f"request={self._process_path(request_path)}",
                    "--script-param",
                    f"response={self._process_path(response_path)}",
                    "--script",
                    self._process_path(runtime_bridge_path),
                ],
                operation=f"bridge:{operation}",
            )
            if not response_path.is_file():
                diagnostic = (result.stderr or result.stdout).strip()
                diagnostic_suffix = f": {diagnostic}" if diagnostic else ""
                raise AsepriteMCPError(
                    "BRIDGE_PROTOCOL_ERROR",
                    f"Aseprite did not produce a bridge response{diagnostic_suffix}",
                )
            if response_path.stat().st_size > self.settings.max_capture_bytes:
                raise AsepriteMCPError("LIMIT_EXCEEDED", "Bridge response exceeded the size limit")
            try:
                logger.debug(
                    "Reading bridge response operation=%s bytes=%d",
                    operation,
                    response_path.stat().st_size,
                )
                response: Any = json.loads(response_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                raise AsepriteMCPError(
                    "BRIDGE_PROTOCOL_ERROR", "Aseprite returned malformed bridge JSON"
                ) from exc
            if not isinstance(response, dict) or not isinstance(response.get("ok"), bool):
                raise AsepriteMCPError(
                    "BRIDGE_PROTOCOL_ERROR", "Aseprite returned an invalid bridge envelope"
                )
            if not response["ok"]:
                error = response.get("error", {})
                code = error.get("code", "ASEPRITE_FAILED")
                message = str(error.get("message", "Aseprite bridge operation failed"))
                logger.debug("Aseprite bridge failure: %s", message)
                public_message = message.splitlines()[0]
                raise AsepriteMCPError(str(code), public_message)
            bridge_result = response.get("result")
            if not isinstance(bridge_result, dict):
                raise AsepriteMCPError(
                    "BRIDGE_PROTOCOL_ERROR", "Aseprite bridge result must be an object"
                )
            logger.info("Completed Lua bridge operation=%s", operation)
            return bridge_result

    async def health(self, server_version: str) -> HealthResult:
        logger.info("Running Aseprite health check server_version=%s", server_version)
        executable = self.settings.aseprite_executable
        if executable is None:
            logger.warning("Health check failed because no Aseprite executable was found")
            return HealthResult(
                ok=False,
                server_version=server_version,
                executable_path=None,
                aseprite_version=None,
                api_version=None,
                allowed_roots=[str(path) for path in self.settings.allowed_roots],
                timeout_seconds=self.settings.timeout_seconds,
                max_concurrency=self.settings.max_concurrency,
                execution_mode=self.execution_mode,
                bridge_temp_root=(
                    str(self.bridge_temp_root) if self.bridge_temp_root is not None else None
                ),
                error="ASEPRITE_NOT_FOUND: configure --aseprite or ASEPRITE_EXECUTABLE",
            )
        try:
            version_result = await self._run(["--version"], operation="version")
            bridge_health = await self._bridge("health", {})
            version = version_result.stdout.strip() or str(
                bridge_health.get("aseprite_version", "")
            )
            api_version = int(bridge_health["api_version"])
            logger.info(
                "Aseprite health check passed version=%s api_version=%d", version, api_version
            )
            return HealthResult(
                ok=True,
                server_version=server_version,
                executable_path=str(executable),
                aseprite_version=version,
                api_version=api_version,
                allowed_roots=[str(path) for path in self.settings.allowed_roots],
                timeout_seconds=self.settings.timeout_seconds,
                max_concurrency=self.settings.max_concurrency,
                execution_mode=self.execution_mode,
                bridge_temp_root=(
                    str(self.bridge_temp_root) if self.bridge_temp_root is not None else None
                ),
            )
        except AsepriteMCPError as exc:
            logger.warning(
                "Aseprite health check failed code=%s message=%s", exc.code, exc.message
            )
            return HealthResult(
                ok=False,
                server_version=server_version,
                executable_path=str(executable),
                aseprite_version=None,
                api_version=None,
                allowed_roots=[str(path) for path in self.settings.allowed_roots],
                timeout_seconds=self.settings.timeout_seconds,
                max_concurrency=self.settings.max_concurrency,
                execution_mode=self.execution_mode,
                bridge_temp_root=(
                    str(self.bridge_temp_root) if self.bridge_temp_root is not None else None
                ),
                error=str(exc),
            )

    async def inspect_sprite(
        self, source_path: str, *, include_palette_colors: bool = False
    ) -> SpriteInfo:
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        logger.info(
            "Inspecting sprite source=%s include_palette_colors=%s",
            source,
            include_palette_colors,
        )
        async with self._locked([source]):
            result = await self._bridge(
                "inspect",
                {
                    "source_path": self._process_path(source),
                    "include_palette_colors": include_palette_colors,
                },
            )
            result["source_path"] = str(source)
            result["sha256"] = sha256_file(source)
            sprite = SpriteInfo.model_validate(result)
            logger.info(
                "Sprite inspection completed source=%s size=%dx%d frames=%d",
                source,
                sprite.width,
                sprite.height,
                sprite.frame_count,
            )
            return sprite

    @staticmethod
    def _validate_source_hash(source: Path, expected_source_hash: str | None) -> str:
        actual = sha256_file(source)
        if expected_source_hash is not None and actual.lower() != expected_source_hash.lower():
            raise AsepriteMCPError(
                "SOURCE_CHANGED", "Source hash does not match expected_source_hash"
            )
        return actual

    async def render(
        self,
        source_path: str,
        output_path: str,
        *,
        frame: int | None,
        tag: str | None,
        layers: list[str],
        scale: float,
        overwrite: bool,
    ) -> RenderResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        output = self.paths.output_file(
            output_path, extensions=RENDER_EXTENSIONS, overwrite=overwrite
        )
        output_format = cast(Literal["png", "gif"], output.suffix.lower().lstrip("."))
        if frame is not None and tag is not None:
            raise AsepriteMCPError("INVALID_SELECTOR", "frame and tag are mutually exclusive")
        if output_format == "png" and tag is not None:
            raise AsepriteMCPError("INVALID_SELECTOR", "PNG rendering does not accept a tag")
        if frame is not None and frame < 0:
            raise AsepriteMCPError("INVALID_SELECTOR", "frame must be zero or greater")
        if not 0.1 <= scale <= 16:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "scale must be between 0.1 and 16")

        temporary = temporary_sibling(output)
        logger.info(
            "Rendering sprite source=%s output=%s format=%s frame=%s tag=%s "
            "scale=%s layers=%d overwrite=%s",
            source,
            output,
            output_format,
            frame,
            tag,
            f"{scale:g}",
            len(layers),
            overwrite,
        )
        arguments = ["--batch", "--noinapp"]
        for layer in layers:
            arguments.extend(["--layer", layer])
        if tag is not None:
            arguments.extend(["--tag", tag])
        selected_frame = frame
        if output_format == "png" and selected_frame is None:
            selected_frame = 0
        if selected_frame is not None:
            arguments.extend(["--frame-range", f"{selected_frame},{selected_frame}"])
        arguments.append(self._process_path(source))
        if scale != 1:
            arguments.extend(["--scale", f"{scale:g}"])
        arguments.extend(["--save-as", self._process_path(temporary)])

        async with self._locked([source, output]):
            try:
                await self._run(arguments, operation="render")
                if not temporary.is_file():
                    raise AsepriteMCPError(
                        "ASEPRITE_FAILED", "Aseprite did not create the rendered file"
                    )
                publish_file(temporary, output)
            finally:
                temporary.unlink(missing_ok=True)
        render_result = RenderResult(
            output_path=str(output),
            byte_size=output.stat().st_size,
            sha256=sha256_file(output),
            format=output_format,
            frame=selected_frame,
            tag=tag,
            scale=scale,
        )
        logger.info(
            "Render completed output=%s bytes=%d", output, render_result.byte_size
        )
        return render_result

    async def export_sprite_sheet(
        self,
        source_path: str,
        image_output_path: str,
        data_output_path: str,
        *,
        layout: Literal["horizontal", "vertical", "rows", "columns", "packed"],
        tag: str | None,
        layers: list[str],
        trim: bool,
        extrude: bool,
        border_padding: int,
        shape_padding: int,
        inner_padding: int,
        overwrite: bool,
    ) -> SpriteSheetResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        image_output = self.paths.output_file(
            image_output_path, extensions=frozenset({".png"}), overwrite=overwrite
        )
        data_output = self.paths.output_file(
            data_output_path, extensions=frozenset({".json"}), overwrite=overwrite
        )
        if image_output == data_output:
            raise AsepriteMCPError("PATH_NOT_ALLOWED", "Image and data outputs must differ")
        for value in (border_padding, shape_padding, inner_padding):
            if not 0 <= value <= 1024:
                raise AsepriteMCPError("LIMIT_EXCEEDED", "padding must be between 0 and 1024")

        image_temporary = temporary_sibling(image_output)
        data_temporary = temporary_sibling(data_output)
        logger.info(
            "Exporting sprite sheet source=%s image=%s data=%s layout=%s tag=%s "
            "layers=%d overwrite=%s",
            source,
            image_output,
            data_output,
            layout,
            tag,
            len(layers),
            overwrite,
        )
        arguments = ["--batch", "--noinapp"]
        for layer in layers:
            arguments.extend(["--layer", layer])
        if tag is not None:
            arguments.extend(["--tag", tag])
        arguments.append(self._process_path(source))
        arguments.extend(["--sheet-type", layout])
        if trim:
            arguments.append("--trim")
        if extrude:
            arguments.append("--extrude")
        if border_padding:
            arguments.extend(["--border-padding", str(border_padding)])
        if shape_padding:
            arguments.extend(["--shape-padding", str(shape_padding)])
        if inner_padding:
            arguments.extend(["--inner-padding", str(inner_padding)])
        arguments.extend(
            [
                "--sheet",
                self._process_path(image_temporary),
                "--format",
                "json-array",
                "--data",
                self._process_path(data_temporary),
            ]
        )

        async with self._locked([source, image_output, data_output]):
            try:
                await self._run(arguments, operation="export_sprite_sheet")
                if not image_temporary.is_file() or not data_temporary.is_file():
                    raise AsepriteMCPError(
                        "ASEPRITE_FAILED", "Aseprite did not create both sprite-sheet outputs"
                    )
                try:
                    sheet_data = json.loads(data_temporary.read_text(encoding="utf-8-sig"))
                except json.JSONDecodeError as exc:
                    raise AsepriteMCPError(
                        "ASEPRITE_FAILED", "Aseprite produced invalid sprite-sheet JSON"
                    ) from exc
                frame_count = len(sheet_data.get("frames", []))
                publish_file(image_temporary, image_output)
                publish_file(data_temporary, data_output)
            finally:
                image_temporary.unlink(missing_ok=True)
                data_temporary.unlink(missing_ok=True)

        sheet_result = SpriteSheetResult(
            image=self._file_result(image_output),
            data=self._file_result(data_output),
            layout=layout,
            frame_count=frame_count,
        )
        logger.info(
            "Sprite-sheet export completed image=%s data=%s frames=%d",
            image_output,
            data_output,
            frame_count,
        )
        return sheet_result

    async def create_sprite(
        self,
        output_path: str,
        *,
        width: int,
        height: int,
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

    async def _bridge_mutation(
        self,
        operation: str,
        source_path: str,
        output_path: str,
        *,
        overwrite: bool,
        expected_source_hash: str | None,
        payload: dict[str, Any],
    ) -> MutationResult:
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
            "Starting sprite mutation operation=%s source=%s output=%s overwrite=%s hash_guard=%s",
            operation,
            source,
            output,
            overwrite,
            expected_source_hash is not None,
        )
        async with self._locked([source, output]):
            source_hash = self._validate_source_hash(source, expected_source_hash)
            try:
                await self._bridge(
                    operation,
                    {
                        "source_path": self._process_path(source),
                        "output_path": self._process_path(temporary),
                        **payload,
                    },
                )
                if not temporary.is_file():
                    raise AsepriteMCPError(
                        "ASEPRITE_FAILED", "Aseprite did not create the edited sprite document"
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
        logger.info("Sprite mutation completed operation=%s output=%s", operation, output)
        return mutation

    @staticmethod
    def _file_result(path: Path) -> FileResult:
        return FileResult(
            output_path=str(path), byte_size=path.stat().st_size, sha256=sha256_file(path)
        )

    @staticmethod
    def _validate_creation_limits(
        width: int,
        height: int,
        layers: list[LayerDefinition],
        frames: list[FrameDefinition],
        pixels: list[PixelInput],
    ) -> None:
        if width < 1 or height < 1:
            raise AsepriteMCPError("INVALID_INPUT", "width and height must be positive")
        if width > MAX_CANVAS_DIMENSION or height > MAX_CANVAS_DIMENSION:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", f"Canvas dimensions may not exceed {MAX_CANVAS_DIMENSION}"
            )
        if width * height > MAX_CANVAS_PIXELS:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "Canvas pixel count exceeds the limit")
        if not layers:
            raise AsepriteMCPError("INVALID_INPUT", "At least one layer is required")
        if len(layers) > MAX_LAYERS:
            raise AsepriteMCPError("LIMIT_EXCEEDED", f"At most {MAX_LAYERS} layers are allowed")
        if not frames:
            raise AsepriteMCPError("INVALID_INPUT", "At least one frame is required")
        if len(frames) > MAX_FRAMES:
            raise AsepriteMCPError("LIMIT_EXCEEDED", f"At most {MAX_FRAMES} frames are allowed")
        if len(pixels) > MAX_PIXEL_EDITS:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", f"At most {MAX_PIXEL_EDITS} initial pixels are allowed"
            )

    @staticmethod
    def _validate_canvas_dimensions(width: int, height: int) -> None:
        if width < 1 or height < 1:
            raise AsepriteMCPError("INVALID_INPUT", "width and height must be positive")
        if width > MAX_CANVAS_DIMENSION or height > MAX_CANVAS_DIMENSION:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", f"Canvas dimensions may not exceed {MAX_CANVAS_DIMENSION}"
            )
        if width * height > MAX_CANVAS_PIXELS:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "Canvas pixel count exceeds the limit")
