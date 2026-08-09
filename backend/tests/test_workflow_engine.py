"""Offline integration tests for bounded YAML workflow execution."""

from app.action.fake import FakeActionDevice
from app.observation.models import Observation, ObservationNode, PageType
from app.workflow.engine import WorkflowEngine
from app.workflow.loader import WorkflowLoader
from app.workflow.models import WorkflowContext, WorkflowStatus


def make_observation(observation_id: str = "obs-1", page_type: PageType = PageType.SEARCH) -> Observation:
    return Observation(
        observation_id=observation_id,
        page_type=page_type,
        nodes=[
            ObservationNode(node_id="search", text="Search", clickable=True),
            ObservationNode(node_id="input", text="Search input", editable=True),
            ObservationNode(node_id="submit", text="Search submit", clickable=True),
        ],
    )


def test_engine_runs_sequential_steps_and_resolves_task_value() -> None:
    workflow = WorkflowLoader().from_text(
        """
        name: search_product
        steps:
          - id: open_search
            action: click
            target: {semantic_hint: search}
          - id: input_keyword
            action: set_text
            target: {semantic_hint: search input}
            value_from: task.product_keyword
          - id: submit
            action: click
            target: {semantic_hint: search submit}
            expected: {expected_page_type: search}
        """
    )
    device = FakeActionDevice(make_observation())
    context = WorkflowContext(task_id="task-1", goal="查找牛奶", task={"product_keyword": "牛奶"})

    result = WorkflowEngine().run(workflow, context, device)

    assert result.status is WorkflowStatus.SUCCEEDED
    assert result.completed_steps == ["open_search", "input_keyword", "submit"]
    assert [call.name for call in device.calls] == ["click", "set_text", "click"]
    assert device.calls[1].value == "牛奶"


def test_engine_retries_transient_device_rejection() -> None:
    workflow = WorkflowLoader().from_text(
        """
        name: retry
        steps:
          - id: click_search
            action: click
            target: {semantic_hint: search}
            retry_limit: 1
        """
    )
    device = FakeActionDevice(make_observation())
    device.reject_once_actions.add("click")
    context = WorkflowContext(task_id="task-2", goal="retry")

    result = WorkflowEngine().run(workflow, context, device)

    assert result.status is WorkflowStatus.SUCCEEDED
    assert context.retry_count == 1
    assert len(device.calls) == 2


def test_optional_step_is_skipped_without_stopping_workflow() -> None:
    workflow = WorkflowLoader().from_text(
        """
        name: optional
        steps:
          - id: optional_coupon
            action: click
            target: {semantic_hint: coupon}
            optional: true
          - id: finish
            action: wait
        """
    )
    device = FakeActionDevice(make_observation())
    result = WorkflowEngine().run(workflow, WorkflowContext(task_id="task-3", goal="optional"), device)

    assert result.status is WorkflowStatus.SUCCEEDED
    assert result.skipped_steps == ["optional_coupon"]
    assert result.completed_steps == ["finish"]


def test_ambiguous_or_explicit_agent_step_does_not_execute() -> None:
    workflow = WorkflowLoader().from_text(
        """
        name: ambiguous
        steps:
          - id: choose_result
            action: click
            target: {semantic_hint: product_result}
            requires_agent_decision: true
        """
    )
    device = FakeActionDevice(make_observation())
    result = WorkflowEngine().run(workflow, WorkflowContext(task_id="task-4", goal="choose"), device)

    assert result.status is WorkflowStatus.NEEDS_AGENT_DECISION
    assert result.agent_decision_step_id == "choose_result"
    assert device.calls == []


def test_payment_observation_causes_safety_stop() -> None:
    observation = make_observation()
    payment = observation.model_copy(
        update={
            "observation_id": "payment",
            "nodes": [ObservationNode(node_id="pay", text="确认支付")],
        }
    )
    workflow = WorkflowLoader().from_text(
        """
        name: blocked
        steps:
          - id: back
            action: back
        """
    )
    device = FakeActionDevice(payment)
    result = WorkflowEngine().run(workflow, WorkflowContext(task_id="task-5", goal="blocked"), device)

    assert result.status is WorkflowStatus.SAFETY_STOP
    assert result.action_results == []
    assert device.calls[-1].name == "stop"


def test_cart_workflow_requires_explicit_opt_in() -> None:
    workflow = WorkflowLoader().from_path("workflows/add_to_cart.yaml")
    device = FakeActionDevice(make_observation())
    result = WorkflowEngine().run(workflow, WorkflowContext(task_id="task-6", goal="cart"), device)

    assert result.status is WorkflowStatus.SAFETY_STOP
    assert "allow_cart" in (result.failure_reason or "")
    assert device.calls[-1].name == "stop"
