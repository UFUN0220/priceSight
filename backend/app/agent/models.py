"""Bounded context and structured decision models for Agent Planner."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.action.models import ActionRequest
from app.observation.models import Observation


class AgentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_goal: str
    current_platform: str | None = None
    workflow_state: str
    observation: Observation | None = None
    previous_action: ActionRequest | None = None
    known_constraints: list[str] = Field(default_factory=list)
    retry_budget: int = Field(default=0, ge=0)


class AgentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_summary: str
    action: ActionRequest | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    requires_verification: bool = True


class AgentPlanStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    MALFORMED_OUTPUT = "MALFORMED_OUTPUT"
    INVALID_ACTION = "INVALID_ACTION"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    SAFETY_STOP = "SAFETY_STOP"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"


class AgentPlanResult(BaseModel):
    """Auditable planner outcome; only ACCEPTED decisions may execute."""

    status: AgentPlanStatus
    decision: AgentDecision | None = None
    failure_reason: str | None = None
    attempts: int = Field(default=0, ge=0)
    provider: str | None = None
