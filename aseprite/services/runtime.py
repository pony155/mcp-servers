"""Typed, policy-enforcing adapter around the Aseprite CLI and Lua bridge."""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal, cast

from ..config import Settings
from ..errors import AsepriteMCPError
from ..interop import ProcessPathMapper, resolve_execution_mode
from ..models import (
    AnimationFrameDefinition,
    AnimationEventEditOperation,
    AnimationTagDefinition,
    AnimationValidationResult,
    AssetSetValidationResult,
    AssetValidationItem,
    AtlasResult,
    BatchExportItem,
    BatchExportJob,
    BatchExportResult,
    BitmapFontResult,
    BitmapGlyphInput,
    BlendModeEditOperation,
    CelEditOperation,
    CelInspectionResult,
    CompositedPixelReadResult,
    ContactSheetResult,
    CollisionMaskResult,
    CollisionPolygonResult,
    ExportProfile,
    ExportProfileIssue,
    ExportProfileValidationResult,
    FileResult,
    FrameComparisonResult,
    FrameExportInput,
    FrameExportItem,
    FrameExportResult,
    FrameEditOperation,
    FrameDefinition,
    HealthResult,
    LayerDefinition,
    LayerEditOperation,
    LoopTransitionValidationResult,
    MotionReportResult,
    MutationResult,
    PaletteAnalysisResult,
    PaletteColorInput,
    PaletteEntryEditOperation,
    PixelInput,
    PixelArtValidationResult,
    PixelReadResult,
    PixelRunInput,
    PropertyEditOperation,
    RectangleInput,
    RenderResult,
    SelectionEditOperation,
    ShapeInput,
    SliceEditOperation,
    SliceExtractionInput,
    SliceExtractionItem,
    SliceExtractionResult,
    SpriteComparisonResult,
    SpriteInfo,
    SpriteSheetResult,
    StrokeInput,
    TagEditOperation,
    TilemapCellInput,
    TileMetadataEditOperation,
    TileMetadataResult,
    TilesetEditOperation,
    TilesetExportResult,
    TilesetInspectionResult,
    TilesetValidationResult,
)
from ..paths import (
    RENDER_EXTENSIONS,
    SPRITE_DOCUMENT_EXTENSIONS,
    SPRITE_INPUT_EXTENSIONS,
    PathPolicy,
    publish_file,
    sha256_file,
    temporary_sibling,
)
from ..process_runner import ProcessResult, ProcessRunner

logger = logging.getLogger(__name__)

BRIDGE_PROTOCOL_VERSION = 1
MAX_CANVAS_DIMENSION = 4096
MAX_CANVAS_PIXELS = 16_777_216
MAX_FRAMES = 256
MAX_LAYERS = 128
MAX_PIXEL_EDITS = 10_000
MAX_ANIMATION_PIXEL_EDITS = 100_000
MAX_VALIDATION_PIXEL_VISITS = 16_777_216
MAX_PIXEL_READS = 65_536
MAX_PIXEL_RUN_EDITS = 100_000
PALETTE_EXTENSIONS = frozenset({".act", ".col", ".gpl", ".hex", ".pal", ".png"})
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

BRIDGE_FRAGMENT_NAMES = (
    "runtime.lua",
    "core.lua",
    "pixels.lua",
    "documents.lua",
    "palettes.lua",
    "animation.lua",
    "tiles.lua",
    "export.lua",
    "validation.lua",
    "dispatch.lua",
)



class AsepriteRuntime:
    """Shared process, path, locking, and bridge runtime."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.paths = PathPolicy(settings.allowed_roots)
        self.runner = ProcessRunner(settings.timeout_seconds, settings.max_capture_bytes)
        self.bridge_directory = Path(__file__).parent.parent / "scripts" / "bridge"
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
            "Aseprite adapter paths bridge_directory=%s bridge_temp_root=%s",
            self.bridge_directory,
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
        fragment_paths = [self.bridge_directory / name for name in BRIDGE_FRAGMENT_NAMES]
        missing = [path.name for path in fragment_paths if not path.is_file()]
        if missing:
            raise AsepriteMCPError(
                "BRIDGE_PROTOCOL_ERROR",
                f"Packaged Lua bridge fragments are missing: {', '.join(missing)}",
            )

        logger.info("Starting Lua bridge operation=%s", operation)
        with tempfile.TemporaryDirectory(
            prefix="aseprite-mcp-", dir=self.bridge_temp_root
        ) as temporary_directory:
            temp_root = Path(temporary_directory)
            request_path = temp_root / "request.json"
            response_path = temp_root / "response.json"
            runtime_bridge_path = temp_root / "bridge.lua"
            runtime_bridge_path.write_text(
                "\n".join(path.read_text(encoding="utf-8") for path in fragment_paths),
                encoding="utf-8",
            )
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

    @staticmethod
    def _validate_source_hash(source: Path, expected_source_hash: str | None) -> str:
        actual = sha256_file(source)
        if expected_source_hash is not None and actual.lower() != expected_source_hash.lower():
            raise AsepriteMCPError(
                "SOURCE_CHANGED", "Source hash does not match expected_source_hash"
            )
        return actual

    async def _bridge_mutation(
        self,
        operation: str,
        source_path: str,
        output_path: str,
        *,
        overwrite: bool,
        expected_source_hash: str | None,
        payload: dict[str, Any],
        additional_lock_paths: list[Path] | None = None,
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
        async with self._locked([source, output, *(additional_lock_paths or [])]):
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

    @classmethod
    def _validate_animation_creation(
        cls,
        width: int,
        height: int,
        layers: list[LayerDefinition],
        frames: list[AnimationFrameDefinition],
        tags: list[AnimationTagDefinition],
    ) -> None:
        cls._validate_canvas_dimensions(width, height)
        if not layers:
            raise AsepriteMCPError("INVALID_INPUT", "At least one layer is required")
        if len(layers) > MAX_LAYERS:
            raise AsepriteMCPError("LIMIT_EXCEEDED", f"At most {MAX_LAYERS} layers are allowed")
        layer_names = [layer.name for layer in layers]
        if len(set(layer_names)) != len(layer_names):
            raise AsepriteMCPError("INVALID_INPUT", "Animation layer names must be unique")
        if not frames:
            raise AsepriteMCPError("INVALID_INPUT", "At least one animation frame is required")
        if len(frames) > MAX_FRAMES:
            raise AsepriteMCPError("LIMIT_EXCEEDED", f"At most {MAX_FRAMES} frames are allowed")
        if width * height * len(frames) > MAX_CANVAS_PIXELS:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED", "Animation canvas pixel count exceeds the limit"
            )

        total_pixels = 0
        known_layers = set(layer_names)
        for frame_index, frame in enumerate(frames):
            if len(frame.cels) > MAX_LAYERS:
                raise AsepriteMCPError(
                    "LIMIT_EXCEEDED", f"Frame {frame_index} contains too many cels"
                )
            cel_layers: set[str] = set()
            for cel in frame.cels:
                if cel.layer not in known_layers:
                    raise AsepriteMCPError(
                        "INVALID_SELECTOR",
                        f"Frame {frame_index} references unknown layer: {cel.layer}",
                    )
                if cel.layer in cel_layers:
                    raise AsepriteMCPError(
                        "INVALID_INPUT",
                        f"Frame {frame_index} contains more than one cel for layer: {cel.layer}",
                    )
                cel_layers.add(cel.layer)
                if len(cel.pixels) > MAX_PIXEL_EDITS:
                    raise AsepriteMCPError(
                        "LIMIT_EXCEEDED",
                        f"A cel may contain at most {MAX_PIXEL_EDITS} pixels",
                    )
                for pixel in cel.pixels:
                    if pixel.x >= width or pixel.y >= height:
                        raise AsepriteMCPError(
                            "INVALID_SELECTOR",
                            f"Frame {frame_index} contains a pixel outside the canvas",
                        )
                total_pixels += len(cel.pixels)
        if total_pixels > MAX_ANIMATION_PIXEL_EDITS:
            raise AsepriteMCPError(
                "LIMIT_EXCEEDED",
                f"An animation may contain at most {MAX_ANIMATION_PIXEL_EDITS} pixel edits",
            )

        tag_names: set[str] = set()
        for tag in tags:
            if tag.name in tag_names:
                raise AsepriteMCPError("INVALID_INPUT", "Animation tag names must be unique")
            tag_names.add(tag.name)
            if tag.from_frame > tag.to_frame:
                raise AsepriteMCPError(
                    "INVALID_SELECTOR", f"Tag {tag.name} starts after it ends"
                )
            if tag.to_frame >= len(frames):
                raise AsepriteMCPError(
                    "INVALID_SELECTOR", f"Tag {tag.name} references a frame outside the animation"
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
