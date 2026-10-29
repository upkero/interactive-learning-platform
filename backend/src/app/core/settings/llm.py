from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["anthropic", "openai", "openai_compatible", "ollama"]


class LLMSettings(BaseSettings):
    provider: LLMProvider = Field(default="ollama", description="Primary LLM provider.")
    api_key: SecretStr | None = Field(default=None, description="Provider API key.")
    model: str = Field(default="llama3.2", description="Primary model.")
    base_url: str | None = Field(
        default="http://localhost:11434/v1",
        description="Base URL for OpenAI-compatible APIs (e.g. Ollama).",
    )
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    timeout_seconds: float = Field(default=120.0, gt=0.0)
    max_retries: int = Field(default=2, ge=0)
    max_tokens: int | None = Field(default=None, ge=1)
    reasoning_effort: str | None = Field(default=None)
    price_prompt_per_1m: float | None = Field(default=None, ge=0.0)
    price_completion_per_1m: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def validate_provider_requirements(self) -> Self:
        if self.provider in ("openai", "anthropic") and not self.api_key:
            raise ValueError(f"api_key is required for provider '{self.provider}'")
        if self.provider == "ollama" and not self.base_url:
            self.base_url = "http://localhost:11434/v1"
        return self

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        extra="ignore",
    )


class CheapLLMSettings(BaseSettings):
    provider: LLMProvider = Field(default="ollama", description="Provider for light tasks.")
    api_key: SecretStr | None = Field(default=None, description="API key for the cheap model.")
    model: str = Field(default="llama3.2", description="Cheap vision model.")
    base_url: str | None = Field(default="http://localhost:11434/v1", description="Base URL.")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    timeout_seconds: float = Field(default=60.0, gt=0.0)
    max_retries: int = Field(default=2, ge=0)
    max_tokens: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_provider_requirements(self) -> Self:
        if self.provider in ("openai", "anthropic") and not self.api_key:
            raise ValueError(f"api_key is required for provider '{self.provider}'")
        if self.provider == "ollama" and not self.base_url:
            self.base_url = "http://localhost:11434/v1"
        return self

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
