"""Route workflow handoffs through the planner and action grounding boundary."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.action.executor import ActionDevice, ActionExecutor
from app.action.models import ActionResult, ActionStatus
from app.agent.models import AgentContext, AgentPlanResult, AgentPlanStatus
from app.agent.planner import AgentPlanner
from app.core.safety import SafetyDecision, SafetyGuard
from app.action.verifier import VerificationExpectation
from app.workflow.models import WorkflowResult, WorkflowStatus


class AgentRouteStatus(StrEnum):
    EXECUTED = "EXECUTED"
    PLANNER_REJECTED = "PLANNER_REJECTED"
    SAFETY_STOP = "SAFETY_STOP"
    INVALID_HANDOFF = "INVALID_HANDOFF"


class AgentRouteResult(BaseModel):
    status: AgentRouteStatus
    plan: AgentPlanResult | None = None
    action_result: ActionResult | None = None
    failure_reason: str | None = None
    attempts: int = Field(default=0, ge=0)


class AgentDecisionRouter:
    """Execute only accepted, freshly bound planner decisions."""

    def __init__(
        self,
        planner: AgentPlanner,
        action_executor: ActionExecutor | None = None,
        safety_guard: SafetyGuard | None = None,
    ) -> None:
        self.planner = planner
        self.action_executor = action_executor or ActionExecutor()
        self.safety_guard = safety_guard or SafetyGuard()

    def route(
        self,
        handoff: WorkflowResult,
        context: AgentContext,
        device: ActionDevice,
    ) -> AgentRouteResult:
        if handoff.status is not WorkflowStatus.NEEDS_AGENT_DECISION:
            return AgentRouteResult(
                status=AgentRouteStatus.INVALID_HANDOFF,
                failure_reason="workflow result is not waiting for an agent decision",
            )
        observation = handoff.final_observation or device.observe()
        plan = self.planner.plan(context)
        if plan.status is not AgentPlanStatus.ACCEPTED or plan.decision is None or plan.decision.action is None:
            route_status = (
                AgentRouteStatus.SAFETY_STOP
                if plan.status is AgentPlanStatus.SAFETY_STOP
                else AgentRouteStatus.PLANNER_REJECTED
            )
            return AgentRouteResult(
                status=route_status,
                plan=plan,
                failure_reason=plan.failure_reason,
                attempts=plan.attempts,
            )

        action = plan.decision.action.model_copy(update={"observation_id": observation.observation_id})
        if self.safety_guard.evaluate(action.model_dump_json()).decision is SafetyDecision.STOP:
            device.stop()
            return AgentRouteResult(
                status=AgentRouteStatus.SAFETY_STOP,
                plan=plan,
                failure_reason="deterministic safety guard rejected the routed action",
                attempts=plan.attempts,
            )
        expectation = (
            VerificationExpectation(require_observation_change=True)
            if plan.decision.requires_verification
            else None
        )
        result = self.action_executor.execute(action, observation, device, expectation)
        if result.status is ActionStatus.SAFETY_BLOCKED:
            device.stop()
            return AgentRouteResult(
                status=AgentRouteStatus.SAFETY_STOP,
                plan=plan,
                action_result=result,
                failure_reason=result.message,
                attempts=plan.attempts,
            )
        return AgentRouteResult(
            status=AgentRouteStatus.EXECUTED if result.success else AgentRouteStatus.PLANNER_REJECTED,
            plan=plan,
            action_result=result,
            failure_reason=None if result.success else result.message,
            attempts=plan.attempts,
        )
