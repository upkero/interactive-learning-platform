from functools import lru_cache

from pydantic import Field, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProgressSettings(BaseSettings):
    url: RedisDsn = Field(
        default=RedisDsn("redis://redis:6379/1"),
        description="Redis DB for progress streams.",
    )
    stream_maxlen: int = Field(
        default=1000,
        gt=0,
        description="Approximate MAXLEN of progress:{document_id}.",
    )
    stream_ttl_seconds: int = Field(
        default=86_400,
        gt=0,
        description="TTL of a progress stream.",
    )

    model_config = SettingsConfigDict(
        env_prefix="REDIS_PROGRESS_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_progress_settings() -> ProgressSettings:
    return ProgressSettings()