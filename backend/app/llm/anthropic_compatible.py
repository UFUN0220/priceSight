"""Anthropic-compatible synchronous provider with environment-only configuration."""

from __future__ import annotations

import os

import httpx

from app.core.exceptions import ProviderError
from app.llm.base import LLMRequest, LLMResponse


class AnthropicCompatibleProvider:
    """Call an Anthropic Messages-compatible endpoint without an SDK dependency."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        api_version: str,
        timeout: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key or not base_url or not model or not api_version:
            raise ProviderError("Anthropic-compatible provider requires API key, base URL, model, and API version")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_version = api_version
        self.timeout = timeout
        self.client = client or httpx.Client(timeout=timeout)

    @classmethod
    def from_env(cls) -> AnthropicCompatibleProvider:
        return cls(
            api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
            base_url=os.environ.get("ANTHROPIC_BASE_URL", "").strip(),
            model=os.environ.get("ANTHROPIC_MODEL", "").strip(),
            api_version=os.environ.get("ANTHROPIC_VERSION", "").strip(),
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": request.model or self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        try:
            response = self.client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": self.api_version,
                    "content-type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["content"][0]["text"]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
            raise ProviderError(f"Anthropic-compatible provider request failed: {type(error).__name__}") from error
        if not isinstance(content, str):
            raise ProviderError("Anthropic-compatible provider returned non-text content")
        return LLMResponse(content=content, provider="anthropic-compatible", model=payload["model"])
