"""Offline contract tests for OpenAI- and Anthropic-compatible providers."""

import httpx
import pytest

from app.core.exceptions import ProviderError
from app.llm.anthropic_compatible import AnthropicCompatibleProvider
from app.llm.base import LLMRequest
from app.llm.openai_compatible import OpenAICompatibleProvider


def test_openai_compatible_provider_maps_chat_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}]})

    provider = OpenAICompatibleProvider(
        api_key="secret",
        base_url="https://example.test/v1",
        model="model-a",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    response = provider.complete(LLMRequest(prompt="return json"))

    assert response.content == '{"ok":true}'
    assert response.provider == "openai-compatible"


def test_anthropic_compatible_provider_maps_messages_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/messages"
        assert request.headers["x-api-key"] == "secret"
        return httpx.Response(200, json={"content": [{"type": "text", "text": '{"ok":true}'}]})

    provider = AnthropicCompatibleProvider(
        api_key="secret",
        base_url="https://example.test",
        model="model-b",
        api_version="version",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    response = provider.complete(LLMRequest(prompt="return json"))

    assert response.content == '{"ok":true}'
    assert response.provider == "anthropic-compatible"


def test_provider_from_env_requires_explicit_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    with pytest.raises(ProviderError):
        OpenAICompatibleProvider.from_env()
