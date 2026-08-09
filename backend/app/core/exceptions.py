"""Domain exception hierarchy shared by backend packages."""


class DomainError(Exception):
    """Base class for expected application-level failures."""


class DeviceDisconnectedError(DomainError):
    """The device or device transport is unavailable."""


class ObservationUnavailableError(DomainError):
    """A current device observation could not be obtained."""


class TargetNotFoundError(DomainError):
    """An action target could not be resolved."""


class WorkflowStateError(DomainError):
    """A workflow transition is invalid for the current state."""


class ProviderError(DomainError):
    """An LLM provider returned an infrastructure or contract failure."""


class SafetyViolationError(DomainError):
    """A requested operation crossed the deterministic safety boundary."""

