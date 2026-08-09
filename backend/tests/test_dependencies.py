"""Tests for the explicit dependency composition root."""

from app.core.config import Settings
from app.core.dependencies import build_container, get_container
from app.llm.fake import FakeLLMProvider
from app.transport.fake import FakeTransport


def test_default_container_is_fully_offline() -> None:
    container = build_container(Settings(app_env="test"))

    assert isinstance(container.llm_provider, FakeLLMProvider)
    assert isinstance(container.transport, FakeTransport)
    assert container.settings.safe_mode is True


def test_default_container_is_cached() -> None:
    get_container.cache_clear()

    assert get_container() is get_container()

