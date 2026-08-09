"""Minimal dependency container for local and testable backend composition."""

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import Settings, load_settings
from app.llm.base import LLMProvider
from app.llm.factory import build_llm_provider
from app.transport.base import DeviceTransport
from app.transport.event import EventDrivenTransport
from app.transport.fake import FakeTransport
from app.transport.session import DeviceSessionManager
from app.transport.store import SQLiteSessionStore


@dataclass(frozen=True)
class AppContainer:
    """Explicit composition root for backend services."""

    settings: Settings
    llm_provider: LLMProvider
    transport: DeviceTransport
    device_sessions: DeviceSessionManager


def build_container(
    settings: Settings | None = None,
    llm_provider: LLMProvider | None = None,
    transport: DeviceTransport | None = None,
    device_sessions: DeviceSessionManager | None = None,
) -> AppContainer:
    """Build a container with fake implementations by default."""

    resolved_settings = settings or load_settings()
    resolved_transport = transport
    if resolved_transport is None and resolved_settings.transport_mode == "event":
        resolved_transport = EventDrivenTransport(stabilization_ms=resolved_settings.event_stabilization_ms)

    resolved_sessions = device_sessions
    if resolved_sessions is None:
        store = SQLiteSessionStore(resolved_settings.session_store_path) if resolved_settings.session_store_backend == "sqlite" else None
        resolved_sessions = DeviceSessionManager(
            store=store,
            max_queue_size=resolved_settings.session_max_queue_size,
            lease_timeout_seconds=resolved_settings.session_lease_timeout_seconds,
            device_timeout_seconds=resolved_settings.session_device_timeout_seconds,
            max_lease_retries=resolved_settings.session_max_lease_retries,
        )
    return AppContainer(
        settings=resolved_settings,
        llm_provider=llm_provider or build_llm_provider(resolved_settings),
        transport=resolved_transport or FakeTransport(),
        device_sessions=resolved_sessions,
    )


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    """Return the process-local default container."""

    return build_container()
