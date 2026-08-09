"""Phase 6 session store reliability and persistence tests."""

from concurrent.futures import ThreadPoolExecutor
from time import sleep

import pytest

from app.action.models import ActionRequest, ActionResult, ActionStatus, ActionTarget, ActionType
from app.observation.models import Observation, ObservationNode
from app.transport.models import DeviceActionResultReport
from app.transport.session import DeviceSessionManager
from app.transport.store import InMemorySessionStore, SQLiteSessionStore, SessionQueueFullError


def _observation(observation_id: str) -> Observation:
    return Observation(
        observation_id=observation_id,
        package_name="com.example.shop",
        timestamp_epoch_ms=123,
        nodes=[
            ObservationNode(
                node_id="root:0",
                text="商品详情",
                clickable=True,
                enabled=True,
                visible=True,
                bounds=(0, 0, 100, 100),
                depth=0,
                children=[],
            )
        ],
    )


def _click(observation_id: str, action_id: str | None = None) -> ActionRequest:
    return ActionRequest(
        action_id=action_id or ActionRequest.model_fields["action_id"].default_factory(),
        action_type=ActionType.CLICK,
        target=ActionTarget(node_id="root:0", bounds=(0, 0, 100, 100)),
        observation_id=observation_id,
    )


def test_two_consumers_cannot_lease_the_same_action() -> None:
    manager = DeviceSessionManager(lease_timeout_seconds=10)
    manager.receive_observation("device-1", _observation("obs-1"))
    manager.enqueue_action("device-1", _click("obs-1", "action-concurrent"))

    with ThreadPoolExecutor(max_workers=2) as executor:
        leases = list(executor.map(lambda _: manager.next_action("device-1"), range(2)))

    assert sum(lease is not None for lease in leases) == 1


def test_completed_action_is_idempotent_and_never_leased_again() -> None:
    manager = DeviceSessionManager()
    manager.receive_observation("device-1", _observation("obs-1"))
    command = manager.enqueue_action("device-1", _click("obs-1", "action-complete"))
    assert manager.next_action("device-1") is not None
    report = DeviceActionResultReport(
        command_id=command.command_id,
        result=ActionResult(success=True, status=ActionStatus.SUCCESS),
    )

    manager.complete_action("device-1", report)
    manager.complete_action("device-1", report)

    assert manager.next_action("device-1") is None
    assert manager.result(command.command_id) is not None


def test_expired_lease_is_requeued_with_retry_count() -> None:
    manager = DeviceSessionManager(lease_timeout_seconds=0.001, max_lease_retries=2)
    manager.receive_observation("device-1", _observation("obs-1"))
    manager.enqueue_action("device-1", _click("obs-1", "action-timeout"))
    first = manager.next_action("device-1")
    assert first is not None
    first_lease_id = first.lease_id

    sleep(0.02)
    second = manager.next_action("device-1")
    assert second is not None
    assert second.command_id == first.command_id
    assert second.retry_count == 1
    assert second.lease_id != first_lease_id


def test_stale_observation_action_is_cleaned_and_never_leased() -> None:
    manager = DeviceSessionManager()
    manager.receive_observation("device-1", _observation("obs-1"))
    command = manager.enqueue_action("device-1", _click("obs-1", "action-stale"))
    manager.receive_observation("device-1", _observation("obs-2"))

    assert manager.next_action("device-1") is None
    assert manager.result(command.command_id) is not None
    assert manager.result(command.command_id).result.status is ActionStatus.STALE_OBSERVATION


def test_queue_limit_applies_backpressure() -> None:
    manager = DeviceSessionManager(max_queue_size=1)
    manager.receive_observation("device-1", _observation("obs-1"))
    manager.enqueue_action("device-1", _click("obs-1", "action-1"))

    with pytest.raises(SessionQueueFullError, match="queue is full"):
        manager.enqueue_action("device-1", _click("obs-1", "action-2"))


def test_disconnected_device_does_not_receive_queued_action() -> None:
    manager = DeviceSessionManager(device_timeout_seconds=0.001)
    manager.receive_observation("device-1", _observation("obs-1"))
    manager.enqueue_action("device-1", _click("obs-1", "action-disconnected"))
    sleep(0.02)

    assert manager.next_action("device-1") is None
    assert manager.snapshot("device-1").connected is False


def test_sqlite_store_survives_manager_recreation(tmp_path) -> None:
    path = tmp_path / "device-sessions.sqlite3"
    first_manager = DeviceSessionManager(store=SQLiteSessionStore(path))
    first_manager.receive_observation("device-1", _observation("obs-persisted"))
    command = first_manager.enqueue_action("device-1", _click("obs-persisted", "action-persisted"))
    first_manager.store.close()

    second_store = SQLiteSessionStore(path)
    second_manager = DeviceSessionManager(store=second_store)
    assert second_manager.latest_observation("device-1").observation_id == "obs-persisted"
    leased = second_manager.next_action("device-1")
    assert leased is not None
    assert leased.command_id == command.command_id
    second_manager.record_result(
        "device-1",
        DeviceActionResultReport(
            command_id=command.command_id,
            result=ActionResult(success=True, status=ActionStatus.SUCCESS),
        ),
    )
    assert second_manager.snapshot("device-1").completed_action_count == 1
    second_store.close()


def test_sqlite_store_leases_once_under_two_consumers(tmp_path) -> None:
    manager = DeviceSessionManager(store=SQLiteSessionStore(tmp_path / "concurrent.sqlite3"))
    manager.receive_observation("device-1", _observation("obs-1"))
    manager.enqueue_action("device-1", _click("obs-1", "action-sqlite-concurrent"))

    with ThreadPoolExecutor(max_workers=2) as executor:
        leases = list(executor.map(lambda _: manager.next_action("device-1"), range(2)))

    assert sum(lease is not None for lease in leases) == 1
    manager.store.close()


def test_in_memory_store_remains_explicitly_available() -> None:
    manager = DeviceSessionManager(store=InMemorySessionStore())
    manager.receive_observation("device-1", _observation("obs-1"))
    assert manager.latest_observation("device-1").observation_id == "obs-1"
