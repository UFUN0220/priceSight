"""Common runtime identity independent from Android or browser transport."""

from enum import StrEnum

from pydantic import BaseModel, Field


class RuntimeType(StrEnum):
    BROWSER = "browser"
    ANDROID = "android"
    MOCK = "mock"


class RuntimeStatus(StrEnum):
    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    STOPPED = "stopped"
    FAILED = "failed"


class RuntimeSession(BaseModel):
    """Auditable runtime identity used by task orchestration and traces."""

    runtime_id: str = Field(min_length=1, max_length=128)
    runtime_type: RuntimeType
    platform_id: str | None = None
    status: RuntimeStatus = RuntimeStatus.CREATED
    latest_observation_id: str | None = None
    allowed_hosts: list[str] = Field(default_factory=list)
