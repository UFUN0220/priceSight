"""Repeatable safe-mode end-to-end scenario over the mock shopping device."""

from __future__ import annotations

import re
import time
from decimal import Decimal

from pydantic import BaseModel, Field

from app.agent.models import AgentContext
from app.agent.planner import AgentPlanner
from app.agent.router import AgentDecisionRouter, AgentRouteStatus
from app.llm.base import LLMResponse
from app.llm.fake import FakeLLMProvider
from app.platform.mock_shopping import MockShoppingDevice
from app.workflow.engine import WorkflowEngine
from app.workflow.loader import WorkflowLoader
from app.workflow.models import WorkflowContext, WorkflowResult, WorkflowStatus


class MockE2EResult(BaseModel):
    task_id: str
    task_success: bool
    steps: int = Field(ge=0)
    retries: int = Field(ge=0)
    llm_calls: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    safety_result: WorkflowStatus
    final_price: Decimal | None = None
    compression_runs: int = Field(ge=0)
    compressed_observation_count: int = Field(ge=0)
    raw_observation_count: int = Field(ge=0)
    action_attempts: int = Field(ge=0)
    action_success_rate: float = Field(ge=0.0, le=1.0)
    safety_stop_correct: bool
    failure_reason: str | None = None


def run_mock_e2e() -> MockE2EResult:
    """Run search → agent selection → spec/coupon/cart → safe checkout stop."""

    started = time.perf_counter()
    device = MockShoppingDevice()
    engine = WorkflowEngine(max_steps=20)
    task_id = "mock-e2e-coca-cola-500ml"

    search_workflow = WorkflowLoader().from_text(
        """
        name: e2e_search
        steps:
          - id: open_search
            action: click
            target: {semantic_hint: search}
            expected: {expected_page_type: search}
          - id: input_keyword
            action: set_text
            target: {semantic_hint: search_input}
            value_from: task.product_keyword
          - id: submit_search
            action: click
            target: {semantic_hint: search_submit}
            expected: {expected_page_type: unknown}
        """
    )
    search_context = WorkflowContext(
        task_id=task_id,
        goal="搜索可口可乐500ml，选择2瓶规格，领取优惠并加入购物车",
        task={"product_keyword": "可口可乐500ml"},
    )
    search_result = engine.run(search_workflow, search_context, device)
    if search_result.status is not WorkflowStatus.SUCCEEDED:
        return _finish(task_id, False, [search_result], [], device, started, "search workflow failed")

    handoff_workflow = WorkflowLoader().from_text(
        """
        name: e2e_choose_product
        steps:
          - id: choose_product
            action: click
            requires_agent_decision: true
        """
    )
    handoff = engine.run(
        handoff_workflow,
        WorkflowContext(task_id=task_id, goal=search_context.goal),
        device,
    )
    provider = FakeLLMProvider(
        [
            LLMResponse(
                provider="fake",
                content=(
                    '{"reason_summary":"选择500ml两瓶商品结果","action":'
                    '{"action_type":"CLICK","target":{"resource_id":"result.cola.1"},'
                    '"observation_id":"stale"},"confidence":0.95,"requires_verification":true}'
                ),
            )
        ]
    )
    agent_context = AgentContext(
        user_goal=search_context.goal,
        current_platform="mock-shopping",
        workflow_state="choose_product",
        observation=device.observe(),
        known_constraints=["safe_mode", "do_not_submit_order", "do_not_pay"],
        retry_budget=1,
    )
    route_result = AgentDecisionRouter(AgentPlanner(provider)).route(handoff, agent_context, device)
    if route_result.status is not AgentRouteStatus.EXECUTED:
        return _finish(task_id, False, [search_result, handoff], [route_result], device, started, "agent route failed")

    detail_workflow = WorkflowLoader().from_text(
        """
        name: e2e_detail_to_cart
        steps:
          - id: open_spec
            action: click
            target: {semantic_hint: spec_selector}
            expected: {expected_page_type: product}
          - id: choose_spec
            action: click
            target: {semantic_hint: spec_2_bottles}
            expected: {expected_page_type: product}
          - id: open_coupon
            action: click
            target: {semantic_hint: coupon}
            expected: {expected_page_type: product}
          - id: claim_coupon
            action: click
            target: {semantic_hint: coupon_claim}
            expected: {expected_page_type: product}
          - id: return_to_detail
            action: back
            expected: {expected_page_type: product}
          - id: add_to_cart
            action: click
            target: {semantic_hint: add_to_cart}
            requires_cart_opt_in: true
            expected: {expected_page_type: cart}
        """
    )
    detail_result = engine.run(
        detail_workflow,
        WorkflowContext(
            task_id=task_id,
            goal=search_context.goal,
            allow_cart=True,
        ),
        device,
    )
    if detail_result.status is not WorkflowStatus.SUCCEEDED:
        return _finish(task_id, False, [search_result, handoff, detail_result], [route_result], device, started, "detail workflow failed")

    checkout_workflow = WorkflowLoader().from_text(
        """
        name: e2e_checkout_safety
        steps:
          - id: open_order_confirmation
            action: click
            target: {semantic_hint: checkout}
            expected: {expected_page_type: unknown}
          - id: submit_order_must_stop
            action: click
            target: {semantic_hint: submit_order}
        """
    )
    checkout_result = engine.run(
        checkout_workflow,
        WorkflowContext(task_id=task_id, goal=search_context.goal),
        device,
    )
    final_price = _extract_price(detail_result.final_observation or device.observe())
    all_workflows = [search_result, handoff, detail_result, checkout_result]
    success = (
        search_result.status is WorkflowStatus.SUCCEEDED
        and handoff.status is WorkflowStatus.NEEDS_AGENT_DECISION
        and route_result.status is AgentRouteStatus.EXECUTED
        and detail_result.status is WorkflowStatus.SUCCEEDED
        and checkout_result.status is WorkflowStatus.SAFETY_STOP
        and final_price == Decimal("10.90")
        and device.safety_stop_requested
    )
    return _finish(
        task_id,
        success,
        all_workflows,
        [route_result],
        device,
        started,
        None if success else "safe-mode E2E assertions failed",
        final_price,
        len(provider.calls),
    )


def _extract_price(observation) -> Decimal | None:
    for node in observation.nodes:
        if node.text and "最终价" in node.text:
            match = re.search(r"¥\s*(\d+(?:\.\d+)?)", node.text)
            if match:
                return Decimal(match.group(1))
    return None


def _finish(
    task_id: str,
    success: bool,
    workflows: list[WorkflowResult],
    routes: list,
    device: MockShoppingDevice,
    started: float,
    failure_reason: str | None,
    final_price: Decimal | None = None,
    llm_calls: int = 0,
) -> MockE2EResult:
    action_results = [action_result for workflow in workflows for action_result in workflow.action_results]
    action_results.extend(
        route.action_result
        for route in routes
        if getattr(route, "action_result", None) is not None
    )
    action_attempts = len(action_results)
    action_success_rate = (
        sum(result.success for result in action_results) / action_attempts
        if action_attempts
        else 0.0
    )
    safety_stop_correct = bool(workflows) and workflows[-1].status is WorkflowStatus.SAFETY_STOP and device.safety_stop_requested
    return MockE2EResult(
        task_id=task_id,
        task_success=success,
        steps=sum(item.context.step_count for item in workflows) + len(routes),
        retries=sum(item.context.retry_count for item in workflows),
        llm_calls=llm_calls,
        latency_ms=(time.perf_counter() - started) * 1000,
        safety_result=workflows[-1].status if workflows else WorkflowStatus.FAILED,
        final_price=final_price,
        compression_runs=len(device.compression_stats),
        compressed_observation_count=sum(item.compressed_node_count for item in device.compression_stats),
        raw_observation_count=sum(item.raw_node_count for item in device.compression_stats),
        action_attempts=action_attempts,
        action_success_rate=action_success_rate,
        safety_stop_correct=safety_stop_correct,
        failure_reason=failure_reason,
    )
