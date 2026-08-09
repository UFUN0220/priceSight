"""Deterministic fake provider for tests and local development."""

from collections import deque
from collections.abc import Iterable

from app.llm.base import LLMProvider, LLMRequest, LLMResponse


class FakeLLMProvider:
    """Replay queued responses without external API keys or network access."""

    def __init__(self, responses: Iterable[LLMResponse] = ()) -> None:
        self._responses = deque(responses)
        self.calls: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        if self._responses:
            return self._responses.popleft()
        return LLMResponse(content="", provider="fake")

    def queue_response(self, response: LLMResponse) -> None:
        """Append one deterministic response for a future request."""

        self._responses.append(response)


def fake_provider_is_valid(provider: LLMProvider) -> bool:
    """Small runtime-checkable helper used by dependency tests."""

    return isinstance(provider, LLMProvider)

