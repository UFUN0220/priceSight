"""设备观察、动作下发和结果回传闭环测试。"""

import pytest

from app.action.models import ActionLifecycle, ActionRequest, ActionResult, ActionStatus, ActionTarget, ActionType
from app.core.exceptions import SafetyViolationError
from app.observation.models import Observation, ObservationNode
from app.transport.session import DeviceActionResultReport, DeviceSessionManager


def _observation(observation_id: str, text: str = "商品详情") -> Observation:
    return Observation(
        observation_id=observation_id,
        package_name="com.example.shop",
        timestamp_epoch_ms=123,
        nodes=[
            ObservationNode(
                node_id="root:0",
                text=text,
                clickable=True,
                enabled=True,
                visible=True,
                bounds=(0, 0, 100, 100),
                depth=0,
                children=[],
            )
        ],
    )


def _click(observation_id: str) -> ActionRequest:
    return ActionRequest(
        action_type=ActionType.CLICK,
        target=ActionTarget(node_id="root:0", bounds=(0, 0, 100, 100)),
        observation_id=observation_id,
    )


def test_device_session_completes_observation_action_result_cycle() -> None:
    manager = DeviceSessionManager()
    manager.receive_observation("device-1", _observation("obs-1"))

    command = manager.enqueue_action("device-1", _click("obs-1"))
    assert command.lifecycle is ActionLifecycle.QUEUED
    assert manager.next_action("device-1") == command
    assert command.lifecycle is ActionLifecycle.DISPATCHED

    manager.record_result(
        "device-1",
        DeviceActionResultReport(
            command_id=command.command_id,
            result=ActionResult(success=True, status=ActionStatus.SUCCESS),
        ),
    )

    snapshot = manager.snapshot("device-1")
    assert snapshot.latest_observation_id == "obs-1"
    assert snapshot.pending_action_count == 0
    assert snapshot.completed_action_count == 1
    assert snapshot.lifecycle_counts[ActionLifecycle.SUCCESS.value] == 1


def test_device_session_rejects_action_planned_from_old_observation() -> None:
    manager = DeviceSessionManager()
    manager.receive_observation("device-1", _observation("obs-2"))

    with pytest.raises(ValueError, match="latest observation"):
        manager.enqueue_action("device-1", _click("obs-1"))


def test_device_session_drops_action_that_becomes_stale_before_dispatch() -> None:
    manager = DeviceSessionManager()
    manager.receive_observation("device-1", _observation("obs-1"))
    command = manager.enqueue_action("device-1", _click("obs-1"))
    manager.receive_observation("device-1", _observation("obs-2"))

    assert manager.next_action("device-1") is None
    report = manager.result(command.command_id)
    assert report is not None
    assert report.result.status is ActionStatus.STALE_OBSERVATION
    assert report.lifecycle is ActionLifecycle.STALE


def test_device_session_deduplicates_same_action_id_and_result_callback() -> None:
    manager = DeviceSessionManager()
    manager.receive_observation("device-1", _observation("obs-1"))
    action = _click("obs-1").model_copy(update={"action_id": "action-retry-1"})

    first = manager.enqueue_action("device-1", action)
    second = manager.enqueue_action("device-1", action)
    assert second.command_id == first.command_id
    assert manager.snapshot("device-1").pending_action_count == 1

    manager.next_action("device-1")
    report = DeviceActionResultReport(
        command_id=first.command_id,
        result=ActionResult(success=True, status=ActionStatus.SUCCESS),
    )
    manager.record_result("device-1", report)
    manager.record_result("device-1", report)
    assert manager.snapshot("device-1").completed_action_count == 1


@pytest.mark.parametrize(
    ("status", "lifecycle"),
    [
        (ActionStatus.TARGET_NOT_FOUND, ActionLifecycle.FAILED),
        (ActionStatus.SAFETY_BLOCKED, ActionLifecycle.SAFETY_BLOCKED),
        (ActionStatus.ACTION_REJECTED, ActionLifecycle.FAILED),
    ],
)
def test_device_session_maps_terminal_action_status_to_lifecycle(
    status: ActionStatus,
    lifecycle: ActionLifecycle,
) -> None:
    manager = DeviceSessionManager()
    manager.receive_observation("device-1", _observation("obs-1"))
    command = manager.enqueue_action("device-1", _click("obs-1"))
    manager.next_action("device-1")

    manager.record_result(
        "device-1",
        DeviceActionResultReport(
            command_id=command.command_id,
            result=ActionResult(success=False, status=status),
        ),
    )

    assert manager.snapshot("device-1").lifecycle_counts[lifecycle.value] == 1


def test_device_session_blocks_unsafe_page_before_queueing() -> None:
    manager = DeviceSessionManager()
    manager.receive_observation("device-1", _observation("obs-1", "确认支付"))

    with pytest.raises(SafetyViolationError, match="Safety stop"):
        manager.enqueue_action("device-1", _click("obs-1"))
