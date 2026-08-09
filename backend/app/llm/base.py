"""Provider-neutral LLM request/response contracts."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class LLMRequest(BaseModel):
    prompt: str
    system_prompt: str | None = None
    model: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    content: str
    provider: str
    model: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Synchronous provider interface used by later planners."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Return a provider response for one request."""

