"""Framework-neutral action schemas."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ActionType(StrEnum):
    CLICK = "CLICK"
    SET_TEXT = "SET_TEXT"
    SCROLL_FORWARD = "SCROLL_FORWARD"
    SCROLL_BACKWARD = "SCROLL_BACKWARD"
    BACK = "BACK"
    WAIT = "WAIT"
    STOP = "STOP"


class ActionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    ACTION_REJECTED = "ACTION_REJECTED"
    STATE_UNCHANGED = "STATE_UNCHANGED"
    TIMEOUT = "TIMEOUT"
    SAFETY_BLOCKED = "SAFETY_BLOCKED"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    STALE_OBSERVATION = "STALE_OBSERVATION"
    REPLAN_REQUIRED = "REPLAN_REQUIRED"


class ActionTarget(BaseModel):
    node_id: str | None = None
    resource_id: str | None = None
    text: str | None = None
    content_description: str | None = None
    semantic_hint: str | None = None
    bounds: tuple[int, int, int, int] | None = None


class ActionRequest(BaseModel):
    action_type: ActionType
    target: ActionTarget | None = None
    value: str | None = None
    observation_id: str | None = None
    timeout_ms: int = Field(default=3000, ge=0, le=120000)


class ActionResult(BaseModel):
    success: bool
    status: ActionStatus
    message: str | None = None
    observation_id: str | None = None
    matched_node_id: str | None = None
    match_strategy: str | None = None
    match_score: float | None = None
