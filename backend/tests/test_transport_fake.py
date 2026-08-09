"""Tests for fake device and transport boundaries."""

from app.observation.models import Observation
from app.transport.base import DeviceAction
from app.transport.fake import FakeDevice, FakeTransport


def test_fake_transport_observes_and_records_actions() -> None:
    device = FakeDevice(Observation(observation_id="obs-1"))
    transport = FakeTransport(device)
    action = DeviceAction(name="inspect", parameters={"source": "test"})

    assert transport.observe().observation_id == "obs-1"
    result = transport.execute(action)

    assert result.success is True
    assert result.observation is not None
    assert device.actions == [action]

