"""Tests for safe action execution and fresh-observation verification."""

from app.action.executor import ActionExecutor
from app.action.fake import FakeActionDevice
from app.action.models import ActionRequest, ActionStatus, ActionType
from app.action.verifier import VerificationExpectation
from app.observation.models import Observation, ObservationNode, PageType


def make_observation(observation_id: str = "obs-1", text: str = "Search") -> Observation:
    return Observation(
        observation_id=observation_id,
        page_type=PageType.SEARCH,
        nodes=[
            ObservationNode(
                node_id="search",
                text=text,
                editable=True,
                resource_id="search_box",
                bounds=(0, 0, 100, 50),
            )
        ],
    )


def test_click_uses_fresh_match_and_verifies_transition() -> None:
    before = make_observation()
    after = Observation(
        observation_id="obs-2",
        page_type=PageType.PRODUCT,
        nodes=[ObservationNode(node_id="title", text="商品详情")],
    )
    device = FakeActionDevice(before)
    device.set_next_observation(after)

    result = ActionExecutor().execute(
        ActionRequest(
            action_type=ActionType.CLICK,
            target={"resource_id": "search_box"},
            observation_id="obs-1",
        ),
        before,
        device,
        VerificationExpectation(expected_page_type=PageType.PRODUCT, required_text="商品详情"),
    )

    assert result.status is ActionStatus.SUCCESS
    assert result.matched_node_id == "search"
    assert device.calls[0].name == "click"


def test_stale_observation_is_rejected_before_matching() -> None:
    observation = make_observation()

    result = ActionExecutor().execute(
        ActionRequest(
            action_type=ActionType.CLICK,
            target={"resource_id": "search_box"},
            observation_id="old-observation",
        ),
        observation,
        FakeActionDevice(observation),
    )

    assert result.status is ActionStatus.STALE_OBSERVATION


def test_payment_page_is_deterministically_blocked() -> None:
    observation = make_observation(text="确认支付并输入支付密码")

    result = ActionExecutor().execute(
        ActionRequest(action_type=ActionType.BACK, observation_id=observation.observation_id),
        observation,
        FakeActionDevice(observation),
    )

    assert result.status is ActionStatus.SAFETY_BLOCKED


def test_empty_target_is_not_required_for_root_scroll() -> None:
    observation = make_observation()
    result = ActionExecutor().execute(
        ActionRequest(action_type=ActionType.SCROLL_FORWARD, observation_id=observation.observation_id),
        observation,
        FakeActionDevice(observation),
    )

    assert result.status is ActionStatus.SUCCESS


def test_unknown_scroll_target_is_rejected() -> None:
    observation = make_observation()
    result = ActionExecutor().execute(
        ActionRequest(
            action_type=ActionType.SCROLL_FORWARD,
            target={"node_id": "missing"},
            observation_id=observation.observation_id,
        ),
        observation,
        FakeActionDevice(observation),
    )

    assert result.status is ActionStatus.TARGET_NOT_FOUND


def test_rejected_device_action_has_explicit_status() -> None:
    observation = make_observation()
    device = FakeActionDevice(observation)
    device.reject_actions.add("back")

    result = ActionExecutor().execute(
        ActionRequest(action_type=ActionType.BACK, observation_id=observation.observation_id),
        observation,
        device,
    )

    assert result.status is ActionStatus.ACTION_REJECTED
