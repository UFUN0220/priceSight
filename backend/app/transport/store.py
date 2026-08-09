"""Replaceable device session stores with a local SQLite implementation."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Protocol
from uuid import uuid4

from app.action.models import ActionLifecycle, ActionRequest, ActionResult, ActionStatus
from app.observation.models import Observation
from app.transport.models import DeviceActionCommand, DeviceActionResultReport, DeviceSessionSnapshot


class SessionStoreError(RuntimeError):
    """Base error for session storage failures."""


class SessionQueueFullError(SessionStoreError):
    """Raised when a device queue reaches its configured backpressure limit."""


class SessionStore(Protocol):
    """Storage contract for observation and action session state."""

    def save_observation(self, device_id: str, observation: Observation) -> None: ...

    def get_latest_observation(self, device_id: str) -> Observation | None: ...

    def enqueue_action(self, device_id: str, command: DeviceActionCommand, *, max_queue_size: int) -> DeviceActionCommand: ...

    def lease_next_action(self, device_id: str, *, lease_timeout_seconds: float, device_timeout_seconds: float, max_lease_retries: int) -> DeviceActionCommand | None: ...

    def complete_action(self, device_id: str, report: DeviceActionResultReport) -> None: ...

    def fail_action(self, device_id: str, report: DeviceActionResultReport) -> None: ...

    def get_device_state(self, device_id: str, *, device_timeout_seconds: float) -> DeviceSessionSnapshot: ...

    def get_result(self, command_id: str) -> DeviceActionResultReport | None: ...


class InMemorySessionStore:
    """Thread-safe store used by unit tests and explicitly local sessions."""

    def __init__(self) -> None:
        self._observations: dict[str, Observation] = {}
        self._last_seen: dict[str, datetime] = {}
        self._commands: dict[str, DeviceActionCommand] = {}
        self._action_index: dict[tuple[str, str], str] = {}
        self._results: dict[str, DeviceActionResultReport] = {}
        self._lock = RLock()

    def save_observation(self, device_id: str, observation: Observation) -> None:
        with self._lock:
            self._observations[device_id] = observation
            self._last_seen[device_id] = datetime.now(timezone.utc)

    def get_latest_observation(self, device_id: str) -> Observation | None:
        with self._lock:
            return self._observations.get(device_id)

    def enqueue_action(self, device_id: str, command: DeviceActionCommand, *, max_queue_size: int) -> DeviceActionCommand:
        with self._lock:
            existing_id = self._action_index.get((device_id, command.action_id))
            if existing_id is not None:
                existing = self._commands[existing_id]
                if existing.action != command.action:
                    raise ValueError("action_id was already used for a different action")
                return existing
            if self._active_count(device_id) >= max_queue_size:
                raise SessionQueueFullError(f"device action queue is full: {device_id}")
            self._commands[command.command_id] = command
            self._action_index[(device_id, command.action_id)] = command.command_id
            return command

    def lease_next_action(self, device_id: str, *, lease_timeout_seconds: float, device_timeout_seconds: float, max_lease_retries: int) -> DeviceActionCommand | None:
        with self._lock:
            if not self._connected(device_id, device_timeout_seconds):
                return None
            self._reclaim_expired(device_id, max_lease_retries)
            observation = self._observations.get(device_id)
            candidates = sorted(
                (command for command in self._commands.values() if command.device_id == device_id and command.lifecycle is ActionLifecycle.QUEUED),
                key=lambda command: command.created_at,
            )
            for command in candidates:
                if observation is None or command.action.observation_id != observation.observation_id:
                    self._mark_stale(command, observation)
                    continue
                command.lifecycle = ActionLifecycle.DISPATCHED
                command.lease_id = uuid4().hex
                command.leased_until = datetime.now(timezone.utc) + timedelta(seconds=lease_timeout_seconds)
                return command
            return None

    def complete_action(self, device_id: str, report: DeviceActionResultReport) -> None:
        self._record_terminal(device_id, report, ActionLifecycle.SUCCESS)

    def fail_action(self, device_id: str, report: DeviceActionResultReport) -> None:
        self._record_terminal(device_id, report, report.lifecycle or _lifecycle_for_result(report.result))

    def get_device_state(self, device_id: str, *, device_timeout_seconds: float) -> DeviceSessionSnapshot:
        with self._lock:
            observation = self._observations.get(device_id)
            commands = [command for command in self._commands.values() if command.device_id == device_id]
            lifecycle_counts = {lifecycle.value: sum(command.lifecycle is lifecycle for command in commands) for lifecycle in ActionLifecycle}
            return DeviceSessionSnapshot(
                device_id=device_id,
                latest_observation_id=observation.observation_id if observation else None,
                pending_action_count=sum(command.lifecycle is ActionLifecycle.QUEUED for command in commands),
                leased_action_count=sum(command.lifecycle in {ActionLifecycle.DISPATCHED, ActionLifecycle.EXECUTING} for command in commands),
                completed_action_count=sum(command.command_id in self._results for command in commands),
                retry_count=sum(command.retry_count for command in commands),
                connected=self._connected(device_id, device_timeout_seconds),
                lifecycle_counts=lifecycle_counts,
            )

    def get_result(self, command_id: str) -> DeviceActionResultReport | None:
        with self._lock:
            return self._results.get(command_id)

    def _record_terminal(self, device_id: str, report: DeviceActionResultReport, lifecycle: ActionLifecycle) -> None:
        with self._lock:
            command = self._commands.get(report.command_id)
            if command is None or command.device_id != device_id:
                raise ValueError("action result does not belong to this device session")
            if report.command_id in self._results:
                return
            command.lifecycle = lifecycle
            command.lease_id = None
            command.leased_until = None
            self._results[report.command_id] = report.model_copy(update={"lifecycle": lifecycle})

    def _reclaim_expired(self, device_id: str, max_lease_retries: int) -> None:
        now = datetime.now(timezone.utc)
        for command in self._commands.values():
            if command.device_id == device_id and command.lifecycle in {ActionLifecycle.DISPATCHED, ActionLifecycle.EXECUTING} and command.leased_until is not None and command.leased_until <= now:
                command.lease_id = None
                command.leased_until = None
                command.retry_count += 1
                if command.retry_count > max_lease_retries:
                    self._results[command.command_id] = DeviceActionResultReport(
                        command_id=command.command_id,
                        result=ActionResult(success=False, status=ActionStatus.RETRY_EXHAUSTED, message="action lease expired too many times"),
                        lifecycle=ActionLifecycle.FAILED,
                    )
                    command.lifecycle = ActionLifecycle.FAILED
                else:
                    command.lifecycle = ActionLifecycle.QUEUED

    def _mark_stale(self, command: DeviceActionCommand, observation: Observation | None) -> None:
        command.lifecycle = ActionLifecycle.STALE
        self._results[command.command_id] = DeviceActionResultReport(
            command_id=command.command_id,
            result=ActionResult(success=False, status=ActionStatus.STALE_OBSERVATION, message="action was not dispatched because the device observation changed", observation_id=observation.observation_id if observation else None),
            lifecycle=ActionLifecycle.STALE,
        )

    def _active_count(self, device_id: str) -> int:
        return sum(command.device_id == device_id and command.lifecycle in {ActionLifecycle.QUEUED, ActionLifecycle.DISPATCHED, ActionLifecycle.EXECUTING} for command in self._commands.values())

    def _connected(self, device_id: str, timeout_seconds: float) -> bool:
        last_seen = self._last_seen.get(device_id)
        return last_seen is not None and timeout_seconds > 0 and datetime.now(timezone.utc) - last_seen <= timedelta(seconds=timeout_seconds)


class SQLiteSessionStore:
    """Small local durable store; SQLite is enough for this single-process app."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, check_same_thread=False, timeout=5)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS device_observations (
                device_id TEXT PRIMARY KEY,
                observation_json TEXT NOT NULL,
                observed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS device_actions (
                command_id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                action_id TEXT NOT NULL,
                action_json TEXT NOT NULL,
                lifecycle TEXT NOT NULL,
                created_at TEXT NOT NULL,
                lease_id TEXT,
                leased_until TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                result_json TEXT,
                result_lifecycle TEXT,
                UNIQUE(device_id, action_id)
            );
            CREATE INDEX IF NOT EXISTS idx_device_actions_queue
                ON device_actions(device_id, lifecycle, created_at);
            """
        )
        self._connection.commit()
        self._lock = RLock()

    def save_observation(self, device_id: str, observation: Observation) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO device_observations(device_id, observation_json, observed_at) VALUES (?, ?, ?) "
                "ON CONFLICT(device_id) DO UPDATE SET observation_json=excluded.observation_json, observed_at=excluded.observed_at",
                (device_id, observation.model_dump_json(), _now_iso()),
            )
            self._connection.commit()

    def get_latest_observation(self, device_id: str) -> Observation | None:
        with self._lock:
            row = self._connection.execute("SELECT observation_json FROM device_observations WHERE device_id = ?", (device_id,)).fetchone()
        return Observation.model_validate_json(row["observation_json"]) if row else None

    def enqueue_action(self, device_id: str, command: DeviceActionCommand, *, max_queue_size: int) -> DeviceActionCommand:
        with self._lock:
            existing = self._connection.execute("SELECT * FROM device_actions WHERE device_id = ? AND action_id = ?", (device_id, command.action_id)).fetchone()
            if existing:
                stored = self._row_to_command(existing)
                if stored.action != command.action:
                    raise ValueError("action_id was already used for a different action")
                return stored
            active = self._connection.execute(
                "SELECT COUNT(*) FROM device_actions WHERE device_id = ? AND lifecycle IN (?, ?, ?)",
                (device_id, ActionLifecycle.QUEUED.value, ActionLifecycle.DISPATCHED.value, ActionLifecycle.EXECUTING.value),
            ).fetchone()[0]
            if active >= max_queue_size:
                raise SessionQueueFullError(f"device action queue is full: {device_id}")
            self._connection.execute(
                "INSERT INTO device_actions(command_id, device_id, action_id, action_json, lifecycle, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (command.command_id, device_id, command.action_id, command.action.model_dump_json(), command.lifecycle.value, command.created_at.isoformat()),
            )
            self._connection.commit()
            return command

    def lease_next_action(self, device_id: str, *, lease_timeout_seconds: float, device_timeout_seconds: float, max_lease_retries: int) -> DeviceActionCommand | None:
        with self._lock:
            if not self._connected(device_id, device_timeout_seconds):
                return None
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._reclaim_expired(device_id, max_lease_retries)
                observation_row = self._connection.execute("SELECT observation_json FROM device_observations WHERE device_id = ?", (device_id,)).fetchone()
                observation = Observation.model_validate_json(observation_row["observation_json"]) if observation_row else None
                rows = self._connection.execute("SELECT * FROM device_actions WHERE device_id = ? AND lifecycle = ? ORDER BY created_at", (device_id, ActionLifecycle.QUEUED.value)).fetchall()
                for row in rows:
                    command = self._row_to_command(row)
                    if observation is None or command.action.observation_id != observation.observation_id:
                        self._mark_stale(command, observation)
                        continue
                    lease_id = uuid4().hex
                    leased_until = datetime.now(timezone.utc) + timedelta(seconds=lease_timeout_seconds)
                    self._connection.execute("UPDATE device_actions SET lifecycle = ?, lease_id = ?, leased_until = ? WHERE command_id = ?", (ActionLifecycle.DISPATCHED.value, lease_id, leased_until.isoformat(), command.command_id))
                    self._connection.commit()
                    return command.model_copy(update={"lifecycle": ActionLifecycle.DISPATCHED, "lease_id": lease_id, "leased_until": leased_until})
                self._connection.commit()
                return None
            except Exception:
                self._connection.rollback()
                raise

    def complete_action(self, device_id: str, report: DeviceActionResultReport) -> None:
        self._record_terminal(device_id, report, ActionLifecycle.SUCCESS)

    def fail_action(self, device_id: str, report: DeviceActionResultReport) -> None:
        self._record_terminal(device_id, report, report.lifecycle or _lifecycle_for_result(report.result))

    def get_device_state(self, device_id: str, *, device_timeout_seconds: float) -> DeviceSessionSnapshot:
        with self._lock:
            observation_row = self._connection.execute("SELECT * FROM device_observations WHERE device_id = ?", (device_id,)).fetchone()
            rows = self._connection.execute("SELECT lifecycle, retry_count, result_json FROM device_actions WHERE device_id = ?", (device_id,)).fetchall()
            lifecycle_counts = {lifecycle.value: 0 for lifecycle in ActionLifecycle}
            for row in rows:
                lifecycle_counts[row["lifecycle"]] = lifecycle_counts.get(row["lifecycle"], 0) + 1
            return DeviceSessionSnapshot(
                device_id=device_id,
                latest_observation_id=Observation.model_validate_json(observation_row["observation_json"]).observation_id if observation_row else None,
                pending_action_count=sum(row["lifecycle"] == ActionLifecycle.QUEUED.value for row in rows),
                leased_action_count=sum(row["lifecycle"] in {ActionLifecycle.DISPATCHED.value, ActionLifecycle.EXECUTING.value} for row in rows),
                completed_action_count=sum(row["result_json"] is not None for row in rows),
                retry_count=sum(row["retry_count"] for row in rows),
                connected=self._connected(device_id, device_timeout_seconds),
                lifecycle_counts=lifecycle_counts,
            )

    def get_result(self, command_id: str) -> DeviceActionResultReport | None:
        with self._lock:
            row = self._connection.execute("SELECT result_json FROM device_actions WHERE command_id = ?", (command_id,)).fetchone()
        return DeviceActionResultReport.model_validate_json(row["result_json"]) if row and row["result_json"] else None

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def _record_terminal(self, device_id: str, report: DeviceActionResultReport, lifecycle: ActionLifecycle) -> None:
        with self._lock:
            row = self._connection.execute("SELECT device_id, result_json FROM device_actions WHERE command_id = ?", (report.command_id,)).fetchone()
            if row is None or row["device_id"] != device_id:
                raise ValueError("action result does not belong to this device session")
            if row["result_json"]:
                return
            self._connection.execute("UPDATE device_actions SET lifecycle = ?, lease_id = NULL, leased_until = NULL, result_json = ?, result_lifecycle = ? WHERE command_id = ?", (lifecycle.value, report.model_copy(update={"lifecycle": lifecycle}).model_dump_json(), lifecycle.value, report.command_id))
            self._connection.commit()

    def _reclaim_expired(self, device_id: str, max_lease_retries: int) -> None:
        now = datetime.now(timezone.utc)
        rows = self._connection.execute("SELECT * FROM device_actions WHERE device_id = ? AND lifecycle IN (?, ?) AND leased_until IS NOT NULL AND leased_until <= ?", (device_id, ActionLifecycle.DISPATCHED.value, ActionLifecycle.EXECUTING.value, now.isoformat())).fetchall()
        for row in rows:
            retry_count = row["retry_count"] + 1
            if retry_count > max_lease_retries:
                report = DeviceActionResultReport(command_id=row["command_id"], result=ActionResult(success=False, status=ActionStatus.RETRY_EXHAUSTED, message="action lease expired too many times"), lifecycle=ActionLifecycle.FAILED)
                self._connection.execute("UPDATE device_actions SET lifecycle = ?, retry_count = ?, lease_id = NULL, leased_until = NULL, result_json = ?, result_lifecycle = ? WHERE command_id = ?", (ActionLifecycle.FAILED.value, retry_count, report.model_dump_json(), ActionLifecycle.FAILED.value, row["command_id"]))
            else:
                self._connection.execute("UPDATE device_actions SET lifecycle = ?, retry_count = ?, lease_id = NULL, leased_until = NULL WHERE command_id = ?", (ActionLifecycle.QUEUED.value, retry_count, row["command_id"]))

    def _mark_stale(self, command: DeviceActionCommand, observation: Observation | None) -> None:
        report = DeviceActionResultReport(command_id=command.command_id, result=ActionResult(success=False, status=ActionStatus.STALE_OBSERVATION, message="action was not dispatched because the device observation changed", observation_id=observation.observation_id if observation else None), lifecycle=ActionLifecycle.STALE)
        self._connection.execute("UPDATE device_actions SET lifecycle = ?, result_json = ?, result_lifecycle = ? WHERE command_id = ?", (ActionLifecycle.STALE.value, report.model_dump_json(), ActionLifecycle.STALE.value, command.command_id))

    def _row_to_command(self, row: sqlite3.Row) -> DeviceActionCommand:
        return DeviceActionCommand(command_id=row["command_id"], action_id=row["action_id"], device_id=row["device_id"], action=ActionRequest.model_validate_json(row["action_json"]), lifecycle=ActionLifecycle(row["lifecycle"]), created_at=datetime.fromisoformat(row["created_at"]), lease_id=row["lease_id"], leased_until=datetime.fromisoformat(row["leased_until"]) if row["leased_until"] else None, retry_count=row["retry_count"])

    def _connected(self, device_id: str, timeout_seconds: float) -> bool:
        row = self._connection.execute("SELECT observed_at FROM device_observations WHERE device_id = ?", (device_id,)).fetchone()
        if not row or timeout_seconds <= 0:
            return False
        return datetime.now(timezone.utc) - datetime.fromisoformat(row["observed_at"]) <= timedelta(seconds=timeout_seconds)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lifecycle_for_result(result: ActionResult) -> ActionLifecycle:
    if result.status is ActionStatus.SUCCESS:
        return ActionLifecycle.SUCCESS
    if result.status is ActionStatus.STALE_OBSERVATION:
        return ActionLifecycle.STALE
    if result.status is ActionStatus.SAFETY_BLOCKED:
        return ActionLifecycle.SAFETY_BLOCKED
    return ActionLifecycle.FAILED
