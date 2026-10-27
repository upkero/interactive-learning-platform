"""LLMSettings + CheapLLMSettings unit tests: defaults, validation, resolve()."""

import pytest
from pydantic import SecretStr, ValidationError

from src.app.core.settings.llm import CheapLLMSettings, LLMSettings


def _fallback() -> LLMSettings:
    return LLMSettings(
        provider="anthropic",
        api_key=SecretStr("sk-main"),
        model="main-model",
        temperature=0.2,
        timeout_seconds=12.0,
        max_retries=3,
        max_tokens=100,
    )


@pytest.mark.unit
def test_local_defaults_are_ollama() -> None:
    settings = LLMSettings()
    assert settings.provider == "ollama"
    assert settings.model == "llama3.2"
    assert settings.timeout_seconds == 120.0
    assert settings.max_retries == 2


@pytest.mark.unit
def test_anthropic_requires_api_key() -> None:
    with pytest.raises(ValidationError):
        LLMSettings(provider="anthropic")
    # With a key present validation passes
    LLMSettings(provider="anthropic", api_key=SecretStr("sk"))


@pytest.mark.unit
def test_cheap_resolve_without_overrides_returns_fallback() -> None:
    fallback = _fallback()
    resolved = CheapLLMSettings().resolve(fallback)

    assert resolved == fallback


@pytest.mark.unit
def test_cheap_resolve_overrides_only_set_fields() -> None:
    cheap = CheapLLMSettings(model="cheap-model", timeout_seconds=15.0)
    resolved = cheap.resolve(_fallback())

    assert resolved.model == "cheap-model"
    assert resolved.timeout_seconds == 15.0
    assert resolved.provider == "anthropic"
    assert resolved.api_key == SecretStr("sk-main")
    assert resolved.max_retries == 3
    assert resolved.temperature == 0.2


@pytest.mark.unit
def test_cheap_resolve_full_override_with_provider() -> None:
    cheap = CheapLLMSettings(
        provider="openai_compatible",
        api_key=SecretStr("sk-cheap"),
        base_url="http://local/v1",
        temperature=0.5,
        max_tokens=77,
        max_retries=0,
    )
    resolved = cheap.resolve(_fallback())

    assert resolved.provider == "openai_compatible"
    assert resolved.api_key == SecretStr("sk-cheap")
    assert resolved.base_url == "http://local/v1"
    assert resolved.temperature == 0.5
    assert resolved.max_tokens == 77
    assert resolved.max_retries == 0
    # Non-overridden fields stay from the main profile
    assert resolved.model == "main-model"
    assert resolved.timeout_seconds == 12.0


@pytest.mark.unit
def test_cheap_settings_are_all_optional() -> None:
    settings = CheapLLMSettings()
    assert settings.model is None
    assert settings.provider is None
    # Пустая модель в оверрайдах запрещена
    with pytest.raises(ValidationError):
        CheapLLMSettings(model="")
