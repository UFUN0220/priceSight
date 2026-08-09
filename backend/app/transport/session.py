"""In-memory device sessions for observation, action, and result exchange."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from pydantic import BaseModel, Field

from app.action.models import ActionLifecycle, ActionRequest, ActionResult, ActionStatus
from app.core.exceptions import ObservationUnavailableError, SafetyViolationError
from app.core.safety import SafetyDecision, SafetyGuard
from app.observation.models import Observation


class DeviceActionCommand(BaseModel):
    command_id: str
    action_id: str
    device_id: str
    action: ActionRequest
    lifecycle: ActionLifecycle = ActionLifecycle.QUEUED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DeviceActionResultReport(BaseModel):
    command_id: str
    result: ActionResult
    lifecycle: ActionLifecycle | None = None


class DeviceSessionSnapshot(BaseModel):
    device_id: str
    latest_observation_id: str | None = None
    pending_action_count: int = 0
    completed_action_count: int = 0
    lifecycle_counts: dict[str, int] = Field(default_factory=dict)


class DeviceSessionManager:
    """Process-local session store used by the local Android bridge."""

    def __init__(self, safety_guard: SafetyGuard | None = None) -> None:
        self.safety_guard = safety_guard or SafetyGuard()
        self._observations: dict[str, Observation] = {}
        self._pending: dict[str, deque[DeviceActionCommand]] = defaultdict(deque)
        self._commands: dict[str, DeviceActionCommand] = {}
        self._action_index: dict[tuple[str, str], str] = {}
        self._results: dict[str, DeviceActionResultReport] = {}
        self._lock = RLock()

    def receive_observation(self, device_id: str, observation: Observation) -> None:
        with self._lock:
            self._observations[device_id] = observation

    def latest_observation(self, device_id: str) -> Observation:
        with self._lock:
            observation = self._observations.get(device_id)
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
        with self._lock:
            action_id = action.action_id or uuid4().hex
            existing_command_id = self._action_index.get((device_id, action_id))
            if existing_command_id is not None:
                existing = self._commands[existing_command_id]
                if existing.action != action.model_copy(update={"action_id": action_id}):
                    raise ValueError("action_id was already used for a different action")
                return existing
            normalized_action = action.model_copy(update={"action_id": action_id})
            command = DeviceActionCommand(
                command_id=uuid4().hex,
                action_id=action_id,
                device_id=device_id,
                action=normalized_action,
            )
            self._pending[device_id].append(command)
            self._commands[command.command_id] = command
            self._action_index[(device_id, action_id)] = command.command_id
        return command

    def next_action(self, device_id: str) -> DeviceActionCommand | None:
        with self._lock:
            queue = self._pending[device_id]
            while queue:
                command = queue.popleft()
                observation = self._observations.get(device_id)
                if (
                    observation is not None
                    and command.action.observation_id == observation.observation_id
                ):
                    command.lifecycle = ActionLifecycle.DISPATCHED
                    return command
                command.lifecycle = ActionLifecycle.STALE
                self._results[command.command_id] = DeviceActionResultReport(
                    command_id=command.command_id,
                    result=ActionResult(
                        success=False,
                        status=ActionStatus.STALE_OBSERVATION,
                        message="action was not dispatched because the device observation changed",
                        observation_id=observation.observation_id if observation else None,
                    ),
                    lifecycle=ActionLifecycle.STALE,
                )
            return None

    def record_result(self, device_id: str, report: DeviceActionResultReport) -> None:
        with self._lock:
            command = self._commands.get(report.command_id)
            if command is None or command.device_id != device_id:
                raise ValueError("action result does not belong to this device session")
            if report.command_id in self._results:
                return
            command.lifecycle = ActionLifecycle.EXECUTING
            final_lifecycle = report.lifecycle or self._lifecycle_for_result(report.result)
            command.lifecycle = final_lifecycle
            report = report.model_copy(update={"lifecycle": final_lifecycle})
            self._results[report.command_id] = report

    def result(self, command_id: str) -> DeviceActionResultReport | None:
        with self._lock:
            return self._results.get(command_id)

    def snapshot(self, device_id: str) -> DeviceSessionSnapshot:
        with self._lock:
            observation = self._observations.get(device_id)
            completed = sum(
                1
                for command_id, command in self._commands.items()
                if command.device_id == device_id and command_id in self._results
            )
            lifecycle_counts = {
                lifecycle.value: sum(
                    1
                    for command in self._commands.values()
                    if command.device_id == device_id and command.lifecycle is lifecycle
                )
                for lifecycle in ActionLifecycle
            }
            return DeviceSessionSnapshot(
                device_id=device_id,
                latest_observation_id=observation.observation_id if observation else None,
                pending_action_count=len(self._pending[device_id]),
                completed_action_count=completed,
                lifecycle_counts=lifecycle_counts,
            )

    @staticmethod
    def _lifecycle_for_result(result: ActionResult) -> ActionLifecycle:
        if result.status is ActionStatus.SUCCESS:
            return ActionLifecycle.SUCCESS
        if result.status is ActionStatus.STALE_OBSERVATION:
            return ActionLifecycle.STALE
        if result.status is ActionStatus.SAFETY_BLOCKED:
            return ActionLifecycle.SAFETY_BLOCKED
        return ActionLifecycle.FAILED

    @staticmethod
    def _safety_text(observation: Observation, action: ActionRequest) -> str:
        observation_text = " ".join(
            value
            for node in observation.nodes
            for value in (node.text, node.content_description)
            if value
        )
        return f"{observation_text} {action.model_dump_json()}"
