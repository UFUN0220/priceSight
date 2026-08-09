"""Tests for bounded structured Agent Planner and decision routing."""

import json

from app.action.fake import FakeActionDevice
from app.action.models import ActionRequest, ActionStatus, ActionType
from app.agent.models import AgentContext, AgentPlanStatus
from app.agent.planner import AgentPlanner
from app.agent.router import AgentDecisionRouter, AgentRouteStatus
from app.llm.fake import FakeLLMProvider
from app.llm.base import LLMResponse
from app.observation.models import Observation, ObservationNode, PageType
from app.workflow.models import WorkflowContext, WorkflowResult, WorkflowStatus


def make_context(retry_budget: int = 0) -> AgentContext:
    return AgentContext(
        user_goal="找到牛奶",
        current_platform="mock",
        workflow_state="choose_product",
        observation=Observation(
            observation_id="obs-1",
            page_type=PageType.SEARCH,
            nodes=[ObservationNode(node_id="result", text="牛奶 500ml", clickable=True)],
        ),
        known_constraints=["safe_mode"],
        retry_budget=retry_budget,
    )


def decision_json(*, confidence: float = 0.9, target_text: str = "牛奶 500ml") -> str:
    return json.dumps(
        {
            "reason_summary": "商品名称和规格匹配",
            "action": {
                "action_type": "CLICK",
                "target": {"text": target_text},
                "observation_id": "stale-id-from-model",
            },
            "confidence": confidence,
            "requires_verification": True,
        },
        ensure_ascii=False,
    )


def test_planner_uses_only_bounded_structured_context() -> None:
    provider = FakeLLMProvider([LLMResponse(content=decision_json(), provider="fake")])
    context = make_context()
    context.previous_action = ActionRequest(action_type=ActionType.WAIT)

    result = AgentPlanner(provider).plan(context)

    assert result.status is AgentPlanStatus.ACCEPTED
    payload = json.loads(provider.calls[0].prompt)
    assert set(payload) == {
        "user_goal",
        "current_page_type",
        "compact_observation",
        "workflow_state",
        "previous_important_action",
        "known_constraints",
        "retry_budget",
    }
    assert "task_id" not in provider.calls[0].prompt
    assert "current_platform" not in provider.calls[0].prompt


def test_malformed_output_retries_with_remaining_budget() -> None:
    provider = FakeLLMProvider(
        [
            LLMResponse(content="not json", provider="fake"),
            LLMResponse(content=decision_json(), provider="fake"),
        ]
    )
    context = make_context(retry_budget=1)

    result = AgentPlanner(provider).plan(context)

    assert result.status is AgentPlanStatus.ACCEPTED
    assert result.attempts == 2
    assert context.retry_budget == 0


def test_low_confidence_is_not_executable() -> None:
    provider = FakeLLMProvider([LLMResponse(content=decision_json(confidence=0.2), provider="fake")])

    result = AgentPlanner(provider).plan(make_context())

    assert result.status is AgentPlanStatus.LOW_CONFIDENCE
    assert result.decision is None


def test_invalid_action_shape_is_rejected() -> None:
    content = json.dumps(
        {
            "reason_summary": "不确定",
            "action": {"action_type": "CLICK"},
            "confidence": 0.9,
            "requires_verification": True,
        }
    )
    result = AgentPlanner(FakeLLMProvider([LLMResponse(content=content, provider="fake")])).plan(make_context())

    assert result.status is AgentPlanStatus.INVALID_ACTION
    assert "target" in (result.failure_reason or "")


def test_unsafe_action_is_deterministically_stopped() -> None:
    content = decision_json(target_text="确认支付")
    result = AgentPlanner(FakeLLMProvider([LLMResponse(content=content, provider="fake")])).plan(make_context())

    assert result.status is AgentPlanStatus.SAFETY_STOP
    assert result.decision is not None


def test_router_rebinds_decision_to_fresh_observation_before_execution() -> None:
    observation = make_context().observation
    assert observation is not None
    provider = FakeLLMProvider([LLMResponse(content=decision_json(), provider="fake")])
    planner = AgentPlanner(provider)
    router = AgentDecisionRouter(planner)
    device = FakeActionDevice(observation)
    handoff = WorkflowResult(
        status=WorkflowStatus.NEEDS_AGENT_DECISION,
        final_observation=observation,
        context=WorkflowContext(task_id="task-1", goal="choose"),
    )

    result = router.route(handoff, make_context(), device)

    assert result.status is AgentRouteStatus.EXECUTED
    assert result.action_result is not None
    assert result.action_result.status is ActionStatus.SUCCESS
    assert device.calls[0].name == "click"
    assert provider.calls[0].model is None


def test_router_rejects_non_agent_workflow_handoff() -> None:
    planner = AgentPlanner(FakeLLMProvider())
    result = AgentDecisionRouter(planner).route(
        WorkflowResult(status=WorkflowStatus.SUCCEEDED, context=WorkflowContext(task_id="t", goal="done")),
        make_context(),
        FakeActionDevice(make_context().observation),  # type: ignore[arg-type]
    )

    assert result.status is AgentRouteStatus.INVALID_HANDOFF
