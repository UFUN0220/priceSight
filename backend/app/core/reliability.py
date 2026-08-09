"""Replayable reliability primitives for bounded action execution."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum

from pydantic import BaseModel, Field

from app.action.models import ActionRequest, ActionResult, ActionStatus
from app.observation.models import Observation


class BadCaseCategory(StrEnum):
    TARGET_MISSING = "TARGET_MISSING"
    DUPLICATE_TARGET = "DUPLICATE_TARGET"
    STALE_OBSERVATION = "STALE_OBSERVATION"
    PAGE_TRANSITION_DELAY = "PAGE_TRANSITION_DELAY"
    UNEXPECTED_DIALOG = "UNEXPECTED_DIALOG"
    SPEC_AMBIGUITY = "SPEC_AMBIGUITY"
    ACTION_NO_EFFECT = "ACTION_NO_EFFECT"


class ActionTraceEvent(BaseModel):
    """Sanitized event suitable for replay and Bad Case regression reports."""

    task_id: str
    step_id: str
    observation_hash: str
    action_type: str
    target_summary: str | None = None
    match_strategy: str | None = None
    confidence: float | None = None
    execution_result: ActionStatus
    latency_ms: float = Field(ge=0)
    retry_count: int = Field(default=0, ge=0)
    bad_case: BadCaseCategory | None = None


class RepetitionDetector:
    """Detect the same action against the same unchanged observation."""

    def __init__(self, threshold: int = 2) -> None:
        if threshold < 2:
            raise ValueError("repetition threshold must be at least 2")
        self.threshold = threshold
        self._counts: dict[tuple[str, str], int] = {}

    def register(self, observation: Observation, action: ActionRequest) -> bool:
        key = (observation_hash(observation), action_signature(action))
        count = self._counts.get(key, 0) + 1
        self._counts[key] = count
        return count >= self.threshold


def observation_hash(observation: Observation) -> str:
    payload = json.dumps(observation.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def action_signature(action: ActionRequest) -> str:
    payload = action.model_dump(mode="json", exclude={"observation_id"})
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def classify_bad_case(result: ActionResult) -> BadCaseCategory | None:
    if result.status is ActionStatus.TARGET_NOT_FOUND:
        if result.message and "multiple" in result.message:
            return BadCaseCategory.DUPLICATE_TARGET
        return BadCaseCategory.TARGET_MISSING
    if result.status is ActionStatus.STALE_OBSERVATION:
        return BadCaseCategory.STALE_OBSERVATION
    if result.status is ActionStatus.STATE_UNCHANGED:
        return BadCaseCategory.ACTION_NO_EFFECT
    if result.status is ActionStatus.TIMEOUT:
        return BadCaseCategory.PAGE_TRANSITION_DELAY
    if result.status is ActionStatus.REPLAN_REQUIRED:
        return BadCaseCategory.ACTION_NO_EFFECT
    return None


def target_summary(action: ActionRequest) -> str | None:
    if action.target is None:
        return None
    fields = action.target.model_dump(exclude_none=True)
    return " ".join(f"{key}={value}" for key, value in fields.items()) or None
