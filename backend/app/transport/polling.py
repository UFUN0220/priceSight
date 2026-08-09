"""Polling transport wrapper with a bounded wait-for-change primitive."""

from __future__ import annotations

import time

from app.observation.models import Observation
from app.transport.base import DeviceAction, DeviceTransport, TransportResult


class PollingTransport:
    """Keep the existing polling contract while making delivery measurable."""

    def __init__(self, delegate: DeviceTransport, poll_interval_ms: int = 20) -> None:
        if poll_interval_ms < 0:
            raise ValueError("poll_interval_ms must be non-negative")
        self.delegate = delegate
        self.poll_interval_seconds = poll_interval_ms / 1000

    def observe(self) -> Observation:
        return self.delegate.observe()

    def execute(self, action: DeviceAction) -> TransportResult:
        return self.delegate.execute(action)

    def wait_for_change(self, previous: Observation, timeout_ms: int = 1000) -> Observation | None:
        """Poll until the observation ID changes or the bounded timeout expires."""

        if timeout_ms < 0:
            raise ValueError("timeout_ms must be non-negative")
        deadline = time.perf_counter() + timeout_ms / 1000
        while True:
            current = self.observe()
            if current.observation_id != previous.observation_id:
                return current
            if time.perf_counter() >= deadline:
                return None
            time.sleep(max(self.poll_interval_seconds, 0.001))
