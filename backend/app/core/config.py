"""Application configuration loaded from environment variables."""

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    """Validated runtime settings with safe defaults."""

    model_config = ConfigDict(extra="forbid")

    app_env: str = "development"
    safe_mode: bool = True
    allow_coupons: bool = False
    allow_cart: bool = False
    max_retries: int = Field(default=3, ge=0, le=10)
    max_llm_calls: int = Field(default=3, ge=0, le=20)
    llm_provider: str = "fake"
    agent_min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    max_workflow_steps: int = Field(default=20, ge=1, le=100)
    transport_mode: Literal["polling", "event"] = "polling"
    event_stabilization_ms: int = Field(default=25, ge=0, le=5000)
    device_shared_token: str = ""
    max_transport_message_chars: int = Field(default=1_000_000, ge=1024, le=10_000_000)


def _env_value(environ: Mapping[str, str], name: str, default: str) -> str:
    value = environ.get(name)
    return default if value is None or not value.strip() else value.strip()


def _parse_bool(value: str, name: str) -> bool:
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Build validated settings from a supplied or process environment."""

    source = environ or {}
    import os

    if environ is None:
        source = os.environ

    return Settings(
        app_env=_env_value(source, "APP_ENV", "development"),
        safe_mode=_parse_bool(_env_value(source, "SAFE_MODE", "true"), "SAFE_MODE"),
        allow_coupons=_parse_bool(
            _env_value(source, "SAFE_MODE_ALLOW_COUPONS", "false"),
            "SAFE_MODE_ALLOW_COUPONS",
        ),
        allow_cart=_parse_bool(
            _env_value(source, "SAFE_MODE_ALLOW_CART", "false"),
            "SAFE_MODE_ALLOW_CART",
        ),
        max_retries=int(_env_value(source, "MAX_RETRIES", "3")),
        max_llm_calls=int(_env_value(source, "MAX_LLM_CALLS", "3")),
        llm_provider=_env_value(source, "LLM_PROVIDER", "fake"),
        agent_min_confidence=float(_env_value(source, "AGENT_MIN_CONFIDENCE", "0.6")),
        max_workflow_steps=int(_env_value(source, "MAX_WORKFLOW_STEPS", "20")),
        transport_mode=_env_value(source, "TRANSPORT_MODE", "polling").lower(),
        event_stabilization_ms=int(_env_value(source, "EVENT_STABILIZATION_MS", "25")),
        device_shared_token=_env_value(source, "DEVICE_SHARED_TOKEN", ""),
        max_transport_message_chars=int(
            _env_value(source, "MAX_TRANSPORT_MESSAGE_CHARS", "1000000")
        ),
    )
