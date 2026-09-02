"""Beat-'em-up combat metadata authoring and validation services."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Literal

from ..errors import AsepriteMCPError
from ..models import (
    ActionMetadataEditOperation,
    BeatEmUpBundleResult,
    CancelWindowEditOperation,
    CharacterRosterItem,
    CharacterRosterValidationResult,
    CombatActionValidationResult,
    CombatBoxEditOperation,
    CombatManifestResult,
    CombatSetValidationResult,
    CombatValidationIssue,
    FrameAnchorEditOperation,
    MutationResult,
    RootMotionEditOperation,
    StageGameplayValidationResult,
    StageGameplayZoneEditOperation,
)
from ..paths import (
    SPRITE_DOCUMENT_EXTENSIONS,
    SPRITE_INPUT_EXTENSIONS,
    publish_file,
    sha256_file,
    temporary_sibling,
)
from .runtime import AsepriteRuntime, MAX_CANVAS_PIXELS


class CombatService(AsepriteRuntime):
    """Edit, inspect, preview, and export engine-neutral combat metadata."""

    async def edit_combat_boxes(
        self, source_path: str, output_path: str, *,
        operations: list[CombatBoxEditOperation], overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        return await self._bridge_mutation(
            "edit_combat_boxes", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": [item.model_dump() for item in operations]},
        )

    async def edit_frame_anchors(
        self, source_path: str, output_path: str, *,
        operations: list[FrameAnchorEditOperation], overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        return await self._bridge_mutation(
            "edit_frame_anchors", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": [item.model_dump() for item in operations]},
        )

    async def edit_action_metadata(
        self, source_path: str, output_path: str, *,
        operations: list[ActionMetadataEditOperation], overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        return await self._bridge_mutation(
            "edit_action_metadata", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": [item.model_dump() for item in operations]},
        )

    async def edit_cancel_windows(
        self, source_path: str, output_path: str, *,
        operations: list[CancelWindowEditOperation], overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        return await self._bridge_mutation(
            "edit_cancel_windows", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": [item.model_dump() for item in operations]},
        )

    async def edit_root_motion(
        self, source_path: str, output_path: str, *,
        operations: list[RootMotionEditOperation], overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        return await self._bridge_mutation(
            "edit_root_motion", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": [item.model_dump() for item in operations]},
        )

    async def edit_stage_gameplay_zones(
        self, source_path: str, output_path: str, *,
        operations: list[StageGameplayZoneEditOperation], overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        return await self._bridge_mutation(
            "edit_stage_gameplay_zones", source_path, output_path, overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": [item.model_dump() for item in operations]},
        )

    async def preview_combat_overlay(
        self, source_path: str, *, action_tag: str, frame: int,
        kinds: list[str], scale: int,
    ) -> bytes:
        source = self.paths.existing_file(source_path, extensions=SPRITE_INPUT_EXTENSIONS)
        if source.suffix.lower() not in SPRITE_DOCUMENT_EXTENSIONS:
            raise AsepriteMCPError(
                "UNSUPPORTED_FORMAT",
                "combat metadata previews require an .ase or .aseprite document",
            )
        with tempfile.TemporaryDirectory(
            prefix="aseprite-combat-preview-", dir=self.bridge_temp_root
        ) as directory:
            output = Path(directory) / "preview.png"
            async with self._locked([source]):
                await self._bridge("preview_combat_overlay", {
                    "source_path": self._process_path(source), "action_tag": action_tag,
                    "frame": frame, "kinds": {kind: True for kind in kinds},
                    "scale": scale, "output_path": self._process_path(output),
                    "max_pixels": MAX_CANVAS_PIXELS,
                })
            if not output.is_file():
                raise AsepriteMCPError("ASEPRITE_FAILED", "combat overlay preview was not created")
            if output.stat().st_size > self.settings.max_capture_bytes:
                raise AsepriteMCPError(
                    "LIMIT_EXCEEDED", "combat overlay preview exceeds inline limit"
                )
            return output.read_bytes()

    async def preview_combat_animation(
        self, source_path: str, *, action_tag: str, kinds: list[str], scale: int,
    ) -> bytes:
        source = self.paths.existing_file(source_path, extensions=SPRITE_DOCUMENT_EXTENSIONS)
        with tempfile.TemporaryDirectory(
            prefix="aseprite-combat-animation-", dir=self.bridge_temp_root
        ) as directory:
            output = Path(directory) / "preview.gif"
            async with self._locked([source]):
                await self._bridge("preview_combat_animation", {
                    "source_path": self._process_path(source), "action_tag": action_tag,
                    "kinds": {kind: True for kind in kinds}, "scale": scale,
                    "output_path": self._process_path(output),
                    "max_pixels": MAX_CANVAS_PIXELS,
                })
            if not output.is_file():
                raise AsepriteMCPError("ASEPRITE_FAILED", "animated combat preview was not created")
            if output.stat().st_size > self.settings.max_capture_bytes:
                raise AsepriteMCPError(
                    "LIMIT_EXCEEDED", "animated combat preview exceeds inline limit"
                )
            return output.read_bytes()

    async def validate_combat_action(
        self, source_path: str, *, action_tag: str, require_hurtbox: bool,
        require_active_frames: bool, required_anchors: list[str],
    ) -> CombatActionValidationResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_DOCUMENT_EXTENSIONS)
        async with self._locked([source]):
            result = await self._bridge("validate_combat_action", {
                "source_path": self._process_path(source), "action_tag": action_tag,
                "require_hurtbox": require_hurtbox,
                "require_active_frames": require_active_frames,
                "required_anchors": required_anchors,
            })
        result["source_path"] = str(source)
        result["sha256"] = sha256_file(source)
        return CombatActionValidationResult.model_validate(result)

    async def validate_combat_set(
        self, source_path: str, *, action_tags: list[str], require_hurtbox: bool,
        require_active_frames: bool, required_anchors: list[str],
        require_action_metadata: bool,
    ) -> CombatSetValidationResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_DOCUMENT_EXTENSIONS)
        async with self._locked([source]):
            result = await self._bridge("validate_combat_set", {
                "source_path": self._process_path(source), "action_tags": action_tags,
                "require_hurtbox": require_hurtbox,
                "require_active_frames": require_active_frames,
                "required_anchors": required_anchors,
                "require_action_metadata": require_action_metadata,
            })
            source_hash = sha256_file(source)
        result["source_path"] = str(source)
        result["sha256"] = source_hash
        for action in result.get("actions", []):
            action["source_path"] = str(source)
            action["sha256"] = source_hash
        return CombatSetValidationResult.model_validate(result)

    async def validate_stage_gameplay(
        self, source_path: str, *, require_spawn: bool, require_exit: bool,
        require_camera: bool,
    ) -> StageGameplayValidationResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_DOCUMENT_EXTENSIONS)
        async with self._locked([source]):
            result = await self._bridge("validate_stage_gameplay", {
                "source_path": self._process_path(source), "require_spawn": require_spawn,
                "require_exit": require_exit, "require_camera": require_camera,
            })
            source_hash = sha256_file(source)
        result["source_path"] = str(source)
        result["sha256"] = source_hash
        return StageGameplayValidationResult.model_validate(result)

    async def export_combat_manifest(
        self, source_path: str, output_path: str, *, action_tag: str | None,
        overwrite: bool,
    ) -> CombatManifestResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_DOCUMENT_EXTENSIONS)
        output = self.paths.output_file(
            output_path, extensions=frozenset({".json"}), overwrite=overwrite
        )
        temporary = temporary_sibling(output)
        source_hash = ""
        async with self._locked([source, output]):
            source_hash = sha256_file(source)
            result = await self._bridge("inspect_combat_manifest", {
                "source_path": self._process_path(source), "action_tag": action_tag,
            })
            result["source_path"] = str(source)
            result["source_sha256"] = source_hash
            try:
                temporary.write_text(
                    json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
                publish_file(temporary, output)
            finally:
                temporary.unlink(missing_ok=True)
        return CombatManifestResult(
            source_path=str(source), source_sha256=source_hash,
            manifest=self._file_result(output), action_count=len(result.get("actions", [])),
            box_count=len(result.get("boxes", [])),
            anchor_count=len(result.get("anchors", [])),
            event_count=len(result.get("events", [])),
        )

    async def export_beat_em_up_bundle(
        self, source_path: str, output_path: str, *,
        layout: Literal["horizontal", "vertical", "rows", "columns", "packed"],
        tag: str | None, layers: list[str], trim: bool, extrude: bool,
        border_padding: int, shape_padding: int, inner_padding: int,
        overwrite: bool,
    ) -> BeatEmUpBundleResult:
        source = self.paths.existing_file(source_path, extensions=SPRITE_DOCUMENT_EXTENSIONS)
        output = self.paths.output_file(
            output_path, extensions=frozenset({".zip"}), overwrite=overwrite
        )
        if source == output:
            raise AsepriteMCPError("PATH_NOT_ALLOWED", "bundle output must differ from its source")
        temporary = temporary_sibling(output)
        for value in (border_padding, shape_padding, inner_padding):
            if not 0 <= value <= 1024:
                raise AsepriteMCPError("LIMIT_EXCEEDED", "padding must be between 0 and 1024")
        source_hash = ""
        manifest: dict[str, Any] = {}
        frame_count = 0
        with tempfile.TemporaryDirectory(
            prefix="aseprite-beat-em-up-bundle-", dir=self.bridge_temp_root
        ) as directory:
            directory_path = Path(directory)
            sheet_path = directory_path / "sheet.png"
            frames_path = directory_path / "frames.json"
            manifest_path = directory_path / "manifest.json"
            arguments = ["--batch", "--noinapp"]
            for layer in layers:
                arguments.extend(["--layer", layer])
            if tag is not None:
                arguments.extend(["--tag", tag])
            arguments.extend([self._process_path(source), "--sheet-type", layout])
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
            arguments.extend([
                "--sheet", self._process_path(sheet_path), "--format", "json-array",
                "--data", self._process_path(frames_path),
            ])
            async with self._locked([source, output]):
                source_hash = sha256_file(source)
                manifest = await self._bridge("inspect_combat_manifest", {
                    "source_path": self._process_path(source), "action_tag": tag,
                })
                manifest["source_path"] = str(source)
                manifest["source_sha256"] = source_hash
                manifest["bundle_format_version"] = 1
                manifest_path.write_text(
                    json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
                try:
                    await self._run(arguments, operation="export_beat_em_up_bundle")
                    if not sheet_path.is_file() or not frames_path.is_file():
                        raise AsepriteMCPError(
                            "ASEPRITE_FAILED", "Aseprite did not create bundle sheet metadata"
                        )
                    try:
                        frame_data = json.loads(frames_path.read_text(encoding="utf-8-sig"))
                    except json.JSONDecodeError as exc:
                        raise AsepriteMCPError(
                            "ASEPRITE_FAILED", "Aseprite produced invalid bundle frame JSON"
                        ) from exc
                    frame_count = len(frame_data.get("frames", []))
                    with zipfile.ZipFile(
                        temporary, "w", compression=zipfile.ZIP_DEFLATED
                    ) as archive:
                        archive.write(sheet_path, "sheet.png")
                        archive.write(frames_path, "frames.json")
                        archive.write(manifest_path, "manifest.json")
                    publish_file(temporary, output)
                finally:
                    temporary.unlink(missing_ok=True)
        return BeatEmUpBundleResult(
            source_path=str(source), source_sha256=source_hash,
            bundle=self._file_result(output), frame_count=frame_count,
            action_count=len(manifest.get("actions", [])),
            box_count=len(manifest.get("boxes", [])),
            anchor_count=len(manifest.get("anchors", [])),
            zone_count=len(manifest.get("stage_zones", [])),
        )

    async def validate_character_roster(
        self, source_paths: list[str], *, required_actions: list[str],
        required_anchors: list[str], require_consistent_canvas: bool,
        require_consistent_color_mode: bool,
    ) -> CharacterRosterValidationResult:
        sources = [
            self.paths.existing_file(path, extensions=SPRITE_DOCUMENT_EXTENSIONS)
            for path in source_paths
        ]
        if len(set(sources)) != len(sources):
            raise AsepriteMCPError("INVALID_INPUT", "source_paths must not contain duplicates")
        inspected: list[dict[str, Any]] = []
        async with self._locked(sources):
            for source in sources:
                item = await self._bridge("inspect_combat_character", {
                    "source_path": self._process_path(source)
                })
                item["source_path"] = str(source)
                item["sha256"] = sha256_file(source)
                inspected.append(item)

        shared_issues: list[CombatValidationIssue] = []
        canvas_sizes = {(item["width"], item["height"]) for item in inspected}
        if require_consistent_canvas and len(canvas_sizes) > 1:
            shared_issues.append(CombatValidationIssue(
                code="INCONSISTENT_CANVAS", severity="error",
                message="character documents do not share one canvas size",
            ))
        if require_consistent_color_mode and len({item["color_mode"] for item in inspected}) > 1:
            shared_issues.append(CombatValidationIssue(
                code="INCONSISTENT_COLOR_MODE", severity="error",
                message="character documents do not share one color mode",
            ))

        characters: list[CharacterRosterItem] = []
        for item in inspected:
            actions = set(item["actions"])
            anchors = set(item["anchor_names"])
            missing_actions = sorted(set(required_actions) - actions)
            missing_anchors = sorted(set(required_anchors) - anchors)
            issues: list[CombatValidationIssue] = []
            if missing_actions:
                issues.append(CombatValidationIssue(
                    code="MISSING_ACTIONS", severity="error",
                    message="missing required action tags: " + ", ".join(missing_actions),
                ))
            if missing_anchors:
                issues.append(CombatValidationIssue(
                    code="MISSING_ANCHORS", severity="error",
                    message="missing required combat anchors: " + ", ".join(missing_anchors),
                ))
            characters.append(CharacterRosterItem(
                source_path=item["source_path"], sha256=item["sha256"],
                valid=not issues and not shared_issues, width=item["width"], height=item["height"],
                color_mode=item["color_mode"], actions=item["actions"],
                missing_actions=missing_actions, missing_anchors=missing_anchors, issues=issues,
            ))
        return CharacterRosterValidationResult(
            valid=all(item.valid for item in characters) and not shared_issues,
            characters=characters, issues=shared_issues,
        )
