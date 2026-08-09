"""Device session facade preserving the existing API over a SessionStore."""

from __future__ import annotations

from uuid import uuid4

from app.action.models import ActionLifecycle, ActionRequest, ActionResult, ActionStatus
from app.core.exceptions import ObservationUnavailableError, SafetyViolationError
from app.core.safety import SafetyDecision, SafetyGuard
from app.observation.models import Observation
from app.transport.models import DeviceActionCommand, DeviceActionResultReport, DeviceSessionSnapshot
from app.transport.store import InMemorySessionStore, SessionStore

__all__ = [
    "DeviceActionCommand",
    "DeviceActionResultReport",
    "DeviceSessionManager",
    "DeviceSessionSnapshot",
]


class DeviceSessionManager:
    """Safety-aware facade for either an in-memory or SQLite session store."""

    def __init__(
        self,
        safety_guard: SafetyGuard | None = None,
        *,
        store: SessionStore | None = None,
        max_queue_size: int = 32,
        lease_timeout_seconds: float = 30.0,
        device_timeout_seconds: float = 60.0,
        max_lease_retries: int = 3,
    ) -> None:
        self.safety_guard = safety_guard or SafetyGuard()
        self.store = store or InMemorySessionStore()
        self.max_queue_size = max_queue_size
        self.lease_timeout_seconds = lease_timeout_seconds
        self.device_timeout_seconds = device_timeout_seconds
        self.max_lease_retries = max_lease_retries

    def receive_observation(self, device_id: str, observation: Observation) -> None:
        self.store.save_observation(device_id, observation)

    def latest_observation(self, device_id: str) -> Observation:
        observation = self.store.get_latest_observation(device_id)
        if observation is None:
            raise ObservationUnavailableError(f"no observation is available for device: {device_id}")
        return observation

    def enqueue_action(self, device_id: str, action: ActionRequest) -> DeviceActionCommand:
        observation = self.latest_observation(device_id)
        if action.observation_id != observation.observation_id:
            raise ValueError("action observation_id must match the device's latest observation")
        safety = self.safety_guard.evaluate(self._safety_text(observation, action))
        if safety.decision is SafetyDecision.STOP:
            raise SafetyViolationError(
                f"Safety stop: {safety.reason_code}; terms={safety.matched_terms}"
            )
        action_id = action.action_id or uuid4().hex
        normalized_action = action.model_copy(update={"action_id": action_id})
        command = DeviceActionCommand(
            command_id=uuid4().hex,
            action_id=action_id,
            device_id=device_id,
            action=normalized_action,
        )
        return self.store.enqueue_action(device_id, command, max_queue_size=self.max_queue_size)

    def next_action(self, device_id: str) -> DeviceActionCommand | None:
        return self.store.lease_next_action(
            device_id,
            lease_timeout_seconds=self.lease_timeout_seconds,
            device_timeout_seconds=self.device_timeout_seconds,
            max_lease_retries=self.max_lease_retries,
        )

    def lease_next_action(self, device_id: str) -> DeviceActionCommand | None:
        """Explicit lease-named alias for callers that need the new contract."""

        return self.next_action(device_id)

    def record_result(self, device_id: str, report: DeviceActionResultReport) -> None:
        if report.result.status is ActionStatus.SUCCESS:
            self.store.complete_action(device_id, report)
        else:
            self.store.fail_action(device_id, report)

    def complete_action(self, device_id: str, report: DeviceActionResultReport) -> None:
        self.store.complete_action(device_id, report)

    def fail_action(self, device_id: str, report: DeviceActionResultReport) -> None:
        self.store.fail_action(device_id, report)

    def result(self, command_id: str) -> DeviceActionResultReport | None:
        return self.store.get_result(command_id)

    def snapshot(self, device_id: str) -> DeviceSessionSnapshot:
        return self.store.get_device_state(device_id, device_timeout_seconds=self.device_timeout_seconds)

    def get_device_state(self, device_id: str) -> DeviceSessionSnapshot:
        return self.snapshot(device_id)

    @staticmethod
    def _safety_text(observation: Observation, action: ActionRequest) -> str:
        observation_text = " ".join(
            value
            for node in observation.nodes
            for value in (node.text, node.content_description)
            if value
        )
        return f"{observation_text} {action.model_dump_json()}"
