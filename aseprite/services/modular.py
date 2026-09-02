"""Modular character metadata, previews, validation, and export."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Literal

from ..errors import AsepriteMCPError
from ..models import (
    ModularAnchorInput,
    ModularCharacterValidationResult,
    ModularManifestResult,
    ModularPartEditOperation,
    ModularPartInfo,
    ModularValidationIssue,
    MutationResult,
)
from ..paths import (
    SPRITE_DOCUMENT_EXTENSIONS,
    publish_file,
    sha256_file,
    temporary_sibling,
)
from .runtime import AsepriteRuntime

logger = logging.getLogger(__name__)

MODULAR_SCHEMA = "aseprite-mcp-modular-character"
MODULAR_SCHEMA_VERSION = 1
PROPERTY_PREFIX = "mcp.modular."
PART_PROPERTY_KEYS = (
    "part_id",
    "slot",
    "draw_order",
    "compatibility_tags",
    "requires_part_ids",
    "conflicts_part_ids",
    "anchors",
)


class ModularService(AsepriteRuntime):
    """Operations for layer-based paper-doll character assets."""

    @staticmethod
    def _encoded(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    async def edit_modular_part_metadata(
        self,
        source_path: str,
        output_path: str,
        *,
        operations: list[ModularPartEditOperation],
        overwrite: bool,
        expected_source_hash: str | None,
    ) -> MutationResult:
        if not 1 <= len(operations) <= 32:
            raise AsepriteMCPError("LIMIT_EXCEEDED", "operations must contain 1 to 32 items")
        layers = [operation.layer for operation in operations]
        if len(layers) != len(set(layers)):
            raise AsepriteMCPError("INVALID_INPUT", "each layer may be edited only once")
        part_ids = [
            operation.part_id
            for operation in operations
            if operation.action == "set" and operation.part_id is not None
        ]
        if len(part_ids) != len(set(part_ids)):
            raise AsepriteMCPError("INVALID_INPUT", "part_id values must be unique")

        property_operations: list[dict[str, Any]] = [
            {
                "action": "set",
                "target": "sprite",
                "key": PROPERTY_PREFIX + "schema_version",
                "value": MODULAR_SCHEMA_VERSION,
            }
        ]
        for operation in operations:
            if operation.action == "set":
                if operation.part_id is None or operation.slot is None:
                    raise AsepriteMCPError(
                        "INVALID_INPUT", "set operations require part_id and slot"
                    )
                for values, label in (
                    (operation.compatibility_tags, "compatibility_tags"),
                    (operation.requires_part_ids, "requires_part_ids"),
                    (operation.conflicts_part_ids, "conflicts_part_ids"),
                ):
                    if len(values) != len(set(values)):
                        raise AsepriteMCPError(
                            "INVALID_INPUT", f"{label} values must be unique"
                        )
                anchor_names = [anchor.name for anchor in operation.anchors]
                if len(anchor_names) != len(set(anchor_names)):
                    raise AsepriteMCPError("INVALID_INPUT", "anchor names must be unique")
                values = {
                    "part_id": operation.part_id,
                    "slot": operation.slot,
                    "draw_order": operation.draw_order,
                    "compatibility_tags": self._encoded(operation.compatibility_tags),
                    "requires_part_ids": self._encoded(operation.requires_part_ids),
                    "conflicts_part_ids": self._encoded(operation.conflicts_part_ids),
                    "anchors": self._encoded(
                        [anchor.model_dump() for anchor in operation.anchors]
                    ),
                }
                for key, value in values.items():
                    property_operations.append(
                        {
                            "action": "set",
                            "target": "layer",
                            "layer": operation.layer,
                            "key": PROPERTY_PREFIX + key,
                            "value": value,
                        }
                    )
            else:
                for key in PART_PROPERTY_KEYS:
                    property_operations.append(
                        {
                            "action": "remove",
                            "target": "layer",
                            "layer": operation.layer,
                            "key": PROPERTY_PREFIX + key,
                        }
                    )

        logger.info("Editing modular metadata source=%s parts=%d", source_path, len(operations))
        return await self._bridge_mutation(
            "edit_properties",
            source_path,
            output_path,
            overwrite=overwrite,
            expected_source_hash=expected_source_hash,
            payload={"operations": property_operations},
        )

    @staticmethod
    def _json_list(
        properties: dict[str, Any], key: str, *, layer: str
    ) -> tuple[list[Any], ModularValidationIssue | None]:
        raw = properties.get(PROPERTY_PREFIX + key, "[]")
        if not isinstance(raw, str):
            return [], ModularValidationIssue(
                code="INVALID_METADATA",
                severity="error",
                message=f"{key} must be stored as a JSON array",
                layer=layer,
            )
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = None
        if not isinstance(value, list):
            return [], ModularValidationIssue(
                code="INVALID_METADATA",
                severity="error",
                message=f"{key} is not a valid JSON array",
                layer=layer,
            )
        return value, None

    @classmethod
    def _parse_parts(
        cls, items: list[dict[str, Any]]
    ) -> tuple[list[ModularPartInfo], list[ModularValidationIssue]]:
        parts: list[ModularPartInfo] = []
        issues: list[ModularValidationIssue] = []
        for item in items:
            properties = item.get("properties", {})
            if not isinstance(properties, dict) or not any(
                str(key).startswith(PROPERTY_PREFIX) for key in properties
            ):
                continue
            layer = str(item.get("identifier", ""))
            part_id = properties.get(PROPERTY_PREFIX + "part_id")
            slot = properties.get(PROPERTY_PREFIX + "slot")
            draw_order = properties.get(PROPERTY_PREFIX + "draw_order", 0)
            if not isinstance(part_id, str) or not part_id:
                issues.append(ModularValidationIssue(
                    code="MISSING_PART_ID", severity="error",
                    message="Modular layer is missing a string part_id", layer=layer,
                ))
                continue
            if not isinstance(slot, str) or not slot:
                issues.append(ModularValidationIssue(
                    code="MISSING_SLOT", severity="error",
                    message="Modular layer is missing a string slot", layer=layer,
                    part_id=part_id,
                ))
                continue
            if (
                isinstance(draw_order, bool)
                or not isinstance(draw_order, (int, float))
                or int(draw_order) != draw_order
            ):
                issues.append(ModularValidationIssue(
                    code="INVALID_DRAW_ORDER", severity="error",
                    message="draw_order must be an integer", layer=layer, part_id=part_id,
                ))
                continue
            parsed: dict[str, list[Any]] = {}
            malformed = False
            for key in (
                "compatibility_tags", "requires_part_ids", "conflicts_part_ids", "anchors"
            ):
                value, issue = cls._json_list(properties, key, layer=layer)
                parsed[key] = value
                if issue is not None:
                    issue.part_id = part_id
                    issues.append(issue)
                    malformed = True
            if malformed:
                continue
            try:
                anchors = [ModularAnchorInput.model_validate(value) for value in parsed["anchors"]]
                parts.append(ModularPartInfo(
                    layer=layer,
                    part_id=part_id,
                    slot=slot,
                    draw_order=int(draw_order),
                    compatibility_tags=parsed["compatibility_tags"],
                    requires_part_ids=parsed["requires_part_ids"],
                    conflicts_part_ids=parsed["conflicts_part_ids"],
                    anchors=anchors,
                ))
            except (TypeError, ValueError) as exc:
                issues.append(ModularValidationIssue(
                    code="INVALID_METADATA", severity="error",
                    message=f"Modular metadata has an invalid value: {exc}",
                    layer=layer, part_id=part_id,
                ))
        parts.sort(key=lambda part: (part.draw_order, part.slot, part.part_id))
        return parts, issues

    async def _inspect_modular(
        self, source_path: str
    ) -> tuple[Path, dict[str, Any], list[ModularPartInfo], list[ModularValidationIssue], str]:
        source = self.paths.existing_file(
            source_path, extensions=SPRITE_DOCUMENT_EXTENSIONS
        )
        async with self._locked([source]):
            sprite = await self._bridge(
                "inspect", {"source_path": self._process_path(source), "include_palette_colors": False}
            )
            properties = await self._bridge(
                "inspect_properties",
                {
                    "source_path": self._process_path(source),
                    "targets": ["layer"],
                    "include_empty": False,
                    "max_items": 16_384,
                },
            )
            source_hash = sha256_file(source)
        parts, issues = self._parse_parts(properties.get("items", []))
        return source, sprite, parts, issues, source_hash

    @staticmethod
    def _layer_map(layers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        stack = list(layers)
        while stack:
            layer = stack.pop()
            result[str(layer.get("path", ""))] = layer
            stack.extend(layer.get("children", []))
        return result

    async def validate_modular_character(
        self,
        source_path: str,
        *,
        required_slots: list[str],
        required_tags: list[str],
        required_anchor_names: list[str],
        require_complete_frame_coverage: bool,
        strict_references: bool,
    ) -> ModularCharacterValidationResult:
        source, sprite, parts, issues, source_hash = await self._inspect_modular(source_path)
        part_ids = [part.part_id for part in parts]
        known_ids = set(part_ids)
        slots = sorted({part.slot for part in parts})
        layer_map = self._layer_map(sprite.get("layers", []))

        if not parts:
            issues.append(ModularValidationIssue(
                code="NO_MODULAR_PARTS", severity="error",
                message="No valid modular part metadata was found",
            ))
        for duplicate in sorted({value for value in part_ids if part_ids.count(value) > 1}):
            issues.append(ModularValidationIssue(
                code="DUPLICATE_PART_ID", severity="error",
                message=f"part_id is used by more than one layer: {duplicate}",
                part_id=duplicate,
            ))
        for required in required_slots:
            if required not in slots:
                issues.append(ModularValidationIssue(
                    code="MISSING_REQUIRED_SLOT", severity="error",
                    message=f"Required modular slot is missing: {required}",
                ))
        tag_names = {str(tag.get("name", "")) for tag in sprite.get("tags", [])}
        for required in required_tags:
            if required not in tag_names:
                issues.append(ModularValidationIssue(
                    code="MISSING_REQUIRED_TAG", severity="error",
                    message=f"Required animation tag is missing: {required}",
                ))
        anchor_names = {anchor.name for part in parts for anchor in part.anchors}
        for required in required_anchor_names:
            if required not in anchor_names:
                issues.append(ModularValidationIssue(
                    code="MISSING_REQUIRED_ANCHOR", severity="error",
                    message=f"Required attachment anchor is missing: {required}",
                ))

        frame_count = int(sprite.get("frame_count", 0))
        for part in parts:
            layer = layer_map.get(part.layer)
            if layer is None:
                issues.append(ModularValidationIssue(
                    code="MISSING_LAYER", severity="error",
                    message="Metadata refers to a layer that was not found",
                    layer=part.layer, part_id=part.part_id,
                ))
                continue
            if require_complete_frame_coverage and layer.get("type") == "image":
                cel_count = int(layer.get("cel_count", 0))
                if cel_count != frame_count:
                    issues.append(ModularValidationIssue(
                        code="INCOMPLETE_FRAME_COVERAGE", severity="error",
                        message=f"Layer has {cel_count} cels for {frame_count} frames",
                        layer=part.layer, part_id=part.part_id,
                    ))
            if part.part_id in part.conflicts_part_ids:
                issues.append(ModularValidationIssue(
                    code="SELF_CONFLICT", severity="error",
                    message="A modular part cannot conflict with itself",
                    layer=part.layer, part_id=part.part_id,
                ))
            overlap = set(part.requires_part_ids) & set(part.conflicts_part_ids)
            if overlap:
                issues.append(ModularValidationIssue(
                    code="CONTRADICTORY_REFERENCE", severity="error",
                    message="Parts cannot be both required and conflicting: " + ", ".join(sorted(overlap)),
                    layer=part.layer, part_id=part.part_id,
                ))
            unknown = (set(part.requires_part_ids) | set(part.conflicts_part_ids)) - known_ids
            if unknown:
                issues.append(ModularValidationIssue(
                    code="UNKNOWN_PART_REFERENCE",
                    severity="error" if strict_references else "warning",
                    message="Referenced parts are not present in this document: " + ", ".join(sorted(unknown)),
                    layer=part.layer, part_id=part.part_id,
                ))
            names = [anchor.name for anchor in part.anchors]
            if len(names) != len(set(names)):
                issues.append(ModularValidationIssue(
                    code="DUPLICATE_ANCHOR", severity="error",
                    message="Anchor names must be unique within a part",
                    layer=part.layer, part_id=part.part_id,
                ))
            for anchor in part.anchors:
                if not (0 <= anchor.x < int(sprite.get("width", 0))) or not (
                    0 <= anchor.y < int(sprite.get("height", 0))
                ):
                    issues.append(ModularValidationIssue(
                        code="ANCHOR_OUTSIDE_CANVAS", severity="error",
                        message=f"Anchor is outside the canvas: {anchor.name}",
                        layer=part.layer, part_id=part.part_id,
                    ))

        draw_orders: dict[int, list[str]] = {}
        for part in parts:
            draw_orders.setdefault(part.draw_order, []).append(part.part_id)
        for draw_order, ids in sorted(draw_orders.items()):
            if len(ids) > 1:
                issues.append(ModularValidationIssue(
                    code="SHARED_DRAW_ORDER", severity="warning",
                    message=f"Draw order {draw_order} is shared by: {', '.join(sorted(ids))}",
                ))
        logger.info("Validated modular character source=%s parts=%d issues=%d", source, len(parts), len(issues))
        return ModularCharacterValidationResult(
            source_path=str(source), sha256=source_hash,
            valid=not any(issue.severity == "error" for issue in issues),
            parts=parts, slots=slots, issues=issues,
        )

    async def preview_modular_variant(
        self,
        source_path: str,
        *,
        part_ids: list[str],
        include_layers: list[str],
        mode: Literal["frame", "sheet"],
        frame: int,
        layout: Literal["horizontal", "vertical", "rows", "columns", "packed"],
        tag: str | None,
        scale: float,
        allow_multiple_per_slot: bool,
    ) -> bytes:
        _, _, parts, issues, _ = await self._inspect_modular(source_path)
        if len(part_ids) != len(set(part_ids)):
            raise AsepriteMCPError("INVALID_INPUT", "part_ids must be unique")
        if any(issue.severity == "error" for issue in issues):
            raise AsepriteMCPError(
                "INVALID_METADATA", "Modular metadata is invalid; validate the character first"
            )
        by_id = {part.part_id: part for part in parts}
        missing = sorted(set(part_ids) - set(by_id))
        if missing:
            raise AsepriteMCPError(
                "INVALID_SELECTOR", "Unknown modular part IDs: " + ", ".join(missing)
            )
        selected = [by_id[part_id] for part_id in part_ids]
        if not allow_multiple_per_slot:
            slots = [part.slot for part in selected]
            duplicates = sorted({slot for slot in slots if slots.count(slot) > 1})
            if duplicates:
                raise AsepriteMCPError(
                    "INVALID_INPUT", "Multiple selected parts occupy slots: " + ", ".join(duplicates)
                )
        for part in selected:
            missing_required = set(part.requires_part_ids) - set(part_ids)
            selected_conflicts = set(part.conflicts_part_ids) & set(part_ids)
            if missing_required or selected_conflicts:
                raise AsepriteMCPError(
                    "INCOMPATIBLE_VARIANT",
                    f"Selected part combination violates requirements for {part.part_id}",
                )
        layers = list(dict.fromkeys([*include_layers, *(part.layer for part in selected)]))
        return await self.preview(
            source_path, mode=mode, frame=frame, layout=layout, tag=tag,
            layers=layers, scale=scale,
        )

    async def export_modular_manifest(
        self, source_path: str, output_path: str, *, overwrite: bool
    ) -> ModularManifestResult:
        source, sprite, parts, issues, source_hash = await self._inspect_modular(source_path)
        if any(issue.severity == "error" for issue in issues) or not parts:
            raise AsepriteMCPError(
                "INVALID_METADATA", "Modular metadata is invalid; validate the character first"
            )
        output = self.paths.output_file(
            output_path, extensions=frozenset({".json"}), overwrite=overwrite
        )
        temporary = temporary_sibling(output)
        payload = {
            "schema": MODULAR_SCHEMA,
            "schema_version": MODULAR_SCHEMA_VERSION,
            "source_file": source.name,
            "source_sha256": source_hash,
            "sprite": {
                "width": int(sprite.get("width", 0)),
                "height": int(sprite.get("height", 0)),
                "color_mode": str(sprite.get("color_mode", "")),
                "frame_count": int(sprite.get("frame_count", 0)),
                "frames": sprite.get("frames", []),
                "tags": sprite.get("tags", []),
            },
            "slots": sorted({part.slot for part in parts}),
            "parts": [part.model_dump() for part in parts],
        }
        async with self._locked([output]):
            try:
                temporary.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                publish_file(temporary, output)
            finally:
                temporary.unlink(missing_ok=True)
        logger.info("Exported modular manifest source=%s output=%s parts=%d", source, output, len(parts))
        return ModularManifestResult(
            source_path=str(source), source_sha256=source_hash,
            manifest=self._file_result(output), part_count=len(parts),
            slot_count=len({part.slot for part in parts}),
        )
