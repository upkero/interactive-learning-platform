"""LLMSettings + CheapLLMSettings unit tests: defaults, validation, resolve().

The autouse fixture strips every LLM_* variable from the environment and
disables the .env file, so the tests never depend on the developer's setup
(2.1 review point 9).
"""

import os

import pytest
from pydantic import SecretStr, ValidationError

from src.app.core.settings.llm import CheapLLMSettings, LLMSettings


@pytest.fixture(autouse=True)
def _clean_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("LLM_"):
            monkeypatch.delenv(key, raising=False)


def _fallback() -> LLMSettings:
    return LLMSettings(
        _env_file=None,
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
    settings = LLMSettings(_env_file=None)
    assert settings.provider == "ollama"
    assert settings.model == "llama3.2"
    assert settings.timeout_seconds == 120.0
    assert settings.max_retries == 2


@pytest.mark.unit
def test_anthropic_requires_api_key() -> None:
    with pytest.raises(ValidationError):
        LLMSettings(_env_file=None, provider="anthropic")
    # With a key present validation passes
    LLMSettings(_env_file=None, provider="anthropic", api_key=SecretStr("sk"))


@pytest.mark.unit
def test_openai_compatible_requires_api_key() -> None:
    with pytest.raises(ValidationError):
        LLMSettings(_env_file=None, provider="openai_compatible", base_url="http://proxy/v1")
    LLMSettings(_env_file=None, provider="openai_compatible", api_key=SecretStr("sk"))


@pytest.mark.unit
def test_cheap_resolve_without_overrides_returns_fallback() -> None:
    fallback = _fallback()
    resolved = CheapLLMSettings(_env_file=None).resolve(fallback)

    assert resolved == fallback


@pytest.mark.unit
def test_cheap_resolve_overrides_only_set_fields() -> None:
    cheap = CheapLLMSettings(_env_file=None, model="cheap-model", timeout_seconds=15.0)
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
        _env_file=None,
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
def test_cheap_resolve_provider_change_does_not_inherit_credentials() -> None:
    # Main = Ollama behind a compose URL, cheap = Anthropic: the Ollama
    # endpoint and the absence of a key must not leak into the Anthropic
    # profile — resolve() fails validation instead of sending requests
    # to a foreign provider without credentials.
    fallback = LLMSettings(
        _env_file=None,
        provider="ollama",
        model="llama3.2",
        base_url="http://ollama:11434/v1",
    )
    cheap = CheapLLMSettings(_env_file=None, provider="anthropic", model="claude-haiku-4-5")

    with pytest.raises(ValidationError):
        cheap.resolve(fallback)


@pytest.mark.unit
def test_cheap_resolve_provider_change_uses_own_credentials() -> None:
    fallback = LLMSettings(
        _env_file=None,
        provider="ollama",
        model="llama3.2",
        base_url="http://ollama:11434/v1",
    )
    cheap = CheapLLMSettings(
        _env_file=None,
        provider="openai_compatible",
        api_key=SecretStr("sk-cheap"),
        base_url="http://cheap-proxy/v1",
    )

    resolved = cheap.resolve(fallback)

    assert resolved.provider == "openai_compatible"
    assert resolved.api_key == SecretStr("sk-cheap")
    assert resolved.base_url == "http://cheap-proxy/v1"


@pytest.mark.unit
def test_cheap_resolve_same_provider_inherits_credentials() -> None:
    fallback = _fallback()
    cheap = CheapLLMSettings(_env_file=None, provider="anthropic", model="cheap-model")

    resolved = cheap.resolve(fallback)

    assert resolved.api_key == SecretStr("sk-main")
    assert resolved.provider == "anthropic"


@pytest.mark.unit
def test_cheap_settings_are_all_optional() -> None:
    settings = CheapLLMSettings(_env_file=None)
    assert settings.model is None
    assert settings.provider is None
    # Empty model in the overrides is forbidden
    with pytest.raises(ValidationError):
        CheapLLMSettings(_env_file=None, model="")
