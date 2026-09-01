"""Typed, policy-enforcing adapter around the Aseprite CLI and Lua bridge."""

from __future__ import annotations
import logging
import json
import tempfile
from pathlib import Path
from typing import Literal, cast
from ..errors import AsepriteMCPError
from ..models import (
    AtlasResult,
    BatchExportItem,
    BatchExportJob,
    BatchExportResult,
    BitmapFontResult,
    BitmapGlyphInput,
    ContactSheetResult,
    FrameExportInput,
    FrameExportItem,
    FrameExportResult,
    RenderResult,
    SliceExtractionInput,
    SliceExtractionItem,
    SliceExtractionResult,
    SpriteSheetResult,
)
from ..paths import (
    RENDER_EXTENSIONS,
    SPRITE_DOCUMENT_EXTENSIONS,
    SPRITE_INPUT_EXTENSIONS,
    publish_file,
    sha256_file,
    temporary_sibling,
)
from .runtime import AsepriteRuntime, MAX_CANVAS_PIXELS

logger = logging.getLogger(__name__)


class ExportService(AsepriteRuntime):
    """Export Aseprite operations."""

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
        if image_output == data_output or image_output in sources or data_output in sources:
            raise AsepriteMCPError(
                "PATH_NOT_ALLOWED", "Atlas outputs must differ from each other and every source"
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

    async def preview(
        self,
        source_path: str,
        *,
        mode: Literal["frame", "sheet"],
        frame: int,
        layout: Literal["horizontal", "vertical", "rows", "columns", "packed"],
        tag: str | None,
        layers: list[str],
        scale: float,
    ) -> bytes:
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        if frame < 0:
            raise AsepriteMCPError("INVALID_SELECTOR", "frame must be zero or greater")
        if mode == "frame" and tag is not None:
            raise AsepriteMCPError("INVALID_SELECTOR", "frame previews do not accept a tag")
        if not 0.1 <= scale <= 16:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "scale must be between 0.1 and 16")
        logger.info(
            "Previewing sprite source=%s mode=%s frame=%d tag=%s layers=%d scale=%s",
            source, mode, frame, tag, len(layers), f"{scale:g}",
        )
        with tempfile.TemporaryDirectory(
            prefix="aseprite-preview-", dir=self.bridge_temp_root
        ) as temporary_directory:
            output = Path(temporary_directory) / "preview.png"
            arguments = ["--batch", "--noinapp"]
            for layer in layers:
                arguments.extend(["--layer", layer])
            if tag is not None:
                arguments.extend(["--tag", tag])
            arguments.append(self._process_path(source))
            if scale != 1:
                arguments.extend(["--scale", f"{scale:g}"])
            if mode == "frame":
                arguments.extend(
                    ["--frame-range", f"{frame},{frame}", "--save-as", self._process_path(output)]
                )
            else:
                arguments.extend(
                    ["--sheet-type", layout, "--sheet", self._process_path(output)]
                )
            async with self._locked([source]):
                await self._run(arguments, operation="preview")
            if not output.is_file():
                raise AsepriteMCPError("ASEPRITE_FAILED", "Aseprite did not create the preview")
            byte_size = output.stat().st_size
            if byte_size > self.settings.max_capture_bytes:
                raise AsepriteMCPError(
                    "LIMIT_EXCEEDED",
                    "Preview exceeds the inline response size limit; reduce scale or frame count",
                )
            data = output.read_bytes()
        logger.info("Preview completed source=%s bytes=%d", source, len(data))
        return data

    async def render_contact_sheet(
        self,
        source_path: str,
        output_path: str,
        *,
        columns: int,
        scale: int,
        overwrite: bool,
    ) -> ContactSheetResult:
        if not 1 <= columns <= 64 or not 1 <= scale <= 16:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "columns or scale exceeds the limit")
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        output = self.paths.output_file(
            output_path, extensions=frozenset({".png"}), overwrite=overwrite
        )
        temporary = temporary_sibling(output)
        async with self._locked([source, output]):
            try:
                result = await self._bridge(
                    "render_contact_sheet",
                    {
                        "source_path": self._process_path(source),
                        "output_path": self._process_path(temporary),
                        "columns": columns,
                        "scale": scale,
                        "max_pixels": MAX_CANVAS_PIXELS,
                    },
                )
                if not temporary.is_file():
                    raise AsepriteMCPError(
                        "ASEPRITE_FAILED", "Aseprite did not create the contact sheet"
                    )
                publish_file(temporary, output)
            finally:
                temporary.unlink(missing_ok=True)
        return ContactSheetResult(
            **self._file_result(output).model_dump(),
            frame_count=int(result["frame_count"]),
            columns=int(result["columns"]),
            rows=int(result["rows"]),
            scale=scale,
        )

    async def pack_atlas(
        self,
        source_paths: list[str],
        image_output_path: str,
        data_output_path: str,
        *,
        width: int,
        height: int,
        trim: bool,
        extrude: bool,
        border_padding: int,
        shape_padding: int,
        inner_padding: int,
        overwrite: bool,
    ) -> AtlasResult:
        if not 1 <= len(source_paths) <= 64:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "source_paths must contain 1 to 64 files")
        if width is not None and not 1 <= width <= 16_384:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "atlas width must be between 1 and 16384")
        if height is not None and not 1 <= height <= 16_384:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "atlas height must be between 1 and 16384")
        if any(value < 0 or value > 1024 for value in (
            border_padding, shape_padding, inner_padding
        )):
            raise AsepriteMCPError("LIMIT_EXCEEDED", "atlas padding must be between 0 and 1024")
        sources = [
            self.paths.existing_file(path, extensions=SPRITE_INPUT_EXTENSIONS)
            for path in source_paths
        ]
        image_output = self.paths.output_file(
            image_output_path, extensions=frozenset({".png"}), overwrite=overwrite
        )
        data_output = self.paths.output_file(
            data_output_path, extensions=frozenset({".json"}), overwrite=overwrite
        )
        image_temp, data_temp = temporary_sibling(image_output), temporary_sibling(data_output)
        arguments = ["--batch", "--noinapp", *[self._process_path(path) for path in sources]]
        arguments.append("--sheet-pack")
        if width is not None:
            arguments.extend(["--sheet-width", str(width)])
        if height is not None:
            arguments.extend(["--sheet-height", str(height)])
        if trim:
            arguments.append("--trim")
        if extrude:
            arguments.append("--extrude")
        for flag, value in (
            ("--border-padding", border_padding),
            ("--shape-padding", shape_padding),
            ("--inner-padding", inner_padding),
        ):
            if value:
                arguments.extend([flag, str(value)])
        arguments.extend([
            "--sheet", self._process_path(image_temp), "--format", "json-array",
            "--data", self._process_path(data_temp),
        ])
        async with self._locked([*sources, image_output, data_output]):
            try:
                await self._run(arguments, operation="pack_atlas")
                if not image_temp.is_file() or not data_temp.is_file():
                    raise AsepriteMCPError(
                        "ASEPRITE_FAILED", "Aseprite did not create atlas outputs"
                    )
                metadata = json.loads(data_temp.read_text(encoding="utf-8-sig"))
                frame_count = len(metadata.get("frames", []))
                atlas_size = metadata.get("meta", {}).get("size", {})
                atlas_width = int(atlas_size.get("w", 0))
                atlas_height = int(atlas_size.get("h", 0))
                if (
                    atlas_width < 1
                    or atlas_height < 1
                    or atlas_width > 16_384
                    or atlas_height > 16_384
                    or atlas_width * atlas_height > MAX_CANVAS_PIXELS
                ):
                    raise AsepriteMCPError(
                        "LIMIT_EXCEEDED", "Generated atlas dimensions exceed the server limit"
                    )
                publish_file(image_temp, image_output)
                publish_file(data_temp, data_output)
            except json.JSONDecodeError as exc:
                raise AsepriteMCPError(
                    "ASEPRITE_FAILED", "Aseprite produced invalid atlas JSON"
                ) from exc
            finally:
                image_temp.unlink(missing_ok=True)
                data_temp.unlink(missing_ok=True)
        return AtlasResult(
            image=self._file_result(image_output), data=self._file_result(data_output),
            source_count=len(sources), frame_count=frame_count,
        )

    async def extract_slices(
        self, source_path: str, *, extractions: list[SliceExtractionInput], overwrite: bool,
    ) -> SliceExtractionResult:
        if not 1 <= len(extractions) <= 256:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "extractions must contain 1 to 256 items")
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        outputs = [self.paths.output_file(
            item.output_path, extensions=frozenset({".png"}), overwrite=overwrite
        ) for item in extractions]
        if len(set(outputs)) != len(outputs):
            raise AsepriteMCPError("INVALID_INPUT", "slice output paths must be unique")
        if source in outputs:
            raise AsepriteMCPError("PATH_NOT_ALLOWED", "slice output cannot replace its source")
        temporaries = [temporary_sibling(path) for path in outputs]
        async with self._locked([source, *outputs]):
            try:
                result = await self._bridge("extract_slices", {
                    "source_path": self._process_path(source),
                    "extractions": [{"name": item.name, "frame": item.frame,
                        "output_path": self._process_path(temp)}
                        for item, temp in zip(extractions, temporaries, strict=True)],
                })
                if not all(path.is_file() for path in temporaries):
                    raise AsepriteMCPError("ASEPRITE_FAILED", "Aseprite did not create every slice")
                for temporary, output in zip(temporaries, outputs, strict=True):
                    publish_file(temporary, output)
            finally:
                for temporary in temporaries:
                    temporary.unlink(missing_ok=True)
        items = [SliceExtractionItem(
            name=extraction.name, frame=extraction.frame, file=self._file_result(output),
            bounds=result["items"][index]["bounds"], pivot=result["items"][index].get("pivot"),
        ) for index, (extraction, output) in enumerate(zip(extractions, outputs, strict=True))]
        return SliceExtractionResult(
            source_path=str(source), sha256=sha256_file(source), items=items
        )

    async def batch_export(self, jobs: list[BatchExportJob]) -> BatchExportResult:
        if not 1 <= len(jobs) <= 64:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "jobs must contain 1 to 64 items")
        items: list[BatchExportItem] = []
        for job in jobs:
            try:
                result = await self.export_sprite_sheet(
                    job.source_path, job.image_output_path, job.data_output_path,
                    layout=job.layout, tag=job.tag, layers=job.layers, trim=job.trim,
                    extrude=job.extrude, border_padding=job.border_padding,
                    shape_padding=job.shape_padding, inner_padding=job.inner_padding,
                    overwrite=job.overwrite,
                )
                items.append(BatchExportItem(source_path=job.source_path, ok=True, result=result))
            except AsepriteMCPError as exc:
                items.append(BatchExportItem(
                    source_path=job.source_path, ok=False,
                    error_code=exc.code, error_message=exc.message,
                ))
        succeeded = sum(item.ok for item in items)
        return BatchExportResult(succeeded=succeeded, failed=len(items)-succeeded, items=items)

    async def export_frames(
        self, source_path: str, *, exports: list[FrameExportInput], overwrite: bool,
    ) -> FrameExportResult:
        if not 1 <= len(exports) <= 256:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "exports must contain 1 to 256 items")
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        outputs = [self.paths.output_file(
            item.output_path, extensions=frozenset({".png"}), overwrite=overwrite
        ) for item in exports]
        if len(set(outputs)) != len(outputs) or source in outputs:
            raise AsepriteMCPError(
                "PATH_NOT_ALLOWED", "frame outputs must be unique and differ from the source"
            )
        temporaries = [temporary_sibling(path) for path in outputs]
        async with self._locked([source, *outputs]):
            try:
                await self._bridge("export_frames", {
                    "source_path": self._process_path(source),
                    "exports": [{"frame": item.frame, "output_path": self._process_path(temp)}
                        for item, temp in zip(exports, temporaries, strict=True)],
                })
                if not all(path.is_file() for path in temporaries):
                    raise AsepriteMCPError("ASEPRITE_FAILED", "Aseprite did not export every frame")
                for temporary, output in zip(temporaries, outputs, strict=True):
                    publish_file(temporary, output)
            finally:
                for temporary in temporaries:
                    temporary.unlink(missing_ok=True)
        return FrameExportResult(
            source_path=str(source), sha256=sha256_file(source),
            items=[FrameExportItem(frame=item.frame, file=self._file_result(output))
                   for item, output in zip(exports, outputs, strict=True)],
        )

    async def preview_nine_slice(
        self, source_path: str, *, slice_name: str, frame: int, width: int, height: int,
    ) -> bytes:
        source = self.paths.existing_file(source_path, extensions=SPRITE_DOCUMENT_EXTENSIONS)
        with tempfile.TemporaryDirectory(
            prefix="aseprite-nine-slice-preview-", dir=self.bridge_temp_root
        ) as directory:
            output = Path(directory) / "preview.png"
            async with self._locked([source]):
                await self._bridge("preview_nine_slice", {
                    "source_path": self._process_path(source), "slice": slice_name,
                    "frame": frame, "width": width, "height": height,
                    "output_path": self._process_path(output),
                    "max_pixels": MAX_CANVAS_PIXELS,
                })
            if not output.is_file():
                raise AsepriteMCPError("ASEPRITE_FAILED", "nine-slice preview was not created")
            if output.stat().st_size > self.settings.max_capture_bytes:
                raise AsepriteMCPError("LIMIT_EXCEEDED", "nine-slice preview exceeds inline limit")
            return output.read_bytes()

    async def export_bitmap_font(
        self, source_path: str, image_output_path: str, data_output_path: str, *,
        glyphs: list[BitmapGlyphInput], font_name: str, line_height: int,
        columns: int, padding: int, overwrite: bool,
    ) -> BitmapFontResult:
        if not 1 <= len(glyphs) <= 512:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "glyphs must contain 1 to 512 entries")
        codepoints = [glyph.codepoint for glyph in glyphs]
        if len(set(codepoints)) != len(codepoints):
            raise AsepriteMCPError("INVALID_INPUT", "glyph codepoints must be unique")
        if any(0xD800 <= codepoint <= 0xDFFF for codepoint in codepoints):
            raise AsepriteMCPError("INVALID_INPUT", "surrogate codepoints are not valid Unicode")
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        image_output = self.paths.output_file(
            image_output_path, extensions=frozenset({".png"}), overwrite=overwrite
        )
        data_output = self.paths.output_file(
            data_output_path, extensions=frozenset({".json"}), overwrite=overwrite
        )
        if len({source, image_output, data_output}) != 3:
            raise AsepriteMCPError("PATH_NOT_ALLOWED", "font input and outputs must be distinct")
        image_temp, data_temp = temporary_sibling(image_output), temporary_sibling(data_output)
        async with self._locked([source, image_output, data_output]):
            try:
                await self._bridge("export_bitmap_font", {
                    "source_path": self._process_path(source),
                    "image_output_path": self._process_path(image_temp),
                    "data_output_path": self._process_path(data_temp),
                    "glyphs": [glyph.model_dump() for glyph in glyphs],
                    "font_name": font_name, "line_height": line_height,
                    "columns": columns, "padding": padding,
                    "max_pixels": MAX_CANVAS_PIXELS,
                })
                if not image_temp.is_file() or not data_temp.is_file():
                    raise AsepriteMCPError(
                        "ASEPRITE_FAILED", "bitmap-font outputs were not created"
                    )
                publish_file(image_temp, image_output)
                publish_file(data_temp, data_output)
            finally:
                image_temp.unlink(missing_ok=True)
                data_temp.unlink(missing_ok=True)
        return BitmapFontResult(
            image=self._file_result(image_output), data=self._file_result(data_output),
            glyph_count=len(glyphs), line_height=line_height,
        )
