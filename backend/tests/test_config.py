"""Tests for environment-backed application configuration."""

from app.core.config import load_settings


def test_settings_default_to_safe_mode() -> None:
    settings = load_settings({})

    assert settings.safe_mode is True
    assert settings.allow_cart is False
    assert settings.max_workflow_steps == 20


def test_settings_parse_explicit_values() -> None:
    settings = load_settings(
        {
            "APP_ENV": "test",
            "SAFE_MODE": "true",
            "SAFE_MODE_ALLOW_CART": "true",
            "MAX_RETRIES": "5",
        }
    )

    assert settings.app_env == "test"
    assert settings.allow_cart is True
    assert settings.max_retries == 5


def test_settings_parse_agent_provider_configuration() -> None:
    settings = load_settings(
        {
            "LLM_PROVIDER": "openai-compatible",
            "AGENT_MIN_CONFIDENCE": "0.75",
        }
    )

    assert settings.llm_provider == "openai-compatible"
    assert settings.agent_min_confidence == 0.75
