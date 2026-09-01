"""Engine-neutral beat-'em-up combat authoring schemas."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .common import FileResult, RectangleInfo, RectangleInput, StrictModel


CombatBoxKind = Literal[
    "hurt", "hit", "push", "grab", "throw", "armor", "invulnerable"
]


class CombatBoxEditOperation(StrictModel):
    action: Literal["set", "remove"]
    id: Annotated[str, Field(min_length=1, max_length=128)]
    action_tag: Annotated[str, Field(min_length=1, max_length=128)]
    frame: Annotated[int, Field(ge=0)]
    kind: CombatBoxKind | None = None
    bounds: RectangleInput | None = None
    damage: Annotated[int | None, Field(ge=0, le=1_000_000)] = None
    hitstop_ms: Annotated[int | None, Field(ge=0, le=60_000)] = None
    hitstun_ms: Annotated[int | None, Field(ge=0, le=60_000)] = None
    knockback_x: Annotated[int, Field(ge=-8192, le=8192)] = 0
    knockback_y: Annotated[int, Field(ge=-8192, le=8192)] = 0
    priority: Annotated[int, Field(ge=-32768, le=32767)] = 0
    enabled: bool = True


class FrameAnchorEditOperation(StrictModel):
    action: Literal["set", "remove"]
    name: Annotated[str, Field(min_length=1, max_length=128)]
    action_tag: Annotated[str, Field(min_length=1, max_length=128)]
    frame: Annotated[int, Field(ge=0)]
    x: Annotated[int | None, Field(ge=-8192, le=8192)] = None
    y: Annotated[int | None, Field(ge=-8192, le=8192)] = None


class CombatBoxInfo(StrictModel):
    id: str
    action_tag: str
    frame: int
    kind: CombatBoxKind
    bounds: RectangleInfo
    damage: int | None = None
    hitstop_ms: int | None = None
    hitstun_ms: int | None = None
    knockback_x: int = 0
    knockback_y: int = 0
    priority: int = 0
    enabled: bool = True


class FrameAnchorInfo(StrictModel):
    name: str
    action_tag: str
    frame: int
    x: int
    y: int


class ActionMetadataEditOperation(StrictModel):
    action: Literal["set", "remove"]
    action_tag: Annotated[str, Field(min_length=1, max_length=128)]
    action_type: Literal[
        "locomotion", "attack", "special", "grab", "throw", "reaction",
        "defense", "knockdown", "get_up", "death", "other"
    ] | None = None
    facing_policy: Literal["inherit", "free", "locked"] = "inherit"
    movement_mode: Literal["stationary", "ground", "air", "lane"] = "stationary"
    next_action: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    landing_action: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    speed_multiplier: Annotated[float, Field(ge=0, le=16)] = 1.0
    can_turn: bool = False


class ActionMetadataInfo(StrictModel):
    action_tag: str
    action_type: str
    facing_policy: str = "inherit"
    movement_mode: str = "stationary"
    next_action: str | None = None
    landing_action: str | None = None
    speed_multiplier: float = 1.0
    can_turn: bool = False


class CancelWindowEditOperation(StrictModel):
    action: Literal["set", "remove"]
    id: Annotated[str, Field(min_length=1, max_length=128)]
    action_tag: Annotated[str | None, Field(min_length=1, max_length=128)] = None
    from_frame: Annotated[int | None, Field(ge=0)] = None
    to_frame: Annotated[int | None, Field(ge=0)] = None
    targets: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=128)]], Field(max_length=64)
    ] = Field(default_factory=list)
    on_hit: bool = True
    on_block: bool = False
    on_whiff: bool = False
    resource_cost: Annotated[int, Field(ge=0, le=1_000_000)] = 0


class CancelWindowInfo(StrictModel):
    id: str
    action_tag: str
    from_frame: int
    to_frame: int
    targets: list[str]
    on_hit: bool
    on_block: bool
    on_whiff: bool
    resource_cost: int = 0


class RootMotionEditOperation(StrictModel):
    action: Literal["set", "remove"]
    action_tag: Annotated[str, Field(min_length=1, max_length=128)]
    frame: Annotated[int, Field(ge=0)]
    delta_x: Annotated[int, Field(ge=-8192, le=8192)] = 0
    delta_y: Annotated[int, Field(ge=-8192, le=8192)] = 0
    delta_lane: Annotated[int, Field(ge=-8192, le=8192)] = 0


class RootMotionInfo(StrictModel):
    action_tag: str
    frame: int
    delta_x: int = 0
    delta_y: int = 0
    delta_lane: int = 0


class StageGameplayZoneEditOperation(StrictModel):
    action: Literal["set", "remove"]
    id: Annotated[str, Field(min_length=1, max_length=128)]
    kind: Literal[
        "walkable", "camera", "encounter", "spawn", "exit", "hazard", "pit", "foreground"
    ] | None = None
    bounds: RectangleInput | None = None
    target: Annotated[str | None, Field(min_length=1, max_length=256)] = None
    order: Annotated[int, Field(ge=0, le=65_535)] = 0
    enabled: bool = True


class StageGameplayZoneInfo(StrictModel):
    id: str
    kind: str
    bounds: RectangleInfo
    target: str | None = None
    order: int = 0
    enabled: bool = True


class CombatValidationIssue(StrictModel):
    code: str
    severity: Literal["warning", "error"]
    message: str
    frames: list[int] = Field(default_factory=list)


class CombatActionValidationResult(StrictModel):
    source_path: str
    sha256: str
    action_tag: str
    valid: bool
    from_frame: int
    to_frame: int
    startup_frames: int
    active_frames: list[int]
    recovery_frames: int
    boxes: list[CombatBoxInfo]
    anchors: list[FrameAnchorInfo]
    issues: list[CombatValidationIssue]


class CombatSetValidationResult(StrictModel):
    source_path: str
    sha256: str
    valid: bool
    actions: list[CombatActionValidationResult]
    issues: list[CombatValidationIssue]


class StageGameplayValidationResult(StrictModel):
    source_path: str
    sha256: str
    valid: bool
    zones: list[StageGameplayZoneInfo]
    issues: list[CombatValidationIssue]


class CombatManifestResult(StrictModel):
    source_path: str
    source_sha256: str
    manifest: FileResult
    action_count: int
    box_count: int
    anchor_count: int
    event_count: int


class BeatEmUpBundleResult(StrictModel):
    source_path: str
    source_sha256: str
    bundle: FileResult
    frame_count: int
    action_count: int
    box_count: int
    anchor_count: int
    zone_count: int


class CharacterRosterItem(StrictModel):
    source_path: str
    sha256: str
    valid: bool
    width: int
    height: int
    color_mode: str
    actions: list[str]
    missing_actions: list[str]
    missing_anchors: list[str]
    issues: list[CombatValidationIssue]


class CharacterRosterValidationResult(StrictModel):
    valid: bool
    characters: list[CharacterRosterItem]
    issues: list[CombatValidationIssue]


__all__ = [
    "ActionMetadataEditOperation",
    "ActionMetadataInfo",
    "BeatEmUpBundleResult",
    "CancelWindowEditOperation",
    "CancelWindowInfo",
    "CombatActionValidationResult",
    "CombatBoxEditOperation",
    "CombatBoxInfo",
    "CombatManifestResult",
    "CombatValidationIssue",
    "CombatSetValidationResult",
    "CharacterRosterItem",
    "CharacterRosterValidationResult",
    "FrameAnchorEditOperation",
    "FrameAnchorInfo",
    "RootMotionEditOperation",
    "RootMotionInfo",
    "StageGameplayValidationResult",
    "StageGameplayZoneEditOperation",
    "StageGameplayZoneInfo",
]
