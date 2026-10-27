"""LLM settings: the main profile (LLM_*) and the cheap one (LLM_CHEAP_*).

Everything not set in the cheap profile is taken from the main one
(CheapLLMSettings.resolve(fallback), like QueryPreprocessingLLMSettings in
faq-assistant). The default is local Ollama; production sets anthropic in
.env.
"""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["anthropic", "openai_compatible", "ollama"]

# Providers that talk to a paid hosted API and therefore cannot work without
# a key. "ollama" is the local no-key setup.
_PROVIDERS_REQUIRING_KEY = ("anthropic", "openai_compatible")


class LLMSettings(BaseSettings):
    provider: LLMProvider = Field(default="ollama", description="Main LLM provider.")
    api_key: SecretStr | None = Field(default=None, description="Provider API key.")
    model: str = Field(default="llama3.2", min_length=1, description="Main model.")
    base_url: str | None = Field(
        default=None,
        description=(
            "Base URL for openai_compatible providers (Ollama, OpenRouter, a proxy). "
            "Empty means the official OpenAI API."
        ),
    )
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    timeout_seconds: float = Field(default=120.0, gt=0.0)
    max_retries: int = Field(default=2, ge=0)
    max_tokens: int | None = Field(default=None, ge=1)
    reasoning_effort: str | None = Field(default=None)
    price_prompt_per_1m: float | None = Field(default=None, ge=0.0)
    price_completion_per_1m: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def validate_provider_requirements(self) -> Self:
        if self.provider in _PROVIDERS_REQUIRING_KEY and not self.api_key:
            raise ValueError(f"api_key is required for provider '{self.provider}'")
        return self

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        extra="ignore",
    )


class CheapLLMSettings(BaseSettings):
    """Overrides for the cheap model: every field is optional."""

    provider: LLMProvider | None = Field(default=None, description="Provider for light tasks.")
    api_key: SecretStr | None = Field(default=None, description="API key for the cheap model.")
    model: str | None = Field(default=None, min_length=1, description="Cheap model.")
    base_url: str | None = Field(default=None, description="Base URL of the cheap provider.")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    timeout_seconds: float | None = Field(default=None, gt=0.0)
    max_retries: int | None = Field(default=None, ge=0)
    max_tokens: int | None = Field(default=None, ge=1)
    reasoning_effort: str | None = Field(default=None)

    def resolve(self, fallback: LLMSettings) -> LLMSettings:
        """Build a full profile: unset cheap fields come from the main one.

        If the cheap profile sets a different provider, ``api_key`` and
        ``base_url`` are NOT inherited from the main one — credentials and
        endpoints belong to the provider and must not leak across providers
        (e.g. an Anthropic key reaching an Ollama endpoint).
        """
        provider_changed = self.provider is not None and self.provider != fallback.provider
        if provider_changed:
            api_key = self.api_key
            base_url = self.base_url
        else:
            api_key = self.api_key if self.api_key is not None else fallback.api_key
            base_url = self.base_url if self.base_url is not None else fallback.base_url

        return LLMSettings(
            provider=self.provider or fallback.provider,
            model=self.model or fallback.model,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=(self.timeout_seconds if self.timeout_seconds is not None else fallback.timeout_seconds),
            max_retries=self.max_retries if self.max_retries is not None else fallback.max_retries,
            temperature=self.temperature if self.temperature is not None else fallback.temperature,
            max_tokens=(self.max_tokens if self.max_tokens is not None else fallback.max_tokens),
            reasoning_effort=(
                self.reasoning_effort if self.reasoning_effort is not None else fallback.reasoning_effort
            ),
        )

    model_config = SettingsConfigDict(
        env_prefix="LLM_CHEAP_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_llm_settings() -> LLMSettings:
    return LLMSettings()


@lru_cache(maxsize=1)
def get_cheap_llm_settings() -> CheapLLMSettings:
    return CheapLLMSettings()
