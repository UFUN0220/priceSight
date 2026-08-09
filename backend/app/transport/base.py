"""Framework-neutral device transport contracts."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.observation.models import Observation


class DeviceAction(BaseModel):
    name: str
    parameters: dict[str, str] = Field(default_factory=dict)


class TransportResult(BaseModel):
    success: bool
    message: str | None = None
    observation: Observation | None = None


@runtime_checkable
class DeviceTransport(Protocol):
    """Minimal synchronous boundary for a device or fake device."""

    def observe(self) -> Observation:
        """Read the current serializable observation."""

    def execute(self, action: DeviceAction) -> TransportResult:
        """Execute one already-grounded device action."""

