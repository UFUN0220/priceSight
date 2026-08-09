"""Fake device and transport for backend-only tests."""

from app.observation.models import Observation
from app.transport.base import DeviceAction, DeviceTransport, TransportResult


class FakeDevice:
    """In-memory device state with an auditable action history."""

    def __init__(self, observation: Observation | None = None) -> None:
        self.current_observation = observation or Observation(observation_id="fake-initial")
        self.actions: list[DeviceAction] = []

    def observe(self) -> Observation:
        return self.current_observation

    def execute(self, action: DeviceAction) -> TransportResult:
        self.actions.append(action)
        return TransportResult(
            success=True,
            message="fake action accepted",
            observation=self.current_observation,
        )


class FakeTransport:
    """DeviceTransport implementation that never touches Android or a network."""

    def __init__(self, device: FakeDevice | None = None) -> None:
        self.device = device or FakeDevice()

    def observe(self) -> Observation:
        return self.device.observe()

    def execute(self, action: DeviceAction) -> TransportResult:
        return self.device.execute(action)

