from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ObservabilitySettings(BaseSettings):
    worker_metrics_port: int = Field(default=9101, ge=1, le=65535)

    model_config = SettingsConfigDict(env_prefix="OBSERVABILITY_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_observability_settings() -> ObservabilitySettings:
    return ObservabilitySettings()
