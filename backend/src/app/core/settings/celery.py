from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CelerySettings(BaseSettings):
    broker_url: str = Field(
        default="redis://localhost:6379/0",
        description="URL of the Celery message broker (Redis logical DB 0).",
    )

    model_config = SettingsConfigDict(
        env_prefix="CELERY_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_celery_settings() -> CelerySettings:
    return CelerySettings()
