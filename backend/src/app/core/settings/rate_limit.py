from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RateLimitSettings(BaseSettings):
    storage_uri: str = Field(
        default="redis://localhost:6379/2",
        description="Redis URI for shared rate-limit counters; use memory:// in tests.",
    )

    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_rate_limit_settings() -> RateLimitSettings:
    return RateLimitSettings()
