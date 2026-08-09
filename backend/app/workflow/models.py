"""Typed YAML workflow definitions and execution results."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.action.models import ActionRequest, ActionResult, ActionTarget, ActionType
from app.action.verifier import VerificationExpectation
from app.core.reliability import ActionTraceEvent
from app.observation.models import Observation, PageType


class WorkflowStatus(StrEnum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    NEEDS_AGENT_DECISION = "NEEDS_AGENT_DECISION"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SAFETY_STOP = "SAFETY_STOP"


class WorkflowGuard(BaseModel):
    """Deterministic precondition evaluated against the current observation."""

    model_config = ConfigDict(extra="forbid")

    expected_page_type: PageType | None = None
    required_text: str | None = None
    forbidden_text: str | None = None


class WorkflowStep(BaseModel):
    """One bounded deterministic action in a workflow."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    action: ActionType
    target: ActionTarget | None = None
    value: str | None = None
    value_from: str | None = None
    timeout_ms: int = Field(default=3000, ge=0, le=120000)
    retry_limit: int = Field(default=0, ge=0, le=10)
    guard: WorkflowGuard | None = None
    expected: VerificationExpectation | None = None
    optional: bool = False
    requires_agent_decision: bool = False
    requires_cart_opt_in: bool = False
    on_success: str | None = None
    on_failure: str | None = None

    @model_validator(mode="after")
    def validate_value_source(self) -> WorkflowStep:
        if self.value is not None and self.value_from is not None:
            raise ValueError("a workflow step cannot define both value and value_from")
        if self.action is ActionType.SET_TEXT and self.value is None and self.value_from is None:
            raise ValueError("SET_TEXT requires value or value_from")
        return self


class WorkflowDefinition(BaseModel):
    """A validated, finite workflow loaded from YAML."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    steps: list[WorkflowStep] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_step_graph(self) -> WorkflowDefinition:
        step_ids = [step.id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("workflow step IDs must be unique")
        known = set(step_ids)
        for step in self.steps:
            for route in (step.on_success, step.on_failure):
                if route is not None and route != "NEEDS_AGENT_DECISION" and route not in known:
                    raise ValueError(f"workflow route references unknown step: {route}")
        return self


class WorkflowContext(BaseModel):
    """Bounded runtime context; task values are intentionally simple strings."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    goal: str
    task: dict[str, str] = Field(default_factory=dict)
    allow_cart: bool = False
    status: WorkflowStatus = WorkflowStatus.IDLE
    retry_count: int = Field(default=0, ge=0)
    step_count: int = Field(default=0, ge=0)
    current_step_id: str | None = None
    completed_steps: list[str] = Field(default_factory=list)
    skipped_steps: list[str] = Field(default_factory=list)
    current_observation: Observation | None = None
    previous_result: ActionResult | None = None
    trace_events: list[ActionTraceEvent] = Field(default_factory=list)


class WorkflowResult(BaseModel):
    """Stable result envelope for API/reporting layers."""

    status: WorkflowStatus
    completed_steps: list[str] = Field(default_factory=list)
    skipped_steps: list[str] = Field(default_factory=list)
    failed_step_id: str | None = None
    failure_reason: str | None = None
    final_observation: Observation | None = None
    action_results: list[ActionResult] = Field(default_factory=list)
    trace_events: list[ActionTraceEvent] = Field(default_factory=list)
    agent_decision_step_id: str | None = None
    context: WorkflowContext


class PlannedStep(BaseModel):
    """Internal representation after resolving a step's task value."""

    request: ActionRequest
    expectation: VerificationExpectation | None = None
