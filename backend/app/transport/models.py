"""Device session DTOs shared by in-memory and SQLite stores."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.action.models import ActionLifecycle, ActionRequest, ActionResult


class DeviceActionCommand(BaseModel):
    command_id: str
    action_id: str
    device_id: str
    action: ActionRequest
    lifecycle: ActionLifecycle = ActionLifecycle.QUEUED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    lease_id: str | None = None
    leased_until: datetime | None = None
    retry_count: int = Field(default=0, ge=0)


class DeviceActionResultReport(BaseModel):
    command_id: str
    result: ActionResult
    lifecycle: ActionLifecycle | None = None


class DeviceSessionSnapshot(BaseModel):
    device_id: str
    latest_observation_id: str | None = None
    pending_action_count: int = 0
    leased_action_count: int = 0
    completed_action_count: int = 0
    retry_count: int = 0
    connected: bool = False
    lifecycle_counts: dict[str, int] = Field(default_factory=dict)
