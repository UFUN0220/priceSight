"""Environment-selected LLM provider composition."""

from app.core.config import Settings
from app.core.exceptions import ProviderError
from app.llm.anthropic_compatible import AnthropicCompatibleProvider
from app.llm.base import LLMProvider
from app.llm.fake import FakeLLMProvider
from app.llm.openai_compatible import OpenAICompatibleProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    """Keep FakeLLMProvider as the safe no-key default."""

    provider = settings.llm_provider.casefold()
    if provider == "fake":
        return FakeLLMProvider()
    if provider in {"openai", "openai-compatible"}:
        return OpenAICompatibleProvider.from_env()
    if provider in {"anthropic", "anthropic-compatible"}:
        return AnthropicCompatibleProvider.from_env()
    raise ProviderError(f"unsupported LLM_PROVIDER: {settings.llm_provider}")
