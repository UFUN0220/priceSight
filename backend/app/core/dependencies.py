"""Minimal dependency container for local and testable backend composition."""

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import Settings, load_settings
from app.llm.base import LLMProvider
from app.llm.factory import build_llm_provider
from app.transport.base import DeviceTransport
from app.transport.event import EventDrivenTransport
from app.transport.fake import FakeTransport


@dataclass(frozen=True)
class AppContainer:
    """Explicit composition root for backend services."""

    settings: Settings
    llm_provider: LLMProvider
    transport: DeviceTransport


def build_container(
    settings: Settings | None = None,
    llm_provider: LLMProvider | None = None,
    transport: DeviceTransport | None = None,
) -> AppContainer:
    """Build a container with fake implementations by default."""

    resolved_settings = settings or load_settings()
    resolved_transport = transport
    if resolved_transport is None and resolved_settings.transport_mode == "event":
        resolved_transport = EventDrivenTransport(stabilization_ms=resolved_settings.event_stabilization_ms)

    return AppContainer(
        settings=resolved_settings,
        llm_provider=llm_provider or build_llm_provider(resolved_settings),
        transport=resolved_transport or FakeTransport(),
    )


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    """Return the process-local default container."""

    return build_container()
