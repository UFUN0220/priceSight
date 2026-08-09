"""OpenAI-compatible synchronous provider with environment-only configuration."""

from __future__ import annotations

import os

import httpx

from app.core.exceptions import ProviderError
from app.llm.base import LLMRequest, LLMResponse


class OpenAICompatibleProvider:
    """Call a chat-completions-compatible endpoint without vendor SDK coupling."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key or not base_url or not model:
            raise ProviderError("OpenAI-compatible provider requires API key, base URL, and model")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.client = client or httpx.Client(timeout=timeout)

    @classmethod
    def from_env(cls) -> OpenAICompatibleProvider:
        return cls(
            api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
            base_url=os.environ.get("OPENAI_BASE_URL", "").strip(),
            model=os.environ.get("OPENAI_MODEL", "").strip(),
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": request.model or self.model,
            "messages": [
                *([{"role": "system", "content": request.system_prompt}] if request.system_prompt else []),
                {"role": "user", "content": request.prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
            raise ProviderError(f"OpenAI-compatible provider request failed: {type(error).__name__}") from error
        if not isinstance(content, str):
            raise ProviderError("OpenAI-compatible provider returned non-text content")
        return LLMResponse(content=content, provider="openai-compatible", model=payload["model"])
