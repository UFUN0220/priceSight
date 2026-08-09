"""Regression tests for phase 11 action-harness reliability behavior."""

from app.action.fake import FakeActionDevice
from app.action.models import ActionStatus
from app.core.reliability import BadCaseCategory, RepetitionDetector, action_signature, observation_hash
from app.observation.models import Observation, ObservationNode, PageType
from app.workflow.engine import WorkflowEngine
from app.workflow.loader import WorkflowLoader
from app.workflow.models import WorkflowContext, WorkflowStatus


def make_observation(observation_id: str = "obs-1", duplicate: bool = False) -> Observation:
    nodes = [ObservationNode(node_id="search", text="Search", clickable=True)]
    if duplicate:
        nodes.append(ObservationNode(node_id="search-2", text="Search", clickable=True))
    return Observation(observation_id=observation_id, page_type=PageType.SEARCH, nodes=nodes)


def test_repeated_rejected_action_requests_replan() -> None:
    workflow = WorkflowLoader().from_text(
        """
        name: repeated_action
        steps:
          - id: click_search
            action: click
            target: {semantic_hint: search}
            retry_limit: 2
        """
    )
    device = FakeActionDevice(make_observation())
    device.reject_actions.add("click")

    result = WorkflowEngine().run(workflow, WorkflowContext(task_id="task-replan", goal="retry"), device)

    assert result.status is WorkflowStatus.NEEDS_AGENT_DECISION
    assert result.action_results[-1].status is ActionStatus.REPLAN_REQUIRED
    assert result.trace_events[-1].bad_case is BadCaseCategory.ACTION_NO_EFFECT
    assert len(device.calls) == 1


def test_missing_target_is_recorded_as_bad_case() -> None:
    workflow = WorkflowLoader().from_text(
        """
        name: missing_target
        steps:
          - id: click_missing
            action: click
            target: {semantic_hint: coupon}
        """
    )

    result = WorkflowEngine().run(
        workflow,
        WorkflowContext(task_id="task-missing", goal="find coupon"),
        FakeActionDevice(make_observation()),
    )

    assert result.status is WorkflowStatus.FAILED
    assert result.trace_events[0].bad_case is BadCaseCategory.TARGET_MISSING


def test_duplicate_target_is_recorded_as_bad_case() -> None:
    workflow = WorkflowLoader().from_text(
        """
        name: duplicate_target
        steps:
          - id: click_search
            action: click
            target: {semantic_hint: search}
        """
    )

    result = WorkflowEngine().run(
        workflow,
        WorkflowContext(task_id="task-duplicate", goal="choose search"),
        FakeActionDevice(make_observation(duplicate=True)),
    )

    assert result.status is WorkflowStatus.FAILED
    assert result.trace_events[0].bad_case is BadCaseCategory.DUPLICATE_TARGET


def test_reliability_keys_are_stable_and_ignore_observation_id_for_action() -> None:
    first = make_observation("obs-1")
    second = make_observation("obs-2")
    workflow = WorkflowLoader().from_text(
        """
        name: key_stability
        steps:
          - id: click_search
            action: click
            target: {semantic_hint: search}
        """
    )
    assert observation_hash(first) != observation_hash(second)
    detector = RepetitionDetector()
    planned_request = WorkflowEngine._plan(workflow.steps[0], WorkflowContext(task_id="task", goal="key"), first).request
    refreshed_request = planned_request.model_copy(update={"observation_id": "obs-2"})
    assert action_signature(planned_request) == action_signature(refreshed_request)
    assert detector.register(first, planned_request) is False
    assert detector.register(first, planned_request) is True
