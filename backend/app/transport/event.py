"""Event-driven observation transport with debounce/stabilization semantics."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.observation.models import Observation
from app.transport.base import DeviceAction, DeviceTransport, TransportResult


class AccessibilityEvent(BaseModel):
    """Serializable event envelope suitable for an Android WebSocket client."""

    event_id: str = Field(min_length=1)
    event_type: str = Field(default="WINDOW_CONTENT_CHANGED", min_length=1)
    observation: Observation
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EventDrivenTransport:
    """Queue observations and emit only the stabilized latest state."""

    def __init__(
        self,
        delegate: DeviceTransport | None = None,
        initial_observation: Observation | None = None,
        stabilization_ms: int = 25,
    ) -> None:
        if stabilization_ms < 0:
            raise ValueError("stabilization_ms must be non-negative")
        self.delegate = delegate
        self.stabilization_seconds = stabilization_ms / 1000
        self._latest = initial_observation or Observation(observation_id="event-initial")
        self._events: asyncio.Queue[AccessibilityEvent] = asyncio.Queue()

    def observe(self) -> Observation:
        if self.delegate is not None:
            self._latest = self.delegate.observe()
        return self._latest

    def execute(self, action: DeviceAction) -> TransportResult:
        if self.delegate is None:
            return TransportResult(success=False, message="event transport has no action delegate")
        result = self.delegate.execute(action)
        if result.observation is not None:
            self._latest = result.observation
        return result

    def publish(self, event: AccessibilityEvent) -> None:
        """Accept an event without blocking the producer, as a WebSocket handler should."""

        self._events.put_nowait(event)

    def publish_observation(self, observation: Observation, event_id: str) -> None:
        self.publish(AccessibilityEvent(event_id=event_id, observation=observation))

    async def wait_for_change(self, previous: Observation, timeout_ms: int = 1000) -> Observation | None:
        """Wait for a changed observation, debouncing bursts into the latest event."""

        if timeout_ms < 0:
            raise ValueError("timeout_ms must be non-negative")
        timeout_seconds = timeout_ms / 1000
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        previous_fingerprint = self._fingerprint(previous)
        while True:
            remaining = max(0.0, deadline - asyncio.get_running_loop().time())
            try:
                event = await asyncio.wait_for(self._events.get(), timeout=remaining)
            except (asyncio.TimeoutError, ValueError):
                return None
            latest = event
            if self.stabilization_seconds:
                remaining = max(0.0, deadline - asyncio.get_running_loop().time())
                delay = min(self.stabilization_seconds, remaining)
                if delay:
                    await asyncio.sleep(delay)
                while True:
                    try:
                        latest = self._events.get_nowait()
                    except asyncio.QueueEmpty:
                        break
            candidate = latest.observation
            self._latest = candidate
            if self._fingerprint(candidate) != previous_fingerprint:
                return candidate

    @staticmethod
    def _fingerprint(observation: Observation) -> str:
        payload = json.dumps(observation.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
