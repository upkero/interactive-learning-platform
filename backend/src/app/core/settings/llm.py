from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["anthropic", "openai", "openai_compatible", "ollama"]


class LLMSettings(BaseSettings):
    provider: LLMProvider = Field(default="anthropic", description="Основной LLM провайдер.")
    api_key: SecretStr | None = Field(default=None, description="API ключ провайдера.")
    model: str = Field(default="claude-3-5-sonnet-20241022", description="Основная модель.")
    base_url: str | None = Field(
        default=None,
        description="Базовый URL для OpenAI-совместимого API (например, Ollama).",
    )
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    timeout_seconds: float = Field(default=120.0, gt=0.0)
    max_retries: int = Field(default=2, ge=0)
    max_tokens: int | None = Field(default=None, ge=1)
    reasoning_effort: str | None = Field(default=None)
    price_prompt_per_1m: float | None = Field(default=None, ge=0.0)
    price_completion_per_1m: float | None = Field(default=None, ge=0.0)

    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        extra="ignore",
    )


class CheapLLMSettings(BaseSettings):
    provider: LLMProvider = Field(default="anthropic", description="Провайдер для легких задач.")
    api_key: SecretStr | None = Field(default=None, description="API ключ для легкой модели.")
    model: str = Field(default="claude-3-5-haiku-20241022", description="Дешёвая vision модель.")
    base_url: str | None = Field(default=None, description="Базовый URL.")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    timeout_seconds: float = Field(default=60.0, gt=0.0)
    max_retries: int = Field(default=2, ge=0)
    max_tokens: int | None = Field(default=None, ge=1)

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