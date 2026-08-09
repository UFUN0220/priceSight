"""Tests for the provider-neutral fake LLM implementation."""

from app.llm.base import LLMRequest, LLMResponse
from app.llm.fake import FakeLLMProvider, fake_provider_is_valid


def test_fake_provider_replays_response_and_records_call() -> None:
    provider = FakeLLMProvider(
        [LLMResponse(content="structured result", provider="fake", model="test")]
    )
    request = LLMRequest(prompt="test prompt", model="test")

    response = provider.complete(request)

    assert response.content == "structured result"
    assert provider.calls == [request]
    assert fake_provider_is_valid(provider)


def test_fake_provider_has_deterministic_empty_fallback() -> None:
    response = FakeLLMProvider().complete(LLMRequest(prompt="empty"))

    assert response.provider == "fake"
    assert response.content == ""

